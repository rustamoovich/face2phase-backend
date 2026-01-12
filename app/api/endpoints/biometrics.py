"""
Эндпоинты для биометрической аутентификации и поиска фото по лицу.

⚠️ ПОЛИТИКА БЕЗОПАСНОСТИ БИОМЕТРИИ:
- Исходные селфи НЕ сохраняются (ни в R2, ни где-либо еще)
- Хранятся ТОЛЬКО 512-мерные векторы (эмбеддинги)
- Невозможно восстановить изображение лица из эмбеддинга
- Соответствует требованиям GDPR и биометрической безопасности
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
from app.schemas import (
    BiometricsUploadResponse, 
    BiometricsInfoResponse,
    BiometricsDeleteResponse,
    MyMomentsResponse, 
    FaceMatchResult
)
from app.api.deps import get_current_user
from app.services.face_service import get_face_service

router = APIRouter(prefix="/auth", tags=["biometrics"])
feed_router = APIRouter(prefix="/feed", tags=["feed"])

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)


@router.get("/biometrics", response_model=BiometricsInfoResponse)
async def get_biometrics_info(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Получить информацию о биометрии текущего пользователя.
    
    Возвращает:
    - Статус наличия биометрии (есть/нет вектор)
    - Дату создания/обновления биометрии
    
    ⚠️ ВАЖНО:
    - Исходные селфи НЕ хранятся (только векторы)
    - source_image_path всегда NULL (политика безопасности)
    """
    result = await db.execute(
        select(UserBiometrics).where(UserBiometrics.user_id == current_user.id)
    )
    user_bio = result.scalar_one_or_none()
    
    if not user_bio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Биометрия не найдена. Загрузите селфи через POST /auth/biometrics"
        )
    
    return BiometricsInfoResponse(
        id=user_bio.id,
        user_id=user_bio.user_id,
        has_biometrics=user_bio.embedding is not None,
        source_image_path=None,  # Всегда NULL (не храним селфи)
        created_at=user_bio.created_at
    )


@router.post("/biometrics", response_model=BiometricsUploadResponse)
async def create_biometrics(
    file: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Загрузить селфи для биометрической идентификации (первичная загрузка).
    
    Требования:
    - На фото должно быть ровно одно лицо
    - Лицо должно быть четким (confidence > 0.8)
    - Файл обрабатывается и УДАЛЯЕТСЯ
    - В БД сохраняется ТОЛЬКО 512-мерный вектор (эмбеддинг)
    
    ⚠️ БЕЗОПАСНОСТЬ:
    - Исходное селфи НЕ сохраняется
    - Невозможно восстановить лицо из эмбеддинга
    - Соответствует требованиям GDPR и биометрической безопасности
    
    Примечание: Если биометрия уже существует, используйте PUT /auth/biometrics
    """
    # Создание временного файла для обработки
    temp_filename = f"temp_{current_user.id}_{uuid.uuid4()}{Path(file.filename).suffix if file.filename else '.jpg'}"
    temp_path = TEMP_DIR / temp_filename
    
    try:
        # Чтение файла
        contents = await file.read()
        
        # Сохранение временного файла для обработки
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
        
        # ⚠️ ВАЖНО: Селфи НЕ сохраняется!
        # Сохраняем ТОЛЬКО эмбеддинг (512 чисел)
        
        # Проверяем, есть ли уже биометрия
        result = await db.execute(
            select(UserBiometrics).where(UserBiometrics.user_id == current_user.id)
        )
        existing_bio = result.scalar_one_or_none()
        
        if existing_bio:
            # Обновляем существующую запись
            existing_bio.embedding = face_data['embedding']
            existing_bio.source_image_path = None  # Не храним путь к файлу
        else:
            # Создаем новую запись
            new_bio = UserBiometrics(
                user_id=current_user.id,
                embedding=face_data['embedding'],
                source_image_path=None  # Не храним путь к файлу
            )
            db.add(new_bio)
        
        await db.commit()
        
        return BiometricsUploadResponse(
            status="success",
            message="Биометрия успешно сохранена (только вектор, исходное фото удалено)",
            confidence=face_data['confidence']
        )
        
    finally:
        # КРИТИЧНО: Удаляем временный файл
        if temp_path.exists():
            os.remove(temp_path)


@router.put("/biometrics", response_model=BiometricsUploadResponse)
async def update_biometrics(
    file: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Обновить селфи для биометрической идентификации.
    
    Использование:
    - Когда пользователь хочет обновить свое эталонное селфи
    - При изменении внешности (новая прическа, борода и т.д.)
    
    Требования:
    - На фото должно быть ровно одно лицо
    - Лицо должно быть четким (confidence > 0.8)
    - Файл обрабатывается и УДАЛЯЕТСЯ
    - В БД сохраняется ТОЛЬКО обновленный вектор
    
    ⚠️ БЕЗОПАСНОСТЬ:
    - Исходное селфи НЕ сохраняется
    - Старый эмбеддинг заменяется на новый
    """
    # Проверяем, существует ли биометрия
    result = await db.execute(
        select(UserBiometrics).where(UserBiometrics.user_id == current_user.id)
    )
    existing_bio = result.scalar_one_or_none()
    
    if not existing_bio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Биометрия не найдена. Используйте POST /auth/biometrics для первичной загрузки"
        )
    
    # Создание временного файла для обработки
    temp_filename = f"temp_{current_user.id}_{uuid.uuid4()}{Path(file.filename).suffix if file.filename else '.jpg'}"
    temp_path = TEMP_DIR / temp_filename
    
    try:
        # Чтение файла
        contents = await file.read()
        
        # Сохранение временного файла для обработки
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
        
        # Обновляем только эмбеддинг (НЕ сохраняем файл!)
        existing_bio.embedding = face_data['embedding']
        existing_bio.source_image_path = None
        
        await db.commit()
        
        return BiometricsUploadResponse(
            status="success",
            message="Биометрия успешно обновлена (только вектор, исходное фото удалено)",
            confidence=face_data['confidence']
        )
        
    finally:
        # КРИТИЧНО: Удаляем временный файл
        if temp_path.exists():
            os.remove(temp_path)


