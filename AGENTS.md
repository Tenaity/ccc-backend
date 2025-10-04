# AGENTS

## Context
SQLite via SQLAlchemy; migrations via `make migrate`. Models: `Staff`, `Assignment`, `FixedAssignment` (with `position`), `OffDay`, `Holiday`, `MonthConfig`, `ShiftPlanDefaults`, **`Department`** (multi-department support), **`ShiftConfig`** (custom shifts per department). Scheduler engines live in `scheduler/engine/phase_night.py`, `phase_day.py`, `utils_rank.py`, `placements.py`, `core.py`. Profiles and rules are under `rules/*` (profile `CSKH_2025`). See [ARCHITECTURE](../docs/ARCHITECTURE.md).

## Phase 1 & 2: Multi-Department Support (COMPLETED)

## Phase 3: Schedule Reporting (COMPLETED)

- 2024-05-07: Added department-active listing plus schedule reporting APIs (`GET /api/departments?active=1`, `/api/schedule`, `/api/schedule/overview`) with unit tests for filtering, counts, and coverage summaries.

## Phase 4: Staff Preferences & Work-Life Balance (COMPLETED)

### Overview
Implemented staff scheduling preferences to improve work-life balance and staff satisfaction. The scheduler now considers individual preferences when assigning shifts.

### Backend Changes

#### New Model (models.py)
**StaffPreferences Model**:
```python
- staff_id: Integer (PK, FK -> Staff)
- preferred_shifts: JSON - Array of preferred shift codes (e.g., ["K", "CA1"])
- unavailable_days: JSON - Array of ISO dates staff cannot work (e.g., ["2025-10-15"])
- max_consecutive_days: Integer - Max working days before rest (default 6)
- preferred_days_off: JSON - Array of weekday numbers 0-6 (e.g., [5, 6] for Sat/Sun)
- notes: String - Additional preference notes
```

#### New Scheduler Components

**PreferencesAdapter** (`scheduler/preferences_adapter.py`):
- Loads and caches staff preferences from database
- Methods:
  * `is_preferred_shift(staff_id, shift_code)` - Check if shift is preferred
  * `is_unavailable(staff_id, day)` - Hard constraint check
  * `is_preferred_day_off(staff_id, day)` - Soft preference check
  * `calculate_preference_weight(...)` - Calculate match score
  * `filter_available_staff(...)` - Remove unavailable staff
  * `sort_by_preference(...)` - Sort by preference weight

**Preferences Helper** (`scheduler/engine/preferences_helper.py`):
- Integration helpers for phase_day and phase_night
- Functions:
  * `filter_by_preferences(ctx, candidates, day, shift_code)` - Filter & sort
  * `filter_queue_by_preferences(...)` - Queue filtering with preferences
  * `get_preferred_staff_for_shift(...)` - Get staff who prefer specific shift
  * `should_skip_due_to_preferences(...)` - Check hard constraints

**Context Integration** (`scheduler/engine/core.py`):
- Added `preferences: Optional[PreferencesAdapter]` to Context dataclass
- Initialized in `build_context()` function
- Available as `ctx.preferences` throughout engine

#### Preference Weight Scoring
- Unavailable (hard): -1000 (blocked)
- Preferred shift: +10
- Not on preferred day off: +2
- On preferred day off: -5
- Below max consecutive: +3
- Above max consecutive: -8

#### New APIs (app.py)
- `GET /api/staff/<id>/preferences` - Get staff preferences (lines 991-1018)
- `PUT /api/staff/<id>/preferences` - Update preferences (lines 1021-1095)

### Frontend Changes

#### New Page
**StaffPreferences.tsx** (`/staff-preferences`):
- Premium glass-morphism UI
- Staff selector dropdown with department info
- 3 tabbed sections:
  1. **Shift Preferences**: Day/Night shift preferences with priority
  2. **Day Off Preferences**: Weekday selection (Mon-Sun)
  3. **Constraints**: Max consecutive days, min rest days
