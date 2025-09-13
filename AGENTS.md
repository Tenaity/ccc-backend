# AGENTS

## Context
SQLite via SQLAlchemy; migrations via `make migrate`. Models: `Staff`, `Assignment`, `FixedAssignment` (with `position`), `OffDay`, `Holiday`. Scheduler engines live in `scheduler/engine/phase_night.py`, `phase_day.py`, `utils_rank.py`, `placements.py`, `core.py`. Profiles and rules are under `rules/*` (profile `CSKH_2025`). See [ARCHITECTURE](../docs/ARCHITECTURE.md).

## Commands
- `make venv` – create virtualenv and install deps
- `make migrate` – generate migrations
- `make seed` – seed sample data
- `make run` – start dev server
- `make test` – run unit tests

## Guardrails
- Never place more than one night TC leader per day
- Respect fixed assignments and off days as hard constraints
- Balance GDV rank1/rank2 roughly 50/50; TC may join rank1 pool but not as extra night leaders
- Do not overwrite fixed placements; log `FIX_BLOCK` and surface via `/api/schedule/validate`

## Testing
- Add unit tests for each engine change (night/day phases, fairness, validation)
- `backend/tests/test_export_month_csv.py` must assert CSV has non‑empty rows

## APIs to know
`/api/fixed`, `/api/off` (CRUD), `/api/schedule/generate`, `/api/schedule/validate`, `/api/export/month.csv`

## Common pitfalls
Session lifetimes, quota leaks, duplicate leader guards
