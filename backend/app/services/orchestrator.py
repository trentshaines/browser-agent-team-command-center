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
    Run one orchestrator turn. Streams SSE events to the session.
    Uses Claude SDK if available, otherwise falls back to direct Anthropic API.
    """
    settings = get_settings()
    session_id_str = str(session_id)

    try:
        await _run_with_sdk(session_id_str, assistant_message_id, history, db, settings)
    except ImportError:
        logger.info("claude_agent_sdk not available, falling back to direct API")
        if settings.llm_provider == "bedrock":
            await _run_with_bedrock(session_id_str, assistant_message_id, history, db, settings)
        else:
            await _run_with_anthropic(session_id_str, assistant_message_id, history, db, settings)


async def _run_with_sdk(
    session_id_str: str,
    message_id: uuid.UUID,
    history: list[dict],
    db: AsyncSession,
    settings,
) -> None:
    from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition, HookMatcher

    BROWSER_AGENT_PROMPT = """You are a browser agent. You take real actions on the web using a visible browser.

Run: python scripts/browser_agent.py --task "<exact task>" --visible

The browser opens visibly so the user can watch. You can:
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

        steps = _parse_browser_steps(transcript_path)
        final = _parse_final_result(transcript_path)

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

    async for event in query(
        prompt=_build_prompt(history),
        options=ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            allowed_tools=["Task"],
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
        if hasattr(event, "text"):
            await sse.publish(session_id_str, "delta", {"message_id": str(message_id), "delta": event.text})
            full_response += event.text

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
    full_response = ""

    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=history,
    ) as stream:
        async for text in stream.text_stream:
            await sse.publish(session_id_str, "delta", {"message_id": str(message_id), "delta": text})
            full_response += text

    await _save_and_complete(session_id_str, message_id, full_response, db)


async def _run_with_bedrock(
    session_id_str: str,
    message_id: uuid.UUID,
    history: list[dict],
    db: AsyncSession,
    settings,
) -> None:
    import os
    import anthropic

    # Ensure botocore picks up the Bedrock API key for bearer token auth
    if settings.aws_bearer_token_bedrock:
        os.environ.setdefault("AWS_BEARER_TOKEN_BEDROCK", settings.aws_bearer_token_bedrock)

    client = anthropic.AsyncAnthropicBedrock(aws_region=settings.aws_region)
    full_response = ""

    async with client.messages.stream(
        model="us.anthropic.claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=history,
    ) as stream:
        async for text in stream.text_stream:
            await sse.publish(session_id_str, "delta", {"message_id": str(message_id), "delta": text})
            full_response += text

    await _save_and_complete(session_id_str, message_id, full_response, db)


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


def _parse_browser_steps(transcript_path: str | None) -> list[dict]:
    """Extract browser_step records from JSONL inside Bash tool results in an agent transcript."""
    if not transcript_path:
        return []
    steps = []
    try:
        data = json.loads(Path(transcript_path).read_text())
        messages = data if isinstance(data, list) else data.get("messages", [])
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
    except Exception:
        pass
    return steps


def _parse_final_result(transcript_path: str | None) -> dict | None:
    """Extract the browser_result record from an agent transcript."""
    if not transcript_path:
        return None
    try:
        data = json.loads(Path(transcript_path).read_text())
        messages = data if isinstance(data, list) else data.get("messages", [])
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
    except Exception:
        pass
    return None
