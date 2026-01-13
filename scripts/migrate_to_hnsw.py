"""
Миграция с IVFFlat на HNSW индексирование для векторного поиска.

HNSW (Hierarchical Navigable Small World) обеспечивает:
- Более быстрый поиск (10-100x по сравнению с IVFFlat)
- Лучшую точность
- Не требует тренировки на данных

Использование:
    python scripts/migrate_to_hnsw.py
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal


async def migrate_to_hnsw():
    """
    Замена IVFFlat индекса на HNSW для таблицы detected_faces.
    """
    async with AsyncSessionLocal() as db:
        print("🔄 Начало миграции на HNSW индексирование...")
        
        # 1. Удаление старого индекса (если существует)
        print("1️⃣ Удаление старого IVFFlat индекса...")
        try:
            await db.execute(text("""
                DROP INDEX IF EXISTS detected_faces_embedding_idx;
            """))
            await db.commit()
            print("✅ Старый индекс удален")
        except Exception as e:
            print(f"⚠️ Ошибка при удалении старого индекса: {e}")
            await db.rollback()
        
        # 2. Создание нового HNSW индекса
        print("\n2️⃣ Создание HNSW индекса...")
        print("   Параметры:")
        print("   - m = 16 (количество соединений на уровень)")
        print("   - ef_construction = 64 (размер списка при построении)")
        
        try:
            await db.execute(text("""
                CREATE INDEX detected_faces_embedding_hnsw_idx 
                ON detected_faces 
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """))
            await db.commit()
            print("✅ HNSW индекс создан успешно!")
        except Exception as e:
            print(f"❌ Ошибка при создании HNSW индекса: {e}")
            await db.rollback()
            return
        
        # 3. Проверка созданного индекса
        print("\n3️⃣ Проверка индекса...")
        result = await db.execute(text("""
            SELECT 
                indexname, 
                indexdef
            FROM pg_indexes
            WHERE tablename = 'detected_faces'
            AND indexname LIKE '%hnsw%';
        """))
        
        indexes = result.fetchall()
        if indexes:
            print("✅ Индекс найден:")
            for idx in indexes:
                print(f"   Имя: {idx.indexname}")
                print(f"   Определение: {idx.indexdef[:100]}...")
        else:
            print("⚠️ Индекс не найден в pg_indexes")
        
        # 4. Получение статистики
        print("\n4️⃣ Статистика таблицы detected_faces:")
        result = await db.execute(text("""
            SELECT 
                COUNT(*) as total_faces,
                COUNT(DISTINCT media_item_id) as unique_media_items
            FROM detected_faces;
        """))
        
        stats = result.fetchone()
        if stats:
            print(f"   Всего лиц: {stats.total_faces}")
            print(f"   Уникальных медиафайлов: {stats.unique_media_items}")
        
        print("\n🎉 Миграция завершена успешно!")
        print("\n📊 Рекомендации:")
        print("   - Для баз > 100K векторов рассмотрите m=32, ef_construction=128")
        print("   - Для максимальной точности используйте m=48, ef_construction=200")
        print("   - Мониторьте производительность через EXPLAIN ANALYZE")


async def test_search_performance():
    """
    Тестирование производительности поиска с HNSW индексом.
    """
    async with AsyncSessionLocal() as db:
        print("\n🧪 Тестирование производительности поиска...")
        
        # Проверяем, есть ли данные для тестирования
        result = await db.execute(text("""
            SELECT embedding 
            FROM detected_faces 
            LIMIT 1;
        """))
        
        test_embedding = result.scalar_one_or_none()
        
        if not test_embedding:
            print("⚠️ Нет данных для тестирования. Загрузите фото через API.")
            return
        
        # Преобразуем embedding в строку для запроса
        embedding_str = str(test_embedding.tolist() if hasattr(test_embedding, 'tolist') else test_embedding)
        
        # EXPLAIN ANALYZE для оценки производительности
        result = await db.execute(text("""
            EXPLAIN ANALYZE
            SELECT id, embedding <=> :embedding as distance
            FROM detected_faces
            ORDER BY embedding <=> :embedding
            LIMIT 100;
        """), {"embedding": embedding_str})
        
        explain_output = result.fetchall()
        print("\n📈 EXPLAIN ANALYZE результаты:")
        for row in explain_output:
            print(f"   {row[0]}")


async def main():
    """
    Главная функция - запускает миграцию и опционально тестирование.
    """
    # Выполняем миграцию
    await migrate_to_hnsw()
    
    # Спрашиваем о тестировании
    test = input("\n❓ Хотите протестировать производительность? (y/n): ")
    if test.lower() == 'y':
        await test_search_performance()


if __name__ == "__main__":
    print("=" * 60)
    print("HNSW Индексирование для pgvector")
    print("=" * 60)
    
    asyncio.run(main())

