# Browser Agent Team Command Center — Agent Guide

AI agent reference for working in this codebase. Covers architecture, deployments, common commands, and service IDs.

---

## Architecture Overview

```
User
 └─ Frontend: SvelteKit + TailwindCSS (Vercel)
       └─ Backend: FastAPI + SQLAlchemy (Railway)
             └─ Database: Neon Postgres (serverless)
             └─ Browser Agents: browser-use + Playwright
             └─ LLM: OpenRouter / MiniMax / Anthropic
```

### Key Design Decisions
- **SSE (Server-Sent Events)** for streaming agent output to frontend — requires persistent connections, hence Railway not Vercel Functions
- **Async throughout** — SQLAlchemy async + asyncpg driver + FastAPI async endpoints
- **Cookie-based auth** — JWT in httpOnly cookies, not localStorage (CSRF-safe)
- **Alembic migrations** — run on startup before uvicorn (`alembic upgrade head && uvicorn ...`)

---

## Services

### Railway (Backend — FastAPI)

**Project:** `industrious-prosperity`
**Project ID:** `24187938-9190-42fd-932c-9030aeb80ff9`
**Service ID:** `bdcdfdcc-cb27-4ae2-a433-47a52d6a8c6b`
**Region:** `us-west1`
**Dashboard:** https://railway.com/project/24187938-9190-42fd-932c-9030aeb80ff9

**Deploy:**
```bash
# From repo root — link service first
railway service backend

# Deploy from backend/ directory
cd backend && railway up --detach

# Watch logs
railway logs --deployment

# Check deployment status
railway deployment list

# Set env vars
railway variables set KEY=value

# Open dashboard
railway open
```

**Important:** `railway.toml` is only read when deployed via GitHub integration. For local `railway up`, the Dockerfile and Procfile are used.

**Builder:** Dockerfile (`backend/Dockerfile`)
**Start command:** `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
**Health check:** `GET /health` → `{"status": "ok"}`

**Required env vars (set via `railway variables set`):**
```
DATABASE_URL         # postgresql+asyncpg://... (from Neon, use asyncpg driver)
SECRET_KEY           # min 32 chars, generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
GOOGLE_CLIENT_ID     # from Google Cloud Console → APIs & Services → Credentials
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI  # https://<vercel-frontend-url>/auth/callback/google
OPENROUTER_API_KEY   # from openrouter.ai/keys
ENVIRONMENT          # production
COOKIE_SECURE        # true (in production)
COOKIE_SAMESITE      # none (cross-origin frontend/backend)
FRONTEND_URL         # https://<vercel-frontend-url>
BROWSER_AGENT_MODEL  # default: google/gemini-2.0-flash-001
```

---

### Vercel (Frontend — SvelteKit)

**Adapter:** `@sveltejs/adapter-vercel` (already configured)
**Root directory:** `frontend/`

**Deploy:**
```bash
# Install Vercel CLI
npm i -g vercel

# From frontend/ directory
cd frontend && vercel

# Production deploy
cd frontend && vercel --prod

# Set env vars
vercel env add PUBLIC_API_URL production
```

**Required env vars:**
```
PUBLIC_API_URL    # https://<railway-backend-url>  (the Railway service public URL)
```

**Get Railway backend URL:**
```bash
railway domain  # generates a railway.app URL for the service
```

---

### Neon (Postgres Database)

**Neon** is a serverless Postgres provider. Connection strings use the pooler endpoint.

**Connection string format:**
```
postgresql+asyncpg://user:pass@<endpoint>-pooler.<region>.aws.neon.tech/dbname?ssl=require
```
⚠️ Must use `postgresql+asyncpg://` (not `postgresql://`) for SQLAlchemy async
⚠️ Use `ssl=require` (not `sslmode=require`) — asyncpg uses different parameter name
⚠️ Remove `channel_binding=require` if present — asyncpg doesn't support it

**Dashboard:** https://console.neon.tech

**Common operations:**
```bash
# Run migrations (from backend/)
alembic upgrade head

# Create new migration after model changes
alembic revision --autogenerate -m "describe change"

# Rollback one migration
alembic downgrade -1

# Show migration history
alembic history
```

---

## Backend Structure (`backend/`)

