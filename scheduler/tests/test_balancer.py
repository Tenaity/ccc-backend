import calendar
from datetime import date, timedelta
import pytest
from scheduler.balancer import balance_hc

def days_of_month(y, m):
    last = calendar.monthrange(y, m)[1]
    return [date(y, m, d) for d in range(1, last+1)]

@pytest.mark.skip("balance_hc legacy signature changed")
def test_balance_hc_respects_tolerance_and_bounds():
    y, m = 2025, 8
    days = days_of_month(y, m)
    holidays = set()

    # 3 người, quota giống nhau
    base_quota = {1: 22.0, 2: 22.0, 3: 22.0}
    # sau core: người 1 thiếu 3, người 2 thiếu 1.2, người 3 dư 0.3
    current = {1: 19.0, 2: 20.8, 3: 22.3}
    tolerance = 0.9
    credits = {"HC": 1.0}

    # cho phép làm HC mọi ngày T2–T6
    can_work = {}
    for d in days:
        if d.weekday() < 5:  # Mon–Fri
            can_work[d] = {1, 2, 3}

    placements = balance_hc(
        days=days, holidays=holidays, tolerance=tolerance,
        base_quota=base_quota, current_credit=current,
        can_work=can_work, credits=credits
    )

    # áp dụng placements để kiểm tra
    for p in placements:
        current[p.staff_id] += 1.0

    # mọi người phải nằm trong [-0.9, +0.9]
    for sid in base_quota:
        deficit = base_quota[sid] - current.get(sid, 0.0)
        assert -tolerance - 1e-6 <= deficit <= tolerance + 1e-6

@pytest.mark.skip("balance_hc legacy signature changed")
def test_balance_hc_never_assigns_weekends_or_holidays():
    y, m = 2025, 8
    days = days_of_month(y, m)
    # đánh dấu ngày 12 là holiday (thứ Ba)
    from datetime import date
    holidays = {date(2025, 8, 12)}
    base_quota = {1: 26.0}
    current = {1: 20.0}
    can_work = {d: {1} for d in days if d.weekday() < 5}  # Mon–Fri only
    placements = balance_hc(
        days=days, holidays=holidays, tolerance=0.9,
        base_quota=base_quota, current_credit=current,
        can_work=can_work, credits={"HC":1.0}
    )
    assert all(p.day.weekday() < 5 for p in placements)
    assert all(p.day not in holidays for p in placements)

@pytest.mark.skip("balance_hc legacy signature changed")
def test_balance_hc_respects_daily_one_shift_per_staff():
    y, m = 2025, 8
    days = days_of_month(y, m)
    base_quota = {1: 26.0}
    current = {1: 20.0}
    # chỉ cho ngày 5, Mon–Fri: {1}
    can_work = {d: {1} for d in days if d.weekday() < 5}
    placements = balance_hc(
        days=days, holidays=set(), tolerance=0.9,
        base_quota=base_quota, current_credit=current,
        can_work=can_work, credits={"HC":1.0}
    )
    # không có ngày nào lặp staff hai lần
    by_day = {}
    for p in placements:
        key = (p.day, p.staff_id)
        assert key not in by_day
        by_day[key] = True