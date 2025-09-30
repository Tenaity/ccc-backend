# Customer Care Center Backend

Backend Flask app for the Customer Care Center project split out from the monorepo.

## Quick start
- Copy `.env.example` to `.env` and adjust if needed
- `make venv` to create the local virtualenv
- `make migrate && make seed` to prepare sample data
- `make run` to serve the API on http://localhost:8000

Detailed workflows live in `BUILD_AND_RUN.md`; main API surface is documented in `APIs.md`.