- Save/Reset functionality

#### Routing Updates
- Added to Schedule submenu in `routes.tsx`
- Route: `/staff-preferences`
- Icon: UserCog
- Lazy-loaded in `App.tsx`

### Integration Documentation
See `scheduler/PREFERENCES_INTEGRATION.md` for:
- Architecture overview
- Usage examples
- Integration patterns for phase_day/phase_night
- Testing guidelines
- Future enhancement ideas

### How It Works

1. **Configuration Phase**: Staff set preferences via `/staff-preferences` UI
2. **Schedule Generation**:
   - Preferences loaded into `ctx.preferences` adapter
   - Each staff assignment checks:
     * Hard constraint: Unavailable days (blocks assignment)
     * Soft constraints: Preferred shifts, days off, consecutive limits
   - Weight score calculated for each candidate
   - Higher-weighted candidates preferred (but quota/coverage priority)
3. **Result**: Better work-life balance while maintaining coverage

### Usage Pattern
```python
# In phase_day or phase_night:
from scheduler.engine.preferences_helper import filter_by_preferences

candidates = filter_by_preferences(ctx, all_staff, day, shift_code)
if candidates:
    best_match = candidates[0]
    ctx.do_place(day, best_match.id, shift_code, position)
```

### Testing Status
- ✅ Models and API endpoints created
- ✅ PreferencesAdapter implemented with caching
- ✅ Helper functions for engine integration
- ✅ Context integration completed
- ✅ Frontend UI completed
- ✅ Documentation created
- ⚠️ Phase integration optional (helpers ready for use)

### Notes
- Preferences are **soft constraints** (except unavailable days)
- Quota and coverage requirements take priority
- Staff should understand preferences are considered but not guaranteed
- Future: Track preference satisfaction metrics


### Overview
Added department management and custom shift configuration to support multiple departments with different shift requirements.

### Backend Changes

#### New Models (models.py)
1. **Department Model**:
   ```python
   - id: Integer (PK)
   - name: String (unique) - Department name
   - code: String (unique) - Short code (e.g., "CC", "IT")
   - color: String - Hex color for UI (#3b82f6)
   - icon: String - Lucide icon name (e.g., "Headphones")
   - description: String (optional) - Department description
   - is_active: Boolean - Active status
   - settings: JSON - Department-specific settings:
     * working_hours: {start: "08:00", end: "17:00"}
     * weekend_policy: "sat_off" | "sat_work_am" | "sat_work"
     * max_hours_per_month: 208
     * min_staff_per_shift: 2
   ```

2. **ShiftConfig Model**:
   ```python
   - id: Integer (PK)
   - department_id: Integer (FK -> Department)
   - name: String - Shift name (e.g., "Ca Sáng")
   - code: String - Short code for matrix display (e.g., "CS")
   - start_time: String - "HH:MM" format
   - end_time: String - "HH:MM" format
   - color: String - Pastel color for UI
   - icon: String - Lucide icon (Sun, Moon, Coffee, etc.)
   - is_active: Boolean
   - display_order: Integer - For sorting
   - rules: JSON - Shift-specific rules (optional)
   - Unique constraint: (department_id, code)
   ```

3. **Staff Model Update**:
   ```python
   - department_id: Integer (FK -> Department, nullable)
   - department: Relationship to Department
   ```

#### New APIs (app.py)

**Department Management:**
- `GET /api/departments` - List all departments with staff_count & shift_count
- `POST /api/departments` - Create department
- `PUT /api/departments/<id>` - Update department
- `DELETE /api/departments/<id>` - Delete (validates no staff exists)

**Shift Configuration:**
- `GET /api/shift-configs?department_id=<id>` - List shifts (filterable)
- `POST /api/shift-configs` - Create shift config
- `PUT /api/shift-configs/<id>` - Update shift config
- `DELETE /api/shift-configs/<id>` - Delete shift config

**Staff API Update:**
- `GET /api/staff?department_id=<id>` - Now supports department filtering
- Returns `department_id` and `department_name` in response

