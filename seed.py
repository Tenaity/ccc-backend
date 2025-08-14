# backend/seed.py
# -*- coding: utf-8 -*-
from models import init_db, SessionLocal, Staff

# ===== DANH SÁCH THEO ẢNH =====

TC_MAIN = [
    "Mai Công Tuấn",
    "Lê Thị Ngọc Linh",
    "Trần Văn Phong",
    "Nguyễn Phương Thanh",
    "Nguyễn Thị Thu Hương",  # thêm TC chính
]

# Không còn TC phụ/backup theo sheet mới -> để trống
TC_SUB = []
TC_BACKUP = []

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
    "Nguyễn Thị Thu Hương",  # GDV trùng tên với TC? Nếu khác người, giữ lại; nếu cùng người, có thể xoá dòng này.
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

# ===== Helpers =====
def upsert_staff(full_name, role, *, can_night=True, base_quota=26.0, notes=None):
    with SessionLocal() as s:
        r = s.query(Staff).filter_by(full_name=full_name).first()
        if r:
            changed = False
            if r.role != role:
                r.role = role; changed = True
            if bool(r.can_night) != bool(can_night):
                r.can_night = bool(can_night); changed = True
            if (r.notes or "") != (notes or ""):
                r.notes = notes; changed = True
            if float(r.base_quota) != float(base_quota):
                r.base_quota = float(base_quota); changed = True
            if changed:
                s.add(r); s.commit()
        else:
            s.add(Staff(
                full_name=full_name,
                role=role,
                can_night=bool(can_night),
                base_quota=float(base_quota),
                notes=notes,
            ))
            s.commit()

def run():
    init_db()

    # Hành chính: auto HC, không làm đêm
    for name in HC:
        upsert_staff(name, role="HC", can_night=False, base_quota=26.0, notes="Hành chính")

    # Trưởng ca (làm đêm được)
    for name in TC_MAIN:
        upsert_staff(name, role="TC", can_night=True, notes="TC chính")
    for name in TC_SUB:
        upsert_staff(name, role="TC", can_night=True, notes="TC phụ")
    for name in TC_BACKUP:
        upsert_staff(name, role="TC", can_night=False, notes="TC backup")

    # GDV
    for name in GDV:
        if name == "Phạm Khánh Linh":
            # Nghỉ sinh: không xếp, không tính công
            upsert_staff(name, role="GDV", can_night=False, base_quota=0, notes="Nghỉ sinh")
        else:
            upsert_staff(name, role="GDV", can_night=True)

if __name__ == "__main__":
    run()
    print("Seeded staff.")
