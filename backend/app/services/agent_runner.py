import asyncio
import json
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


async def run_browser_agent(task: str) -> dict:
    """Run browser_agent.py as a subprocess and return parsed JSON result."""
    python = PROJECT_ROOT / ".venv" / "bin" / "python"
    script = PROJECT_ROOT / "scripts" / "browser_agent.py"

    proc = await asyncio.create_subprocess_exec(
        str(python),
        str(script),
        "--task", task,
        "--visible",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(PROJECT_ROOT),
    )

    stdout, stderr = await proc.communicate()

    try:
        result = json.loads(stdout.decode())
    except json.JSONDecodeError:
        result = {
            "success": False,
            "task": task,
            "error": stderr.decode() or "Failed to parse agent output",
        }

    return result
