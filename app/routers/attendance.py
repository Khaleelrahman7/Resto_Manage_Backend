from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from datetime import datetime
from io import StringIO
import csv
from app.db import db
from app.models import User, Role
from app.models_attendance import AttendanceRecord, AttendanceAdminRecord, AttendanceStatus
from app.auth import get_current_user, check_role

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _get_employee_for_user(user_id: str) -> Dict[str, Any]:
    employees = db.get_all("employees")
    for emp in employees:
        if emp.get("user_id") == user_id:
            return emp
    raise HTTPException(status_code=404, detail="Employee profile not found for this user")


def _get_month_range(month: str) -> tuple[datetime, datetime]:
    try:
        month_start = datetime.fromisoformat(f"{month}-01T00:00:00")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")

    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    return month_start, next_month


def _employee_summary(employee: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": employee.get("id", ""),
        "first_name": employee.get("first_name", ""),
        "last_name": employee.get("last_name", ""),
        "email": employee.get("email", ""),
        "department": employee.get("department", ""),
        "position": employee.get("position", ""),
    }


@router.post("/punch-in", response_model=AttendanceRecord)
def punch_in(
    employee_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    if current_user.role == Role.STAFF:
        employee_id = _get_employee_for_user(current_user.id)["id"]
    elif not employee_id:
        raise HTTPException(status_code=400, detail="employee_id is required")

    # Check if already punched in today
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    records = db.get_all("attendance_records")
    
    for record in records:
        if record["employee_id"] == employee_id:
            punch_in_time = datetime.fromisoformat(str(record["punch_in"]))
            if punch_in_time >= today_start and record["punch_out"] is None:
                raise HTTPException(status_code=400, detail="Already punched in")

    new_record = {
        "employee_id": employee_id,
        "punch_in": datetime.now(),
        "punch_out": None,
        "status": AttendanceStatus.PRESENT,
        "notes": ""
    }
    
    created_record = db.add("attendance_records", new_record)
    return created_record

@router.post("/punch-out", response_model=AttendanceRecord)
def punch_out(
    employee_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    if current_user.role == Role.STAFF:
        employee_id = _get_employee_for_user(current_user.id)["id"]
    elif not employee_id:
        raise HTTPException(status_code=400, detail="employee_id is required")

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    records = db.get_all("attendance_records")
    
    active_record = None
    for record in records:
        if record["employee_id"] == employee_id:
            punch_in_time = datetime.fromisoformat(str(record["punch_in"]))
            if punch_in_time >= today_start and record["punch_out"] is None:
                active_record = record
                break
    
    if not active_record:
        raise HTTPException(status_code=400, detail="No active punch-in found")
        
    updates = {"punch_out": datetime.now()}
    updated_record = db.update("attendance_records", active_record["id"], updates)
    return updated_record

@router.get("/me/today", response_model=Optional[AttendanceRecord])
def get_my_today_attendance(
    current_user: User = Depends(check_role([Role.STAFF]))
):
    employee_id = _get_employee_for_user(current_user.id)["id"]
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    records = db.get_all("attendance_records")
    for record in records:
        if record.get("employee_id") != employee_id:
            continue
        try:
            punch_in_time = datetime.fromisoformat(str(record["punch_in"]))
        except Exception:
            continue
        if punch_in_time >= today_start:
            return record
    return None


@router.get("/me", response_model=List[AttendanceRecord])
def get_my_attendance(
    month: str,
    current_user: User = Depends(check_role([Role.STAFF]))
):
    employee_id = _get_employee_for_user(current_user.id)["id"]
    month_start, next_month = _get_month_range(month)

    records = db.get_all("attendance_records")
    results: List[Dict[str, Any]] = []
    for record in records:
        if record.get("employee_id") != employee_id:
            continue
        try:
            punch_in_time = datetime.fromisoformat(str(record["punch_in"]))
        except Exception:
            continue
        if month_start <= punch_in_time < next_month:
            results.append(record)
    return results

@router.get("/admin", response_model=List[AttendanceAdminRecord])
def get_attendance_admin(
    month: Optional[str] = None,
    employee_id: Optional[str] = None,
    department: Optional[str] = None,
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN, Role.MANAGER]))
):
    records = db.get_all("attendance_records")
    employees = db.get_all("employees")
    employee_by_id: Dict[str, Dict[str, Any]] = {e.get("id"): e for e in employees if e.get("id")}

    month_start: Optional[datetime] = None
    next_month: Optional[datetime] = None
    if month:
        month_start, next_month = _get_month_range(month)

    results: List[Dict[str, Any]] = []
    for record in records:
        rec_employee_id = record.get("employee_id")
        if not rec_employee_id:
            continue
        if employee_id and rec_employee_id != employee_id:
            continue

        employee = employee_by_id.get(rec_employee_id)
        if not employee:
            continue
        if department and employee.get("department") != department:
            continue

        if month_start and next_month:
            try:
                punch_in_time = datetime.fromisoformat(str(record.get("punch_in")))
            except Exception:
                continue
            if not (month_start <= punch_in_time < next_month):
                continue

        results.append({**record, "employee": _employee_summary(employee)})

    results.sort(key=lambda r: (r.get("employee", {}).get("last_name", ""), r.get("employee", {}).get("first_name", ""), str(r.get("punch_in", ""))))
    return results


