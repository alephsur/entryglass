SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help setup dev-api dev-web validate-provider import-wallet test browser-test check format up down
help:
	@printf '%s\n' \
	  'make setup    Install local dependencies and create .env safely.' \
	  'make dev-api  Run the API; keep this terminal open.' \
	  'make dev-web  Run the web app in a second terminal.' \
	  'make validate-provider ARGS="..."  Dry-run or execute one bounded provider check.' \
	  'make import-wallet ARGS="..."  Dry-run or execute one budgeted wallet import.' \
	  'make test     Run Python and frontend API-client tests.' \
	  'make browser-test  Run the offline browser journey tests.' \
	  'make check    Run tests, Python lint, frontend typecheck, and build.' \
	  'make format   Format Python source and tests.' \
	  'make up       Start the Docker development environment.' \
	  'make down     Stop the Docker development environment.'

setup:
	bash scripts/setup.sh

dev-api:
	uv run --project backend uvicorn entryglass.main:app --reload --host 127.0.0.1 --port 8000

dev-web:
	npm --prefix frontend run dev

validate-provider:
	uv run --project backend entryglass-validate-nansen $(ARGS)

import-wallet:
	uv run --project backend entryglass-import-wallet $(ARGS)

test:
	uv run --project backend pytest backend/tests
	npm --prefix frontend test

browser-test:
	npm --prefix frontend run test:e2e

check: test
	uv run --project backend ruff check backend
	uv run --project backend ruff format --check backend
	npm --prefix frontend run typecheck
	npm --prefix frontend run build

format:
	uv run --project backend ruff format backend

up:
	@test -f .env || cp .env.example .env
	docker compose up --build

down:
	docker compose down