#### Migration (init_db)
- Auto-migration adds `department_id` column to `staff` table (nullable for backward compatibility)
- Creates `department` and `shift_config` tables

### Frontend Changes

#### New Pages
1. **DepartmentManagement.tsx** (`/departments`):
   - Premium Apple-inspired UI with glass-morphism
   - 3 stats cards: Total Departments, Total Staff, Custom Shifts
   - Department cards grid with hover effects
   - Create/Edit dialog with:
     * Icon picker (8 options: Building2, Users, Headphones, Briefcase, etc.)
     * Color picker (8 colors)
     * Name, code, description inputs
   - Delete validation (prevents deletion if staff exists)

2. **ShiftConfig.tsx** (`/shift-config`):
   - Department selector dropdown
   - 3 stats cards: Total Shifts, Active Department, Departments count
   - Shift cards grid showing:
     * Shift name, code, start/end times
     * Color-coded badges
     * Icon display
   - Create/Edit dialog with:
     * Shift icon picker (8 icons: Sun, Moon, Coffee, Clock, etc.)
     * Pastel color picker (10 colors)
     * Time pickers for start/end
     * Name & code inputs

#### New Components
- `PageHeader.tsx` - Reusable page header with gradient title
- `Textarea.tsx` - Standard textarea component

#### Routing Updates
- Added 2 sub-items under Schedule menu in `routes.tsx`:
  * Departments (Building2 icon)
  * Shift Config (Clock icon)
- Lazy-loaded in `App.tsx`

### Sample Data Created
```bash
# Departments
1. Customer Care (CC) - Blue (#3b82f6) - Headphones icon
2. IT Support (IT) - Green (#10b981) - Monitor icon

# Shifts for Customer Care
1. Ca Sáng (CS) - 08:00-12:00 - Blue (#60a5fa) - Sun icon
2. Ca Chiều (CC) - 13:00-17:00 - Amber (#fbbf24) - Coffee icon
3. Ca Đêm (CĐ) - 18:00-22:00 - Violet (#a78bfa) - Moon icon
```

### Design System
- **Glass-morphism**: backdrop-blur-3xl with white/95 opacity
- **Colors**: Blue-Pink gradient theme consistent across app
- **Icons**: Lucide React icons
- **Animations**: 300ms ease-ios transitions
- **Shadows**: iOS-style shadow-glass layering

### Testing Status
- ✅ Backend APIs tested with curl (CRUD operations work)
- ✅ Frontend compiles without errors
- ✅ Sample data seeded successfully
- ✅ All imports resolved (PageHeader, Textarea, GlassPanel)

## Phase 5: Clean Architecture Migration (COMPLETED ✅)

### Overview
Migrated codebase from monolithic `app.py` to Clean Architecture pattern with clear separation of concerns.

### Architecture Layers

**1. Domain Layer** (`src/domain/`):
- Pure business entities and DTOs
- No dependencies on infrastructure or frameworks
- Files: `holiday.py`

**2. Application Layer** (`src/application/`):
- Business logic services
- Use cases and workflows
- Services:
  * `holiday_service.py` - Holiday management and import
  * `metrics_service.py` - Workload metrics and department comparison
  * `export_service.py` - CSV export for schedule data
  * `shift_defaults_service.py` - Shift plan defaults management
  * `month_config_service.py` - Month configuration management

**3. Infrastructure Layer** (`src/infrastructure/`):
- Persistence:
  * `database.py` - SQLAlchemy engine and session management with caching
  * `models.py` - ORM models and database migrations
- Providers:
  * `holiday_provider.py` - External holiday API integration (Nager.Date)

**4. Presentation Layer** (`src/presentation/api/`):
- HTTP endpoints using Flask blueprints
- Request/response handling
- Blueprints:
  * `holidays.py` - Holiday CRUD and import endpoints
  * `metrics.py` - Metrics dashboards (workload, cost, attendance)
  * `reports.py` - CSV export endpoints
  * `schedule.py` - Schedule generation and management
  * `shift_defaults.py` - Shift defaults configuration
  * `month_config.py` - Month configuration

