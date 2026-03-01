#!/usr/bin/env python3
"""Quick test: invoke the orchestrator SDK directly (no auth, no HTTP)."""
import asyncio
import os
import sys
import uuid
from pathlib import Path

# Load backend env
env_file = Path(__file__).parent.parent / "backend" / ".env"
for line in env_file.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

SESSION_ID = str(uuid.uuid4())

BROWSER_AGENT_PROMPT = f"""You are a browser agent. You take real actions on the web using a visible browser.

Run: uv run python ../scripts/browser_agent.py --task "<exact task>" --visible --session-id {SESSION_ID}

The script is at ../scripts/browser_agent.py relative to the backend/ working directory.
Return the JSON result from the script exactly as-is."""

SYSTEM_PROMPT = """You are an AI assistant with a fleet of browser agents.
DEFAULT TO USING BROWSER AGENTS. Always spawn one for web tasks.
After agents return results, synthesize into a clear response."""

async def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "what is the current bitcoin price"
    print(f"Session: {SESSION_ID}")
    print(f"Prompt: {prompt}\n")

    # Unset CLAUDECODE so the SDK subprocess behaves correctly
    old = os.environ.pop("CLAUDECODE", None)
    print(f"CLAUDECODE was: {'set' if old else 'unset'}")

    try:
        async for event in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                system_prompt=SYSTEM_PROMPT,
                allowed_tools=["Task"],
                permission_mode="bypassPermissions",
                agents={
                    "browser-agent": AgentDefinition(
                        description="Browses the web.",
                        prompt=BROWSER_AGENT_PROMPT,
                        tools=["Bash"],
                    )
                },
            ),
        ):
            if hasattr(event, "text") and event.text:
                print(event.text, end="", flush=True)
            elif hasattr(event, "thinking") and event.thinking:
                print(f"\n[thinking]: {event.thinking[:100]}...\n", flush=True)
    finally:
        if old is not None:
            os.environ["CLAUDECODE"] = old

    print("\n\nDone.")

asyncio.run(main())
