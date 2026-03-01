import asyncio
import json
from collections import defaultdict
from typing import AsyncGenerator

_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

def subscribe(session_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers[session_id].append(q)
    return q

def unsubscribe(session_id: str, q: asyncio.Queue) -> None:
    try:
        _subscribers[session_id].remove(q)
    except ValueError:
        pass
    if not _subscribers[session_id]:
        del _subscribers[session_id]

async def publish(session_id: str, event_name: str, data: dict) -> None:
    payload = f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
    for q in list(_subscribers.get(session_id, [])):
        await q.put(payload)

async def stream(session_id: str) -> AsyncGenerator[str, None]:
    q = subscribe(session_id)
    try:
        # Send a keepalive comment immediately
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
        unsubscribe(session_id, q)
