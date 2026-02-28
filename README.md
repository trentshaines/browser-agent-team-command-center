# Browser Agent Team Command Center

A Claude Code skill that orchestrates a team of browser agents. Each agent gets its own Chromium browser instance powered by [browser-use](https://github.com/browser-use/browser-use) + Playwright.

## Setup

```bash
# 1. Install dependencies (already done if you cloned this)
uv venv --python 3.12 && uv pip install browser-use langchain-openai playwright python-dotenv
playwright install chromium

# 2. Configure your API key
cp config.example .env
# Edit .env and add your OpenRouter API key
```

## Usage

### From Claude Code

Invoke the skill:
```
/browser-team
```

Then chat with the orchestrator: "Compare the pricing of Vercel, Netlify, and Railway" — it'll dispatch 3 browser agents in parallel.

### Direct (single agent)

```bash
.venv/bin/python scripts/browser_agent.py --task "Go to example.com and get the page title"
.venv/bin/python scripts/browser_agent.py --task "Search for Python tutorials" --visible
```

## Architecture

```
You (Claude Code)
  → /browser-team skill (orchestrator)
    → browser-agent subagent → Python browser-use → Browser 1
    → browser-agent subagent → Python browser-use → Browser 2
    → browser-agent subagent → Python browser-use → Browser 3
  → Results synthesized back to you
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | (required) | Your OpenRouter API key |
| `BROWSER_AGENT_MODEL` | `google/gemini-2.0-flash-001` | LLM model for browser agents |