### Key Improvements

**Database Session Management**:
- Factory pattern with `get_session_factory()` for dependency injection
- `reset_engine()` for test isolation (clears global caching)
- Proper session lifecycle with context managers

**Test Isolation**:
- Centralized `conftest.py` fixture with database reset
- Each test gets fresh SQLite database
- `importlib.reload()` pattern to pick up new DB_URL
- **All 43 tests passing (100%)**

**Migration Path**:
- Deleted legacy files: `api/` folder, `legacy_app.py`
- All business logic moved to application services
- Backwards-compatible database migrations in `models.init_db()`
- Constants moved from `api/constants.py` to `application/metrics_service.py`

### Migrated Components

**Metrics & Reports**:
- `api/metrics.py` → `src/application/metrics_service.py`
  * `load_staff_workload()` - Per-staff hours and night hours
  * `load_department_comparison()` - Department workload with overtime (respects dept settings)
  * Uses department-specific `max_hours_per_month` from settings

- `api/export_month_csv.py` → `src/application/export_service.py`
  * `export_month_csv()` - Monthly schedule CSV with streaming
  * Columns: Ngày, Staff, Role, Rank, Shift, Position, Công

**Endpoints**:
- `GET /api/metrics/staff-workload` - Staff workload with totals
- `GET /api/metrics/department-compare` - Department comparison
- `GET /api/metrics/attendance` - Attendance stub (future impl)
- `GET /api/metrics/cost` - Labor cost (uses LABOR_COST_PER_HOUR env var)
- `GET /api/reports/staff-workload.csv` - Staff workload CSV export
- `GET /api/reports/department-compare.csv` - Department comparison CSV
- `GET /api/reports/schedule-month.csv` - Monthly schedule CSV

### Database Migration Logic

**Holiday Table Evolution** (`models.init_db()`):
1. Rename `holidays` → `holiday` (if legacy table exists)
2. Rename column `day` → `date`
3. Add columns: `kind`, `official`, `source`
4. Create unique index on `date`
5. Idempotent - safe to run multiple times

**Position Column** (FixedAssignment):
1. Auto-add `position` column if missing
2. Enables PGD/TD tracking in fixed assignments

### Testing Strategy

**Test Fixture Pattern** (`tests/conftest.py`):
```python
@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_URL", f"sqlite:///{tmp_path}/test.db")
    db_module.reset_engine()
    importlib.reload(models)
    models.init_db()
    importlib.reload(app_module)
    return SimpleNamespace(
        client=app_module.app.test_client(),
        models=models,
        module=app_module,
    )
```

**Key Lessons**:
- Always call `reset_engine()` before reloading models in tests
- Module-level engine assignment needs reload to pick up new DB_URL
- Use `db_module.get_engine()` directly when module globals might be stale
- Test migration logic with both individual and full suite runs

### Status
- ✅ Clean Architecture structure implemented
- ✅ All business logic migrated to services
- ✅ Database session management refactored
- ✅ Test isolation fixed with proper engine reset
- ✅ Legacy files deleted (api/, legacy_app.py)
- ✅ All 43 tests passing
- ✅ Database migrations working correctly

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

## Scheduler engine cheat sheet
- `schedule_month` phases: (0) scatter weekday HC, (1) night assignments with single TC leader cap, (2) day shifts with rank fairness, (3) optional HC rebalance, then validation for exactly one K@TD per day via `validate_one_day_leader`.
- Demand profiles live in `rules/CSKH_2025`; keep `expectedByDay` aligned whenever you tweak shift requirements so frontend advanced stats remain accurate.
- Always call `reset_trackers()` before generating; stale credit state causes quota leaks and duplicate leaders.
- Engine responses should populate `perDayLeaders`, conflict lists, and credit deltas—frontend glass UI surfaces these for operators.

