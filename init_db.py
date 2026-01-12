import asyncio
from app.database import engine
from app.models import Base

async def init_models():
    async with engine.begin() as conn:
        from sqlalchemy import text
        
        # 1. Создание расширения pgvector
        print("1️⃣ Создание расширения pgvector...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("✅ Расширение pgvector создано")
        
        # 2. Создание всех таблиц
        print("\n2️⃣ Создание таблиц...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Таблицы созданы")
        
        # 3. Создание HNSW индекса для detected_faces
        print("\n3️⃣ Создание HNSW индекса для векторного поиска...")
        print("   Параметры: m=16, ef_construction=64 (оптимально для < 100K векторов)")
        try:
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS detected_faces_embedding_hnsw_idx 
                ON detected_faces 
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """))
            print("✅ HNSW индекс создан")
        except Exception as e:
            print(f"⚠️ Ошибка при создании индекса: {e}")
        
        # 4. Создание индекса для user_biometrics (опционально, для быстрого доступа)
        print("\n4️⃣ Создание вспомогательных индексов...")
        try:
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS user_biometrics_user_id_idx 
                ON user_biometrics(user_id);
            """))
            print("✅ Индекс на user_biometrics.user_id создан")
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
        
        # 5. Добавление колонки is_active для существующих таблиц
        print("\n5️⃣ Проверка и добавление колонки is_active...")
        try:
            # Проверка существования колонки
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='is_active';
            """))
            column_exists = result.fetchone()
            
            if not column_exists:
                print("   Колонка is_active не найдена, добавляем...")
                await conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true;
                """))
                print("✅ Колонка is_active добавлена")
            else:
                print("✅ Колонка is_active уже существует")
        except Exception as e:
            print(f"⚠️ Ошибка при добавлении is_active: {e}")
    
    print("\n🎉 База данных успешно инициализирована!")
    print("\n📊 Следующие шаги:")
    print("   1. Запустите сервер: uvicorn app.main:app --reload")
    print("   2. Откройте Swagger: http://localhost:8000/docs")
    print("   3. Зарегистрируйте пользователя через POST /auth/register")
    print("\n💡 Для миграции на более мощный HNSW индекс (> 100K векторов):")
    print("   python scripts/migrate_to_hnsw.py")

if __name__ == "__main__":
    asyncio.run(init_models())