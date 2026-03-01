from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any


class EventType(Enum):
    # Agent lifecycle
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"

    # Step-level
    STEP = "step"
    THINKING = "thinking"
    NAVIGATION = "navigation"
    JUDGE = "judge"
    CORRECTION = "correction"

    # Handoff / human intervention
    HANDOFF = "handoff"
    PAUSED = "paused"
    RESUMED = "resumed"
    HUMAN_INPUT_RECEIVED = "human_input_received"

    # Recovery / retry
    RETRY = "retry"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"

    # Output
    OUTPUT = "output"
    SUMMARY = "summary"


class Event:
    __slots__ = ("type", "data")

    def __init__(self, type: EventType, data: dict[str, Any]) -> None:
        self.type = type
        self.data = data

    def __repr__(self) -> str:
        return f"Event({self.type.value}, {self.data})"


# ---------------------------------------------------------------------------
# Broadcast model — each SSE client subscribes and gets its own queue.
# add_event() fans out to all subscribers.
# ---------------------------------------------------------------------------

_subscribers: set[asyncio.Queue[Event]] = set()


def subscribe() -> asyncio.Queue[Event]:
    """Create a per-client queue and register it for broadcast."""
    q: asyncio.Queue[Event] = asyncio.Queue()
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue[Event]) -> None:
    """Remove a client queue from the broadcast set."""
    _subscribers.discard(q)


def add_event(event_type: EventType, data: dict[str, Any]) -> None:
    """Push an event to every subscriber (non-blocking)."""
    event = Event(type=event_type, data=data)
    for q in _subscribers:
        q.put_nowait(event)


def pending_count() -> int:
    """Total events waiting across all subscribers."""
    return sum(q.qsize() for q in _subscribers)