## Testing
- Add unit tests for each engine change (night/day phases, fairness, validation)
- Exercise both happy-path & quota edge cases (locked staff, fixed Đ@TD, fairness 7-day window)
- `backend/tests/test_export_month_csv.py` must assert CSV has non‑empty rows

## Metrics & Reports
- Dashboard metrics live under `/api/metrics/*` (staff workload, department compare, attendance stub, cost).
- CSV exports for metrics are exposed at `/api/reports/*.csv`; reuse helpers to keep headers consistent.
- `LABOR_COST_PER_HOUR` controls cost metric; defaults to 0 when unset. Update docs if you change this contract.

## Schedule Generation Flow

### Pre-requisites (Configuration Phase)
Before generating schedules, the system requires configuration for each month:

1. **Month Configuration** (`MonthConfig`):
   - `weekend_policy`: Defines weekends (sat_sun, sun_only, none)
   - `extra_workdays`: Array of YYYY-MM-DD dates (work on normally off days)
   - `extra_offdays`: Array of YYYY-MM-DD dates (off on normally work days)
   - `working_days_override`: Manual override for auto-calculated working days
   - Endpoint: `PUT /api/month-config` (year, month required)

2. **Shift Defaults** (`ShiftPlanDefaults`):
   - `day_shifts`: Number of day shifts per person
   - `night_shifts`: Number of night shifts per person
   - `leader_shifts`: Number of leader shifts required
   - `pgd_shifts`: Number of PGD shifts required
   - Endpoint: `PUT /api/shift-defaults` (year, month required)

3. **Holidays** (Optional but recommended):
   - Import Vietnamese holidays: `POST /api/holidays/import?year=2025&source=nager`
   - Manual entry: `POST /api/holidays` with day, name
   - Used to calculate working days and shift requirements

### Generation Flow
```
POST /api/schedule/generate?year=2025&month=10
├─ Validate: MonthConfig exists? → 400 if missing
├─ Validate: ShiftPlanDefaults exists? → 400 if missing
├─ Load: staff, fixed assignments, off days, holidays
├─ Phase 0: Scatter weekday HC assignments (non-holiday weekdays)
├─ Phase 1: Night shifts (Đ)
│   ├─ Enforce: Max 1 TC leader per night
│   ├─ Balance: GDV rank1 vs rank2 (~50/50)
│   └─ Fairness window: 7 days
├─ Phase 2: Day shifts (K, CA1, CA2)
│   ├─ Round-robin TC leader assignment
│   ├─ Balance: GDV rank1 vs rank2 (~50/50)
│   └─ Fairness window: 7 days
├─ Phase 3: Optional HC rebalance
├─ Validate: Exactly one K@TD per day
└─ Return: assignments, perDayLeaders, conflicts, credit deltas
```

### Response Structure
```json
{
  "ok": true,
  "planned": [
    {
      "day": "2025-10-01",
      "staff_id": 11,
      "shift_code": "K",
      "position": "TD"
    }
  ],
  "perDayLeaders": {
    "2025-10-01": { "day": 11, "night": 12 }
  },
  "conflicts": [],
  "creditDeltas": { "11": 1, "12": 1 }
}
```

## APIs to know
- **Config**: `/api/month-config` (GET/PUT), `/api/shift-defaults` (GET/PUT)
- **Holidays**: `/api/holidays` (GET/POST/DELETE), `/api/holidays/import` (POST)
- **Assignments**: `/api/fixed` (CRUD), `/api/off` (CRUD)
- **Schedule**: `/api/schedule/generate` (POST), `/api/schedule/validate` (GET), `/api/schedule/estimate` (GET)
- **Export**: `/api/export/month.csv` (GET)

## Common pitfalls
- Missing `MonthConfig` or `ShiftPlanDefaults` → 400 error on generate
- Not calling `reset_trackers()` before generate → quota leaks
- Session lifetimes, duplicate leader guards
- Fixed assignments conflicting with off days → validation errors
