"""Application services for shift configuration management."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from src.utils.logging import instrument_service
from src.domain.exceptions import NotFoundError, ValidationError
from src.infrastructure.persistence import database as persistence_db
from src.infrastructure.persistence.models import (
    Department,
    ShiftConfig,
)


@instrument_service
class ShiftConfigService:
    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    def _session(self):
        factory = self._session_factory or persistence_db.get_session_factory()
        return factory()

    def list_shift_configs(self, *, department_id: Optional[int] = None) -> List[dict]:
        with self._session() as session:
            query = select(ShiftConfig).order_by(
                ShiftConfig.department_id,
                ShiftConfig.display_order,
                ShiftConfig.name,
            )
            if department_id:
                query = query.where(ShiftConfig.department_id == department_id)
            rows = session.execute(query).scalars().all()
            return [self._serialize(row) for row in rows]

    def create_shift_config(self, data: dict) -> dict:
        dept_id = data.get("department_id")
        name = (data.get("name") or "").strip()
        code = (data.get("code") or "").strip().upper()

        if not dept_id:
            raise ValidationError("department_id is required")
        if not name:
            raise ValidationError("Shift name is required")
        if not code:
            raise ValidationError("Shift code is required")

        with self._session() as session:
            dept = session.get(Department, dept_id)
            if not dept:
                raise NotFoundError("Department not found")

            existing = session.execute(
                select(ShiftConfig).where(
                    (ShiftConfig.department_id == dept_id)
                    & (ShiftConfig.code == code)
                )
            ).scalar_one_or_none()
            if existing:
                raise ValidationError(
                    f"Shift code '{code}' already exists in this department"
                )

            row = ShiftConfig(
                department_id=dept_id,
                name=name,
                code=code,
                start_time=data.get("start_time", "08:00"),
                end_time=data.get("end_time", "17:00"),
                color=data.get("color", "#60a5fa"),
                icon=data.get("icon", "Sun"),
                is_active=data.get("is_active", True),
                display_order=data.get("display_order", 0),
                rules=data.get("rules", {}),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._serialize(row)

    def update_shift_config(self, shift_id: int, data: dict) -> dict:
        with self._session() as session:
            shift = session.get(ShiftConfig, shift_id)
            if not shift:
                raise NotFoundError("Shift configuration not found")

            if "name" in data:
                shift.name = (data["name"] or "").strip()
            if "code" in data:
                shift.code = (data["code"] or "").strip().upper()
            if "start_time" in data:
                shift.start_time = data["start_time"]
            if "end_time" in data:
                shift.end_time = data["end_time"]
            if "color" in data:
                shift.color = data["color"]
            if "icon" in data:
                shift.icon = data["icon"]
            if "is_active" in data:
                shift.is_active = bool(data["is_active"])
            if "display_order" in data:
                shift.display_order = data["display_order"]
            if "rules" in data:
                shift.rules = data["rules"]

            session.commit()
            session.refresh(shift)
            return self._serialize(shift)

    def delete_shift_config(self, shift_id: int) -> None:
        with self._session() as session:
            shift = session.get(ShiftConfig, shift_id)
            if not shift:
                raise NotFoundError("Shift configuration not found")
            session.delete(shift)
            session.commit()

    @staticmethod
    def _serialize(row: ShiftConfig) -> dict:
        return {
            "id": row.id,
            "department_id": row.department_id,
            "department_name": row.department.name if row.department else None,
            "name": row.name,
            "code": row.code,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "color": row.color,
            "icon": row.icon,
            "is_active": row.is_active,
            "display_order": row.display_order,
            "rules": row.rules,
        }


__all__ = ["ShiftConfigService"]
