#!/usr/bin/env python3
"""Browser Agent Runner - executes a browser task using browser-use."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def create_llm(model: str):
    """Create the right LLM client based on model name and available keys."""
    # MiniMax direct
    if "minimax" in model.lower():
        from browser_use.llm.openai.chat import ChatOpenAI
        api_key = os.environ.get("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("MINIMAX_API_KEY not set in .env")
        return ChatOpenAI(
            model=model,
            base_url="https://api.minimax.io/v1",
            api_key=api_key,
        )

    # OpenRouter (default)
    from browser_use.llm.openrouter.chat import ChatOpenRouter
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in .env")
    return ChatOpenRouter(
        model=model,
        api_key=api_key,
    )


async def run_task(task: str, model: str, headless: bool) -> dict:
    """Run a browser-use agent with the given task."""
    from browser_use import Agent, BrowserProfile

    try:
        llm = create_llm(model)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    browser_profile = BrowserProfile(headless=headless)

    agent = Agent(
        task=task,
        llm=llm,
        browser_profile=browser_profile,
    )

    try:
        result = await agent.run()
        final_result = result.final_result() if hasattr(result, 'final_result') else str(result)
        return {
            "success": True,
            "task": task,
            "result": final_result,
        }
    except Exception as e:
        return {
            "success": False,
            "task": task,
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="Run a browser agent task")
    parser.add_argument("--task", required=True, help="Natural language task for the browser agent")
    parser.add_argument("--model", default=None, help="Model to use (default: from .env or google/gemini-2.0-flash-001)")
    parser.add_argument("--visible", action="store_true", help="Show the browser window (default: headless)")
    args = parser.parse_args()

    model = args.model or os.environ.get("BROWSER_AGENT_MODEL", "google/gemini-2.0-flash-001")
    headless = not args.visible

    result = asyncio.run(run_task(args.task, model, headless))
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
