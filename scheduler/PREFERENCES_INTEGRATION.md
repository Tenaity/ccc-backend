# Preferences Integration Guide

## Overview

Staff preferences have been integrated into the scheduler engine to improve work-life balance and staff satisfaction. The system now considers:

- **Preferred shifts** - Staff can indicate which shift types they prefer
- **Unavailable days** - Hard constraints for days staff cannot work
- **Preferred days off** - Soft preferences for day-off scheduling
- **Max consecutive days** - Limit on continuous working days

## Architecture

### Components

1. **PreferencesAdapter** (`scheduler/preferences_adapter.py`)
   - Loads and caches staff preferences from database
   - Provides methods to check preferences and calculate weights
   - Filters unavailable staff

2. **Preferences Helper** (`scheduler/engine/preferences_helper.py`)
   - Helper functions for use in phase_day and phase_night
   - Filters and sorts candidates based on preferences
   - Provides convenient wrappers for common operations

3. **Context Integration** (`scheduler/engine/core.py`)
   - PreferencesAdapter is initialized in `build_context()`
   - Available as `ctx.preferences` throughout the engine

## Usage Examples

### Example 1: Filter Staff by Preferences

```python
from scheduler.engine.preferences_helper import filter_by_preferences

# In phase_day or phase_night
candidates = [staff1, staff2, staff3]
day = date(2025, 10, 15)
shift_code = "CA1"

# Filter and sort by preferences
sorted_candidates = filter_by_preferences(
    ctx, candidates, day, shift_code
)

# sorted_candidates now contains staff sorted by preference match
# (unavailable staff are removed)
```

### Example 2: Check if Staff is Unavailable

```python
from scheduler.engine.preferences_helper import should_skip_due_to_preferences

# Check before assigning
if should_skip_due_to_preferences(ctx, staff_id, day):
    continue  # Skip this staff member
```

### Example 3: Get Preferred Staff for a Shift

```python
from scheduler.engine.preferences_helper import get_preferred_staff_for_shift

# Get staff who prefer night shifts
preferred_for_night = get_preferred_staff_for_shift(
    ctx,
    all_staff=ctx.GDV,
    shift_code="Đ",  # Night shift
    day=day,
    locked=locked_today,
    used=used
)

# Try to assign preferred staff first
for staff in preferred_for_night:
    ctx.do_place(day, staff.id, "Đ", "TD")
    break
```

### Example 4: Filter Queue with Preferences

```python
from scheduler.engine.preferences_helper import filter_queue_by_preferences

# Get best candidates from queue
candidates = filter_queue_by_preferences(
    ctx,
    queue=ctx.q_gdv1,
    day=day,
    shift_code="K",
    locked=locked_today,
    used=used,
    max_results=5  # Get top 5 matches
)

# Assign first available
if candidates:
    staff = candidates[0]
    ctx.do_place(day, staff.id, "K", "TD")
```

## Integration Points

### Phase Day (`phase_day.py`)

Replace direct queue access with preference-aware filtering:

**Before:**
```python
while ctx.q_tc_day:
    leader = ctx.q_tc_day.popleft()
    if leader.id in usable:
        ctx.do_place(d, leader.id, "K", "TD")
        break
    ctx.q_tc_day.append(leader)
```

**After:**
```python
from scheduler.engine.preferences_helper import filter_queue_by_preferences

candidates = filter_queue_by_preferences(
    ctx, ctx.q_tc_day, d, "K", locked_today, used, max_results=1
)
if candidates:
    leader = candidates[0]
    ctx.do_place(d, leader.id, "K", "TD")
    # Rotate queue manually if needed
```

### Phase Night (`phase_night.py`)

Similar pattern for night shift assignments.

## Preference Weight Calculation

The system calculates a weight score for each staff-shift-day combination:

- **Unavailable (hard constraint)**: -1000 (effectively blocked)
- **Preferred shift**: +10
- **Not on preferred day off**: +2
- **On preferred day off**: -5
- **Below max consecutive days**: +3
- **Above max consecutive days**: -8

Higher weight = better match with staff preferences.

## API Endpoints

Staff can manage their preferences via:

- `GET /api/staff/<staff_id>/preferences` - Get preferences
- `PUT /api/staff/<staff_id>/preferences` - Update preferences

See `app.py` lines 991-1095 for implementation.

## Database Schema

```python
class StaffPreferences(Base):
    staff_id: int  # FK to staff
    preferred_shifts: List[str]  # e.g., ["K", "CA1"]
    unavailable_days: List[str]  # e.g., ["2025-10-15"]
    max_consecutive_days: int  # default 6
    preferred_days_off: List[int]  # e.g., [5, 6] for Sat, Sun
    notes: str
```

## Testing

To test preferences integration:

1. Set staff preferences via API or directly in database
2. Run scheduler: `POST /api/schedule/generate`
3. Check assignments respect preferences
4. Verify unavailable days are honored (hard constraint)
5. Verify preferred shifts are prioritized (soft constraint)

## Future Enhancements

1. **Preference priority levels** - Allow staff to set importance (1-10)
2. **Team preferences** - Group preferences for shifts
3. **Preference violation tracking** - Report when preferences can't be met
4. **Learning from history** - Adjust weights based on past success
5. **Conflict resolution UI** - Visual tool for resolving preference conflicts

## Notes

- Preferences are **soft constraints** (except unavailable days which are hard)
- The scheduler will try to honor preferences but quota and coverage take priority
- Staff should be informed that preferences are considered but not guaranteed
- Monitor preference satisfaction rate over time to tune the system
