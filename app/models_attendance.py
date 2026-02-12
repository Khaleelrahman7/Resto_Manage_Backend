from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum

class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    HALF_DAY = "half_day"
    LATE = "late"

class AttendanceRecordBase(BaseModel):
    employee_id: str
    punch_in: datetime = Field(default_factory=datetime.now)
    punch_out: Optional[datetime] = None
    status: AttendanceStatus = AttendanceStatus.PRESENT
    notes: Optional[str] = None

class AttendanceRecordCreate(AttendanceRecordBase):
    pass

class AttendanceRecord(AttendanceRecordBase):
    id: str
    created_at: datetime = Field(default_factory=datetime.now)


class EmployeeSummary(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    department: str
    position: str


class AttendanceAdminRecord(AttendanceRecord):
    employee: EmployeeSummary
