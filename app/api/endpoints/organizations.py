"""
Endpoints для управления организациями.

Организации создают мероприятия и управляют фотографами.
"""
import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Organization, User
from app.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    UserCreate,
    UserResponse
)
from app.api.deps import get_current_user
from app.services.storage_service import get_storage_service
from app.core import security

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_in: OrganizationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Создать новую организацию.
    
    Требования:
    - Только admin может создавать организации
    - Slug должен быть уникальным (URL-friendly)
    """
    # Проверка прав
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create organizations"
        )
    
    # Проверка уникальности slug
    result = await db.execute(
        select(Organization).where(Organization.slug == org_in.slug)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization with slug '{org_in.slug}' already exists"
        )
    
    # Проверка уникальности имени
    result = await db.execute(
        select(Organization).where(Organization.name == org_in.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization with name '{org_in.name}' already exists"
        )
    
    # Создание организации
    org = Organization(
        name=org_in.name,
        slug=org_in.slug,
        description=org_in.description,
        website=org_in.website,
        contact_email=org_in.contact_email
    )
    
    db.add(org)
    await db.commit()
    await db.refresh(org)
    
    return org


@router.get("/", response_model=List[OrganizationResponse])
async def list_organizations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    include_inactive: bool = False
):
    """
    Получить список всех организаций.
    
    Параметры:
    - include_inactive: Включить неактивные организации (только для admin)
    """
    query = select(Organization)
    
    if not include_inactive:
        query = query.where(Organization.is_active == True)
    elif current_user.role != "admin":
        # Только admin может видеть неактивные организации
        query = query.where(Organization.is_active == True)
    
    result = await db.execute(query.order_by(Organization.name))
    organizations = result.scalars().all()
    
    return organizations


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Получить информацию об организации"""
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    return organization


@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: uuid.UUID,
    org_update: OrganizationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Обновить информацию об организации.
    
    Требования:
    - Только admin или organizer этой организации
    """
    # Получение организации
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Проверка прав
    if current_user.role != "admin":
        if current_user.role != "organizer" or current_user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough privileges"
            )
    
    # Обновление полей
    update_data = org_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(organization, field, value)
    
    await db.commit()
    await db.refresh(organization)
    
    return organization


@router.post("/{organization_id}/logo")
async def upload_organization_logo(
    organization_id: uuid.UUID,
    file: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Загрузить логотип организации.
    
    Сохраняется в R2: organizations/{organization_id}/logo.{ext}
    """
    # Получение организации
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Проверка прав
    if current_user.role != "admin":
        if current_user.role != "organizer" or current_user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough privileges"
            )
    
    # Проверка типа файла
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed"
        )
    
    # Определение расширения
    extension = "jpg"
    if file.content_type == "image/png":
        extension = "png"
    elif file.content_type == "image/gif":
        extension = "gif"
    elif file.content_type == "image/webp":
        extension = "webp"
    
    # Загрузка в R2
    storage_service = get_storage_service()
    logo_key = f"organizations/{organization_id}/logo.{extension}"
    
    try:
        contents = await file.read()
        await storage_service.upload_file(contents, logo_key, file.content_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload logo: {str(e)}"
        )
    
    # Обновление в БД
    organization.logo_path = logo_key
    await db.commit()
    
    return {
        "status": "success",
        "logo_path": logo_key,
        "logo_url": storage_service.get_public_url(logo_key)
    }


@router.delete("/{organization_id}")
async def deactivate_organization(
    organization_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Деактивировать организацию (soft delete).
    
    Требования:
    - Только admin
    - События организации остаются доступными
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can deactivate organizations"
        )
    
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    organization.is_active = False
    await db.commit()
    
    return {
        "status": "success",
        "message": f"Organization '{organization.name}' has been deactivated",
        "organization_id": organization_id
    }


@router.post("/{organization_id}/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_organization_user(
    organization_id: uuid.UUID,
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Создать пользователя внутри организации (organizer или photographer).
    
    Требования:
    - Только organizer этой организации или admin
    - Роль должна быть 'organizer' или 'photographer'
    - Email должен быть уникальным
    """
    # Получение организации
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Проверка прав
    if current_user.role != "admin":
        if current_user.role != "organizer" or current_user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organizers of this organization can create users"
            )
    
    # Проверка роли
    if user_in.role not in ["organizer", "photographer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'organizer' or 'photographer'"
        )
    
    # Проверка уникальности email
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Создание пользователя
    db_user = User(
        email=user_in.email,
        password_hash=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        organization_id=organization_id  # Привязка к организации
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return db_user


@router.get("/{organization_id}/users", response_model=List[UserResponse])
async def list_organization_users(
    organization_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    role: str | None = None
):
    """
    Получить список пользователей организации.
    
    Требования:
    - Organizer этой организации или admin
    
    Параметры:
    - role: Фильтр по роли (organizer/photographer)
    """
    # Получение организации
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Проверка прав
    if current_user.role != "admin":
        if current_user.role != "organizer" or current_user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organizers of this organization can view users"
            )
    
    # Запрос пользователей
    query = select(User).where(User.organization_id == organization_id)
    
    if role:
        if role not in ["organizer", "photographer"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role filter must be 'organizer' or 'photographer'"
            )
        query = query.where(User.role == role)
    
    result = await db.execute(query.order_by(User.created_at))
    users = result.scalars().all()
    
    return users


@router.patch("/{organization_id}/users/{user_id}/role")
async def update_user_role(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    new_role: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Изменить роль пользователя в организации.
    
    Требования:
    - Только organizer этой организации или admin
    - Можно менять только между organizer и photographer
    """
    # Получение организации
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Проверка прав
    if current_user.role != "admin":
        if current_user.role != "organizer" or current_user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organizers of this organization can change user roles"
            )
    
    # Проверка новой роли
    if new_role not in ["organizer", "photographer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'organizer' or 'photographer'"
        )
    
    # Получение пользователя
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == organization_id
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this organization"
        )
    
    # Обновление роли
    user.role = new_role
    await db.commit()
    await db.refresh(user)
    
    return {
        "status": "success",
        "message": f"User role updated to '{new_role}'",
        "user": UserResponse.model_validate(user)
    }
