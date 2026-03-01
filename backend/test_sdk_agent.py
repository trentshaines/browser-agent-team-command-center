#!/usr/bin/env python3
"""Test the Claude Agent SDK harness with a browser agent for Quincy reviews.

The SDK orchestrator uses ANTHROPIC_API_KEY (direct API).
The browser agent it spawns uses Bedrock (via env vars in .env).

Usage:
    backend/.venv/bin/python test_sdk_agent.py
    backend/.venv/bin/python test_sdk_agent.py --task "Find the best pizza in Boston"
"""

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

# Load env from .env at project root and backend/
load_dotenv(Path(__file__).parent.parent / ".env")
load_dotenv(Path(__file__).parent / ".env")

from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition


SYSTEM_PROMPT = """You are an AI assistant with browser agents that take REAL actions on the web.

When the user asks you to research, search, or find anything on the web, spawn a browser agent.
Your browser agents can navigate to any URL, click, fill forms, and extract data.

After agents return, synthesize the results into a clear response."""

BROWSER_AGENT_PROMPT = """You are a browser agent. Run the browser agent script to complete web tasks.

Run: python scripts/browser_agent.py --task "<exact task>"

The script launches a headless browser, navigates the web, and returns JSON results.
Return the JSON output exactly as-is."""


async def main(task: str):
    print(f"Task: {task}")
    print(f"Orchestrator: Claude Agent SDK (ANTHROPIC_API_KEY)")
    print(f"Browser agent LLM: {os.environ.get('LLM_PROVIDER', 'openrouter')} / {os.environ.get('BROWSER_AGENT_MODEL', 'default')}")
    print()

    # Unset CLAUDECODE if running inside a Claude Code terminal
    os.environ.pop("CLAUDECODE", None)

    async for event in query(
        prompt=task,
        options=ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            allowed_tools=["Task", "Bash"],
            permission_mode="bypassPermissions",
            cwd=str(Path(__file__).parent),
            max_turns=20,
            agents={
                "browser-agent": AgentDefinition(
                    description="Browses the web to search, extract data, or interact with pages.",
                    prompt=BROWSER_AGENT_PROMPT,
                    tools=["Bash"],
                )
            },
        ),
    ):
        print(event)
        if hasattr(event, "text") and event.text:
            print(event.text, end="", flush=True)
        elif hasattr(event, "thinking") and event.thinking:
            pass  # skip thinking output

    print()  # final newline


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task",
        default="Search Google for 'Quincy apartment reviews' and return the top 5 results with titles, URLs, and brief descriptions",
    )
    args = parser.parse_args()
    asyncio.run(main(args.task))
