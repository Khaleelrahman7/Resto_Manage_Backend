from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.db import db
from app.models import Employee, EmployeeCreate, EmployeeLoginCreate, User, Role
from app.auth import check_role, get_password_hash
from datetime import datetime

router = APIRouter(prefix="/employees", tags=["employees"])

@router.get("/", response_model=List[Employee])
def get_employees(
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN, Role.MANAGER]))
):
    return db.get_all("employees")

@router.post("/", response_model=Employee)
def create_employee(
    employee: EmployeeCreate,
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN]))
):
    # Check for duplicate email
    if db.get_by_field("employees", "email", employee.email):
        raise HTTPException(status_code=400, detail="Employee with this email already exists")
        
    employee_dict = employee.model_dump()
    new_employee = db.add("employees", employee_dict)
    return new_employee

@router.get("/me", response_model=Employee)
def get_my_employee_profile(
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN, Role.MANAGER, Role.STAFF]))
):
    employees = db.get_all("employees")
    for emp in employees:
        if emp.get("user_id") == current_user.id:
            return emp
    raise HTTPException(status_code=404, detail="Employee profile not found for this user")

@router.get("/{employee_id}", response_model=Employee)
def get_employee(
    employee_id: str,
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN, Role.MANAGER]))
):
    employee = db.get_by_id("employees", employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@router.put("/{employee_id}", response_model=Employee)
def update_employee(
    employee_id: str,
    employee_update: EmployeeCreate,
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN]))
):
    existing = db.get_by_id("employees", employee_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    updated = db.update("employees", employee_id, employee_update.model_dump())
    return updated

@router.delete("/{employee_id}")
def delete_employee(
    employee_id: str,
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN]))
):
    if not db.delete("employees", employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"message": "Employee deleted successfully"}

@router.post("/{employee_id}/create-login")
def create_employee_login(
    employee_id: str,
    payload: EmployeeLoginCreate,
    current_user: User = Depends(check_role([Role.SUPER_ADMIN, Role.ADMIN]))
):
    employee = db.get_by_id("employees", employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if employee.get("user_id"):
        raise HTTPException(status_code=400, detail="Login already created for this employee")

    email = employee["email"]
    if db.get_by_field("users", "email", email):
        raise HTTPException(status_code=400, detail="A user with this email already exists")

    user_dict = {
        "email": email,
        "password": get_password_hash(payload.password),
        "role": payload.role,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    }
    created_user = db.add("users", user_dict)
    db.update("employees", employee_id, {"user_id": created_user["id"]})
    return {"message": "Employee login created successfully", "email": email}
