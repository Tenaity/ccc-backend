# backend/seed.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Optional

from models import SessionLocal, Staff, init_db

# =========================
#  DANH SÁCH NHÂN SỰ
# =========================

TC_MAIN = [
    "Mai Công Tuấn",
    "Lê Thị Ngọc Linh",
    "Trần Văn Phong",
    "Nguyễn Phương Thanh",
    "Nguyễn Thị Thu Hương",  # TC
]

GDV = [
    # Ghi chú: Phạm Khánh Linh nghỉ sinh -> base_quota=0 để không tính công
    "Phạm Khánh Linh",
    "Nguyễn Thị Thu Thủy",
    "Trần Phương Ly",
    "Trần Thị Thùy Trang",
    "Nguyễn Mai Duy",
    "Vũ Thị Thu Hà",
    "Trương Thị Ngọc Huyền",
    "Nguyễn Nam Hoàng",
    "Nguyễn Minh Ngọc",
    "Nguyễn Quang Huy",
    "Nguyễn Thị Thúy",
    "Nguyễn Thị Hiền Hòa",
    "Trần Đức Anh",
    "Mai Phước Trí",
    "Phạm Thùy Trang",
    "Nguyễn Thị Kim Ngân",
    "Hoàng Thị Thu",
    "Ngô Nguyên Thành Hưng",
    "Hà Thu Đông",
]

HC = [
    "Nguyễn Thị Yến",
    "Nguyễn Thị Hà Uyên",
    "Phùng Duy Anh",
    "Lại Thanh Xuân",
    "Nguyễn Thị Mai Ly",
    "Nguyễn Phan Hương Giang",
    "Trần Thị Thùy Nhung",
    "Phạm Thị Thanh Trang",
    "Nhữ Thị Hoài Linh",
    "Hồ Hải Yến",
]

# =========================
#  RANK (GDV)
#  Rank 1: chuyên nghiệp | Rank 2: nghiệp dư
# =========================

RANK1_GDV = {
    "Nguyễn Thị Hiền Hòa",
    "Trần Đức Anh",
    "Nguyễn Thị Thúy",
    "Nguyễn Thị Kim Ngân",
    "Hoàng Thị Thu",
    "Hà Thu Đông",
    "Trần Thị Thùy Trang",
    "Phạm Thùy Trang",
    "Mai Phước Trí",
    "Trương Thị Ngọc Huyền",
}

RANK2_GDV = {
    "Nguyễn Thị Thu Thủy",
    "Nguyễn Quang Huy",
    "Nguyễn Minh Ngọc",
    "Trần Phương Ly",
    "Nguyễn Nam Hoàng",
    "Vũ Thị Thu Hà",
    "Nguyễn Mai Duy",
    "Phạm Khánh Linh",
    "Ngô Nguyên Thành Hưng",
}

# =========================
#  CODE hiển thị (tuỳ chọn)
# =========================
CODE_MAP: dict[str, int] = {
    # Ví dụ:
    # "Mai Công Tuấn": 1968,
    # "Lê Thị Ngọc Linh": 1994,
}

# =========================
#  Helper: thêm/ghi-đè tag [KEY:VALUE] trong notes
# =========================
TAG_RE = re.compile(r"\[(\w+):([^\]]+)\]")


def set_tag(notes: Optional[str], key: str, value: Optional[str]) -> Optional[str]:
    """
    - Nếu value=None -> xoá tag key khỏi notes.
    - Nếu value có -> ghi đè/đặt tag [key:value].
    """
    base = notes or ""

    # loại bỏ tag cùng key
    def _filter_same_key(txt: str) -> str:
        parts = []
        for m in TAG_RE.finditer(txt):
            k, v = m.group(1), m.group(2)
            if k.upper() != key.upper():
                parts.append(f"[{k}:{v}]")
        return "".join(parts)

    text_only = TAG_RE.sub("", base).strip()
    tags_only = _filter_same_key(base)

    if value is not None and str(value) != "":
        tags_only += f"[{key}:{value}]"

    final = (text_only + " " + tags_only).strip()
    return final or None


# =========================
#  Upsert
# =========================
def upsert_staff(
    full_name: str, role: str, *, can_night=True, base_quota=26.0, notes: Optional[str] = None
):
    with SessionLocal() as s:
        r = s.query(Staff).filter_by(full_name=full_name).first()
        if r:
            changed = False
            if r.role != role:
                r.role = role
                changed = True
            if bool(r.can_night) != bool(can_night):
                r.can_night = bool(can_night)
                changed = True
            old_notes = r.notes or ""
            new_notes = notes or old_notes
            if old_notes != new_notes:
                r.notes = new_notes
                changed = True
            if float(r.base_quota) != float(base_quota):
                r.base_quota = float(base_quota)
                changed = True
            if changed:
                s.add(r)
                s.commit()
        else:
            s.add(
                Staff(
                    full_name=full_name,
                    role=role,
                    can_night=bool(can_night),
                    base_quota=float(base_quota),
                    notes=notes,
                )
            )
            s.commit()


# =========================
#  Seed
# =========================
def run():
    init_db()

    # HC: không đêm, không rank
    for name in HC:
        notes = set_tag(None, "RANK", None)
        code = CODE_MAP.get(name)
        if code:
            notes = set_tag(notes, "CODE", str(code))
        upsert_staff(name, role="HC", can_night=False, base_quota=26.0, notes=notes)

    # TC: làm đêm được, GÁN RANK=1 để tham gia cân bằng ca (ngoài vai trò leader)
    for name in TC_MAIN:
        notes = set_tag(None, "RANK", "1")  # 👈 TC coi như rank1
        code = CODE_MAP.get(name)
        if code:
            notes = set_tag(notes, "CODE", str(code))
        upsert_staff(name, role="TC", can_night=True, notes=notes)

    # GDV: gán rank + code (nếu có)
    for name in GDV:
        rank: Optional[str] = None
        if name in RANK1_GDV:
            rank = "1"
        elif name in RANK2_GDV:
            rank = "2"

        if name == "Phạm Khánh Linh":
            base_quota = 0.0
            can_night = False
            note0 = "Nghỉ sinh"
        else:
            base_quota = 26.0
            can_night = True
            note0 = None

        notes = note0
        notes = set_tag(notes, "RANK", rank)
        code = CODE_MAP.get(name)
        if code:
            notes = set_tag(notes, "CODE", str(code))

        upsert_staff(name, role="GDV", can_night=can_night, base_quota=base_quota, notes=notes)


if __name__ == "__main__":
    run()
    print("Seeded staff with RANK tags (TC=rank1).")
