# Browser Agent Team Command Center

A web app to spin up browser agent swarms and manage them visually. Dispatch multiple AI-controlled browsers in parallel, watch them work in real-time, and review results — all from a single interface.

**Stack:** SvelteKit · FastAPI · Convex · browser-use · Bedrock (Claude)

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node.js 18+
- A [Convex](https://www.convex.dev/) project
- AWS Bedrock access with Claude models enabled
- A [browser-use](https://browser-use.com/) API key

## Setup

### 1. Install dependencies

```bash
make install
# or manually:
uv sync
cd frontend && npm install
```

### 2. Configure environment variables

**Backend** — create `backend/.env`:

```env
BROWSER_USE_API_KEY=your-browser-use-api-key
AWS_BEARER_TOKEN_BEDROCK=your-aws-bearer-token
AWS_REGION=us-east-1
CONVEX_URL=https://your-deployment.convex.cloud
```

**Frontend** — create `frontend/.env.local`:

```env
PUBLIC_CONVEX_URL=https://your-deployment.convex.cloud
CONVEX_DEPLOYMENT=your-deployment-name
```

**Frontend (dev)** — create `frontend/.env.development.local`:

```env
VITE_API_URL=http://localhost:8000
PUBLIC_CONVEX_URL=https://your-deployment.convex.cloud
```

### 3. Start everything

Run all three services (each in its own terminal):

```bash
make backend   # FastAPI on :8000
make frontend  # SvelteKit on :5173
make convex    # Convex dev server
```

Or start backend + frontend together:

```bash
make dev
```

## Environment Variables

| Variable | Where | Description |
|---|---|---|
| `BROWSER_USE_API_KEY` | backend | API key for browser-use cloud browsers |
| `AWS_BEARER_TOKEN_BEDROCK` | backend | Bearer token for AWS Bedrock API |
| `AWS_REGION` | backend | AWS region (default: `us-east-1`) |
| `CONVEX_URL` | backend | Convex deployment URL (for file storage queries) |
| `PUBLIC_CONVEX_URL` | frontend | Convex deployment URL (for client-side queries) |
| `CONVEX_DEPLOYMENT` | frontend | Convex deployment name |
| `VITE_API_URL` | frontend | Backend URL (e.g. `http://localhost:8000`) |
