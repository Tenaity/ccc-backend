.PHONY: venv piptools install migrate seed run test format lint typecheck

venv:
	test -d .venv || python3 -m venv .venv

piptools:
	:

install: venv
	.venv/bin/pip install -r requirements.txt
	-.venv/bin/pip install -r requirements-dev.txt

migrate:
	.venv/bin/python -c "from models import init_db; init_db()"

seed:
	.venv/bin/python seed.py

run:
	.venv/bin/python app.py

test:
	PYTHONPATH=. .venv/bin/pytest -q

format:
	.venv/bin/black .
	.venv/bin/ruff . --fix
	.venv/bin/isort .

lint:
	.venv/bin/ruff .

typecheck:
	:
