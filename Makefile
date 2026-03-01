.PHONY: dev backend frontend install

dev: ## Start backend and frontend concurrently
	@make -j2 backend frontend

backend: ## Start backend on port 8000
	uv run uvicorn backend.server:app --port 8000 --reload

frontend: ## Start frontend on port 5173
	cd frontend && npm run dev

convex:
	cd frontend && npx convex dev

install: ## Install all dependencies
	uv sync
	cd frontend && npm install
