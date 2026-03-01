# Browser Agent Screenshot Streaming

How live screenshots flow from browser-use cloud agents through the backend SSE pipeline into the `AgentBrowserWindowTile` component.

---

## Architecture

Screenshots are produced per-step (not on a timer). Each time browser-use completes a step, the agent downloads the step's `screenshot_url`, base64-encodes it, and pushes it through the existing SSE event bus. No separate internal endpoint or polling loop is needed.

```
browser-use cloud agent
  └─ step.screenshot_url (hosted by browser-use)
      └─ BrowserAgent._emit_frame()          # backend/agent.py
          └─ httpx.get(screenshot_url)
              └─ base64.b64encode()
                  └─ emit("agent_frame", { agent_id, step, url, screenshot })
                      └─ _make_event_callback()   # backend/server.py
                          └─ SSE event: agent_frame
                              └─ EventSource listener  # +page.svelte
                                  └─ agentFrames[agent_id] = { step, url, screenshot, done }
                                      └─ AgentTiles.svelte
                                          └─ src="data:image/jpeg;base64,..."
                                              └─ AgentBrowserWindowTile <img>
```

---

## Layer 1 — Agent emits frames (`backend/agent.py`)

`BrowserAgent._emit_frame(step)` is called after every `yield step` in `start()`, `retry()`, and `recover()`. It runs as fire-and-forget (`asyncio.ensure_future`) so it never blocks the step stream.

```python
def _emit_frame(self, step: TaskStepView) -> None:
    if not step.screenshot_url or not self.on_event:
        return

    async def _download_and_emit():
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(step.screenshot_url, timeout=15, follow_redirects=True)
                resp.raise_for_status()
            b64 = base64.b64encode(resp.content).decode()
            await self._emit("agent_frame", {
                "agent_id": self.task_id,
                "step": step.number,
                "url": step.url,
                "screenshot": b64,
            })
        except Exception:
            pass  # non-critical

    asyncio.ensure_future(_download_and_emit())
```

Frame rate depends on how fast browser-use produces steps — typically one every 1–3 seconds.

---

## Layer 2 — Event translation (`backend/server.py`)

`_make_event_callback()` translates raw agent events into the SSE event names the frontend expects. `agent_frame` passes through unchanged:

| Backend event | SSE event name | Key data fields |
|---|---|---|
| `agent_spawned` | `agent_event` | `type: "agent_spawned"`, `agent_id`, `task` |
| `agent_status` | `agent_event` | `type: "agent_complete"`, `agent_run_id`, `result`, `total_steps` |
| `agent_step` | `agent_log` | `agent_run_id`, `step`, `action`, `content` |
| `agent_frame` | `agent_frame` | `agent_id`, `step`, `url`, `screenshot` |
| `done` | `done` | `agents[]` |

Events are pushed onto per-subscriber `asyncio.Queue` objects and streamed via `GET /sessions/{session_id}/stream`.

---

## Layer 3 — Frontend SSE handler (`+page.svelte`)

The page listens for `agent_frame` events and stores the latest screenshot per agent:

```typescript
// +page.svelte:175-189
eventSource.addEventListener('agent_frame', (e) => {
  const data = JSON.parse(e.data);
  if (!agentRuns.some(r => r.id === data.agent_id)) return;
  agentFrames[data.agent_id] = {
    step: data.step,
    url: data.url,
    screenshot: data.screenshot,
    done: false,
  };
});
```

When the `done` event fires, all tiles are marked `done: true`.

---

## Layer 4 — Tile rendering (`AgentTiles.svelte` → `AgentBrowserWindowTile`)

`AgentTiles.svelte` converts the raw base64 to a data URI and passes it as the `src` prop:

```svelte
<!-- AgentTiles.svelte:60-71 -->
{#each agents as agent, i (agent.agent_id)}
  <AgentBrowserWindowTile
    src={agent.screenshot ? `data:image/jpeg;base64,${agent.screenshot}` : undefined}
    status={agent.done ? 'Done' : 'In-Progress'}
    agentName={agentName(agent)}
    ...
  />
{/each}
```

`AgentBrowserWindowTile` is a generic draggable/resizable window tile. It renders whatever `src` it receives in an `<img>` tag — it has no knowledge of SSE, base64, or agent lifecycle. When `src` is `undefined` (no frame yet), it falls back to a static default image.

---

## File reference

| File | Role |
|---|---|
| `backend/agent.py` : `_emit_frame()` | Downloads screenshot, base64-encodes, emits `agent_frame` event |
| `backend/agent.py` : `start()`, `retry()`, `recover()` | Calls `_emit_frame(step)` after each `yield step` |
| `backend/server.py` : `_make_event_callback()` | Translates event types, pushes to subscriber queues |
| `backend/server.py` : `stream_session()` | SSE endpoint at `GET /sessions/{id}/stream` |
| `frontend/src/routes/chat/[sessionId]/+page.svelte` | SSE consumer, stores frames in `agentFrames` state |
| `frontend/src/lib/components/AgentTiles.svelte` | Maps `agentFrames` → `AgentBrowserWindowTile` instances |
| `frontend/src/lib/components/AgentBrowserWindowTile/` | Generic tile: drag, resize, expand modal, renders `<img src>` |

---

## Key decisions

| Decision | Reason |
|---|---|
| Per-step (not timed) | Frames arrive naturally with each browser-use step. No polling loop or background task needed. |
| Fire-and-forget download | Screenshot download is async and errors are swallowed — never blocks the step stream. |
| Base64 over SSE | Works natively with SSE (text protocol) and data URIs. No WebSocket or binary framing needed. |
| No internal endpoint | Frames flow through the same event callback as all other agent events. No separate `/internal/agent-frame` route. |
| `agent_frame` pass-through | The event callback translates most event names, but `agent_frame` is already what the frontend expects. |
