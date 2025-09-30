# Build and Run Guide

## Prerequisites
- Python 3.11
- `make`

## Environment
1. Copy `.env.example` to `.env`
2. Fill in the `DB_*` variables (host, port, name, user, password, timezone, optional options) or set `DATABASE_URL` directly if you prefer a custom connection string.

## Commands
All helper commands are provided via `Makefile`:

- `make venv` — create `.venv` in-place and install dev requirements from `requirements-dev.txt`
- `make migrate` — initialize the database schema
- `make seed` — load sample data for staff, fixed assignments and holidays
- `make run` — start the Flask development server on `http://0.0.0.0:8000`
- `make test` — execute the pytest suite

### Local workflow
```bash
make venv
cp .env.example .env
make migrate && make seed
make run
```

With the server running you can hit health endpoints:
```bash
curl http://localhost:8000/api/ping
```

See `APIs.md` for schedule, staff and export endpoints.

## Kết nối FE
- Thiết lập biến `VITE_API_BASE_URL=http://localhost:8000` khi chạy FE dev
- Hoặc bật proxy có sẵn trong repo frontend để chuyển tiếp `/api` tới backend

