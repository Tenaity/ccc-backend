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
from scheduler import schedule_month as generate_schedule  
from scheduler.estimator import estimate_month
from scheduler.repo import load_staff, load_locked, load_fixed, load_holidays
from datetime import date, timedelta
from rules import get_profile
from scheduler.utils import ymd, month_last_day, day_kind
from scheduler.validate import validate_month

import csv
import io
import json
from flask import Response, stream_with_context

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


@app.get("/api/fixed")
def list_fixed_assignments():
    """List fixed assignments for a given month."""
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month

    if m < 1 or m > 12:
        return {"error": "month must be 1..12"}, 400

    last_day = calendar.monthrange(y, m)[1]
    start = date(y, m, 1)
    end = date(y, m, last_day)

    try:
        with SessionLocal() as s:
            rows = (
                s.query(FixedAssignment, Staff)
                .join(Staff, FixedAssignment.staff_id == Staff.id)
                .filter(FixedAssignment.day.between(start, end))
                .all()
            )
            out = [
                {
                    "id": fa.id,
                    "staff_id": fa.staff_id,
                    "staff_name": st.full_name,
                    "day": fa.day.isoformat(),
                    "shift_code": fa.shift_code,
                    "position": fa.position,
                }
                for fa, st in rows
            ]
            return jsonify(out)
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.post("/api/fixed")
def create_fixed_assignment():
    data = request.get_json(force=True) or {}
    staff_id = data.get("staff_id")
    day_str = data.get("day")
    shift_code = data.get("shift_code")
    position = data.get("position")

    if staff_id is None or day_str is None or shift_code is None:
        return {"error": "staff_id, day, shift_code required"}, 400

    try:
        staff_id = int(staff_id)
    except Exception:
        return {"error": "staff_id must be int"}, 400

    try:
        d = date.fromisoformat(day_str)
    except Exception:
        return {"error": "day must be YYYY-MM-DD"}, 400

    try:
        with SessionLocal() as s:
            staff = s.get(Staff, staff_id)
            if not staff:
                return {"error": "Staff not found"}, 404

            fa = FixedAssignment(
                staff_id=staff_id,
                day=d,
                shift_code=shift_code,
                position=position,
            )
            s.add(fa)
            s.commit()
            item = {
                "id": fa.id,
                "staff_id": fa.staff_id,
                "staff_name": staff.full_name,
                "day": fa.day.isoformat(),
                "shift_code": fa.shift_code,
                "position": fa.position,
            }
            return {"ok": True, "item": item}, 201
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.put("/api/fixed/<int:fix_id>")
def update_fixed_assignment(fix_id: int):
    data = request.get_json(force=True) or {}
    staff_id = data.get("staff_id")
    day_str = data.get("day")
    shift_code = data.get("shift_code")
    position = data.get("position")

    try:
        with SessionLocal() as s:
            fa = s.get(FixedAssignment, fix_id)
            if not fa:
                return {"error": "Not found"}, 404

            if staff_id is not None:
                try:
                    staff_id = int(staff_id)
                except Exception:
                    return {"error": "staff_id must be int"}, 400
                staff = s.get(Staff, staff_id)
                if not staff:
                    return {"error": "Staff not found"}, 404
                fa.staff_id = staff_id
            else:
                staff = fa.staff

            if day_str is not None:
                try:
                    fa.day = date.fromisoformat(day_str)
                except Exception:
                    return {"error": "day must be YYYY-MM-DD"}, 400

            if shift_code is not None:
                fa.shift_code = shift_code
            if position is not None:
                fa.position = position

            s.commit()
            item = {
                "id": fa.id,
                "staff_id": fa.staff_id,
                "staff_name": staff.full_name if staff else None,
                "day": fa.day.isoformat(),
                "shift_code": fa.shift_code,
                "position": fa.position,
            }
            return {"ok": True, "item": item}
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.delete("/api/fixed/<int:fix_id>")
def delete_fixed_assignment(fix_id: int):
    try:
        with SessionLocal() as s:
            fa = s.get(FixedAssignment, fix_id)
            if not fa:
                return {"error": "Not found"}, 404
            s.delete(fa)
            s.commit()
            return {"ok": True}
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.get("/api/off")
def list_off_days():
    """List off days for a given month (defaults to current)."""
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month

    if m < 1 or m > 12:
        return {"error": "month must be 1..12"}, 400

    last_day = calendar.monthrange(y, m)[1]
    start = date(y, m, 1)
    end = date(y, m, last_day)
    print(f"[API] off GET {y}-{m}", flush=True)

    try:
        with SessionLocal() as s:
            rows = (
                s.query(OffDay, Staff)
                .join(Staff, OffDay.staff_id == Staff.id)
                .filter(OffDay.day.between(start, end))
                .all()
            )
            out = [
                {
                    "id": od.id,
                    "staff_id": od.staff_id,
                    "staff_name": st.full_name,
                    "day": od.day.isoformat(),
                    "reason": od.reason,
                }
                for od, st in rows
            ]
            return jsonify(out)
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.post("/api/off")
def create_off_day():
    data = request.get_json(force=True) or {}
    staff_id = data.get("staff_id")
    day_str = data.get("day")
    reason = data.get("reason")

    if staff_id is None or day_str is None:
        return {"error": "staff_id and day required"}, 400

    try:
        staff_id = int(staff_id)
    except Exception:
        return {"error": "staff_id must be int"}, 400

    try:
        d = date.fromisoformat(day_str)
    except Exception:
        return {"error": "day must be YYYY-MM-DD"}, 400

    print(f"[API] off POST {staff_id} {day_str}", flush=True)

    try:
        with SessionLocal() as s:
            staff = s.get(Staff, staff_id)
            if not staff:
                return {"error": "Staff not found"}, 404

            existing = (
                s.query(OffDay)
                .filter(OffDay.staff_id == staff_id, OffDay.day == d)
                .first()
            )
            if existing:
                return {"id": existing.id, "ok": True}

            off = OffDay(staff_id=staff_id, day=d, reason=reason)
            s.add(off)
            s.commit()
            return {"id": off.id, "ok": True}, 201
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.delete("/api/off/<int:off_id>")
def delete_off_day(off_id: int):
    print(f"[API] off DELETE {off_id}", flush=True)
    try:
        with SessionLocal() as s:
            r = s.get(OffDay, off_id)
            if not r:
                return {"error": "Not found"}, 404
            s.delete(r)
            s.commit()
            return {"ok": True}
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


