from datetime import date

from scheduler.placements import Planned
from scheduler.validators import validate_one_day_leader

def test_validate_one_day_leader_exactly_one():
    first = date(2025,8,1); last = date(2025,8,3)
    planned = [
        Planned(day=date(2025, 8, 1), staff_id=1, shift_code="K", position="TD"),
        # day 2: 0 leader
        Planned(day=date(2025, 8, 3), staff_id=2, shift_code="K", position="TD"),
        Planned(day=date(2025, 8, 3), staff_id=3, shift_code="K", position="TD"),
    ]
    bad = validate_one_day_leader(planned, first, last)
    # ngày 2 và 3 phải bị bắt
    assert any(d.isoformat().endswith("-02") and c == 0 for d, c in bad)
    assert any(d.isoformat().endswith("-03") and c == 2 for d, c in bad)
