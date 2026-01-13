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
from app.services.media_processing_service import MediaProcessingService

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
    Загрузить медиафайлы (фото/видео/PDF) для мероприятия.
    
    Структура хранения в R2:
    - Фото: events/{event_id}/photos/original/{uuid}.jpg
            events/{event_id}/photos/thumbnails/small_{uuid}.jpg
            events/{event_id}/photos/thumbnails/medium_{uuid}.jpg
    - Видео: events/{event_id}/videos/original/{uuid}.mp4
             events/{event_id}/videos/posters/{uuid}.jpg (TODO)
    - PDF: events/{event_id}/documents/files/{uuid}.pdf
           events/{event_id}/documents/previews/{uuid}.jpg
    
    Требования:
    - Пользователь должен быть организатором этого мероприятия
    - Поддерживается загрузка множественных файлов
    - Файлы сохраняются в Cloudflare R2
    - Автоматически создаются thumbnails для фото
    - Автоматически извлекается первая страница PDF
    - После загрузки фото автоматически запускается обработка лиц
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
    media_processor = MediaProcessingService()
    uploaded_media_ids = []
    
    for file in files:
        # Чтение файла
        try:
            contents = await file.read()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read file {file.filename}: {str(e)}"
            )
        
        # Определение типа медиа
        content_type = file.content_type or "application/octet-stream"
        filename = file.filename or "unknown"
        media_folder, file_type = media_processor.detect_media_type(content_type, filename)
        
        # Генерация уникального имени файла
        unique_id = uuid.uuid4()
        unique_filename = f"{unique_id}.{file_type}"
        
        # Путь для оригинала в R2
        if media_folder == "photos":
            original_key = media_processor.get_storage_path(
                str(event_id), media_folder, "original", unique_filename
            )
            media_type = "image"
        elif media_folder == "videos":
            original_key = media_processor.get_storage_path(
                str(event_id), media_folder, "original", unique_filename
            )
            media_type = "video"
        elif media_folder == "documents":
            original_key = media_processor.get_storage_path(
                str(event_id), media_folder, "files", unique_filename
            )
            media_type = "document"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {content_type}"
            )
        
        # Загрузка оригинала в R2
        try:
            await storage_service.upload_file(contents, original_key, content_type)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file to storage: {str(e)}"
            )
        
        # Инициализация путей для thumbnails/превью
        small_thumbnail_key = None
        medium_thumbnail_key = None
        preview_key = None
        
        # Обработка фотографий: создание thumbnails
        if media_folder == "photos":
            try:
                small_thumb, medium_thumb = media_processor.create_image_thumbnails(contents)
                
                # Загрузка small thumbnail
                small_filename = f"small_{unique_id}.jpg"
                small_thumbnail_key = media_processor.get_storage_path(
                    str(event_id), media_folder, "thumbnails", small_filename
                )
                await storage_service.upload_file(small_thumb, small_thumbnail_key, "image/jpeg")
                
                # Загрузка medium thumbnail
                medium_filename = f"medium_{unique_id}.jpg"
                medium_thumbnail_key = media_processor.get_storage_path(
                    str(event_id), media_folder, "thumbnails", medium_filename
                )
                await storage_service.upload_file(medium_thumb, medium_thumbnail_key, "image/jpeg")
                
            except Exception as e:
                print(f"Warning: Failed to create thumbnails for {filename}: {str(e)}")
        
        # Обработка PDF: извлечение первой страницы
        elif media_folder == "documents":
            try:
                preview_jpg = media_processor.extract_pdf_first_page(contents)
                
                preview_filename = f"{unique_id}.jpg"
                preview_key = media_processor.get_storage_path(
                    str(event_id), media_folder, "previews", preview_filename
                )
                await storage_service.upload_file(preview_jpg, preview_key, "image/jpeg")
                
            except Exception as e:
                print(f"Warning: Failed to extract PDF preview for {filename}: {str(e)}")
        
        # Создание записи в БД
        db_media = MediaItem(
            event_id=event_id,
            original_path=original_key,
            small_thumbnail_path=small_thumbnail_key,
            medium_thumbnail_path=medium_thumbnail_key,
            preview_path=preview_key,
            media_type=media_type,
            file_type=file_type,
            ai_status="pending"
        )
        
        db.add(db_media)
        await db.flush()
        uploaded_media_ids.append(db_media.id)
        
        # Запуск обработки лиц для фотографий
        if media_folder == "photos":
            temp_file_path = TEMP_DIR / f"{db_media.id}.{file_type}"
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
                "embedding_size": len(face.embedding) if face.embedding is not None else 0
            }
            for face in faces
        ]
    }


@router.get("/media/{media_item_id}/download")
async def download_original(
    media_item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Скачать оригинальный файл (полный размер).
    
    Возвращает публичный URL для скачивания оригинала.
    Используйте этот эндпоинт для кнопки "Скачать" в интерфейсе.
    """
    # Получение медиафайла
    result = await db.execute(
        select(MediaItem).where(MediaItem.id == media_item_id)
    )
    media_item = result.scalar_one_or_none()
    
    if not media_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media item not found"
        )
    
    # Генерация публичного URL
    storage_service = get_storage_service()
    download_url = storage_service.get_public_url(media_item.original_path)
    
    return {
        "media_item_id": media_item_id,
        "download_url": download_url,
        "media_type": media_item.media_type,
        "file_type": media_item.file_type
    }

