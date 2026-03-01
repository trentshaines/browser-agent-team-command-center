import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

from app.database import AsyncSessionLocal
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
                    agents={
                        "browser-agent": AgentDefinition(
                            description="Browses the web to extract data, research topics, or interact with pages. Use for any task requiring web navigation.",
                            prompt=BROWSER_AGENT_PROMPT,
                            tools=["Bash"],
                        )
                    },
                    # NOTE: SDK hooks (SubagentStart/SubagentStop) require bidirectional
                    # control stream communication between bun subprocess and Python.
                    # When the subprocess calls back via sendRequest, it fails with
                    # "Stream closed" crashing the agent. Hooks are disabled until we
                    # have a reliable out-of-band mechanism (e.g. polling transcript).
                    setting_sources=["project", "local"],
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


