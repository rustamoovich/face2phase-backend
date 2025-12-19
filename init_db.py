import asyncio
from app.database import engine
from app.models import Base

async def init_models():
    async with engine.begin() as conn:
        # Важно: для pgvector нужно сначала создать расширение
        from sqlalchemy import text
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # Создаем все таблицы
        await conn.run_sync(Base.metadata.create_all)
    print("База данных успешно инициализирована!")

if __name__ == "__main__":
    asyncio.run(init_models())