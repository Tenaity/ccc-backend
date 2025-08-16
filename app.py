# backend/app.py
import os
import calendar
import pathlib
from datetime import date
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import select, text

from models import init_db, SessionLocal, Staff, FixedAssignment, OffDay, Assignment, Holiday
from rules import SHIFT_DEFS
from scheduler import schedule_month as generate_schedule  # schedule_month(year, month, shuffle, seed, save[, fill_hc])
from scheduler.estimator import estimate_month

# Trỏ tới thư mục build của frontend (Vite) nếu đã build
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
DB_FILE = pathlib.Path(os.path.join(os.path.dirname(__file__), "cskh.db"))

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
        docs=[
            "/api/ping",
            "/api/shifts",
            "/api/staff",
            "/api/assignments?year=YYYY&month=MM",
            "/api/schedule/generate (POST)",
            "/api/admin/reset?mode=soft (POST)",
        ],
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
        return jsonify([
            {
                "day": r.day.isoformat(),
                "shift_code": r.shift_code,
                "staff_id": r.staff_id,
                "position": r.position,  # PGD | TD | K_WHITE | None
            }
            for r in rows
        ])

@app.post("/api/schedule/generate")
def gen():
    """Generate lịch cho (year, month).
    - save=false (default): preview, không lưu DB, trả planned[]
    - save=true: ghi DB từ đầu theo cùng tham số (shuffle/seed)
    - fill_hc (optional): tự động bù ca HC cho người thiếu công (v2)
    """
    payload = request.get_json(silent=True) or {}
    today = date.today()
    year = int(payload.get("year", today.year))
    month = int(payload.get("month", today.month))
    if month < 1 or month > 12:
        return jsonify({"error": "month must be 1..12"}), 400

    shuffle = bool(payload.get("shuffle", False))
    seed = payload.get("seed")
    try:
        seed = int(seed) if seed is not None else None
    except Exception:
        seed = None
    save_flag = bool(payload.get("save", False))
    fill_hc = bool(payload.get("fill_hc", False))  # 👈 NEW: nhận cờ từ frontend

    # Gọi scheduler; nếu code cũ chưa có tham số fill_hc thì fallback gọi không có tham số
    try:
        result = generate_schedule(year, month, shuffle=shuffle, seed=seed, save=save_flag, fill_hc=fill_hc)
    except TypeError:
        # Phiên bản cũ không nhận fill_hc → vẫn hoạt động bình thường (không auto-fill)
        result = generate_schedule(year, month, shuffle=shuffle, seed=seed, save=save_flag)

    # ✅ handle cả dict và (dict, status)
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict):
        body, status = result
        return jsonify(body), int(status)
    else:
        return jsonify(result)

# ====== Reset DB ======
@app.post("/api/admin/reset")
def admin_reset():
    """
    mode=soft: xoá Assignment (giữ Staff/Off/Fix/Holiday)
    mode=hard: xoá file sqlite và tạo lại schema
    """
    mode = (request.args.get("mode") or "soft").lower()
    if mode not in ("soft", "hard"):
        return {"error": "mode must be soft|hard"}, 400

    if mode == "hard":
        try:
            if DB_FILE.exists():
                DB_FILE.unlink()
            init_db()  # tạo lại schema rỗng
            return {"ok": True, "mode": "hard"}
        except Exception as e:
            return {"error": str(e)}, 500

    # soft reset
    with SessionLocal() as s:
        try:
            s.execute(text("DELETE FROM assignment"))
            s.commit()
            return {"ok": True, "mode": "soft"}
        except Exception as e:
            s.rollback()
            return {"error": str(e)}, 500

@app.get("/api/schedule/estimate")
def api_estimate():
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month
    return jsonify(estimate_month(y, m))

if __name__ == "__main__":
    # 5001 đúng theo log bạn đang dùng
    app.run(host="0.0.0.0", port=5001, debug=True)