.PHONY: venv migrate seed run test dev-api format lint

venv:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -U pip
	. .venv/bin/activate && pip install -r requirements.txt
	- . .venv/bin/activate && pip install -r requirements-dev.txt

migrate:
	. .venv/bin/activate && python3 -c "from models import init_db; init_db()"

seed:
	. .venv/bin/activate && python3 seed.py

run:
        . .venv/bin/activate && FLASK_ENV=development python3 app.py

test:
        . .venv/bin/activate && PYTHONPATH=. pytest -q

format:
        . .venv/bin/activate && black . && ruff --fix .

lint:
        . .venv/bin/activate && ruff .

dev-api:
	. .venv/bin/activate && FLASK_ENV=development python3 app.py
