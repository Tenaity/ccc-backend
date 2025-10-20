# API Overview

All routes are rooted at `http://localhost:8000`. Unless noted otherwise responses are JSON.

## Health
- `GET /api/ping` — simple health probe

## Reference data
- `GET /api/shifts` — list shift definitions
- `GET /api/rules/expected` — expected staffing counts for the selected month (`year`, `month` query params)

## Staff
- `GET /api/staff` — list staff records (supports `department_id`, `role`, `q` filters)
- `POST /api/staff` — create staff (`full_name`, `role`, `can_night`, `base_quota`, `notes`)
- `DELETE /api/staff/{id}` — remove staff

## Fixed assignments
- `GET /api/fixed` — list fixed assignments for the month (`year`, `month` query params)
- `POST /api/fixed` — create fixed assignment (`staff_id`, `day`, `shift_code`, optional `position`)
- `PUT /api/fixed/{id}` — update fixed assignment
- `DELETE /api/fixed/{id}` — delete fixed assignment

## Off days
- `GET /api/off` — list off days (`year`, `month` query params)
- `POST /api/off` — create off day (`staff_id`, `day`, optional `reason`)
- `DELETE /api/off/{id}` — delete off day
- Legacy aliases also exist under `/api/offdays`

## Holidays
- `GET /api/holidays` — list holidays (`year` required, optional `month` filter)
- `POST /api/holidays` — create holiday (`day`, `name`, optional `kind`, `official`, `source`)
- `PUT /api/holidays/{id}` — update holiday metadata/day
- `DELETE /api/holidays/{id}` — delete holiday
- `POST /api/holidays/import?year=YYYY&source=nager` — import official VN holidays from Nager.Date

- `GET /api/departments` — list departments (use `active=1` for active subset)
- `GET /api/schedule` — list assignments for the month (`year`, `month`, optional `department_id`)
- `GET /api/schedule/overview` — aggregated coverage by department (`year`, `month`)
- `GET /api/assignments` — list generated assignments for the month (`year`, `month`)
- `GET /api/schedule/validate` — validate current schedule data for the month
- `GET /api/schedule/estimate` — estimator for staffing expectations
- `POST /api/schedule/generate` — run the scheduler (`year`, `month`, optional `shuffle`, `seed`, `save`, `fill_hc`)

## Admin
- `POST /api/admin/reset?mode=soft|hard` — soft delete assignments or recreate the SQLite database

## Export
- `GET /api/export_audit` — CSV stream of assignments with JSON metadata (accepts `year`, `month`)
- `GET /api/export/month.csv` — CSV stream of the monthly schedule (accepts `year`, `month`)

## Chatbot Data Management
- `GET /api/chatbot-data` — list chatbot data records (paginated, supports `page`, `page_size`)
- `GET /api/chatbot-data/<id>` — get single chatbot data record
- `POST /api/chatbot-data` — create chatbot data record (31+ fields supported)
- `PUT /api/chatbot-data/<id>` — update chatbot data record
- `DELETE /api/chatbot-data/<id>` — delete chatbot data record

## Department Management
- `GET /api/departments` — list departments (supports `active=1` filter)
- `POST /api/departments` — create department (`name`, `code`, optional `color`, `icon`, `description`)
- `PUT /api/departments/<id>` — update department
- `DELETE /api/departments/<id>` — delete department (validates no staff assigned)

## Shift Configuration
- `GET /api/shift-configs` — list shift configs (supports `department_id` filter)
- `POST /api/shift-configs` — create shift config (`name`, `code`, `start_time`, `end_time`, `department_id`)
- `PUT /api/shift-configs/<id>` — update shift config
- `DELETE /api/shift-configs/<id>` — delete shift config

## Staff Preferences
- `GET /api/staff/<id>/preferences` — get staff work-life balance preferences
- `PUT /api/staff/<id>/preferences` — update staff preferences (`preferred_shifts`, `unavailable_days`, `max_consecutive_days`, `preferred_days_off`)

## Metrics & Reports
- `GET /api/metrics/staff-workload` — staff workload metrics
- `GET /api/metrics/department-compare` — department comparison metrics
- `GET /api/metrics/attendance` — attendance tracking (stub)
- `GET /api/metrics/cost` — labor cost calculation (uses `LABOR_COST_PER_HOUR` env var)
- `GET /api/reports/staff-workload.csv` — staff workload CSV export
- `GET /api/reports/department-compare.csv` — department comparison CSV
- `GET /api/reports/schedule-month.csv` — monthly schedule CSV export

## Architecture & Consolidation

### Backend Architecture (Phase 5+)
Clean Architecture pattern with 4 layers:
- **Domain**: Pure business entities (`src/domain/`)
- **Application**: Business logic services (`src/application/`)
- **Infrastructure**: Persistence & providers (`src/infrastructure/`)
- **Presentation**: HTTP endpoints (`src/presentation/api/`)

### Code Quality Consolidation (Phase 6)
Created 4 reusable utility modules (645 total lines) to eliminate 530-770 lines of duplicate code:

**Query Helpers** (`src/infrastructure/persistence/query_helpers.py` - 145 lines)
- Generic `QueryHelper` class with `get_or_404()`, `exists_or_error()`, `find_all()`, `count()`
- Saves: 80-120 lines when applied to 7 service files

**Validators** (`src/application/validators.py` - 155 lines)
- Validation functions: `validate_date_iso()`, `validate_month_range()`, `validate_integer()`, etc.
- Saves: 100-150 lines when applied to services

**Error Handlers** (`src/presentation/api/error_handlers.py` - 165 lines)
- Decorator `@handle_errors` for unified exception handling
- Maps: ValidationError→400, NotFoundError→404, ConflictError→409
- Saves: 150-200 lines when applied to 9 API endpoint files

**Serializers** (`src/infrastructure/persistence/serializers.py` - 180 lines)
- `BaseSerializer` class with `to_dict()`, `to_list()`, `paginated()`, `filtered_dict()`
- `FieldMapping` builder for consistent field name mappings
- Saves: 50-100 lines when applied to services