@router.get("/admin/report.csv")
def download_attendance_report_csv(
    month: str,
    employee_id: Optional[str] = None,
    department: Optional[str] = None,
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN, Role.MANAGER]))
):
    month_start, next_month = _get_month_range(month)
    records = db.get_all("attendance_records")
    employees = db.get_all("employees")
    employee_by_id: Dict[str, Dict[str, Any]] = {e.get("id"): e for e in employees if e.get("id")}

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "employee_id",
        "employee_name",
        "email",
        "department",
        "position",
        "date",
        "punch_in",
        "punch_out",
        "worked_hours",
        "status",
        "notes",
    ])

    for record in records:
        rec_employee_id = record.get("employee_id")
        if not rec_employee_id:
            continue
        if employee_id and rec_employee_id != employee_id:
            continue

        employee = employee_by_id.get(rec_employee_id)
        if not employee:
            continue
        if department and employee.get("department") != department:
            continue

        try:
            punch_in_dt = datetime.fromisoformat(str(record.get("punch_in")))
        except Exception:
            continue
        if not (month_start <= punch_in_dt < next_month):
            continue

        punch_out_raw = record.get("punch_out")
        punch_out_dt: Optional[datetime] = None
        if punch_out_raw:
            try:
                punch_out_dt = datetime.fromisoformat(str(punch_out_raw))
            except Exception:
                punch_out_dt = None

        worked_hours = ""
        if punch_out_dt:
            worked_hours = f"{max(0.0, (punch_out_dt - punch_in_dt).total_seconds() / 3600.0):.2f}"

        full_name = f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip()
        writer.writerow([
            rec_employee_id,
            full_name,
            employee.get("email", ""),
            employee.get("department", ""),
            employee.get("position", ""),
            punch_in_dt.date().isoformat(),
            punch_in_dt.isoformat(sep=" "),
            punch_out_dt.isoformat(sep=" ") if punch_out_dt else "",
            worked_hours,
            record.get("status", ""),
            record.get("notes", "") or "",
        ])

    content = output.getvalue()
    output.close()

    safe_month = month.replace("/", "-")
    filename = f"attendance_{safe_month}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([content]), media_type="text/csv", headers=headers)

@router.get("/", response_model=List[AttendanceRecord])
def get_attendance(
    employee_id: Optional[str] = None,
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN, Role.MANAGER, Role.STAFF]))
):
    records = db.get_all("attendance_records")
    if current_user.role == Role.STAFF:
        employee_id = _get_employee_for_user(current_user.id)["id"]
    if employee_id:
        records = [r for r in records if r.get("employee_id") == employee_id]
    return records
