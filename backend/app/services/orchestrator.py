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
        logger.warning("Claude subprocess stderr: %s", line.rstrip())

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
                                    result_row = await db.execute(select(AgentRun).where(AgentRun.id == agent_run_id))
                                    agent_run = result_row.scalar_one_or_none()
                                    if agent_run:
                                        agent_run.status = AgentRunStatus.COMPLETE
                                        agent_run.completed_at = datetime.now(timezone.utc)
                                    await db.flush()
                                    await sse.publish(session_id_str, "agent_event", {
                                        "type": "agent_complete",
                                        "agent_run_id": str(agent_run_id),
                                        "result": None,
                                        "total_steps": 0,
                                    })
                                    logger.info("Agent complete: run=%s", agent_run_id)
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


def _load_transcript(transcript_path: str) -> list:
    """Load and parse transcript file, returning message list."""
    data = json.loads(Path(transcript_path).read_text())
    return data if isinstance(data, list) else data.get("messages", [])


def _extract_browser_steps(messages: list) -> list[dict]:
    """Extract browser_step records from pre-loaded transcript messages."""
    steps = []
    for msg in messages:
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                raw = block.get("content", "")
                if isinstance(raw, str):
                    for line in raw.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            parsed = json.loads(line)
                            if parsed.get("type") == "browser_step":
                                steps.append(parsed)
                        except json.JSONDecodeError:
                            pass
    return steps


def _extract_final_result(messages: list) -> dict | None:
    """Extract the browser_result record from pre-loaded transcript messages."""
    for msg in reversed(messages):
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in reversed(content):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                raw = block.get("content", "")
                if isinstance(raw, str):
                    for line in reversed(raw.splitlines()):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            parsed = json.loads(line)
                            if parsed.get("type") == "browser_result":
                                return parsed
                        except json.JSONDecodeError:
                            pass
    return None


