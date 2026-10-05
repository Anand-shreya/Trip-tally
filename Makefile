PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
NPM ?= npm

.PHONY: install dev backend frontend test seed seed-docker down

install:
	$(PYTHON) -m pip install -e "./backend[dev]"
	$(NPM) --prefix frontend ci

dev:
	docker compose up --build

backend:
	cd backend && ../$(PYTHON) -m uvicorn app.main:app --reload --port 8000 --no-access-log

frontend:
	$(NPM) --prefix frontend run dev

test:
	$(PYTHON) -m pytest backend/tests
	$(NPM) --prefix frontend test
	$(NPM) --prefix frontend run typecheck
	$(NPM) --prefix frontend run lint

seed:
	cd backend && ../$(PYTHON) -m app.seed

seed-docker:
	docker compose exec backend python -m app.seed

down:
	docker compose down
