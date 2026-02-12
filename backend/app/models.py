from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime

class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    STAFF = "staff"

class UserBase(BaseModel):
    email: EmailStr
    role: Role = Role.STAFF
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str
    created_at: datetime = Field(default_factory=datetime.now)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    position: str
    department: str
    salary: float

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeLoginCreate(BaseModel):
    password: str
    role: Role = Role.STAFF

class Employee(EmployeeBase):
    id: str
    user_id: Optional[str] = None
    joining_date: datetime = Field(default_factory=datetime.now)
    is_active: bool = True
