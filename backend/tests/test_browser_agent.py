"""Unit tests for browser_agent.py screenshot capture and frame posting."""
import base64
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# browser_agent.py lives in scripts/ — add to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
import browser_agent  # noqa: E402


# ---------------------------------------------------------------------------
# _post_frame tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_frame_success(monkeypatch):
    """Frame is POSTed with correct headers and payload."""
    monkeypatch.setenv("BACKEND_URL", "http://localhost:8000")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-token")

    captured = {}

    async def mock_post(url, *, headers, json):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        resp = MagicMock()
        resp.status_code = 200
        return resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("browser_agent.httpx.AsyncClient", return_value=mock_client):
        await browser_agent._post_frame("sess-1", "agent-1", 3, "https://example.com", "abc123")

    assert captured["url"] == "http://localhost:8000/internal/agent-frame"
    assert captured["headers"]["X-Internal-Token"] == "test-token"
    assert captured["json"]["session_id"] == "sess-1"
    assert captured["json"]["agent_id"] == "agent-1"
    assert captured["json"]["step"] == 3
    assert captured["json"]["url"] == "https://example.com"
    assert captured["json"]["screenshot"] == "abc123"


@pytest.mark.asyncio
async def test_post_frame_logs_4xx(monkeypatch, capsys):
    """4xx responses are logged to stderr."""
    monkeypatch.setenv("BACKEND_URL", "http://localhost:8000")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "bad-token")

    async def mock_post(url, *, headers, json):
        resp = MagicMock()
        resp.status_code = 403
        resp.text = "Forbidden"
        return resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("browser_agent.httpx.AsyncClient", return_value=mock_client):
        await browser_agent._post_frame("s", "a", 1, None, "x")

    captured = capsys.readouterr()
    assert "[frame]" in captured.err
    assert "403" in captured.err


@pytest.mark.asyncio
async def test_post_frame_logs_network_error(monkeypatch, capsys):
    """Network errors are logged to stderr and don't raise."""
    monkeypatch.setenv("BACKEND_URL", "http://localhost:8000")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "")

    async def mock_post(url, *, headers, json):
        raise ConnectionRefusedError("refused")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("browser_agent.httpx.AsyncClient", return_value=mock_client):
        await browser_agent._post_frame("s", "a", 1, None, "x")  # must not raise

    captured = capsys.readouterr()
    assert "[frame]" in captured.err


# ---------------------------------------------------------------------------
# Screenshot capture path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_screenshot_uses_browser_session(monkeypatch):
    """on_step_end calls agent.browser_session.take_screenshot (not agent.browser)."""
    fake_jpeg = b"\xff\xd8\xff" + b"\x00" * 100  # minimal JPEG-like bytes

    # Minimal fake agent history entry
    fake_result = MagicMock()
    fake_result.extracted_content = None
    fake_result.success = True
    fake_result.error = None

    fake_metadata = MagicMock()
    fake_metadata.step_number = 1
    fake_metadata.step_start_time = 0.0
    fake_metadata.step_end_time = 1.0
    fake_metadata.duration_seconds = 1.0

    fake_state = MagicMock()
    fake_state.url = "https://example.com"

    fake_output = MagicMock()
    fake_output.action = []
    fake_output.next_goal = "test goal"
    fake_output.evaluation_previous_goal = "ok"
    fake_output.memory = ""

    fake_history_item = MagicMock()
    fake_history_item.model_output = fake_output
    fake_history_item.result = [fake_result]
    fake_history_item.state = fake_state
    fake_history_item.metadata = fake_metadata

    fake_agent = MagicMock()
    fake_agent.history.history = [fake_history_item]
    fake_agent.browser_session = AsyncMock()
    fake_agent.browser_session.take_screenshot = AsyncMock(return_value=fake_jpeg)

    posted_frames = []

    async def mock_post_frame(session_id, agent_id, step, url, screenshot_b64):
        posted_frames.append({"step": step, "screenshot_b64": screenshot_b64})

    monkeypatch.setattr(browser_agent, "_post_frame", mock_post_frame)

    # Build and call on_step_end by running run_task partially
    # We test the internal logic by directly invoking the closure
    # Easiest: patch run_task to capture the on_step_end closure
    captured_cb = {}

    original_run = browser_agent.run_task

    async def patched_agent_run(on_step_end=None, **kwargs):
        captured_cb["fn"] = on_step_end
        return MagicMock(is_successful=lambda: True, final_result=lambda: "done",
                         __len__=lambda self: 1, total_duration_seconds=lambda: 1.0)

    with patch("browser_use.Agent") as MockAgent:
        instance = MockAgent.return_value
        instance.run = patched_agent_run
        with patch("browser_agent.create_llm", return_value=MagicMock()):
            with patch("browser_use.BrowserProfile", return_value=MagicMock()):
                await browser_agent.run_task("test task", "test-model", True, session_id="sess-abc")

    assert captured_cb.get("fn") is not None, "on_step_end callback was not registered"

    # Now invoke the captured callback with our fake agent
    await captured_cb["fn"](fake_agent)

    assert fake_agent.browser_session.take_screenshot.called, \
        "take_screenshot was not called — wrong API used"
    assert len(posted_frames) == 1
    assert posted_frames[0]["screenshot_b64"] == base64.b64encode(fake_jpeg).decode()
