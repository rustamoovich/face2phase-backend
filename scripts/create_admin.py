"""
Скрипт для создания первого администратора платформы.

Использование:
    python scripts/create_admin.py
    или
    python scripts/create_admin.py --email admin@example.com --password admin123 --name "Admin User"
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import asyncio
import argparse
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import User
from app.core import security


async def create_admin(email: str, password: str, full_name: str = "Admin"):
    """Создает администратора платформы"""
    async with AsyncSessionLocal() as db:
        try:
            # Проверка существования админа
            result = await db.execute(select(User).where(User.role == "admin"))
            existing_admin = result.scalar_one_or_none()
            
            if existing_admin:
                print(f"WARNING: Admin already exists: {existing_admin.email}")
                response = input("Do you want to create another admin? (y/n): ")
                if response.lower() != 'y':
                    print("Cancelled.")
                    return
            
            # Проверка email
            result = await db.execute(select(User).where(User.email == email))
            if result.scalar_one_or_none():
                raise ValueError(f"User with email {email} already exists")
            
            # Создание админа
            admin = User(
                email=email,
                password_hash=security.get_password_hash(password),
                full_name=full_name,
                role="admin",
                organization_id=None,  # Админ не привязан к организации
                is_active=True
            )
            
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            
            print("\n=== Admin created successfully! ===")
            print(f"Email: {admin.email}")
            print(f"Full Name: {admin.full_name}")
            print(f"Role: {admin.role}")
            print(f"ID: {admin.id}")
            print("\nYou can now login at: POST /auth/login")
            
        except Exception as e:
            await db.rollback()
            print(f"\nERROR: Failed to create admin: {e}")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--email", type=str, help="Admin email", default="admin@face2phase.com")
    parser.add_argument("--password", type=str, help="Admin password", default="admin123")
    parser.add_argument("--name", type=str, help="Admin full name", default="Admin User")
    
    args = parser.parse_args()
    
    print("Creating admin user...")
    print(f"Email: {args.email}")
    print(f"Name: {args.name}")
    print("Password: " + "*" * len(args.password))
    
    asyncio.run(create_admin(args.email, args.password, args.name))
