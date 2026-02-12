from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user
from app.db import db
from app.models import User, UserCreate, Token, Role
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=User)
def register(user: UserCreate):
    # Check if user exists
    if db.get_by_field("users", "email", user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # If this is the first user, make them super admin
    users = db.get_all("users")
    if not users:
        user.role = Role.SUPER_ADMIN

    user_dict = user.model_dump()
    user_dict["password"] = get_password_hash(user.password) # Hashing not implemented fully in auth.py yet? Wait, it is.
    # Actually auth.py has get_password_hash
    
    # Need to remove password from response or handle it. 
    # The User model doesn't have password field, so we are good for response.
    # But for storage we need it.
    
    # Store with hashed password
    stored_user = user_dict.copy()
    # Create user adds ID and created_at
    new_user = db.add("users", stored_user)
    
    return new_user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user_data = db.get_by_field("users", "email", form_data.username)
    if not user_data or not verify_password(form_data.password, user_data["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user_data["email"], "role": user_data["role"]},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=User)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
