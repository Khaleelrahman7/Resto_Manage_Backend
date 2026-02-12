from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class DashboardEmployee(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    department: Optional[str] = None


class DashboardActivity(BaseModel):
    id: str
    type: str
    message: str
    timestamp: datetime
    employee: Optional[DashboardEmployee] = None


class DashboardSummary(BaseModel):
    total_employees: int
    active_employees: int
    present_today: int
    attendance_rate_today: float
    pending_leave_requests: int
    on_leave_today: int
    recent_activity: List[DashboardActivity]

