import uuid
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict, Field

# Organization schemas
class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=200, pattern="^[a-z0-9-]+$")
    description: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[EmailStr] = None

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[EmailStr] = None

class OrganizationResponse(OrganizationBase):
    id: uuid.UUID
    logo_path: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "user"  # user/photographer/organizer/admin
    organization_id: Optional[uuid.UUID] = None

class UserResponse(UserBase):
    id: uuid.UUID
    role: str
    organization_id: Optional[uuid.UUID] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[uuid.UUID] = None

# Event schemas
class PartnerData(BaseModel):
    """Информация о партнере мероприятия"""
    name: str
    logo_path: Optional[str] = None
    website: Optional[str] = None

class EventBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    event_date: Optional[date] = None
    location: Optional[str] = None
    status: Optional[str] = Field(default="draft", pattern="^(draft|published|archived)$")

class EventCreate(EventBase):
    organization_id: uuid.UUID

class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    event_date: Optional[date] = None
    location: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(draft|published|archived)$")
    partners_data: Optional[List[PartnerData]] = None

class EventResponse(EventBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    organizer_id: Optional[uuid.UUID] = None
    cover_image_path: Optional[str] = None
    map_image_path: Optional[str] = None
    partners_data: Optional[List[PartnerData]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Media schemas
class MediaItemResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    original_path: str
    small_thumbnail_path: Optional[str] = None  # Small preview for feed
    medium_thumbnail_path: Optional[str] = None  # Medium preview for viewing
    preview_path: Optional[str] = None  # For PDF first page or video poster
    media_type: str
    file_type: Optional[str] = None
    ai_status: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MediaUploadResponse(BaseModel):
    uploaded_count: int
    media_ids: list[uuid.UUID]

# Biometrics schemas
class BiometricsUploadResponse(BaseModel):
    status: str
    message: str
    confidence: float

class BiometricsInfoResponse(BaseModel):
    """
    Информация о биометрии пользователя.
    
    ⚠️ ВАЖНО: source_image_path всегда NULL
    Исходные селфи не хранятся (политика безопасности).
    Только векторы (эмбеддинги).
    """
    id: uuid.UUID
    user_id: uuid.UUID
    has_biometrics: bool
    source_image_path: Optional[str] = None  # Всегда NULL (не храним селфи)
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class BiometricsDeleteResponse(BaseModel):
    """Ответ на удаление биометрии"""
    status: str
    message: str
    deleted_biometrics: bool
    deleted_image_from_storage: bool

class ProfileDeleteResponse(BaseModel):
    """Ответ на удаление профиля"""
    status: str
    message: str
    deleted_user_id: uuid.UUID
    deleted_biometrics: bool
    deleted_events_count: int
    deleted_media_count: int

class DeactivateResponse(BaseModel):
    """Ответ на деактивацию профиля организатора"""
    status: str
    message: str
    user_id: uuid.UUID
    is_active: bool

# Feed schemas
class FaceMatchResult(BaseModel):
    media_item_id: uuid.UUID
    event_id: uuid.UUID
    event_title: str
    similarity_score: float
    small_thumbnail_path: Optional[str] = None  # Small preview for feed
    medium_thumbnail_path: Optional[str] = None  # Medium preview for viewing
    original_path: str

class MyMomentsResponse(BaseModel):
    total_matches: int
    matches: list[FaceMatchResult]

# Event Access schemas (photographer permissions)
class EventAccessCreate(BaseModel):
    """Предоставить фотографу доступ к событию"""
    event_id: uuid.UUID
    photographer_id: uuid.UUID

class EventAccessResponse(BaseModel):
    """Информация о доступе фотографа"""
    id: uuid.UUID
    event_id: uuid.UUID
    photographer_id: uuid.UUID
    granted_by: Optional[uuid.UUID] = None
    granted_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PhotographerWithAccess(BaseModel):
    """Фотограф с информацией о доступе"""
    user_id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    granted_at: datetime
    granted_by: Optional[uuid.UUID] = None
