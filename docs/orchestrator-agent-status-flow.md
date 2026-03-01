# Orchestrator & Agent Status Flow

How the orchestrator detects when agents are blocked/paused/need help, and the full event flow from backend to frontend.

## Agent States

Defined in `helpers.py` as `AgentState`:

| State | Meaning |
|---|---|
| `pending` | Created, not yet started |
| `running` | Actively executing browser steps |
| `paused` | Blocked — waiting for human intervention |
| `complete` | Task finished successfully |
| `error` | Task failed |

## Detection Mechanisms

Three parallel checks run during agent execution in `BrowserAgent._drain_one_stream()` (`backend/agent.py`):

### 1. Vision-based Detection

- **Function**: `needs_handoff(goal, step)` in `helpers.py`
- **When**: After every step
- **How**: Captures a screenshot and sends it to Claude vision API via Bedrock
- **Detects**: CAPTCHAs, login forms, payment/checkout screens, age verification, 2FA, email verification
- **Result**: If intervention needed → triggers `_do_handoff()` → agent enters `PAUSED`

### 2. Step-level Judging

- **Function**: `judge_step(goal, steps)` in `helpers.py`
- **When**: Every N steps (`JUDGE_EVERY_N_STEPS = 3`)
- **How**: An LLM judge evaluates whether the agent is on track
- **Returns**:
  - `"ON_TRACK"` → continue
  - `"NEEDS_HUMAN: <reason>"` → trigger handoff
  - Correction instruction → stop and retry with correction
- **Result**: If `NEEDS_HUMAN` verdict → triggers `_do_handoff()` → agent enters `PAUSED`

### 3. Goal Check

- **Function**: `check_goal(goal, output, steps)` in `helpers.py`
- **When**: After each agent completes its task
- **How**: LLM checks if the goal was fully achieved
- **Returns**:
  - `("COMPLETE", "")` → success
  - `("AGENT", "<instruction>")` → keep going with follow-up
  - `("HUMAN", "<reason>")` → needs human intervention
- **Result**: If `HUMAN` verdict → triggers `_do_handoff()` → agent enters `PAUSED`

## Handoff Flow

```
Agent running
  → Vision/Judge/GoalCheck detects problem
    → _do_handoff() called (agent.py)
      → agent.handoff(reason)
        → self.state = AgentState.PAUSED
        → self._resume_event.clear()
        → self._log(LogAction.PAUSED, reason)
        → self._emit(EventType.HANDOFF, { agent_id, message, handoff_url, source })
```

The `source` field indicates which mechanism triggered the handoff: `"vision"`, `"judge"`, or `"goal_check"`.

## SSE Event Translation

Events are translated in `server.py` `_translate_event()` before being sent to the frontend:

| Backend EventType | Frontend SSE Event | Data Payload |
|---|---|---|
| `agent_started` | `agent_event` (type: agent_spawned) | agent_id, prompt, session_id, live_url |
| `step` | `agent_log` | agent_run_id, step, url, actions, thought |
| `agent_frame` | `agent_frame` | agent_id, step, url, screenshot |
| `handoff` | `handoff` | agent_id, message, handoff_url, source |
| `human_input_received` | `human_input_received` | agent_id |
| `agent_completed` | `agent_event` (type: agent_complete) | agent_run_id, result, total_steps |
| `done` | `done` | agents array with status |

## Frontend SSE Handlers

All handlers live in `frontend/src/routes/james/+page.svelte`:

- **`agent_event`** — Handles `agent_spawned` (creates agent run entry) and `agent_complete` (marks done)
- **`agent_log`** — Accumulates step logs for narration
- **`handoff`** — Updates agent to `paused` status, shows "Needs help: \<reason\>" in chat
- **`human_input_received`** — Updates agent back to `running` status
- **`agent_frame`** — Updates live screenshot and URL
- **`done`** — Marks all agents complete, persists streaming messages

## Resume Flow

When an agent is paused (handoff), the user interacts with the browser directly, then clicks **Resume Agent** to hand control back:

```
User clicks "Resume Agent" on a paused agent tile
  → handleResumeAgent(agentId)      (page.svelte)
    → POST /task/{task_id}/respond/{agent_id}  (tasks.respond() in api.ts)
      → server.py respond() endpoint
        → Finds agent by agent.id (UUID)
        → agent.signal_human_done()
          → Sets _resume_event → unblocks wait_for_human()
            → Agent resumes execution on the same browser session
              → Emits HUMAN_INPUT_RECEIVED
                → Frontend receives SSE 'human_input_received'
                  → Updates agent status → 'running'
```

**Important:** The respond and reprompt endpoints match agents by `agent.id` (UUID), **not** `agent.task_id` (browser-use SDK ID). The frontend only knows the UUID.

## Reprompt Flow

After an agent completes, the user can @-mention it in the chat to reprompt it on its existing browser session:

```
User types "@AgentName do something else" in the chat widget
  → AgentMentionInput autocomplete resolves the name to an agent ID
  → sendMessage(content)             (page.svelte)
    → Detects @-mention, extracts agent ID + instruction
    → POST /task/{task_id}/agent/{agent_id}/reprompt  (tasks.reprompt() in api.ts)
      → server.py reprompt_agent() endpoint
        → Finds agent by agent.id (UUID)
        → Calls agent.retry(prompt) as a background task
          → Emits AGENT_STARTED → frontend flips status back to 'running'
          → Streams steps → frontend accumulates logs + narration
          → Emits AGENT_COMPLETED → frontend marks 'complete'
```

The `retry()` method reuses the existing browser session (no new session creation), emitting the same lifecycle events as the initial run so the frontend can track status.

## Key Files

| File | Purpose |
|---|---|
| `backend/agent.py` | Agent lifecycle, `handoff()`, `retry()`, `_do_handoff()`, `_drain_one_stream()` |
| `helpers.py` | `AgentState` enum, `needs_handoff()`, `judge_step()`, `check_goal()` |
| `backend/server.py` | FastAPI server, SSE event translation, `/respond/` and `/reprompt` endpoints |
| `event_queue.py` | `EventType` enum definitions |
| `frontend/src/lib/api.ts` | `tasks.respond()` for resuming, `tasks.reprompt()` for @-mention reprompt |
| `frontend/src/routes/james/+page.svelte` | SSE handlers, @-mention parsing, agent state management |
| `frontend/src/lib/chat/AgentMentionInput.svelte` | Contenteditable input with @-mention autocomplete |
| `frontend/src/lib/chat/ProgressPanel.svelte` | Progress tab UI showing agent statuses |

## Mock Backend

For frontend-only development, mock routes in `frontend/src/routes/api/mock/` simulate the event sequence:

1. `agent_spawned` → 300-500ms
2. `agent_frame` → 800-1000ms
3. `agent_log` → 1000-1200ms
4. `agent_complete` → 3000-3200ms
5. `done` → 3500ms+

Note: The mock does not currently simulate `handoff` events.
