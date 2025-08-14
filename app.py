# backend/app.py
import os
import calendar
from datetime import date
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import select
from models import init_db, SessionLocal, Staff, FixedAssignment, OffDay, Assignment, Holiday
from rules import SHIFT_DEFS
from scheduler import schedule_month as generate_schedule

# Trỏ tới thư mục build của frontend (Vite) nếu đã build
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

app = Flask(
    __name__,
    static_folder=FRONTEND_DIST if os.path.isdir(FRONTEND_DIST) else None,
    static_url_path="/",
)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Khởi tạo DB (tạo bảng nếu chưa có)
init_db()


# ---------- Root / SPA ----------
@app.get("/")
def root():
    """Nếu đã build frontend thì trả index.html, còn không trả JSON giới thiệu API."""
    if app.static_folder and os.path.isfile(os.path.join(app.static_folder, "index.html")):
        return send_from_directory(app.static_folder, "index.html")
    return jsonify(
        service="customer-care-center API",
        ok=True,
        docs=["/api/ping", "/api/shifts", "/api/staff", "/api/assignments?year=YYYY&month=MM"],
    )


@app.route("/<path:path>")
def spa_assets(path: str):
    """Phục vụ static assets và fallback cho route SPA."""
    if app.static_folder:
        p = os.path.join(app.static_folder, path)
        if os.path.isfile(p):
            return send_from_directory(app.static_folder, path)
        index_html = os.path.join(app.static_folder, "index.html")
        if os.path.isfile(index_html):
            return send_from_directory(app.static_folder, "index.html")
    return {"error": "Not Found"}, 404


# ---------- API ----------
@app.get("/api/ping")
def ping():
    return {"ok": True}


@app.get("/api/shifts")
def shifts():
    return jsonify(SHIFT_DEFS)


@app.get("/api/staff")
def list_staff():
    with SessionLocal() as s:
        rows = s.execute(select(Staff)).scalars().all()
        return jsonify(
            [
                {
                    "id": r.id,
                    "full_name": r.full_name,
                    "role": r.role,
                    "can_night": r.can_night,
                    "base_quota": r.base_quota,
                    "notes": r.notes,
                }
                for r in rows
            ]
        )


@app.post("/api/staff")
def add_staff():
    data = request.get_json(force=True)
    with SessionLocal() as s:
        r = Staff(
            full_name=data["full_name"],
            role=data.get("role", "GDV"),
            can_night=bool(data.get("can_night", True)),
            base_quota=float(data.get("base_quota", 26.0)),
            notes=data.get("notes"),
        )
        s.add(r)
        s.commit()
        return {"id": r.id}


@app.delete("/api/staff/<int:staff_id>")
def del_staff(staff_id: int):
    with SessionLocal() as s:
        r = s.get(Staff, staff_id)
        if not r:
            return {"error": "Not found"}, 404
        s.delete(r)
        s.commit()
        return {"ok": True}


@app.get("/api/assignments")
def list_assignments():
    """Trả danh sách phân ca theo tháng (mặc định tháng hiện tại nếu thiếu params)."""
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month

    if m < 1 or m > 12:
        return {"error": "month must be 1..12"}, 400

    last_day = calendar.monthrange(y, m)[1]
    start = date(y, m, 1)
    end = date(y, m, last_day)

    with SessionLocal() as s:
        rows = s.query(Assignment).filter(Assignment.day.between(start, end)).all()
        # >>> ĐÃ THÊM 'position' Ở ĐÂY <<<
        return jsonify([
            {
                "day": r.day.isoformat(),
                "shift_code": r.shift_code,
                "staff_id": r.staff_id,
                "position": r.position,  # ✅ thêm
                # "position": getattr(r, "position", None),  # PGD | TD | K_WHITE | None
            }
            for r in rows
        ])


@app.post("/api/schedule/generate")
def gen():
    """Gọi hàm sinh lịch cho (year, month). Nếu thiếu thì dùng tháng hiện tại."""
    payload = request.get_json(silent=True) or {}
    today = date.today()
    year = int(payload.get("year", today.year))
    month = int(payload.get("month", today.month))
    if month < 1 or month > 12:
        return {"error": "month must be 1..12"}, 400

    result = generate_schedule(year, month)
    return jsonify(result)


@app.post("/api/fixed")
def add_fixed():
    data = request.get_json(force=True)
    with SessionLocal() as s:
        r = FixedAssignment(
            staff_id=int(data["staff_id"]),
            day=date.fromisoformat(data["day"]),
            shift_code=data["shift_code"],
        )
        s.add(r)
        s.commit()
        return {"id": r.id}


@app.post("/api/off")
def add_off():
    data = request.get_json(force=True)
    with SessionLocal() as s:
        r = OffDay(
            staff_id=int(data["staff_id"]),
            day=date.fromisoformat(data["day"]),
            reason=data.get("reason"),
        )
        s.add(r)
        s.commit()
        return {"id": r.id}


@app.get("/api/holidays")
def list_holidays():
    with SessionLocal() as s:
        rows = s.query(Holiday).order_by(Holiday.day.asc()).all()
        return jsonify([{"id": r.id, "day": r.day.isoformat(), "name": r.name} for r in rows])


@app.post("/api/holidays")
def add_holiday():
    data = request.get_json(force=True)
    with SessionLocal() as s:
        r = Holiday(day=date.fromisoformat(data["day"]), name=data.get("name"))
        s.add(r); s.commit()
        return {"id": r.id}


@app.delete("/api/holidays/<int:hid>")
def del_holiday(hid):
    with SessionLocal() as s:
        r = s.get(Holiday, hid)
        if not r:
            return {"error": "Not found"}, 404
        s.delete(r); s.commit()
        return {"ok": True}


if __name__ == "__main__":
    # 5001 đúng theo log bạn đang dùng
    app.run(host="0.0.0.0", port=5001, debug=True)
