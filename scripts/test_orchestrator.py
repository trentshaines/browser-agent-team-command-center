#!/usr/bin/env python3
"""
Direct test of the claude_agent_sdk orchestrator — no HTTP, no auth, no DB.
Prints every SDK event so you can see if subagents are actually being spawned.

Usage:
    .venv/bin/python scripts/test_orchestrator.py "what is the current price of bitcoin?"
"""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

SYSTEM_PROMPT = """You are an orchestrator for a team of browser agents. You help users accomplish web-based tasks.

DEFAULT TO USING BROWSER AGENTS. When in doubt, spawn one.

Always use browser agents for any question requiring current information (prices, news, availability).
Spawn agents IN PARALLEL when tasks decompose naturally.

After agents return results, synthesize into a clear, markdown-formatted response."""

BROWSER_AGENT_PROMPT = """You are a browser agent. You take real actions on the web using a visible browser.

Run: python scripts/browser_agent.py --task "<exact task>" --visible

Return the JSON result from the script exactly as-is."""


async def main(prompt: str) -> None:
    from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition, HookMatcher

    print(f"\n{'='*60}")
    print(f"PROMPT: {prompt}")
    print(f"{'='*60}\n")

    event_count = 0

    async def on_pre_task(input_data, tool_use_id, context):
        task = input_data.get("tool_input", {}).get("prompt", "")
        print(f"  [PreToolUse:Task] tool_use_id={tool_use_id} task={task[:80]!r}")
        return {}

    async def on_subagent_start(input_data, tool_use_id, context):
        print(f"  [SubagentStart] agent_id={input_data.get('agent_id')} tool_use_id={tool_use_id}")
        return {}

    async def on_subagent_stop(input_data, tool_use_id, context):
        transcript = input_data.get("agent_transcript_path", "no transcript")
        print(f"  [SubagentStop]  agent_id={input_data.get('agent_id')} transcript={transcript}")
        return {}

    async for event in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            allowed_tools=["Task"],
            permission_mode="bypassPermissions",
            agents={
                "browser-agent": AgentDefinition(
                    description="Browses the web to extract data, research topics, or interact with pages.",
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
        event_count += 1
        event_type = type(event).__name__

        if hasattr(event, "text") and event.text:
            print(f"[{event_type}] text: {event.text[:120]!r}")
        else:
            attrs = {k: v for k, v in vars(event).items() if not k.startswith("_") and v is not None}
            print(f"[{event_type}] {attrs}")

    print(f"\n{'='*60}")
    print(f"Done. {event_count} events total.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "What is the current price of bitcoin?"
    asyncio.run(main(prompt))
