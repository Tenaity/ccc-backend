# AGENTS

## Context
SQLite via SQLAlchemy; migrations via `make migrate`. Models: `Staff`, `Assignment`, `FixedAssignment` (with `position`), `OffDay`, `Holiday`, `MonthConfig`, `ShiftPlanDefaults`, **`Department`** (multi-department support), **`ShiftConfig`** (custom shifts per department). Scheduler engines live in `scheduler/engine/phase_night.py`, `phase_day.py`, `utils_rank.py`, `placements.py`, `core.py`. Profiles and rules are under `rules/*` (profile `CSKH_2025`). See [ARCHITECTURE](../docs/ARCHITECTURE.md).

## Phase 1 & 2: Multi-Department Support (COMPLETED)

## Phase 3: Schedule Reporting (IN PROGRESS)

- 2024-05-07: Added department-active listing plus schedule reporting APIs (`GET /api/departments?active=1`, `/api/schedule`, `/api/schedule/overview`) with unit tests for filtering, counts, and coverage summaries.


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
