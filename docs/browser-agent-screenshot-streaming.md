# Browser Agent Screenshot Streaming

How to capture live screenshots from a `browser-use` agent and stream them to a frontend in real time.

---

## Overview

The pipeline runs at ~0.67 fps (one frame every 1.5 seconds). Each frame is a JPEG screenshot, base64-encoded, pushed over an SSE (Server-Sent Events) connection to the browser, and rendered as a plain `<img>` tag.

```
browser-use agent (Playwright)
  └─ take_screenshot() every 1.5s
      └─ base64-encode JPEG
          └─ POST to internal API endpoint
              └─ publish to SSE bus (per-session queue)
                  └─ EventSource stream held open by browser
                      └─ update Svelte/React state
                          └─ <img src="data:image/jpeg;base64,...">
```

---

## Step 1 — Capture screenshots in the agent

Inside your agent runner, start a background task that loops and calls `take_screenshot()` on the browser session. POST each frame to your own backend.

```python
import asyncio, base64, httpx

async def stream_frames(agent, session_id: str, agent_id: str, stop: asyncio.Event):
    step = 0
    async with httpx.AsyncClient() as client:
        while not stop.is_set():
            try:
                jpeg = await agent.browser_session.take_screenshot(format="jpeg", quality=40)
                b64  = base64.b64encode(jpeg).decode()
                await client.post(
                    "http://localhost:8000/internal/agent-frame",
                    json={"session_id": session_id, "agent_id": agent_id,
                          "step": step, "screenshot": b64},
                    headers={"X-Internal-Token": INTERNAL_TOKEN},
                )
                step += 1
            except Exception:
                pass
            await asyncio.sleep(1.5)   # ~0.67 fps — raise for smoother video

# Start alongside your agent run:
stop_event = asyncio.Event()
frame_task = asyncio.create_task(stream_frames(agent, session_id, agent_id, stop_event))

# ... run agent ...

stop_event.set()
await frame_task
```

**Tips:**
- `quality=40` keeps base64 payloads small (~100–200 KB per frame). Raise for sharper images.
- Use a `stop_event` so the loop exits cleanly when the agent finishes.
- Protect the endpoint with an internal secret token so only your backend can call it.

---

## Step 2 — Internal API endpoint (receives frames, publishes to SSE)

Add a POST route that accepts the frame payload and pushes it onto the SSE bus.

```python
# FastAPI example
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/internal")

class AgentFrameData(BaseModel):
    session_id: str  = Field(..., max_length=36)
    agent_id:   str  = Field(..., max_length=36)
    step:       int  | None = Field(None, ge=0)
    url:        str  | None = Field(None, max_length=2048)
    screenshot: str  | None = Field(None, max_length=500_000)  # ~375 KB base64

@router.post("/agent-frame")
async def agent_frame(data: AgentFrameData, _=Depends(verify_internal_token)):
    await sse_bus.publish(data.session_id, "agent_frame", {
        "agent_id":   data.agent_id,
        "step":       data.step,
        "url":        data.url,
        "screenshot": data.screenshot,
    })
    return {"ok": True}
```

---

## Step 3 — SSE pub/sub bus

A lightweight in-process pub/sub. Each connected client gets an `asyncio.Queue`. `publish()` drops the formatted SSE payload into every subscriber's queue for that session.

```python
import asyncio, json
from collections import defaultdict

class SSEBus:
    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, session_id: str, event: str, data: dict):
        payload = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        for q in list(self._subscribers[session_id]):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass  # drop for slow consumers

    async def stream(self, session_id: str):
        """Async generator — yield SSE payloads as they arrive."""
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._subscribers[session_id].append(q)
        try:
            yield ": connected\n\n"   # initial comment keeps connection alive
            while True:
                yield await q.get()
        finally:
            self._subscribers[session_id].remove(q)

sse_bus = SSEBus()
```

---

## Step 4 — Streaming endpoint (frontend connects here)

Expose an SSE endpoint that the browser holds open with `EventSource`.

```python
from fastapi import Request
from fastapi.responses import StreamingResponse

@router.get("/{session_id}/stream")
async def stream_session(session_id: str, request: Request):
    return StreamingResponse(
        sse_bus.stream(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # prevents nginx from buffering
        },
    )
```

---

## Step 5 — Frontend: consume the SSE stream

Open an `EventSource` connection and listen for `agent_frame` events. Store the latest screenshot per agent in state.

```typescript
// Connect
const eventSource = new EventSource(`/api/sessions/${sessionId}/stream`, {
  withCredentials: true,
});

// State: latest frame per agent_id
let agentFrames: Record<string, {
  screenshot: string | null;
  step: number | null;
  url: string | null;
  done: boolean;
}> = {};

// Handle frames
eventSource.addEventListener('agent_frame', (e) => {
  const data = JSON.parse(e.data);
  agentFrames[data.agent_id] = {
    screenshot: data.screenshot,
    step: data.step,
    url: data.url,
    done: false,
  };
});

// Cleanup
eventSource.close();
```

---

## Step 6 — Frontend: render the screenshot

Convert the raw base64 string to a data URL and drop it into an `<img>` tag. No blob URLs or canvas needed.

**Svelte:**
```svelte
{#each Object.entries(agentFrames) as [agentId, frame]}
  <img
    src={frame.screenshot ? `data:image/jpeg;base64,${frame.screenshot}` : undefined}
    alt="Agent {agentId}"
    style="width: 100%; height: auto;"
  />
{/each}
```

**React:**
```tsx
{Object.entries(agentFrames).map(([agentId, frame]) => (
  <img
    key={agentId}
    src={frame.screenshot ? `data:image/jpeg;base64,${frame.screenshot}` : undefined}
    alt={`Agent ${agentId}`}
    style={{ width: '100%', height: 'auto' }}
  />
))}
```

---

## Key decisions and trade-offs

| Decision | Reason |
|---|---|
| JPEG quality 40 | Keeps payloads small. Raise to 70–80 for sharper text. |
| 1.5s interval | Low enough overhead, sufficient for monitoring. Reduce to 0.5s for smoother feel. |
| Base64 over binary | Works natively with SSE (text protocol) and data URLs. No extra decoding step. |
| SSE over WebSockets | Simpler — SSE is one-directional, auto-reconnects, and works through most proxies. |
| One queue per client | Session-isolated — multiple browser tabs each get their own stream. |
| `put_nowait` with drop | Prevents slow clients from blocking the agent. Frames are ephemeral anyway. |
| Internal token auth | Prevents external callers from injecting fake frames into any session. |

---

## Minimal end-to-end checklist

- [ ] Agent runner calls `take_screenshot()` in a loop and POSTs to `/internal/agent-frame`
- [ ] Internal endpoint validates token, publishes to SSE bus with `session_id` as the key
- [ ] SSE bus maintains a per-session subscriber list of `asyncio.Queue` objects
- [ ] Public stream endpoint returns `StreamingResponse` with `media_type="text/event-stream"`
- [ ] Frontend opens `EventSource`, listens for `agent_frame`, stores latest frame per `agent_id`
- [ ] `<img src="data:image/jpeg;base64,...">` renders the frame
