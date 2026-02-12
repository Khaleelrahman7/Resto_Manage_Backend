from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from datetime import date, datetime, timedelta

from app.auth import check_role
from app.db import db
from app.models import Role, User
from app.models_leave import LeaveRequest, LeaveRequestCreate, LeaveType, LeaveStatus, LeaveBalance, Holiday


router = APIRouter(prefix="/leaves", tags=["leaves"])


DEFAULT_LEAVE_TOTALS: Dict[str, float] = {
    LeaveType.CASUAL.value: 12.0,
    LeaveType.SICK.value: 8.0,
    LeaveType.EARNED.value: 15.0,
}


def _get_employee_for_user(user_id: str) -> Dict[str, Any]:
    employees = db.get_all("employees")
    for emp in employees:
        if emp.get("user_id") == user_id:
            return emp
    raise HTTPException(status_code=404, detail="Employee profile not found for this user")


def _holiday_dates_set() -> set[str]:
    holidays = db.get_all("holidays")
    return {str(h.get("date")) for h in holidays if h.get("date")}


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def _working_days_between(start: date, end: date) -> List[date]:
    holiday_set = _holiday_dates_set()
    days: List[date] = []
    cursor = start
    while cursor <= end:
        if not _is_weekend(cursor) and cursor.isoformat() not in holiday_set:
            days.append(cursor)
        cursor = cursor + timedelta(days=1)
    return days


def _overlaps(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def _reserved_or_used_days(employee_id: str, leave_type: LeaveType) -> float:
    requests = db.get_all("leave_requests")
    total = 0.0
    for r in requests:
        if r.get("employee_id") != employee_id:
            continue
        if r.get("leave_type") != leave_type.value:
            continue
        if r.get("status") not in [LeaveStatus.PENDING.value, LeaveStatus.APPROVED.value]:
            continue
        try:
            total += float(r.get("total_days") or 0.0)
        except Exception:
            continue
    return float(total)


def _get_total_allowance(employee_id: str, leave_type: LeaveType) -> float:
    balances = db.get_all("leave_balances")
    for b in balances:
        if b.get("employee_id") == employee_id and b.get("leave_type") == leave_type.value:
            try:
                return float(b.get("total") or 0.0)
            except Exception:
                return 0.0
    return float(DEFAULT_LEAVE_TOTALS[leave_type.value])


@router.get("/holidays", response_model=List[Holiday])
def list_holidays(
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN, Role.MANAGER, Role.STAFF]))
):
    return db.get_all("holidays")


@router.get("/balance", response_model=List[LeaveBalance])
def get_leave_balance(
    current_user: User = Depends(check_role([Role.STAFF]))
):
    emp = _get_employee_for_user(current_user.id)
    employee_id = emp["id"]

    balances: List[LeaveBalance] = []
    for lt in [LeaveType.CASUAL, LeaveType.SICK, LeaveType.EARNED]:
        total = _get_total_allowance(employee_id, lt)
        used = _reserved_or_used_days(employee_id, lt)
        remaining = max(0.0, total - used)
        balances.append(LeaveBalance(leave_type=lt, total=total, used=used, remaining=remaining))
    return balances


@router.get("/history", response_model=List[LeaveRequest])
def get_leave_history(
    current_user: User = Depends(check_role([Role.STAFF]))
):
    emp = _get_employee_for_user(current_user.id)
    employee_id = emp["id"]
    requests = [r for r in db.get_all("leave_requests") if r.get("employee_id") == employee_id]
    requests.sort(key=lambda x: str(x.get("applied_at") or ""), reverse=True)
    return requests


@router.post("/apply", response_model=LeaveRequest)
def apply_leave(
    payload: LeaveRequestCreate,
    current_user: User = Depends(check_role([Role.STAFF]))
):
    emp = _get_employee_for_user(current_user.id)
    employee_id = emp["id"]

    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="Start date must be on or before end date")

    working_days = _working_days_between(payload.start_date, payload.end_date)
    if len(working_days) == 0:
        raise HTTPException(status_code=400, detail="Selected range contains no working days (weekends/holidays only)")

    existing = db.get_all("leave_requests")
    for r in existing:
        if r.get("employee_id") != employee_id:
            continue
        if r.get("status") not in [LeaveStatus.PENDING.value, LeaveStatus.APPROVED.value]:
            continue
        try:
            r_start = date.fromisoformat(str(r.get("start_date")))
            r_end = date.fromisoformat(str(r.get("end_date")))
        except Exception:
            continue
        if _overlaps(payload.start_date, payload.end_date, r_start, r_end):
            raise HTTPException(status_code=409, detail="Leave dates conflict with an existing leave request")

    total_allowance = _get_total_allowance(employee_id, payload.leave_type)
    used = _reserved_or_used_days(employee_id, payload.leave_type)
    requested = float(len(working_days))
    if requested > (total_allowance - used):
        raise HTTPException(status_code=400, detail="Insufficient leave balance for the selected dates")

    req_dict: Dict[str, Any] = {
        "employee_id": employee_id,
        "user_id": current_user.id,
        "leave_type": payload.leave_type.value,
        "start_date": payload.start_date.isoformat(),
        "end_date": payload.end_date.isoformat(),
        "total_days": requested,
        "status": LeaveStatus.PENDING.value,
        "reason": payload.reason,
        "attachment_name": payload.attachment_name,
        "attachment_base64": payload.attachment_base64,
        "applied_at": datetime.now().isoformat(),
        "reviewed_by": None,
        "reviewed_at": None,
        "review_notes": None,
    }
    created = db.add("leave_requests", req_dict)
    return created


@router.post("/{leave_id}/cancel", response_model=LeaveRequest)
def cancel_leave(
    leave_id: str,
    current_user: User = Depends(check_role([Role.STAFF]))
):
    emp = _get_employee_for_user(current_user.id)
    employee_id = emp["id"]
    leave_req = db.get_by_id("leave_requests", leave_id)
    if not leave_req or leave_req.get("employee_id") != employee_id:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave_req.get("status") != LeaveStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Only pending leave requests can be cancelled")
    updated = db.update("leave_requests", leave_id, {"status": LeaveStatus.CANCELLED.value})
    return updated


@router.post("/{leave_id}/approve", response_model=LeaveRequest)
def approve_leave(
    leave_id: str,
    review_notes: str = "",
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN, Role.MANAGER]))
):
    leave_req = db.get_by_id("leave_requests", leave_id)
    if not leave_req:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave_req.get("status") != LeaveStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Only pending leave requests can be approved")
    updated = db.update(
        "leave_requests",
        leave_id,
        {
            "status": LeaveStatus.APPROVED.value,
            "reviewed_by": current_user.id,
            "reviewed_at": datetime.now().isoformat(),
            "review_notes": review_notes,
        },
    )
    return updated


@router.post("/{leave_id}/reject", response_model=LeaveRequest)
def reject_leave(
    leave_id: str,
    review_notes: str = "",
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN, Role.MANAGER]))
):
    leave_req = db.get_by_id("leave_requests", leave_id)
    if not leave_req:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave_req.get("status") != LeaveStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Only pending leave requests can be rejected")
    updated = db.update(
        "leave_requests",
        leave_id,
        {
            "status": LeaveStatus.REJECTED.value,
            "reviewed_by": current_user.id,
            "reviewed_at": datetime.now().isoformat(),
            "review_notes": review_notes,
        },
    )
    return updated
