# backend/rules.py

SHIFT_DEFS = ["CA1", "CA2", "K", "HC", "Đ", "P"]

# T2–T6: 1 K đỏ (PGD) + 1 K xanh (leader Tổng đài) + 2 CA1 (TD) + 1 CA2 đỏ (PGD) + 3 CA2 (TD) = CA2 tổng 4
# T7:    1 K xanh (leader TD) + 1 K đỏ (PGD) + 1 K trắng (bù công) + 2 CA1 (TD) + 2 CA2 (TD)
# CN:    1 K xanh (leader TD) + 1 CA1 (TD) + 1 CA2 (TD)
REQUIRED_DAY = {
    "WEEKDAY": {"K": 2, "CA1": 2, "CA2": 4},  # K=2 (đỏ+xanh), CA2=4 (1 đỏ PGD + 3 TD)
    "SAT":     {"K": 3, "CA1": 2, "CA2": 2},  # thêm K trắng bắt buộc
    "SUN":     {"K": 1, "CA1": 1, "CA2": 1},
    "HOLIDAY": {"CA1": 1, "CA2": 1},
}

# Ca đêm: để nguyên như hiện tại (1 TC đêm + NV đêm), sẽ đánh dấu trưởng ca đêm qua role=TC trên UI
REQUIRED_NIGHT = {
    "WEEKDAY": {"Đ": 5},  # 1 trong số này là TC (đánh dấu ở UI), tổng 5 người/đêm
    "SAT":     {"Đ": 4},
    "SUN":     {"Đ": 2},
    "HOLIDAY": {"Đ": 2},
}

CREDIT = {"CA1": 1, "CA2": 1, "HC": 1, "K": 1.25, "Đ": 1.5, "P": 0}
ALLOWED_DELTA = 0.9
