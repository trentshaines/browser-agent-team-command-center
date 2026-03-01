# Browser Agent Team Command Center

## Architecture
```
SvelteKit (Vercel) → FastAPI + SQLAlchemy (Railway) → Neon Postgres
                                                     → browser-use + Playwright
                                                     → LLM: OpenRouter / MiniMax / Anthropic
```

- Auth: JWT in httpOnly cookies (Google OAuth)
- Streaming: SSE from backend to frontend
- Migrations: Alembic (runs before uvicorn on startup)
- Rate limiting: slowapi

## Infrastructure

### Railway — Backend (FastAPI)
- **Project ID:** `24187938-9190-42fd-932c-9030aeb80ff9`
- **Service ID:** `bdcdfdcc-cb27-4ae2-a433-47a52d6a8c6b`
- **Deploy:** `cd backend && railway up --detach`
- **Logs:** `railway logs --deployment`
- **Env vars:** `railway variables set KEY=value`

Required env vars: `DATABASE_URL`, `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `OPENROUTER_API_KEY`, `FRONTEND_URL`, `ENVIRONMENT`, `COOKIE_SECURE`, `COOKIE_SAMESITE`
Optional: `ANTHROPIC_API_KEY` (orchestrator fallback), `MINIMAX_API_KEY`

### Vercel — Frontend (SvelteKit)
- **Deploy:** `cd frontend && vercel --prod`
- Required env var: `PUBLIC_API_URL` = Railway backend URL (`railway domain`)

### Neon — Postgres
- **Dashboard:** https://console.neon.tech
- Connection string must use `postgresql+asyncpg://` with `ssl=require`
- Migrations: `cd backend && alembic upgrade head`

## Frontend Styling Rules

- **No pills.** Buttons, badges, tags, and chips must use `rounded-lg` (8px) or `rounded-xl` (12px) — never `rounded-full` on rectangular/clickable elements. `rounded-full` is reserved for truly circular elements (spinners, status dots, avatars).
- Modals and large containers use `rounded-2xl` or `rounded-[1.5rem]`.
- Chat bubbles and input fields use `rounded-2xl`.

## Key Paths

```
backend/
├── app/main.py          # FastAPI entry, routers: /auth /sessions
├── app/config.py        # All env var definitions
├── app/models/          # SQLAlchemy: user, session, message, agent_run
├── app/routers/         # auth.py, sessions.py, messages.py
├── app/services/        # auth, agent_runner, orchestrator, sse
├── app/limiter.py       # slowapi instance
├── alembic/             # migrations
└── Dockerfile + Procfile

frontend/
├── src/routes/          # SvelteKit pages
└── src/lib/             # shared components (Svelte 5, TailwindCSS 4)

scripts/
└── browser_agent.py     # run browser-use agent: --task --model --visible
```

## GitHub
**Repo:** https://github.com/trentshaines/browser-agent-team-command-center
**Branch:** `master`
