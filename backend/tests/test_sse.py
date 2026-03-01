"""Unit tests for SSEBus — no DB or network required."""
import asyncio

import pytest

from app.services.sse import SSEBus


class TestSSEBus:
    def test_subscribe_returns_queue(self):
        bus = SSEBus()
        q = bus.subscribe("session-1")
        assert isinstance(q, asyncio.Queue)

    def test_unsubscribe_removes_queue(self):
        bus = SSEBus()
        q = bus.subscribe("session-1")
        bus.unsubscribe("session-1", q)
        assert "session-1" not in bus._subscribers

    def test_unsubscribe_unknown_queue_is_safe(self):
        bus = SSEBus()
        q = asyncio.Queue()
        bus.unsubscribe("nonexistent", q)  # should not raise

    async def test_publish_delivers_to_subscriber(self):
        bus = SSEBus()
        q = bus.subscribe("session-1")
        await bus.publish("session-1", "text_delta", {"text": "hello"})
        item = q.get_nowait()
        assert "text_delta" in item
        assert "hello" in item

    async def test_publish_to_session_with_no_subscribers_is_safe(self):
        bus = SSEBus()
        await bus.publish("nobody", "ping", {})  # should not raise

    async def test_publish_reaches_multiple_subscribers(self):
        bus = SSEBus()
        q1 = bus.subscribe("session-x")
        q2 = bus.subscribe("session-x")
        await bus.publish("session-x", "ping", {"n": 1})
        assert not q1.empty()
        assert not q2.empty()

    async def test_publish_does_not_cross_sessions(self):
        bus = SSEBus()
        q_a = bus.subscribe("session-a")
        q_b = bus.subscribe("session-b")
        await bus.publish("session-a", "ping", {})
        assert not q_a.empty()
        assert q_b.empty()

    async def test_stream_yields_published_events(self):
        bus = SSEBus()

        async def producer():
            await asyncio.sleep(0)
            await bus.publish("s", "delta", {"text": "hi"})

        results = []

        async def consumer():
            async for chunk in bus.stream("s"):
                if chunk.startswith(": keepalive"):
                    continue
                results.append(chunk)
                break  # stop after first real event

        await asyncio.gather(consumer(), producer())
        assert len(results) == 1
        assert "delta" in results[0]
        assert "hi" in results[0]

    async def test_instances_are_isolated(self):
        """Two SSEBus instances share no state."""
        bus1 = SSEBus()
        bus2 = SSEBus()
        q = bus1.subscribe("s")
        await bus2.publish("s", "ping", {})
        assert q.empty()