```
backend/
├── app/
│   ├── main.py          # FastAPI app, CORS, router registration
│   ├── config.py        # Pydantic settings (reads from env)
│   ├── database.py      # SQLAlchemy async engine + session
│   ├── models/          # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── session.py
│   │   ├── message.py
│   │   └── agent_run.py
│   ├── schemas/         # Pydantic request/response schemas
│   ├── routers/         # FastAPI route handlers
│   │   ├── auth.py      # Google OAuth + JWT cookie auth
│   │   ├── sessions.py  # Chat session management
│   │   └── messages.py  # Message CRUD + SSE streaming
│   └── services/
│       ├── auth.py      # JWT encode/decode, OAuth flow
│       ├── agent_runner.py  # browser-use agent execution
│       ├── orchestrator.py  # multi-agent coordination
│       └── sse.py       # Server-Sent Events helpers
├── alembic/             # Database migrations
├── alembic.ini
├── Dockerfile
├── Procfile
├── railway.toml
└── pyproject.toml       # Dependencies (fastapi, sqlalchemy, asyncpg, alembic, ...)
```

**Local dev:**
```bash
cd backend
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e .
cp env.example .env  # fill in values
alembic upgrade head
uvicorn app.main:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

---

## Frontend Structure (`frontend/`)

```
frontend/
├── src/
│   ├── app.html         # HTML shell
│   ├── app.css          # TailwindCSS global styles
│   ├── lib/             # Shared components + utilities
│   └── routes/          # SvelteKit file-based routing
├── svelte.config.js     # adapter-vercel configured
├── vite.config.ts
└── package.json
```

**Stack:** SvelteKit 2 + Svelte 5 + TailwindCSS 4 + TypeScript
**UI libs:** bits-ui, lucide-svelte, svelte-sonner (toasts), marked (markdown)

**Local dev:**
```bash
cd frontend
npm install
cp .env.example .env.local  # set PUBLIC_API_URL=http://localhost:8000
npm run dev
# Available at http://localhost:5173
```

---

## Browser Agents (`scripts/`)

**`browser_agent.py`** — runs a single browser-use agent task
```bash
# Headless (default)
python scripts/browser_agent.py --task "Go to example.com and get the title"

# Visible browser
python scripts/browser_agent.py --task "..." --visible

# Custom model
python scripts/browser_agent.py --task "..." --model minimax/MiniMax-M2.5
```

**`team.fish`** — Claude Code skill orchestrator for multi-agent browser teams

**Visual feedback options** (not yet wired up in browser_agent.py, but available):
```python
# GIF of all steps
agent = Agent(..., generate_gif="output/run.gif")

# Per-step screenshot callback
agent = Agent(..., register_new_step_callback=on_step)

# Access history after run
result.screenshot_paths()
result.action_names()
```

---

## Claude Code Skills

**`/browser-team`** — dispatch multiple browser agents in parallel
- Defined in `.claude/skills/browser-team/SKILL.md`
- Agent definition in `.claude/agents/browser-agent.md`

**Neon Postgres skill** — installed via `skills-lock.json`
- Source: `neondatabase/agent-skills`
- Provides Neon-aware SQL helpers

---

## Git / GitHub

**Repo:** https://github.com/trentshaines/browser-agent-team-command-center
**Branch:** `master` (main branch for PRs: `main` — not yet created)

**Push changes:**
```bash
git add <files>
git commit -m "message"
git push origin master
```

**Railway auto-deploy:** Not yet configured (GitHub App not authorized). Currently deploy manually with `railway up` from `backend/`.

---

## Common Gotchas

| Issue | Fix |
|-------|-----|
| `railway.toml` ignored on `railway up` | Only read via GitHub integration; use Dockerfile/Procfile for local deploys |
| `asyncpg` won't connect to Neon | Use `postgresql+asyncpg://` not `postgresql://`; use `ssl=require` not `sslmode=require` |
| CORS errors in browser | Check `FRONTEND_URL` env var matches exact Vercel URL (no trailing slash) |
| Auth cookie not sent cross-origin | Need `COOKIE_SAMESITE=none` + `COOKIE_SECURE=true` in production |
| SSE connection drops | Don't deploy backend to Vercel Functions — use Railway (persistent process) |
| Alembic can't find models | Run from `backend/` directory, not repo root |
