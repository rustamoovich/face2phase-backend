"""
Скрипт для проверки обработанных лиц в базе данных.
"""

import asyncio
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models import DetectedFace, MediaItem

async def check_detected_faces():
    async with AsyncSessionLocal() as db:
        # Подсчет общего количества лиц
        result = await db.execute(select(func.count(DetectedFace.id)))
        total_faces = result.scalar()
        print(f"📊 Всего найдено лиц: {total_faces}")
        
        if total_faces == 0:
            print("⚠️  Лица не найдены. Проверьте:")
            print("   1. Загружены ли фото через /events/{event_id}/upload")
            print("   2. Запущена ли фоновая обработка (BackgroundTasks)")
            print("   3. Есть ли ошибки в логах сервера")
            return
        
        # Получить последние 5 найденных лиц
        result = await db.execute(
            select(DetectedFace)
            .order_by(DetectedFace.id.desc())
            .limit(5)
        )
        faces = result.scalars().all()
        
        print(f"\n🔍 Последние {len(faces)} найденных лиц:\n")
        for face in faces:
            print(f"  ID: {face.id}")
            print(f"  Media Item ID: {face.media_item_id}")
            print(f"  Confidence: {face.confidence:.2%}")
            print(f"  Bounding Box: {face.bounding_box}")
            # Безопасная проверка размера embedding
            try:
                embedding_size = len(face.embedding) if face.embedding is not None else 0
            except (TypeError, ValueError):
                embedding_size = 0
            print(f"  Embedding size: {embedding_size}")
            print("  " + "-" * 50)
        
        # Проверить статус обработки медиафайлов
        result = await db.execute(
            select(MediaItem.ai_status, func.count(MediaItem.id))
            .group_by(MediaItem.ai_status)
        )
        statuses = result.all()
        
        print("\n📈 Статистика обработки медиафайлов:")
        for status, count in statuses:
            print(f"  {status}: {count}")

if __name__ == "__main__":
    asyncio.run(check_detected_faces())

