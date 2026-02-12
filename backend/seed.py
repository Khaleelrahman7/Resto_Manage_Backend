from app.db import db
from app.auth import get_password_hash
from app.models import Role, User

def seed_admin():
    # Check if admin exists
    existing = db.get_by_field("users", "email", "admin@restaurant.com")
    if existing:
        print("Admin user already exists.")
        return

    admin_user = {
        "email": "admin@restaurant.com",
        "password": get_password_hash("admin"),
        "role": Role.SUPER_ADMIN,
        "is_active": True,
        # ID and created_at are handled by db.add if not present, 
        # but User model expects them. JsonDB.add adds 'id'.
        # 'created_at' is generic in JsonDB? No, JsonDB is generic.
        # User model in models.py has default factory for created_at.
        # But JsonDB just stores dicts.
    }
    
    # We need to manually add created_at string if we want it consistent, 
    # or let the Pydantic model handle it when read?
    # For simple JSON, let's just add it.
    from datetime import datetime
    admin_user["created_at"] = datetime.now().isoformat()

    db.add("users", admin_user)
    print("Admin user created: admin@restaurant.com / admin")

if __name__ == "__main__":
    seed_admin()
