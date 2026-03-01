import asyncio
import json
from collections import defaultdict
from typing import AsyncGenerator


class SSEBus:
    """Pub/sub bus for Server-Sent Events. One instance per app; create a fresh
    instance in tests to avoid shared state between test cases."""

    def __init__(self) -> None:
        # session_id -> list of queues (one per connected client)
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, session_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers[session_id].append(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        try:
            self._subscribers[session_id].remove(q)
        except ValueError:
            pass
        if not self._subscribers[session_id]:
            del self._subscribers[session_id]

    async def publish(self, session_id: str, event_name: str, data: dict) -> None:
        payload = f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
        for q in list(self._subscribers.get(session_id, [])):
            await q.put(payload)

    async def stream(self, session_id: str) -> AsyncGenerator[str, None]:
        q = self.subscribe(session_id)
        try:
            yield ": keepalive\n\n"
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield data
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self.unsubscribe(session_id, q)


# Module-level singleton used by the application.
# Tests should create their own SSEBus() instance instead of using this.
default_bus = SSEBus()


# Module-level convenience functions that delegate to the default bus.
def subscribe(session_id: str) -> asyncio.Queue:
    return default_bus.subscribe(session_id)


def unsubscribe(session_id: str, q: asyncio.Queue) -> None:
    default_bus.unsubscribe(session_id, q)


async def publish(session_id: str, event_name: str, data: dict) -> None:
    await default_bus.publish(session_id, event_name, data)


async def stream(session_id: str) -> AsyncGenerator[str, None]:
    async for chunk in default_bus.stream(session_id):
        yield chunk