@router.delete("/biometrics", response_model=BiometricsDeleteResponse)
async def delete_biometrics(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Удалить все биометрические данные текущего пользователя (Hard Delete).
    
    Что удаляется:
    - 512-мерный эмбеддинг лица из базы данных
    
    Что НЕ удаляется (так как не хранится):
    - Исходное селфи (никогда не сохранялось в соответствии с политикой безопасности)
    
    Примечание:
    - После удаления вы не сможете использовать "Мои моменты"
    - Для восстановления потребуется заново загрузить селфи
    """
    # Получаем биометрию пользователя
    result = await db.execute(
        select(UserBiometrics).where(UserBiometrics.user_id == current_user.id)
    )
    user_bio = result.scalar_one_or_none()
    
    if not user_bio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Биометрия не найдена"
        )
    
    # Удаление из базы данных
    await db.delete(user_bio)
    await db.commit()
    
    return BiometricsDeleteResponse(
        status="success",
        message="Биометрический вектор удален безвозвратно",
        deleted_biometrics=True,
        deleted_image_from_storage=False  # Никогда не хранили
    )


@feed_router.get("/my-moments", response_model=MyMomentsResponse)
async def get_my_moments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    threshold: float = 0.4,
    limit: int = 100,
    ef_search: int = 100
):
    """
    Получить все фото, где найдено лицо текущего пользователя.
    
    Использует HNSW индексирование через pgvector для быстрого векторного поиска.
    
    Args:
        threshold: Порог схожести (0.0-1.0). Меньше = строже. По умолчанию 0.4.
        limit: Максимальное количество результатов. По умолчанию 100.
        ef_search: Параметр точности HNSW (40-200). Больше = точнее, но медленнее. По умолчанию 100.
    
    Performance:
        - < 10ms для 100K векторов
        - < 50ms для 1M векторов
    """
    # Настройка HNSW параметров для текущей сессии
    await db.execute(text(f"SET hnsw.ef_search = {ef_search}"))
    
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
    
    # Преобразуем вектор в правильный формат: [1.0, 2.0, 3.0, ...]
    if hasattr(user_bio.embedding, 'tolist'):
        embedding_list = user_bio.embedding.tolist()
    elif isinstance(user_bio.embedding, list):
        embedding_list = user_bio.embedding
    else:
        embedding_list = list(user_bio.embedding)
    
    # Форматируем как строку для pgvector: '[1.0,2.0,3.0,...]'
    embedding_str = '[' + ','.join(str(float(x)) for x in embedding_list) + ']'
    
    # Векторный поиск с HNSW индексом
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

