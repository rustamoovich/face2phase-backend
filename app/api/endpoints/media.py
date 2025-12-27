import os
import uuid
from pathlib import Path
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, AsyncSessionLocal
from app.models import Event, MediaItem, User, DetectedFace
from app.schemas import MediaUploadResponse, MediaItemResponse
from app.api.deps import get_current_user
from app.services.face_service import get_face_service
from app.services.storage_service import get_storage_service

router = APIRouter(prefix="/events", tags=["media"])

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)


async def process_faces_task(media_item_id: uuid.UUID, temp_file_path: str):
    """
    Фоновая задача для обработки лиц на изображении.
    
    Args:
        media_item_id: ID медиафайла в базе данных
        temp_file_path: Временный путь к файлу на диске (будет удален после обработки)
    """
    try:
        # Получение сервиса распознавания лиц
        face_service = get_face_service()
        
        # Обработка изображения
        faces = face_service.process_image(temp_file_path, min_confidence=0.6)
        
        # Сохранение результатов в БД
        async with AsyncSessionLocal() as db:
            for face_data in faces:
                detected_face = DetectedFace(
                    media_item_id=media_item_id,
                    embedding=face_data['embedding'],
                    bounding_box={
                        "x": face_data['bbox'][0],
                        "y": face_data['bbox'][1],
                        "w": face_data['bbox'][2] - face_data['bbox'][0],
                        "h": face_data['bbox'][3] - face_data['bbox'][1]
                    },
                    confidence=face_data['confidence']
                )
                db.add(detected_face)
            
            # Обновление статуса обработки
            result = await db.execute(
                select(MediaItem).where(MediaItem.id == media_item_id)
            )
            media_item = result.scalar_one_or_none()
            if media_item:
                media_item.ai_status = "processed" if faces else "no_faces"
            
            await db.commit()
            
    except Exception as e:
        # Логирование ошибки и обновление статуса
        print(f"Error processing faces for media {media_item_id}: {str(e)}")
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(MediaItem).where(MediaItem.id == media_item_id)
            )
            media_item = result.scalar_one_or_none()
            if media_item:
                media_item.ai_status = "failed"
                await db.commit()
    finally:
        # Удаляем временный файл
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@router.post("/{event_id}/upload", response_model=MediaUploadResponse)
async def upload_media(
    event_id: uuid.UUID,
    files: Annotated[List[UploadFile], File(...)],
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Загрузить медиафайлы (фото/видео) для мероприятия.
    
    Требования:
    - Пользователь должен быть организатором этого мероприятия
    - Поддерживается загрузка множественных файлов
    - Файлы сохраняются в Cloudflare R2
    - После загрузки автоматически запускается обработка лиц
    """
    # Проверка существования мероприятия
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Проверка прав доступа
    if event.organizer_id != current_user.id and current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges"
        )
    
    storage_service = get_storage_service()
    uploaded_media_ids = []
    
    for file in files:
        # Определение типа медиа
        content_type = file.content_type or "application/octet-stream"
        media_type = "video" if content_type.startswith("video/") else "image"
        
        # Генерация уникального имени файла
        file_extension = Path(file.filename).suffix if file.filename else ""
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Путь в R2: events/{event_id}/original/{unique_filename}
        r2_key = f"events/{event_id}/original/{unique_filename}"
        
        # Чтение файла
        try:
            contents = await file.read()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read file: {str(e)}"
            )
        
        # Загрузка в R2
        try:
            await storage_service.upload_file(contents, r2_key, content_type)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file to storage: {str(e)}"
            )
        
        # Создание записи в БД с ключом R2
        db_media = MediaItem(
            event_id=event_id,
            original_path=r2_key,  # Теперь храним ключ R2, а не локальный путь
            media_type=media_type,
            ai_status="pending"
        )
        
        db.add(db_media)
        await db.flush()
        uploaded_media_ids.append(db_media.id)
        
        # Для обработки лиц нужен локальный файл
        # Сохраняем временно
        if media_type == "image":
            temp_file_path = TEMP_DIR / f"{db_media.id}{file_extension}"
            with open(temp_file_path, "wb") as f:
                f.write(contents)
            
            background_tasks.add_task(
                process_faces_task,
                media_item_id=db_media.id,
                temp_file_path=str(temp_file_path)
            )
    
    await db.commit()
    
    return MediaUploadResponse(
        uploaded_count=len(uploaded_media_ids),
        media_ids=uploaded_media_ids
    )

@router.get("/{event_id}/media", response_model=List[MediaItemResponse])
async def get_event_media(
    event_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Получить список медиафайлов мероприятия.
    """
    # Проверка существования мероприятия
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Получение медиафайлов
    result = await db.execute(
        select(MediaItem).where(MediaItem.event_id == event_id)
    )
    media_items = result.scalars().all()
    
    return media_items

@router.get("/media/{media_item_id}/faces")
async def get_detected_faces(
    media_item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Получить список найденных лиц на конкретном медиафайле.
    """
    from sqlalchemy import func
    
    # Получение найденных лиц
    result = await db.execute(
        select(DetectedFace).where(DetectedFace.media_item_id == media_item_id)
    )
    faces = result.scalars().all()
    
    return {
        "media_item_id": media_item_id,
        "total_faces": len(faces),
        "faces": [
            {
                "id": str(face.id),
                "confidence": face.confidence,
                "bounding_box": face.bounding_box,
                "embedding_size": len(face.embedding) if face.embedding else 0
            }
            for face in faces
        ]
    }

