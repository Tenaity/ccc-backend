# backend/rules/ranks.py
RANK1: set[int] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}  # id từ sheet cột 1..10
RANK2: set[int] = {11, 12, 13, 14, 15, 16, 17, 18, 19}


def rank_of(staff_id: int) -> int:
    if staff_id in RANK1:
        return 1
    if staff_id in RANK2:
        return 2
    return 2  # default newbie nếu chưa liệt kê
