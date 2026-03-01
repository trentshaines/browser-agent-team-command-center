import logging
import uuid
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

from app.models.message import Message
from app.models.agent_run import AgentRun, AgentRunStatus
from app.services import sse
from app.services.agent_runner import run_browser_agent
from app.config import get_settings

SYSTEM_PROMPT = """You are an orchestrator for a team of browser agents. You help users accomplish web-based tasks.

When a user asks you to research, compare, scrape, or gather information from websites, you should:
1. Break the task into specific browsing subtasks
2. Use the browser agents (via the spawn_browser_agent function described below) to execute them in parallel
3. Synthesize the results into a clear, markdown-formatted response

For conversational questions that don't require browsing, just answer directly.

You have access to browser agents that can:
- Navigate to any URL
- Extract text, data, prices, and structured information
- Fill forms and interact with pages
- Return structured JSON results

Always respond in markdown. Be concise and actionable."""


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
        # Try Claude Agent SDK first
        await _run_with_sdk(session_id_str, assistant_message_id, history, db, settings)
    except ImportError:
        logger.info("claude_agent_sdk not available, falling back to direct Anthropic API")
        await _run_with_anthropic(session_id_str, assistant_message_id, history, db, settings)


async def _run_with_sdk(
    session_id_str: str,
    message_id: uuid.UUID,
    history: list[dict],
    db: AsyncSession,
    settings,
) -> None:
    from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

    BROWSER_AGENT_PROMPT = """You are a browser agent. You execute a single web browsing task using browser-use.

Your only job:
1. Run the browser_agent.py script with the given task
2. Return the JSON result

You have access to Bash to run: python scripts/browser_agent.py --task "..." --visible
"""

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
        ),
    ):
        event_type = type(event).__name__

        # Stream text deltas
        if hasattr(event, "text"):
            await sse.publish(session_id_str, "delta", {"message_id": str(message_id), "delta": event.text})
            full_response += event.text

        # Agent spawned
        elif event_type == "AgentStarted":
            agent_run = AgentRun(
                session_id=uuid.UUID(session_id_str),
                message_id=message_id,
                task=getattr(event, "description", "browser task"),
                status=AgentRunStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
            )
            db.add(agent_run)
            await db.flush()
            await sse.publish(session_id_str, "agent_event", {
                "type": "agent_spawned",
                "agent_id": str(agent_run.id),
                "task": agent_run.task,
            })

        # Agent completed
        elif event_type == "AgentCompleted":
            result_text = getattr(event, "result", "")
            await sse.publish(session_id_str, "agent_event", {
                "type": "agent_complete",
                "result": result_text,
            })

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


async def _save_and_complete(
    session_id_str: str,
    message_id: uuid.UUID,
    content: str,
    db: AsyncSession,
) -> None:
    # Update the assistant message in DB
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
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