# Backwards‑compat aliases for old /api/offdays routes
@app.get("/api/offdays")
def list_off_days_alias():
    return list_off_days()


@app.post("/api/offdays")
def create_off_day_alias():
    return create_off_day()


@app.delete("/api/offdays/<int:off_id>")
def delete_off_day_alias(off_id: int):
    return delete_off_day(off_id)

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
                "position": r.position,  # PGD | TD | None
            }
            for r in rows
        ])


@app.get("/api/export_audit")
def export_audit():
    """Xuất danh sách phân ca kèm JSON metadata ra CSV để audit.

    Sử dụng ``csv.writer`` để đảm bảo trích dẫn đúng các ký tự đặc biệt
    trong cột JSON. Dữ liệu được stream từng hàng thông qua ``io.StringIO``
    nhằm tránh giữ toàn bộ nội dung trong bộ nhớ.
    """
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month

    if m < 1 or m > 12:
        return {"error": "month must be 1..12"}, 400

    last_day = calendar.monthrange(y, m)[1]
    start = date(y, m, 1)
    end = date(y, m, last_day)

    with SessionLocal() as s:
        rows = (
            s.query(Assignment)
            .filter(Assignment.day.between(start, end))
            .all()
        )

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["day", "shift_code", "staff_id", "meta"])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for r in rows:
            # JSON chứa nhiều key, bao gồm chuỗi có dấu phẩy để kiểm tra quoting
            meta = {
                "info": f"{r.shift_code},{r.staff_id}",
                "extra": "value",
            }
            writer.writerow(
                [
                    r.day.isoformat(),
                    r.shift_code,
                    r.staff_id,
                    json.dumps(meta, ensure_ascii=False),
                ]
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    headers = {
        "Content-Disposition": f"attachment; filename=audit-{y:04d}-{m:02d}.csv"
    }
    return Response(
        stream_with_context(generate()),
        content_type="text/csv; charset=utf-8",
        headers=headers,
    )


from api.export_month_csv import export_month_csv as _export_month_csv


@app.get("/api/export/month.csv")
def export_month_csv_endpoint():
    """Xuất lịch phân ca dạng CSV cho một tháng."""
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month
    if m < 1 or m > 12:
        return {"error": "month must be 1..12"}, 400
    return _export_month_csv(y, m)
    
@app.get("/api/rules/expected")
def rule_expected():
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month
    prof = get_profile()

    first = ymd(y, m, 1)
    last  = ymd(y, m, month_last_day(y, m))

    out = {}
    d = first
    # nạp holiday 1 lần
    holidays = load_holidays(SessionLocal())
    while d <= last:
        kind = day_kind(d, holidays)

        day = prof.expected_day_counts(kind)      # {"TD": {"K":..,"CA1":..,"CA2":..}, "PGD": {"K":..,"CA2":..}}
        night = prof.expected_night_counts(kind)  # {"TD": {"Đ": x}, "PGD": {"Đ": y}}  (từ NightDetail.to_engine_dict)

        td = day.get("TD", {})
        pgd = day.get("PGD", {})
        n_td = (night.get("TD", {}) or {})
        n_pgd = (night.get("PGD", {}) or {})

        out[d.day] = {
            "expectedTD": {
                "K":   int(td.get("K", 0)),
                "CA1": int(td.get("CA1", 0)),
                "CA2": int(td.get("CA2", 0)),
                "D":   int(n_td.get("Đ", 0)),   # gộp Đ (đêm @ TD)
            },
            "expectedPGD": {
                "K":   int(pgd.get("K", 0)),
                "CA2": int(pgd.get("CA2", 0)),
                "D":   int(n_pgd.get("Đ", 0)),  # gộp Đ (đêm @ PGD)
            },
        }
        d = d + timedelta(days=1)

    return jsonify({"ok": True, "perDayExpected": out})


@app.get("/api/schedule/validate")
def schedule_validate():
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month
    if m < 1 or m > 12:
        return jsonify({"ok": False, "error": "month must be 1..12"}), 400
    body = validate_month(y, m)
    return jsonify(body)

@app.post("/api/schedule/generate")
def gen():
    payload = request.get_json(silent=True) or {}
    from datetime import date as _date

    today = _date.today()
    year = int(payload.get("year", today.year))
    month = int(payload.get("month", today.month))
    if month < 1 or month > 12:
        return jsonify({"ok": False, "error": "month must be 1..12"}), 400

    shuffle = bool(payload.get("shuffle", False))
    seed = payload.get("seed")
    try:
        seed = int(seed) if seed is not None else None
    except Exception:
        seed = None
    save_flag = bool(payload.get("save", False))
    fill_hc = bool(payload.get("fill_hc", False))

    print("[API] generate begin", year, month, shuffle, seed, save_flag, fill_hc, flush=True)

    try:
        res = generate_schedule(year, month,
                                shuffle=shuffle,
                                seed=seed,
                                save=save_flag,
                                fill_hc=fill_hc)
        print("[API] generate end", type(res), flush=True)
        # engine may return a dict or (dict, status)
        if isinstance(res, tuple) and len(res) == 2 and isinstance(res[0], dict):
            body, status = res
            return jsonify(body), int(status)
        elif isinstance(res, dict):
            return jsonify(res)
        else:
            return jsonify({"ok": False, "error": "Internal error: bad return type"}), 500
    except Exception as e:
        # never bubble raw HTML traceback to the frontend
        return jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}), 500
    
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