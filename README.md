# Customer Care Center Backend

Backend Flask app for the Customer Care Center project implementing Clean Architecture pattern.

## Quick start
- Copy `.env.example` to `.env` and adjust if needed
- `make venv` to create the local virtualenv
- `make migrate && make seed` to prepare sample data
- `make run` to serve the API on http://localhost:8000

Detailed workflows live in `BUILD_AND_RUN.md`; main API surface is documented in `APIs.md`.

## Project Structure

```
ccc-backend/
├── app.py                    # Application entry point
├── models.py                 # Compatibility shim (re-exports from src.infrastructure)
│
├── src/                      # Clean Architecture package
│   ├── domain/              # Business entities and DTOs
│   ├── application/         # Use cases and business services
│   ├── infrastructure/      # Database, external APIs, persistence
│   ├── presentation/        # HTTP layer (Flask blueprints)
│   └── settings/            # Configuration
│
├── scheduler/               # Scheduling engine (domain logic)
│   ├── engine/             # Core scheduling algorithms
│   └── tests/              # Unit tests for scheduler
│
├── rules/                   # Business rules (CSKH_2025 profile, etc.)
│
├── tests/                   # Integration tests for API endpoints
│
├── instance/               # Runtime data (SQLite database)
└── seed.py                 # Database seeding script
```

### Folder Roles

- **`src/`** - Clean Architecture implementation (new code follows this structure)
- **`scheduler/` & `rules/`** - Domain-specific business logic (scheduling algorithms and rules)
- **`tests/`** - Integration tests for HTTP APIs
- **`scheduler/tests/`** - Unit tests for scheduling engine
- **`instance/`** - SQLite database (gitignored, created at runtime)

See `AGENTS.md` for detailed architecture documentation.
