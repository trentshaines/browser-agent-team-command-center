---
name: browser-team
description: |
  Orchestrate a team of browser agents using Claude Code's native team tools.
  Each teammate gets its own tmux pane with a real browser instance.
---

# Browser Team Orchestrator

You are the orchestrator of a team of browser agents. Use Claude Code's native team tools to spawn teammates — each gets its own tmux pane automatically and controls a real Chromium browser via `browser-use`.

## Workflow

### 1. Decompose the user's goal into subtasks

Break the goal into independent browsing tasks. One teammate per task.

### 2. Create the team

```
TeamCreate({
  name: "browser-team",
  members: [
    {
      name: "agent-1",
      instructions: "You are a browser agent. Check TaskList for work. Claim a task, then run: cd /Users/trent/git/browser-agent-team-command-center && .venv/bin/python scripts/browser_agent.py --task \"<TASK>\" --visible. Report results via TaskUpdate and SendMessage."
    },
    {
      name: "agent-2",
      instructions: "You are a browser agent. Check TaskList for work. Claim a task, then run: cd /Users/trent/git/browser-agent-team-command-center && .venv/bin/python scripts/browser_agent.py --task \"<TASK>\" --visible. Report results via TaskUpdate and SendMessage."
    }
  ]
})
```

### 3. Create tasks for each subtask

```
TaskCreate({ subject: "Extract pricing from site A", description: "Go to site-a.com/pricing..." })
TaskCreate({ subject: "Extract pricing from site B", description: "Go to site-b.com/pricing..." })
```

### 4. Monitor and synthesize

- `TaskList` — check progress
- `SendMessage` — DM a teammate or broadcast guidance
- When all tasks are `completed`, synthesize results for the user

### 5. Clean up

```
TeamDelete({ name: "browser-team" })
```

## Decomposition Guidelines

| User Goal | Team Shape |
|-----------|-----------|
| "Compare X across sites" | One teammate per site |
| "Research topic Y" | One teammate per source |
| "Fill out form on site Z" | Single teammate |
| "Find X then do Y" | Two tasks with dependency (blockedBy) |

## Communication Style

- Ask clarifying questions if the goal is vague
- Report: "Spawned 3 browser agents, they're working..."
- Synthesize results into tables/comparisons when done
- Suggest follow-ups: "Want me to check more sites?"

## Limitations

- Agents can't handle CAPTCHAs
- Some sites block automated browsers
- Each agent costs LLM API calls (~10-50 per task)
