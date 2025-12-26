import os
import uuid
from pathlib import Path
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Event, MediaItem, User
from app.schemas import MediaUploadResponse, MediaItemResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/events", tags=["media"])

UPLOAD_DIR = Path("uploads")

@router.post("/{event_id}/upload", response_model=MediaUploadResponse)
async def upload_media(
    event_id: uuid.UUID,
    files: Annotated[List[UploadFile], File(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Загрузить медиафайлы (фото/видео) для мероприятия.
    
    Требования:
    - Пользователь должен быть организатором этого мероприятия
    - Поддерживается загрузка множественных файлов
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
    
    # Создание папки для мероприятия
    event_upload_dir = UPLOAD_DIR / str(event_id)
    event_upload_dir.mkdir(parents=True, exist_ok=True)
    
    uploaded_media_ids = []
    
    for file in files:
        # Определение типа медиа
        content_type = file.content_type or "application/octet-stream"
        media_type = "video" if content_type.startswith("video/") else "image"
        
        # Генерация уникального имени файла
        file_extension = Path(file.filename).suffix if file.filename else ""
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = event_upload_dir / unique_filename
        
        # Сохранение файла
        try:
            contents = await file.read()
            with open(file_path, "wb") as f:
                f.write(contents)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file: {str(e)}"
            )
        
        # Создание записи в БД
        db_media = MediaItem(
            event_id=event_id,
            original_path=str(file_path),
            media_type=media_type,
            ai_status="pending"
        )
        
        db.add(db_media)
        await db.flush()  # Чтобы получить ID до commit
        uploaded_media_ids.append(db_media.id)
    
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

