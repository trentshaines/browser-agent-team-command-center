import asyncio
import json
import uuid
from collections import defaultdict
from typing import AsyncGenerator


# session_id -> list of queues (one per connected client)
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


async def publish(session_id: str, event: dict) -> None:
    data = json.dumps(event)
    for q in list(_subscribers.get(session_id, [])):
        await q.put(data)


async def stream(session_id: str) -> AsyncGenerator[str, None]:
    q = subscribe(session_id)
    try:
        while True:
            data = await q.get()
            yield f"data: {data}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        unsubscribe(session_id, q)
