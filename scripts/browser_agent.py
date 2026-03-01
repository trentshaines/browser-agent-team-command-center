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


def _is_bedrock_model(model: str) -> bool:
    """Detect Bedrock model IDs like 'anthropic.claude-*' or 'us.anthropic.claude-*'."""
    return "anthropic." in model and "/" not in model


def create_llm(model: str):
    """Create the right LLM client based on model name and available keys."""
    # AWS Bedrock (uses browser-use's native Bedrock wrapper)
    if _is_bedrock_model(model):
        from browser_use.llm.aws.chat_bedrock import ChatAWSBedrock
        region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        # With AWS_BEARER_TOKEN_BEDROCK env var set, boto3 uses bearer token auth
        # automatically — aws_sso_auth=True lets it use default credential resolution.
        return ChatAWSBedrock(
            model=model,
            aws_region=region,
            aws_sso_auth=True,
        )

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

    from browser_use.llm.openrouter.chat import ChatOpenRouter
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in .env")
    return ChatOpenRouter(
        model=model,
        api_key=api_key,
    )


def _emit(data: dict) -> None:
    """Write a JSONL record to stdout and flush immediately."""
    print(json.dumps(data, default=str), flush=True)


async def run_task(task: str, model: str, headless: bool) -> dict:
    """Run a browser-use agent with the given task, emitting step logs as JSONL."""
    from browser_use import Agent, BrowserProfile

    try:
        llm = create_llm(model)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    browser_profile = BrowserProfile(headless=headless)
    agent = Agent(task=task, llm=llm, browser_profile=browser_profile)

    async def on_step_end(agent: "Agent") -> None:
        """Emit a browser_step JSONL record after each step completes."""
        history = agent.history
        if not history:
            return
        last = history[-1]

        # Action info — first action in the list
        action_type = None
        action_params = None
        if last.model_output and last.model_output.action:
            action = last.model_output.action[0]
            action_type = type(action).__name__
            try:
                action_params = action.model_dump()
            except Exception:
                action_params = None

        # Result info — first ActionResult
        extracted_content = None
        success = None
        error = None
        if last.result:
            r = last.result[0]
            extracted_content = r.extracted_content
            success = r.success
            error = r.error

        # URL from browser state
        url = None
        if last.state:
            url = getattr(last.state, "url", None)

        # Timing from step metadata
        step_num = len(history)
        step_start_time = None
        step_end_time = None
        duration_seconds = None
        if last.metadata:
            step_num = last.metadata.step_number
            step_start_time = last.metadata.step_start_time
            step_end_time = last.metadata.step_end_time
            try:
                duration_seconds = last.metadata.duration_seconds
            except Exception:
                pass

        _emit({
            "type": "browser_step",
            "step": step_num,
            "url": url,
            "action_type": action_type,
            "action_params": action_params,
            "thought": last.model_output.next_goal if last.model_output else None,
            "evaluation": last.model_output.evaluation_previous_goal if last.model_output else None,
            "memory": last.model_output.memory if last.model_output else None,
            "extracted_content": extracted_content,
            "success": success,
            "error": error,
            "step_start_time": step_start_time,
            "step_end_time": step_end_time,
            "duration_seconds": duration_seconds,
        })

    try:
        result = await agent.run(on_step_end=on_step_end)
        return {
            "success": result.is_successful() or False,
            "task": task,
            "result": result.final_result(),
            "total_steps": len(result),
            "total_duration": result.total_duration_seconds(),
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
    parser.add_argument("--model", default=None, help="Model to use")
    parser.add_argument("--visible", action="store_true", help="Show the browser window")
    args = parser.parse_args()

    model = args.model or os.environ.get("BROWSER_AGENT_MODEL", "google/gemini-2.0-flash-001")
    headless = not args.visible

    result = asyncio.run(run_task(args.task, model, headless))
    # Final result line — always last
    _emit({"type": "browser_result", **result})
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
