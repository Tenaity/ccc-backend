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

## Development Guide

### Project Structure
```
src/
├── domain/              # Business entities & DTOs
├── application/         # Business logic services & use cases
├── infrastructure/      # Persistence, database, external providers
│   ├── persistence/
│   │   ├── models/      # SQLAlchemy ORM models (14 separate files)
│   │   ├── database.py  # Session management (PostgreSQL-only)
│   │   ├── query_helpers.py  # Unified database query patterns
│   │   └── serializers.py    # DTO serialization utilities
│   ├── providers/       # External API integrations (e.g., Nager.Date)
│   └── persistence.py   # Compatibility layer
└── presentation/
    └── api/             # Flask blueprints for HTTP endpoints
        ├── error_handlers.py  # Unified error handling
        ├── chatbot_data.py
        ├── department.py
        ├── holidays.py
        └── [other endpoints]
application/
├── validators.py        # Unified validation functions
└── [service files]

scheduler/              # Schedule generation engine
tests/                  # Unit tests
```

### Code Quality & Consolidation (Phase 6)

Four utility modules created to reduce code duplication by 80%:

**1. Query Helpers** (`src/infrastructure/persistence/query_helpers.py`)
```python
from src.infrastructure.persistence.query_helpers import QueryHelper, date_range_between

# Example usage in services
helper = QueryHelper(Staff)
staff = helper.get_or_404(session, staff_id)  # Returns Staff or raises NotFoundError
all_staff = helper.find_all(session, Staff.is_active == True)
count = helper.count(session)
```

**2. Validators** (`src/application/validators.py`)
```python
from src.application.validators import validate_date_iso, validate_integer, normalize_code

# Example usage
try:
    date_val = validate_date_iso("2025-10-15", "birth_date")
    month = validate_integer(month_input, "month", min_val=1, max_val=12)
    code = normalize_code(user_code)  # Strips and uppercase
except ValidationError as e:
    # Handle validation error
    pass
```

**3. Error Handlers** (`src/presentation/api/error_handlers.py`)
```python
from src.presentation.api.error_handlers import handle_errors

# Example: Replace 5-10 lines of try-except with decorator
@api_bp.get("/<id>")
@handle_errors()
def get_item(id):
    item = service.get_item(id)  # Raises NotFoundError if not found
    return jsonify(serialize(item))

# Decorator automatically:
# - Catches ValidationError → returns (400, error message)
# - Catches NotFoundError → returns (404, error message)
# - Catches ConflictError → returns (409, error message)
# - Catches Exception → returns (500, error message)
```

**4. Serializers** (`src/infrastructure/persistence/serializers.py`)
```python
from src.infrastructure.persistence.serializers import BaseSerializer, FieldMapping

# Example: Consistent DTO serialization
field_map = FieldMapping.create() \
    .add("raw_text", "rawText") \
    .add("major_section", "majorSection") \
    .build()

result = BaseSerializer.to_dict(dto, field_map)

# Paginated response
paginated = BaseSerializer.paginated(items, page, page_size, total, field_map)
```

### Running Tests
```bash
# All tests
make test

# Single test file
.venv/bin/python -m pytest tests/test_chatbot_data_api.py -v

# With coverage
.venv/bin/python -m pytest --cov=src tests/
```

### Database Configuration

**PostgreSQL Setup** (Production):
```bash
# Set environment variables
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=sweb
export DB_USER=postgres
export DB_PASSWORD=your_password
export DB_TIMEZONE=Asia/Ho_Chi_Minh

# Or use DATABASE_URL
export DATABASE_URL="postgresql://user:password@localhost:5432/sweb"

make migrate
make seed
make run
```

**SQLite Setup** (Development/Testing):
```bash
# Already configured for testing
# Tests create temporary SQLite databases automatically
make test
```

## Kết nối FE
- Thiết lập biến `VITE_API_BASE_URL=http://localhost:8000` khi chạy FE dev
- Hoặc bật proxy có sẵn trong repo frontend để chuyển tiếp `/api` tới backend

## Troubleshooting

**Issue**: ImportError when running tests
**Solution**: Make sure you've called `make venv` and `.venv/bin/python -m pytest` (not just `pytest`)

**Issue**: Database connection refused
**Solution**: Check PostgreSQL is running and environment variables are set correctly

**Issue**: Test isolation fails (duplicate constraints)
**Solution**: Tests should automatically create fresh SQLite databases. If issues persist, check `conftest.py` and ensure `reset_engine()` is called

**Issue**: Model import errors
**Solution**: Check that `src/infrastructure/persistence/models/__init__.py` exports all required models

