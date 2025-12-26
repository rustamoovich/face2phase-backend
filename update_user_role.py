"""
Скрипт для обновления роли пользователя.

Использование:
    python update_user_role.py <email> <new_role>
    
Пример:
    python update_user_role.py user@example.com organizer
"""

import asyncio
import sys
from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models import User

async def update_user_role(email: str, new_role: str):
    async with AsyncSessionLocal() as session:
        # Найти пользователя
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"❌ Пользователь с email '{email}' не найден")
            return
        
        print(f"📝 Найден пользователь: {user.email} (текущая роль: {user.role})")
        
        # Обновить роль
        user.role = new_role
        await session.commit()
        
        print(f"✅ Роль пользователя обновлена на '{new_role}'")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python update_user_role.py <email> <new_role>")
        print("Доступные роли: user, organizer, admin")
        sys.exit(1)
    
    email = sys.argv[1]
    new_role = sys.argv[2]
    
    if new_role not in ['user', 'organizer', 'admin']:
        print(f"❌ Недопустимая роль: {new_role}")
        print("Доступные роли: user, organizer, admin")
        sys.exit(1)
    
    asyncio.run(update_user_role(email, new_role))

