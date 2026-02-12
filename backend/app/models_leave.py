from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from datetime import date, datetime


class LeaveType(str, Enum):
    CASUAL = "casual"
    SICK = "sick"
    EARNED = "earned"


class LeaveStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class LeaveRequestCreate(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str
    attachment_name: Optional[str] = None
    attachment_base64: Optional[str] = None


class LeaveRequest(BaseModel):
    id: str
    employee_id: str
    user_id: str
    leave_type: LeaveType
    start_date: date
    end_date: date
    total_days: float
    status: LeaveStatus = LeaveStatus.PENDING
    reason: str
    attachment_name: Optional[str] = None
    attachment_base64: Optional[str] = None
    applied_at: datetime = Field(default_factory=datetime.now)
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None


class LeaveBalance(BaseModel):
    leave_type: LeaveType
    total: float
    used: float
    remaining: float


class Holiday(BaseModel):
    id: str
    date: date
    name: str
