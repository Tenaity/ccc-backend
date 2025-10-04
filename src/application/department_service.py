"""Application services for managing departments."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select

from src.domain.department import DepartmentDTO
from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.infrastructure.persistence import database as persistence_db
from src.infrastructure.persistence.models import (
    Department,
    ShiftConfig,
    Staff,
)


class DepartmentService:
    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    def _session(self):
        factory = self._session_factory or persistence_db.get_session_factory()
        return factory()

    def list_departments(self, *, active: Optional[bool] = None) -> List[DepartmentDTO]:
        with self._session() as session:
            query = select(Department).order_by(Department.name)
            if active is not None:
                query = query.where(Department.is_active.is_(active))

            rows = session.execute(query).scalars().all()
            payload: List[DepartmentDTO] = []
            for row in rows:
                payload.append(
                    DepartmentDTO(
                        id=row.id,
                        name=row.name,
                        code=row.code,
                        color=row.color,
                        icon=row.icon,
                        description=row.description,
                        is_active=row.is_active,
                        settings=row.settings,
                        staff_count=len(row.staff) if row.staff else 0,
                        shift_count=len(row.shifts) if row.shifts else 0,
                    )
                )

            if active is not None:
                for dto in payload:
                    dto.staff_count = None
                    dto.shift_count = None

            return payload

    def create_department(self, *, name: str, code: str, **extra) -> DepartmentDTO:
        name = (name or "").strip()
        code = (code or "").strip().upper()
        if not name:
            raise ValidationError("Department name is required")
        if not code:
            raise ValidationError("Department code is required")

        with self._session() as session:
            existing = session.execute(
                select(Department).where(
                    (Department.name == name) | (Department.code == code)
                )
            ).scalar_one_or_none()
            if existing:
                raise ConflictError("Department with same name or code already exists")

            row = Department(
                name=name,
                code=code,
                color=extra.get("color") or "#3b82f6",
                icon=extra.get("icon") or "Building2",
                description=extra.get("description"),
                is_active=bool(extra.get("is_active", True)),
                settings=extra.get("settings") or {},
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return DepartmentDTO(
                id=row.id,
                name=row.name,
                code=row.code,
                color=row.color,
                icon=row.icon,
                description=row.description,
                is_active=row.is_active,
                settings=row.settings,
            )

    def update_department(self, dept_id: int, **changes) -> DepartmentDTO:
        with self._session() as session:
            dept = session.get(Department, dept_id)
            if not dept:
                raise NotFoundError("Department not found")

            if "name" in changes and changes["name"]:
                dept.name = changes["name"].strip()
            if "code" in changes and changes["code"]:
                dept.code = changes["code"].strip().upper()
            if "color" in changes:
                dept.color = changes["color"]
            if "icon" in changes:
                dept.icon = changes["icon"]
            if "description" in changes:
                dept.description = changes["description"]
            if "is_active" in changes:
                dept.is_active = bool(changes["is_active"])
            if "settings" in changes and changes["settings"] is not None:
                dept.settings = changes["settings"]

            session.commit()
            session.refresh(dept)
            return DepartmentDTO(
                id=dept.id,
                name=dept.name,
                code=dept.code,
                color=dept.color,
                icon=dept.icon,
                description=dept.description,
                is_active=dept.is_active,
                settings=dept.settings,
            )

    def delete_department(self, dept_id: int) -> None:
        with self._session() as session:
            dept = session.get(Department, dept_id)
            if not dept:
                raise NotFoundError("Department not found")

            if dept.staff and len(dept.staff) > 0:
                raise ValidationError(
                    f"Cannot delete department with {len(dept.staff)} staff members. Please reassign or remove staff first."
                )

            session.delete(dept)
            session.commit()


__all__ = ["DepartmentService"]
