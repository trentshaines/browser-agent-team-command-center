"""Unit tests for browser_agent.py screenshot capture and frame posting."""
import base64
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# browser_agent.py lives in scripts/ — add to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
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
    assert "[internal]" in captured.err
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
    assert "[internal]" in captured.err


# ---------------------------------------------------------------------------
# _stream_frames continuous capture
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_frames_captures_and_posts(monkeypatch):
    """_stream_frames calls take_screenshot and posts frames until stop_event is set."""
    import asyncio
    fake_jpeg = b"\xff\xd8\xff" + b"\x00" * 100

    stop_event = asyncio.Event()
    call_count = 0

    async def take_screenshot_once(**kwargs):
        nonlocal call_count
        call_count += 1
        stop_event.set()  # stop after first capture
        return fake_jpeg

    fake_agent = MagicMock()
    fake_agent.browser_session = MagicMock()
    fake_agent.browser_session.take_screenshot = take_screenshot_once

    posted_frames = []

    async def mock_post_frame(session_id, agent_id, step, url, screenshot_b64):
        posted_frames.append({"step": step, "screenshot_b64": screenshot_b64})

    monkeypatch.setattr(browser_agent, "_post_frame", mock_post_frame)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))

    await browser_agent._stream_frames(fake_agent, "sess-1", "agent-1", stop_event)

    assert call_count == 1, "take_screenshot should have been called once"
    assert len(posted_frames) == 1
    assert posted_frames[0]["step"] == 0
    assert posted_frames[0]["screenshot_b64"] == base64.b64encode(fake_jpeg).decode()
