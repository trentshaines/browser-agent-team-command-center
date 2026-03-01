import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import sentry_sdk
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

from app.database import AsyncSessionLocal
from app.models.message import Message
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.agent_run_log import AgentRunLog
from app.services import sse
from app.config import get_settings

SYSTEM_PROMPT = """You are an AI assistant commanding a fleet of real browser agents. Your primary job is to spawn browser agents to get things done.

SPAWN A BROWSER AGENT (via Task tool) for virtually everything:
- Any information that can change: prices, news, availability, scores, weather, stocks, hours, contact info
- Any research or comparison: products, services, reviews, competitors
- Any URL, domain, website, or web service mentioned
- Any action: booking, buying, signing up, submitting forms, logging in
- Any claim that should be verified on a live site
- "What is X?" questions where X is a real-world thing with a web presence

SPAWN MULTIPLE AGENTS IN PARALLEL when the task decomposes:
- Research 3 products → 3 parallel agents (one per product)
- Compare options → one agent per option
- Multi-step workflows → chain results from one agent into the next

ONLY skip browser agents for: basic arithmetic, explaining code the user just pasted, or pure creative writing with absolutely no web component.

After agents complete, synthesize a clear markdown response. Show what was actually found — not just that agents ran."""


async def run_turn(
    session_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    history: list[dict],
    db: AsyncSession,
) -> None:
    """
    Run one orchestrator turn using the Claude Agent SDK with real browser agents.
    Streams SSE events to the session.
    """
    settings = get_settings()
    session_id_str = str(session_id)
    await _run_with_sdk(session_id_str, assistant_message_id, history, db, settings)


