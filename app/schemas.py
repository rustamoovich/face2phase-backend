import uuid
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "user"  # По умолчанию 'user', можно указать 'organizer' или 'admin'

class UserResponse(UserBase):
    id: uuid.UUID
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[uuid.UUID] = None

# Event schemas
class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    event_date: Optional[date] = None
    location: Optional[str] = None

class EventCreate(EventBase):
    pass

class EventResponse(EventBase):
    id: uuid.UUID
    organizer_id: uuid.UUID
    cover_image_path: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Media schemas
class MediaItemResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    original_path: str
    thumbnail_path: Optional[str] = None
    media_type: str
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

# Feed schemas
class FaceMatchResult(BaseModel):
    media_item_id: uuid.UUID
    event_id: uuid.UUID
    event_title: str
    similarity_score: float
    thumbnail_path: Optional[str] = None
    original_path: str

class MyMomentsResponse(BaseModel):
    total_matches: int
    matches: list[FaceMatchResult]

