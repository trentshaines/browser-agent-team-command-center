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

---

## Web App (FastAPI + SvelteKit)

A full-stack ChatGPT-style web interface for the browser agent team.

### Stack

- **Backend**: FastAPI, SQLAlchemy async, Neon Postgres, SSE streaming
- **Frontend**: SvelteKit 5, Tailwind CSS 4, Svelte runes
- **Auth**: Google OAuth + HttpOnly JWT cookies
- **Deploy**: Railway (backend) + Vercel (frontend)

### Local Development

#### Backend

```bash
cd backend

# 1. Create venv and install deps
uv venv --python 3.12
uv pip install -e .

# 2. Configure environment
cp env.example .env
# Edit .env — add DATABASE_URL, SECRET_KEY, GOOGLE_CLIENT_ID/SECRET, ANTHROPIC_API_KEY

# 3. Run migrations (first time)
.venv/bin/alembic upgrade head

# 4. Start server
.venv/bin/uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend

# 1. Install deps (already done)
npm install

# 2. Configure
cp env.example .env.local
# Edit .env.local — set VITE_API_URL=http://localhost:8000

# 3. Start dev server
npm run dev
```

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com) → Credentials → Create OAuth 2.0 Client ID
2. Add authorized redirect URI: `http://localhost:5173/auth/callback/google`
3. Copy Client ID and Secret to `backend/.env`

### Database Migration

```bash
cd backend
# After changing models, generate a new migration:
.venv/bin/alembic revision --autogenerate -m "describe change"
.venv/bin/alembic upgrade head
```

### Production Deployment

**Backend (Railway):**
- Set all env vars from `backend/env.example`
- Set `ENVIRONMENT=production`, `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none`
- Set `FRONTEND_URL=https://your-frontend.vercel.app`
- Set `GOOGLE_REDIRECT_URI=https://your-frontend.vercel.app/auth/callback/google`

**Frontend (Vercel):**
- Set `VITE_API_URL=https://your-backend.up.railway.app`
