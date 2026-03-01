# Architecture Overview

How the frontend, backend, Claude SDK, and browser agents connect.

---

## High-Level Data Flow

```
User types message
      ↓
POST /sessions/{id}/messages
      ↓
orchestrator.py  ←→  claude_agent_sdk.query()  (Claude decides)
      ↓ spawns
browser_agent.py (subprocess, one per agent)
      ↓ POSTs frames/events to /internal/*
SSE bus  →  GET /sessions/{id}/stream  →  Frontend EventSource
```

---

## 1. Frontend → Backend

The user sends a message → `POST /sessions/{id}/messages`. The backend immediately returns a placeholder assistant message. The frontend simultaneously holds an open SSE connection at `GET /sessions/{id}/stream` and reacts to events as they arrive.

---

## 2. Orchestrator (Claude SDK)

`app/services/orchestrator.py` runs as an async background task. It calls `claude_agent_sdk.query()` with:

- The full conversation history
- A system prompt telling Claude to use browser agents for web tasks
- A single allowed tool: `Task`

Claude streams back text (streamed to the frontend as `delta` events) and tool calls. When Claude calls `Task`, the SDK executes `scripts/browser_agent.py` as a **subprocess via Bash** — one per agent, potentially in parallel.

Before each subprocess starts, the orchestrator:
1. Creates an `AgentRun` record in Postgres (status = `running`)
2. Pushes its UUID into an in-memory `agent_registry` queue so the subprocess can claim it

---

## 3. Browser Agent Subprocess (`scripts/browser_agent.py`)

Each agent is an isolated Python subprocess. On startup it:
1. Claims its `agent_run_id` via `POST /internal/agent-claim` (matched from the queue above)
2. Creates a **browser-use** agent (Playwright + Gemini Flash via OpenRouter by default)
3. Runs two loops concurrently:
   - **Main**: `agent.run()` with a step callback that POSTs step details to `/internal/agent-event` after each action
   - **Background**: Captures a screenshot every ~1.5s and POSTs it to `/internal/agent-frame`
4. On completion, emits a final `browser_result` JSONL record and exits

The subprocess communicates back via two channels:
- **HTTP POSTs** to `/internal/*` for real-time events (frames, step logs)
- **JSONL stdout** for the final result, which the orchestrator parses and persists to Postgres

---

## 4. Internal Relay → SSE Bus

`app/routers/internal.py` exposes three endpoints protected by a shared secret (`INTERNAL_API_TOKEN`):

| Endpoint | Purpose |
|---|---|
| `POST /internal/agent-claim` | Browser agent claims its pre-registered `agent_run_id` |
| `POST /internal/agent-frame` | Relays screenshot frame onto SSE bus |
| `POST /internal/agent-event` | Relays step logs and completion events onto SSE bus |

`app/services/sse.py` is an in-memory pub/sub bus keyed by session ID. Any subscriber (frontend SSE connection) for a session receives all published events instantly.

---

## 5. SSE Events Received by the Frontend

| Event | Payload | UI effect |
|---|---|---|
| `delta` | `{message_id, delta}` | Appends text to the streaming assistant message |
| `thinking_delta` | `{message_id, thinking}` | Shows Claude's thinking block |
| `agent_event` (spawned) | `{agent_id, task, name}` | Adds an agent card to the run panel |
| `agent_frame` | `{agent_id, step, url, screenshot}` | Renders/updates a live screenshot tile |
| `agent_log` | `{step, url, action_type, thought, …}` | Adds a step to the graph/progress view |
| `agent_event` (complete) | `{agent_run_id, result, total_steps}` | Marks the agent done |
| `done` | `{message_id, content}` | Finalises the assistant message |
| `error_event` | `{error}` | Shows error state |

---

## 6. Database

PostgreSQL via SQLAlchemy async. Key tables:

- **Session** — a chat conversation
- **Message** — user/assistant turns within a session
- **AgentRun** — one row per browser agent invocation (task, status, result)
- **AgentRunLog** — one row per browser step (URL, action, thought, success, timing)

---

## 7. Key Design Decisions

**Browser agents survive orchestrator cancellation.**
Subprocesses keep running even if the user interrupts Claude mid-turn. Tiles stay live and continue streaming frames.

**Per-session async locks.**
`orchestrator.py` holds a lock per session to prevent two Claude turns competing over the same SDK subprocess state.

**JSONL stdout protocol.**
The browser agent emits `browser_step` and `browser_result` records to stdout. The orchestrator parses these after the subprocess exits and persists them to Postgres as `AgentRunLog` rows.

**Split LLM responsibilities.**
The orchestrator uses Claude (Anthropic API or Bedrock) for high-level reasoning and task decomposition. Browser agents default to Gemini Flash via OpenRouter — faster and cheaper for repetitive browser actions.

**Agent ID handshake.**
The orchestrator pre-registers an `agent_run_id` in the DB and pushes it to a queue. The subprocess claims it on startup. This gives both sides a shared UUID without any coordination overhead.

---

## Key Files

| File | Purpose |
|---|---|
| `app/main.py` | FastAPI app, CORS, route registration |
| `app/services/orchestrator.py` | Claude SDK integration, agent lifecycle, SSE streaming |
| `scripts/browser_agent.py` | Browser-use agent runner, screenshot capture, JSONL output |
| `app/services/sse.py` | In-memory pub/sub SSE bus |
| `app/services/agent_registry.py` | Queue for agent_run_id claiming |
| `app/routers/messages.py` | Message creation, orchestrator task spawning |
| `app/routers/internal.py` | Internal relay endpoints for browser agent → SSE bus |
| `app/models/` | SQLAlchemy ORM (User, Session, Message, AgentRun, AgentRunLog) |
| `app/config.py` | All env var settings |
