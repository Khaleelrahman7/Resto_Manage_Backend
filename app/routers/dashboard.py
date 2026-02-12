from fastapi import APIRouter, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from uuid import uuid4

from app.auth import check_role
from app.db import db
from app.models import Role, User
from app.models_dashboard import DashboardSummary, DashboardActivity, DashboardEmployee


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _employee_view(employee: Dict[str, Any]) -> DashboardEmployee:
    return DashboardEmployee(
        id=str(employee.get("id") or ""),
        first_name=str(employee.get("first_name") or ""),
        last_name=str(employee.get("last_name") or ""),
        email=employee.get("email"),
        department=employee.get("department"),
    )


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN, Role.MANAGER]))
):
    employees = db.get_all("employees")
    employees_by_id: Dict[str, Dict[str, Any]] = {str(e.get("id")): e for e in employees if e.get("id")}

    total_employees = len(employees)
    active_employees = sum(1 for e in employees if bool(e.get("is_active", True)))

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start.replace(hour=23, minute=59, second=59, microsecond=999999)

    attendance_records = db.get_all("attendance_records")
    present_employee_ids: set[str] = set()
    activity_events: List[DashboardActivity] = []

    for record in attendance_records:
        employee_id = str(record.get("employee_id") or "")
        if not employee_id:
            continue

        punch_in_dt = _parse_dt(record.get("punch_in"))
        if punch_in_dt and today_start <= punch_in_dt <= today_end:
            present_employee_ids.add(employee_id)

        employee = employees_by_id.get(employee_id)
        employee_view = _employee_view(employee) if employee else None
        employee_name = ""
        if employee:
            employee_name = f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip()

        if punch_in_dt:
            activity_events.append(
                DashboardActivity(
                    id=str(uuid4()),
                    type="attendance_punch_in",
                    message=f"{employee_name or 'Employee'} punched in",
                    timestamp=punch_in_dt,
                    employee=employee_view,
                )
            )

        punch_out_dt = _parse_dt(record.get("punch_out"))
        if punch_out_dt:
            activity_events.append(
                DashboardActivity(
                    id=str(uuid4()),
                    type="attendance_punch_out",
                    message=f"{employee_name or 'Employee'} punched out",
                    timestamp=punch_out_dt,
                    employee=employee_view,
                )
            )

    present_today = len([eid for eid in present_employee_ids if bool(employees_by_id.get(eid, {}).get("is_active", True))])
    attendance_rate_today = float((present_today / active_employees) * 100.0) if active_employees > 0 else 0.0

    leave_requests = db.get_all("leave_requests")
    pending_leave_requests = sum(1 for r in leave_requests if str(r.get("status")) == "pending")

    today = date.today()
    on_leave_employee_ids: set[str] = set()
    for r in leave_requests:
        if str(r.get("status")) != "approved":
            continue
        try:
            start = date.fromisoformat(str(r.get("start_date")))
            end = date.fromisoformat(str(r.get("end_date")))
        except Exception:
            continue
        if start <= today <= end:
            employee_id = str(r.get("employee_id") or "")
            if employee_id:
                on_leave_employee_ids.add(employee_id)

        applied_at_dt = _parse_dt(r.get("applied_at"))
        reviewed_at_dt = _parse_dt(r.get("reviewed_at"))
        employee_id = str(r.get("employee_id") or "")
        employee = employees_by_id.get(employee_id)
        employee_view = _employee_view(employee) if employee else None
        employee_name = ""
        if employee:
            employee_name = f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip()

        leave_type = str(r.get("leave_type") or "leave")
        start_date = str(r.get("start_date") or "")
        end_date = str(r.get("end_date") or "")

        if applied_at_dt:
            activity_events.append(
                DashboardActivity(
                    id=str(uuid4()),
                    type="leave_applied",
                    message=f"{employee_name or 'Employee'} applied for {leave_type} leave ({start_date} to {end_date})",
                    timestamp=applied_at_dt,
                    employee=employee_view,
                )
            )

        if reviewed_at_dt and str(r.get("status")) in ["approved", "rejected"]:
            activity_events.append(
                DashboardActivity(
                    id=str(uuid4()),
                    type=f"leave_{str(r.get('status'))}",
                    message=f"{employee_name or 'Employee'} leave request {str(r.get('status'))}",
                    timestamp=reviewed_at_dt,
                    employee=employee_view,
                )
            )

    on_leave_today = len([eid for eid in on_leave_employee_ids if bool(employees_by_id.get(eid, {}).get("is_active", True))])

    activity_events.sort(key=lambda a: a.timestamp, reverse=True)
    recent_activity = activity_events[:10]

    return DashboardSummary(
        total_employees=total_employees,
        active_employees=active_employees,
        present_today=present_today,
        attendance_rate_today=round(attendance_rate_today, 2),
        pending_leave_requests=pending_leave_requests,
        on_leave_today=on_leave_today,
        recent_activity=recent_activity,
    )

