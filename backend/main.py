from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from app.routers import auth, employees, attendance, leaves, dashboard

app = FastAPI(title="Restaurant Employee Management System")

# CORS
cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()
if cors_origins_env:
    allow_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    allow_credentials = True
else:
    allow_origins = ["*"]
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(leaves.router)
app.include_router(dashboard.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Restaurant Employee Management API"}
