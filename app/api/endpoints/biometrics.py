"""
Эндпоинты для биометрической аутентификации и поиска фото по лицу.
"""

import os
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import text

from app.database import get_db
from app.models import User, UserBiometrics, DetectedFace, MediaItem, Event
from app.schemas import BiometricsUploadResponse, MyMomentsResponse, FaceMatchResult
from app.api.deps import get_current_user
from app.services.face_service import get_face_service

router = APIRouter(prefix="/auth", tags=["biometrics"])
feed_router = APIRouter(prefix="/feed", tags=["feed"])

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)


@router.post("/biometrics", response_model=BiometricsUploadResponse)
async def upload_biometrics(
    file: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Загрузить селфи для биометрической идентификации.
    
    Требования:
    - На фото должно быть ровно одно лицо
    - Лицо должно быть четким (confidence > 0.8)
    - Фото будет использоваться как эталон для поиска
    """
    # Создание временного файла
    temp_filename = f"temp_{current_user.id}_{uuid.uuid4()}{Path(file.filename).suffix if file.filename else '.jpg'}"
    temp_path = TEMP_DIR / temp_filename
    
    try:
        # Сохранение файла
        contents = await file.read()
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        # Обработка через InsightFace с высоким порогом
        face_service = get_face_service()
        results = face_service.process_image(str(temp_path), min_confidence=0.8)
        
        # Валидация: должно быть ровно 1 лицо
        if len(results) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Лицо не обнаружено. Сделайте четкое селфи с хорошим освещением."
            )
        
        if len(results) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="На фото более одного человека. Сделайте одиночное селфи."
            )
        
        # Получаем единственное лицо
        face_data = results[0]
        
        # Проверяем, есть ли уже биометрия
        result = await db.execute(
            select(UserBiometrics).where(UserBiometrics.user_id == current_user.id)
        )
        existing_bio = result.scalar_one_or_none()
        
        if existing_bio:
            # Обновляем существующую запись
            existing_bio.embedding = face_data['embedding']
            existing_bio.source_image_path = f"biometrics/{current_user.id}.jpg"
        else:
            # Создаем новую запись
            new_bio = UserBiometrics(
                user_id=current_user.id,
                embedding=face_data['embedding'],
                source_image_path=f"biometrics/{current_user.id}.jpg"
            )
            db.add(new_bio)
        
        await db.commit()
        
        return BiometricsUploadResponse(
            status="success",
            message="Биометрия успешно сохранена",
            confidence=face_data['confidence']
        )
        
    finally:
        # Удаляем временный файл
        if temp_path.exists():
            os.remove(temp_path)


@feed_router.get("/my-moments", response_model=MyMomentsResponse)
async def get_my_moments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    threshold: float = 0.4,
    limit: int = 100
):
    """
    Получить все фото, где найдено лицо текущего пользователя.
    
    Использует векторный поиск через pgvector для нахождения похожих лиц.
    
    Args:
        threshold: Порог схожести (0.0-1.0). Меньше = строже. По умолчанию 0.4.
        limit: Максимальное количество результатов. По умолчанию 100.
    """
    # Получаем биометрию пользователя
    result = await db.execute(
        select(UserBiometrics).where(UserBiometrics.user_id == current_user.id)
    )
    user_bio = result.scalar_one_or_none()
    
    if not user_bio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Биометрия не найдена. Сначала загрузите селфи через /auth/biometrics"
        )
    
    # Векторный поиск через pgvector
    # Преобразуем вектор в правильный формат: [1.0, 2.0, 3.0, ...]
    # pgvector не понимает научную нотацию NumPy
    
    # Получаем список чисел из вектора
    if hasattr(user_bio.embedding, 'tolist'):
        # Если это numpy array
        embedding_list = user_bio.embedding.tolist()
    elif isinstance(user_bio.embedding, list):
        embedding_list = user_bio.embedding
    else:
        # Если это строка или другой тип, пытаемся преобразовать
        embedding_list = list(user_bio.embedding)
    
    # Форматируем как строку для pgvector: '[1.0,2.0,3.0,...]'
    embedding_str = '[' + ','.join(str(float(x)) for x in embedding_list) + ']'
    
    query = text("""
        SELECT 
            df.id as face_id,
            df.media_item_id,
            mi.event_id,
            mi.original_path,
            mi.thumbnail_path,
            e.title as event_title,
            df.embedding <=> :user_embedding as distance
        FROM detected_faces df
        JOIN media_items mi ON df.media_item_id = mi.id
        JOIN events e ON mi.event_id = e.id
        WHERE df.embedding <=> :user_embedding < :threshold
        ORDER BY df.embedding <=> :user_embedding ASC
        LIMIT :limit
    """)
    
    result = await db.execute(
        query,
        {
            "user_embedding": embedding_str,
            "threshold": threshold,
            "limit": limit
        }
    )
    
    matches_raw = result.fetchall()
    
    # Формирование ответа
    matches = []
    for row in matches_raw:
        matches.append(FaceMatchResult(
            media_item_id=row.media_item_id,
            event_id=row.event_id,
            event_title=row.event_title,
            similarity_score=1.0 - float(row.distance),  # Преобразуем distance в similarity
            thumbnail_path=row.thumbnail_path,
            original_path=row.original_path
        ))
    
    return MyMomentsResponse(
        total_matches=len(matches),
        matches=matches
    )

