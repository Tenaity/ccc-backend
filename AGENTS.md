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
- Never place more than one night TC leader per day (phase_night enforces via `placed_leader`)
- Respect fixed assignments and off days as hard constraints
- Balance GDV rank1/rank2 roughly 50/50; TC may join rank1 pool but not as extra night leaders
- Fairness window is 7 days (`FairnessWindow`); keep `[FAIR]` logs in sync if you adjust rank math
- Do not overwrite fixed placements; log `FIX_BLOCK` and surface via `/api/schedule/validate`
- Night rescue (`ALLOW_OVERCAP_NIGHT_LEADER`) should stay emergency-only; never use it to bypass quota bugs

## Testing
- Add unit tests for each engine change (night/day phases, fairness, validation)
- Exercise both happy-path & quota edge cases (locked staff, fixed Đ@TD, fairness 7-day window)
- `backend/tests/test_export_month_csv.py` must assert CSV has non‑empty rows

## APIs to know
`/api/fixed`, `/api/off` (CRUD), `/api/schedule/generate`, `/api/schedule/validate`, `/api/export/month.csv`

## Common pitfalls
Session lifetimes, quota leaks, duplicate leader guards
