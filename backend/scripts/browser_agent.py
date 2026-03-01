#!/usr/bin/env python3
"""Browser Agent Runner - executes a browser task using browser-use."""

import argparse
import asyncio
import base64
import json
import os
import sys
import uuid
from pathlib import Path

import httpx
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


async def _post_internal(path: str, payload: dict) -> None:
    """POST to a FastAPI internal endpoint. Logs errors to stderr but never raises."""
    port = os.environ.get("PORT", "8000")
    backend_url = os.environ.get("BACKEND_URL", f"http://localhost:{port}")
    token = os.environ.get("INTERNAL_API_TOKEN", "")
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.post(
                f"{backend_url}{path}",
                headers={"X-Internal-Token": token},
                json=payload,
            )
            if resp.status_code >= 400:
                print(f"[internal] POST {path} -> {resp.status_code}: {resp.text[:200]}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[internal] POST {path} failed: {e}", file=sys.stderr, flush=True)


async def _post_frame(session_id: str, agent_id: str, step: int, url: str | None, screenshot_b64: str) -> None:
    await _post_internal("/internal/agent-frame", {
        "session_id": session_id, "agent_id": agent_id,
        "step": step, "url": url, "screenshot": screenshot_b64,
    })


async def _stream_frames(agent, session_id: str, agent_id: str, stop_event: asyncio.Event) -> None:
    """Continuously capture and stream screenshots until stop_event is set (~0.67 fps)."""
    step = 0
    while not stop_event.is_set():
        try:
            jpeg = await agent.browser_session.take_screenshot(format="jpeg", quality=40)
            b64 = base64.b64encode(jpeg).decode()
            await _post_frame(session_id, agent_id, step, None, b64)
            step += 1
        except Exception:
            pass
        await asyncio.sleep(1.5)


async def run_task(task: str, model: str, headless: bool, session_id: str | None = None) -> dict:
    """Run a browser-use agent with the given task, emitting step logs as JSONL."""
    from browser_use import Agent, BrowserProfile

    agent_id = str(uuid.uuid4())

    try:
        llm = create_llm(model)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    use_cloud = os.environ.get("BROWSER_USE_CLOUD", "").lower() in ("1", "true", "yes")
    profile_kwargs: dict = {"use_cloud": use_cloud, "headless": headless if not use_cloud else True}
    if not use_cloud:
        # Give each parallel agent its own isolated profile dir to avoid Chromium lock conflicts
        import tempfile
        profile_kwargs["user_data_dir"] = Path(tempfile.mkdtemp(prefix="bu_agent_"))
    browser_profile = BrowserProfile(**profile_kwargs)
    agent = Agent(task=task, llm=llm, browser_profile=browser_profile)

    async def on_step_end(agent: "Agent") -> None:
        """Emit a browser_step JSONL record after each step completes."""
        history = agent.history.history if hasattr(agent.history, 'history') else list(agent.history)
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

    stop_event = asyncio.Event()
    if session_id:
        frame_task = asyncio.create_task(
            _stream_frames(agent, session_id, agent_id, stop_event)
        )

    try:
        result = await agent.run(on_step_end=on_step_end)
        outcome = {
            "success": result.is_successful() or False,
            "task": task,
            "result": result.final_result(),
            "total_steps": len(result),
            "total_duration": result.total_duration_seconds(),
        }
        return outcome
    except Exception as e:
        return {
            "success": False,
            "task": task,
            "error": str(e),
        }
    finally:
        stop_event.set()
        if session_id:
            await frame_task


def main():
    parser = argparse.ArgumentParser(description="Run a browser agent task")
    parser.add_argument("--task", required=True, help="Natural language task for the browser agent")
    parser.add_argument("--model", default=None, help="Model to use")
    parser.add_argument("--visible", action="store_true", help="Show the browser window")
    parser.add_argument("--session-id", default=None, help="Session ID for screenshot streaming")
    args = parser.parse_args()

    model = args.model or os.environ.get("BROWSER_AGENT_MODEL", "google/gemini-2.0-flash-001")
    headless = not args.visible

    result = asyncio.run(run_task(args.task, model, headless, session_id=args.session_id))
    # Final result line — always last
    _emit({"type": "browser_result", **result})
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