async def _run_with_sdk(
    session_id_str: str,
    message_id: uuid.UUID,
    history: list[dict],
    db: AsyncSession,
    settings,
) -> None:
    import os
    from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

    # The SDK spawns a claude CLI subprocess. If CLAUDECODE is set (backend was
    # started inside a Claude Code terminal), the subprocess tries to connect to
    # the parent session stream, which is closed, causing it to misbehave and
    # output plain-text fake tool calls instead of using the Task tool. Unset it
    # for the duration of this call.
    _old_claudecode = os.environ.pop("CLAUDECODE", None)
    logger.info("_run_with_sdk: CLAUDECODE was %s", "set" if _old_claudecode else "unset")

    # Ensure Bedrock env vars are set for the SDK subprocess when configured
    if settings.llm_provider == "bedrock":
        os.environ["CLAUDE_CODE_USE_BEDROCK"] = "1"
        os.environ["AWS_REGION"] = settings.aws_region
        os.environ.setdefault("ANTHROPIC_MODEL", settings.anthropic_model)
        os.environ.setdefault("ANTHROPIC_SMALL_FAST_MODEL", settings.anthropic_small_fast_model)
        if settings.aws_bearer_token_bedrock:
            os.environ.setdefault("AWS_BEARER_TOKEN_BEDROCK", settings.aws_bearer_token_bedrock)
        logger.info("_run_with_sdk: Bedrock enabled, region=%s, model=%s", settings.aws_region, settings.anthropic_model)

    BROWSER_AGENT_PROMPT = f"""You are a browser agent. You take real actions on the web using a headless browser.

Run: uv run python scripts/browser_agent.py --task "<exact task>" --session-id {session_id_str}

The script is at scripts/browser_agent.py relative to the backend/ working directory.
The browser runs headlessly and streams screenshots back to the user in real time. You can:
- Navigate to any URL and extract text, tables, prices, listings
- Click buttons, links, and UI elements
- Fill and submit forms (search, contact, checkout, signup)
- Log into services when credentials are provided in the task
- Complete multi-step flows: search → select → fill → submit
- Download or scrape structured data

Write specific, action-oriented tasks. Include the exact URL when known.
Return the JSON result from the script exactly as-is."""

    # Track Task tool calls to publish agent_spawned / agent_complete via stream parsing
    # (SDK hooks require bidirectional IPC that fails in subprocess mode)
    pending_agent_runs: dict[str, uuid.UUID] = {}  # tool_use_id -> AgentRun.id
    seen_tool_ids: set[str] = set()               # dedup partial-message re-emissions

    full_response = ""
    _backend_dir = Path(__file__).parent.parent.parent  # backend/app/services -> backend/

    def _on_stderr(line: str) -> None:
        stripped = line.rstrip()
        if "[frame]" in stripped:
            logger.error("Claude subprocess stderr: %s", stripped)
        else:
            logger.warning("Claude subprocess stderr: %s", stripped)

    logger.info("_run_with_sdk: starting SDK query for session %s", session_id_str)
    try:
        async with asyncio.timeout(300):  # 5-minute hard timeout
            async for event in query(
                prompt=_build_prompt(history),
                options=ClaudeAgentOptions(
                    system_prompt=SYSTEM_PROMPT,
                    allowed_tools=["Task"],
                    permission_mode="bypassPermissions",
                    cwd=_backend_dir,
                    stderr=_on_stderr,
                    model="claude-sonnet-4-6" if settings.llm_provider != "bedrock" else None,
                    include_partial_messages=True,
                    agents={
                        "browser-agent": AgentDefinition(
                            description="Navigates websites, searches the web, extracts data, and takes real actions (click, fill forms, submit). Use for ANY task involving current information, a URL, or web interaction.",
                            prompt=BROWSER_AGENT_PROMPT,
                            tools=["Bash"],
                        )
                    },
                    setting_sources=["project", "local"],
                ),
            ):
                # AssistantMessage has a content list of TextBlock / ThinkingBlock / ToolUseBlock / ToolResultBlock
                if hasattr(event, "content") and isinstance(event.content, list):
                    for block in event.content:
                        block_type = type(block).__name__
                        if block_type == "TextBlock" and getattr(block, "text", None):
                            await sse.publish(session_id_str, "delta", {"message_id": str(message_id), "delta": block.text})
                            full_response += block.text
                        elif block_type == "ThinkingBlock" and getattr(block, "thinking", None):
                            await sse.publish(session_id_str, "thinking_delta", {"message_id": str(message_id), "thinking": block.thinking})
                        elif block_type == "ToolUseBlock" and getattr(block, "name", None) == "Task":
                            # Orchestrator is spawning a browser-agent — record it
                            tool_id = getattr(block, "id", "") or ""
                            inp = getattr(block, "input", {})
                            # Only process once (include_partial_messages may re-emit)
                            if tool_id and tool_id not in seen_tool_ids and isinstance(inp, dict) and inp:
                                seen_tool_ids.add(tool_id)
                                prompt = inp.get("prompt", "browser task")
                                try:
                                    agent_run = AgentRun(
                                        session_id=uuid.UUID(session_id_str),
                                        message_id=message_id,
                                        task=prompt,
                                        status=AgentRunStatus.RUNNING,
                                        started_at=datetime.now(timezone.utc),
                                    )
                                    db.add(agent_run)
                                    await db.flush()
                                    pending_agent_runs[tool_id] = agent_run.id
                                    await sse.publish(session_id_str, "agent_event", {
                                        "type": "agent_spawned",
                                        "agent_id": str(agent_run.id),
                                        "task": prompt,
                                    })
                                    logger.info("Agent spawned: run=%s task=%s", agent_run.id, prompt[:60])
                                except Exception:
                                    logger.warning("Failed to create AgentRun for Task", exc_info=True)
                        elif block_type == "ToolResultBlock":
                            tool_id = getattr(block, "tool_use_id", "") or ""
                            agent_run_id = pending_agent_runs.pop(tool_id, None)
                            if agent_run_id:
                                try:
                                    # Parse JSONL stdout from browser_agent.py
                                    raw_content = getattr(block, "content", "") or ""
                                    if isinstance(raw_content, list):
                                        raw_content = " ".join(
                                            getattr(b, "text", "") for b in raw_content if hasattr(b, "text")
                                        )
                                    steps = []
                                    final_result = None
                                    for line in raw_content.splitlines():
                                        line = line.strip()
                                        if not line:
                                            continue
                                        try:
                                            rec = json.loads(line)
                                            if rec.get("type") == "browser_step":
                                                steps.append(rec)
                                            elif rec.get("type") == "browser_result":
                                                final_result = rec
                                        except json.JSONDecodeError:
                                            pass

                                    # Persist and emit each step
                                    for step in steps:
                                        db.add(AgentRunLog(
                                            agent_run_id=agent_run_id,
                                            step=step.get("step", 0),
                                            url=step.get("url"),
                                            action_type=step.get("action_type"),
                                            action_params=step.get("action_params"),
                                            thought=step.get("thought"),
                                            evaluation=step.get("evaluation"),
                                            memory=step.get("memory"),
                                            extracted_content=step.get("extracted_content"),
                                            success=step.get("success"),
                                            error=step.get("error"),
                                            step_start_time=step.get("step_start_time"),
                                            step_end_time=step.get("step_end_time"),
                                            duration_seconds=step.get("duration_seconds"),
                                        ))
                                        await sse.publish(session_id_str, "agent_log", {
                                            "agent_run_id": str(agent_run_id),
                                            **{k: v for k, v in step.items() if k != "type"},
                                        })

                                    result_row = await db.execute(select(AgentRun).where(AgentRun.id == agent_run_id))
                                    agent_run = result_row.scalar_one_or_none()
                                    if agent_run:
                                        agent_run.status = AgentRunStatus.COMPLETE if (final_result and final_result.get("success")) else AgentRunStatus.ERROR
                                        agent_run.result = final_result.get("result") if final_result else None
                                        agent_run.completed_at = datetime.now(timezone.utc)
                                    await db.flush()
                                    await sse.publish(session_id_str, "agent_event", {
                                        "type": "agent_complete",
                                        "agent_run_id": str(agent_run_id),
                                        "result": final_result.get("result") if final_result else None,
                                        "total_steps": len(steps),
                                    })
                                    logger.info("Agent complete: run=%s steps=%d", agent_run_id, len(steps))
                                except Exception:
                                    logger.warning("Failed to update AgentRun on completion", exc_info=True)
                # ResultMessage has the final synthesized result
                elif hasattr(event, "result") and event.result and not full_response:
                    full_response = event.result

        await _save_and_complete(session_id_str, message_id, full_response, db)
    except TimeoutError as exc:
        sentry_sdk.capture_exception(exc)
        logger.error("Orchestrator timed out (300s) for session %s", session_id_str)
        await sse.publish(session_id_str, "error_event", {"message_id": str(message_id), "error": "Orchestrator timed out after 300s"})
    finally:
        if _old_claudecode is not None:
            os.environ["CLAUDECODE"] = _old_claudecode


