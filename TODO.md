# TODO

## AI / LLM Integration

### Project Creation Modal
**File:** `frontend/src/lib/components/CreateProjectModal.svelte`

The planning stage currently mocks an LLM call that:
1. Streams a "thinking" response (decomposing the user's goal)
2. Returns a structured list of agent tasks (name, task description)
3. Rewrites/refines the original prompt for multi-agent execution

**What needs replacing:**

- [ ] **Real LLM planning call** — Replace `MOCK_THINKING` and `MOCK_AGENTS` with a backend
  request that accepts `{ name: string, prompt: string }` and returns:
  - A streaming thinking/reasoning response (SSE `thinking_delta` events)
  - A finalised agent plan (SSE `done` event with `{ agents: Agent[], rewrittenPrompt: string }`)
  - Suggested endpoint: `POST /projects/plan`

- [ ] **Dispatch rewritten prompt on launch** — `launch()` currently just creates a session
  with the project name as the title. It should also send the LLM-rewritten prompt as the
  first message so the orchestrator kicks off the agent team immediately.

- [ ] **Persist agent configuration** — The planned agent list should be stored against the
  session so the UI can show which agents were originally configured for a project.

- [ ] **Error handling** — If the planning call fails, return to the input stage with an
  inline error rather than silently dropping the user.
