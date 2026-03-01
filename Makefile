.PHONY: dev backend frontend install

dev: ## Start backend and frontend concurrently
	@make -j2 backend frontend

backend: ## Start backend on port 8000
	cd backend && uv run uvicorn app.main:app --port 8000 --reload

frontend: ## Start frontend on port 5173
	cd frontend && npm run dev

install: ## Install all dependencies
	cd backend && uv sync
	cd frontend && npm install