async def _stream_with_client(
    client,
    model: str,
    session_id_str: str,
    message_id: uuid.UUID,
    history: list[dict],
    db: AsyncSession,
) -> None:
    full_response = ""
    async with client.messages.stream(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=history,
    ) as stream:
        async for text in stream.text_stream:
            await sse.publish(session_id_str, "delta", {"message_id": str(message_id), "delta": text})
            full_response += text
    await _save_and_complete(session_id_str, message_id, full_response, db)


async def _run_with_anthropic(
    session_id_str: str,
    message_id: uuid.UUID,
    history: list[dict],
    db: AsyncSession,
    settings,
) -> None:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    await _stream_with_client(client, "claude-sonnet-4-6", session_id_str, message_id, history, db)


async def _run_with_bedrock(
    session_id_str: str,
    message_id: uuid.UUID,
    history: list[dict],
    db: AsyncSession,
    settings,
) -> None:
    import anthropic
    client = anthropic.AsyncAnthropicBedrock(aws_region=settings.aws_region)
    await _stream_with_client(client, "us.anthropic.claude-sonnet-4-6", session_id_str, message_id, history, db)


async def _save_and_complete(
    session_id_str: str,
    message_id: uuid.UUID,
    content: str,
    db: AsyncSession,
) -> None:
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if msg:
        msg.content = content

    await sse.publish(session_id_str, "done", {"message_id": str(message_id), "content": content})


def _build_prompt(history: list[dict]) -> str:
    parts = []
    for msg in history:
        role = msg["role"].upper()
        parts.append(f"{role}: {msg['content']}")
    return "\n\n".join(parts)




