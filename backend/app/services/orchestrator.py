import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

from app.models.message import Message
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.agent_run_log import AgentRunLog
from app.services import sse
from app.config import get_settings

SYSTEM_PROMPT = """You are an AI assistant with a fleet of browser agents that can take REAL actions on the web.

DEFAULT TO USING BROWSER AGENTS. When in doubt, spawn one. Your agents can navigate, click, fill forms, log in, purchase, book, extract data, and complete multi-step web workflows — not just read pages.

ALWAYS use browser agents for:
- Any question requiring current information (prices, news, availability, scores, weather, stocks)
- Research tasks (comparing products, reading reviews, finding contact info, checking hours)
- Taking actions on behalf of the user (submitting forms, booking, signing up, purchasing)
- Extracting structured data from any website
- Verifying facts on a live website
- Anything involving a URL, domain, or named web service

Spawn agents IN PARALLEL when tasks decompose naturally:
- Researching multiple topics → one agent per source
- Comparing options → one agent per option
- Sequential workflows → chain results between agents

Only answer from memory (no browser) for: pure math, explaining code, well-known definitions, or creative writing with zero web dependency.

After agents return results, synthesize into a clear, markdown-formatted response. Show the user what was found, not just that agents ran."""


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
    from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition, HookMatcher

    # The SDK spawns a claude CLI subprocess. If CLAUDECODE is set (backend was
    # started inside a Claude Code terminal), the subprocess tries to connect to
    # the parent session stream, which is closed, causing it to misbehave and
    # output plain-text fake tool calls instead of using the Task tool. Unset it
    # for the duration of this call.
    _old_claudecode = os.environ.pop("CLAUDECODE", None)
    logger.info("_run_with_sdk: CLAUDECODE was %s", "set" if _old_claudecode else "unset")

    BROWSER_AGENT_PROMPT = f"""You are a browser agent. You take real actions on the web using a headless browser.

Run: uv run python ../scripts/browser_agent.py --task "<exact task>" --session-id {session_id_str}

The script is at ../scripts/browser_agent.py relative to the backend/ working directory.
The browser runs headlessly and streams screenshots back to the user in real time. You can:
- Navigate to any URL and extract text, tables, prices, listings
- Click buttons, links, and UI elements
- Fill and submit forms (search, contact, checkout, signup)
- Log into services when credentials are provided in the task
- Complete multi-step flows: search → select → fill → submit
- Download or scrape structured data

Write specific, action-oriented tasks. Include the exact URL when known.
Return the JSON result from the script exactly as-is."""

    # Correlation state captured by hook closures
    pending_tasks: dict[str, str] = {}      # tool_use_id -> task text
    active_runs: dict[str, uuid.UUID] = {}  # sdk_agent_id -> AgentRun.id

    async def on_pre_task(input_data: dict, tool_use_id: str | None, context) -> dict:
        """Capture the task text before the subagent starts so we can store it."""
        if tool_use_id:
            pending_tasks[tool_use_id] = input_data.get("tool_input", {}).get("prompt", "")
        return {}

    async def on_subagent_start(input_data: dict, tool_use_id: str | None, context) -> dict:
        """Create an AgentRun record and notify the frontend when a subagent spawns."""
        sdk_id = input_data.get("agent_id", "")
        task = pending_tasks.get(tool_use_id or "", "browser task")

        agent_run = AgentRun(
            session_id=uuid.UUID(session_id_str),
            message_id=message_id,
            task=task,
            status=AgentRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(agent_run)
        await db.flush()
        active_runs[sdk_id] = agent_run.id

        await sse.publish(session_id_str, "agent_event", {
            "type": "agent_spawned",
            "agent_id": str(agent_run.id),
            "task": task,
        })
        return {}

    async def on_subagent_stop(input_data: dict, tool_use_id: str | None, context) -> dict:
        """Parse the subagent transcript, save browser_step logs, and update AgentRun status."""
        sdk_id = input_data.get("agent_id", "")
        agent_run_id = active_runs.get(sdk_id)
        transcript_path = input_data.get("agent_transcript_path")

        # Parse transcript once in thread pool (blocking I/O)
        messages = []
        if transcript_path:
            try:
                messages = await asyncio.to_thread(_load_transcript, transcript_path)
            except Exception:
                logger.warning("Failed to load transcript from %s", transcript_path, exc_info=True)

        steps = _extract_browser_steps(messages)
        final = _extract_final_result(messages)

        # Persist each browser step as an AgentRunLog row
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

        # Update AgentRun with final status and result
        result_row = await db.execute(select(AgentRun).where(AgentRun.id == agent_run_id))
        agent_run = result_row.scalar_one_or_none()
        if agent_run:
            agent_run.status = AgentRunStatus.COMPLETE if (final and final.get("success")) else AgentRunStatus.ERROR
            agent_run.result = final.get("result") if final else None
            agent_run.error = final.get("error") if final else None
            agent_run.completed_at = datetime.now(timezone.utc)

        await db.flush()

        # SSE each step so the frontend can show the full execution trace
        for step in steps:
            await sse.publish(session_id_str, "agent_log", {
                "agent_run_id": str(agent_run_id),
                **{k: v for k, v in step.items() if k != "type"},
            })

        await sse.publish(session_id_str, "agent_event", {
            "type": "agent_complete",
            "agent_run_id": str(agent_run_id),
            "result": final.get("result") if final else None,
            "total_steps": len(steps),
        })
        return {}

    full_response = ""
    _backend_dir = Path(__file__).parent.parent.parent  # backend/app/services -> backend/

    def _on_stderr(line: str) -> None:
        logger.warning("Claude subprocess stderr: %s", line.rstrip())

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
                    agents={
                        "browser-agent": AgentDefinition(
                            description="Browses the web to extract data, research topics, or interact with pages. Use for any task requiring web navigation.",
                            prompt=BROWSER_AGENT_PROMPT,
                            tools=["Bash"],
                        )
                    },
                    hooks={
                        "PreToolUse": [HookMatcher(matcher="Task", hooks=[on_pre_task])],
                        "SubagentStart": [HookMatcher(hooks=[on_subagent_start])],
                        "SubagentStop": [HookMatcher(hooks=[on_subagent_stop])],
                    },
                ),
            ):
                # AssistantMessage has a content list of TextBlock / ThinkingBlock / ToolUseBlock
                if hasattr(event, "content") and isinstance(event.content, list):
                    for block in event.content:
                        block_type = type(block).__name__
                        if block_type == "TextBlock" and getattr(block, "text", None):
                            await sse.publish(session_id_str, "delta", {"message_id": str(message_id), "delta": block.text})
                            full_response += block.text
                        elif block_type == "ThinkingBlock" and getattr(block, "thinking", None):
                            await sse.publish(session_id_str, "thinking_delta", {"message_id": str(message_id), "thinking": block.thinking})
                # ResultMessage has the final synthesized result
                elif hasattr(event, "result") and event.result and not full_response:
                    full_response = event.result

        await _save_and_complete(session_id_str, message_id, full_response, db)
    except TimeoutError:
        logger.error("Orchestrator timed out (300s) for session %s", session_id_str)
        await sse.publish(session_id_str, "error_event", {"message_id": str(message_id)})
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


