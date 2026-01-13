from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta
from typing import Annotated
import uuid

from app.database import get_db, settings
from app.models import User, UserBiometrics, Event, MediaItem
from app.schemas import UserCreate, UserResponse, Token, ProfileDeleteResponse, DeactivateResponse
from app.core import security
from app.api.deps import get_current_user
from app.services.storage_service import get_storage_service

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    # ... (код регистрации остается прежним)
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    db_user = User(
        email=user_in.email,
        password_hash=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role  # Поддержка указания роли при регистрации
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return db_user

@router.post("/login", response_model=Token)
async def login(
    db: Annotated[AsyncSession, Depends(get_db)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    """
    Вход в систему.
    
    Автоматическая реактивация:
    - Если пользователь был деактивирован, профиль автоматически активируется
    - Это позволяет организаторам легко восстановить доступ
    """
    # Поиск пользователя
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not security.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Автоматическая реактивация при входе
    if not user.is_active:
        user.is_active = True
        await db.commit()
        await db.refresh(user)
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return current_user


@router.delete("/profile", response_model=ProfileDeleteResponse)
async def delete_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Полное удаление профиля пользователя (Hard Delete).
    
    ⚠️ ВНИМАНИЕ: Это действие необратимо!
    
    Доступно только для обычных пользователей (role='user').
    Организаторы должны использовать /auth/deactivate.
    
    Что удаляется:
    - Аккаунт пользователя
    - Биометрические данные (только эмбеддинги, исходные селфи не хранятся)
    - Мероприятия (если пользователь - организатор)
    - Медиафайлы мероприятий (из БД и R2)
    - Найденные лица на фото
    
    Примечание:
    - После удаления вы не сможете войти в систему
    - Все связанные данные будут удалены из-за CASCADE
    """
    # Проверка: организаторы НЕ могут удалить профиль
    if current_user.role in ['organizer', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Организаторы не могут удалить профиль. Используйте /auth/deactivate для деактивации."
        )
    
    user_id = current_user.id
    
    # 1. Подсчет удаляемых данных
    events_result = await db.execute(
        select(Event).where(Event.organizer_id == user_id)
    )
    user_events = events_result.scalars().all()
    events_count = len(user_events)
    
    media_count = 0
    storage_service = get_storage_service()
    
    # 2. Удаление медиафайлов из R2 (если пользователь создавал мероприятия)
    files_to_delete = []
    for event in user_events:
        media_result = await db.execute(
            select(MediaItem).where(MediaItem.event_id == event.id)
        )
        media_items = media_result.scalars().all()
        media_count += len(media_items)
        
        # Собираем все файлы для удаления
        for media in media_items:
            # Оригинал
            if media.original_path:
                files_to_delete.append(media.original_path)
            # Thumbnails
            if media.small_thumbnail_path:
                files_to_delete.append(media.small_thumbnail_path)
            if media.medium_thumbnail_path:
                files_to_delete.append(media.medium_thumbnail_path)
            # Preview (для PDF)
            if media.preview_path:
                files_to_delete.append(media.preview_path)
    
    # Удаляем все файлы разом (batch delete)
    if files_to_delete:
        try:
            await storage_service.delete_multiple_files(files_to_delete)
        except Exception as e:
            print(f"Warning: Failed to delete media from storage: {e}")
    
    # 3. Проверка биометрии (но НЕ удаляем из R2, так как там нет селфи)
    bio_result = await db.execute(
        select(UserBiometrics).where(UserBiometrics.user_id == user_id)
    )
    user_bio = bio_result.scalar_one_or_none()
    deleted_biometrics = user_bio is not None
    
    # 4. Удаление пользователя (CASCADE удалит все связанные данные)
    await db.delete(current_user)
    await db.commit()
    
    return ProfileDeleteResponse(
        status="success",
        message="Профиль и все связанные данные удалены безвозвратно",
        deleted_user_id=user_id,
        deleted_biometrics=deleted_biometrics,
        deleted_events_count=events_count,
        deleted_media_count=media_count
    )


@router.delete("/deactivate", response_model=DeactivateResponse)
async def deactivate_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Деактивация профиля организатора (Soft Delete).
    
    Доступно только для организаторов и администраторов.
    
    Что происходит:
    - Устанавливается is_active = False
    - JWT токен становится недействительным
    - Мероприятия и медиа остаются доступными для пользователей
    - Ничего не удаляется физически
    
    Реактивация:
    - При повторном входе (POST /auth/login) профиль автоматически активируется
    
    Примечание:
    - После деактивации необходимо выполнить logout на клиенте
    - Все данные сохраняются (защита данных пользователей)
    """
    # Проверка: только организаторы и администраторы
    if current_user.role not in ['organizer', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только организаторы и администраторы могут деактивировать профиль. Обычные пользователи должны использовать /auth/profile для удаления."
        )
    
    # Деактивация профиля
    current_user.is_active = False
    await db.commit()
    await db.refresh(current_user)
    
    return DeactivateResponse(
        status="success",
        message="Профиль деактивирован. Для активации войдите в систему повторно.",
        user_id=current_user.id,
        is_active=current_user.is_active
    )

