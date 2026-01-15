import uuid
from datetime import datetime, date
from typing import Optional, List

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    String, 
    DateTime, 
    Date, 
    Text, 
    Float, 
    Boolean,
    ForeignKey,
    func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Organization(Base):
    """
    Организация (компания/сообщество), которая создает мероприятия.
    
    Примеры: "PhotoStudio Pro", "TechConf Organizers", "Wedding Agency"
    """
    __tablename__ = "organizations"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)  # URL-friendly name
    description: Mapped[Optional[str]] = mapped_column(Text)
    logo_path: Mapped[Optional[str]] = mapped_column(String(255))  # R2 path
    website: Mapped[Optional[str]] = mapped_column(String(255))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="organization")
    events: Mapped[List["Event"]] = relationship("Event", back_populates="organization")


class User(Base):
    """
    Пользователь системы.
    
    Роли:
    - user: Обычный пользователь (участник мероприятий)
    - photographer: Фотограф, загружает медиа (привязан к организации)
    - organizer: Администратор организации (может создавать события)
    - admin: Суперадмин платформы
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), server_default="user")  # user/photographer/organizer/admin
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship("Organization", back_populates="users")
    biometrics: Mapped[List["UserBiometrics"]] = relationship("UserBiometrics", back_populates="user", cascade="all, delete-orphan")
    events: Mapped[List["Event"]] = relationship("Event", back_populates="organizer")
    event_access: Mapped[List["EventAccess"]] = relationship("EventAccess", back_populates="photographer", foreign_keys="EventAccess.photographer_id", cascade="all, delete-orphan")


class UserBiometrics(Base):
    __tablename__ = "user_biometrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    
    # Цифровой слепок лица (модель InsightFace)
    embedding: Mapped[Optional[Vector]] = mapped_column(Vector(512))
    
    # Ссылка на исходное селфи в Cloudflare R2
    source_image_path: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="biometrics")


class Event(Base):
    """
    Мероприятие с медиафайлами и статикой для оформления.
    """
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    organizer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))  # Кто конкретно создал
    
    # Основная информация
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    event_date: Mapped[Optional[date]] = mapped_column(Date)
    location: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), server_default="draft")  # draft/published/archived
    
    # Статика для оформления (R2 paths в events/{event_id}/assets/)
    cover_image_path: Mapped[Optional[str]] = mapped_column(String(255))  # Обложка события
    map_image_path: Mapped[Optional[str]] = mapped_column(String(255))  # Карта местоположения
    partners_data: Mapped[Optional[dict]] = mapped_column(JSONB)  # Список партнеров [{name, logo_path, website}]
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="events")
    organizer: Mapped[Optional["User"]] = relationship("User", back_populates="events")
    media_items: Mapped[List["MediaItem"]] = relationship("MediaItem", back_populates="event", cascade="all, delete-orphan")
    photographer_access: Mapped[List["EventAccess"]] = relationship("EventAccess", back_populates="event", cascade="all, delete-orphan")


class MediaItem(Base):
    __tablename__ = "media_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    
    # Paths in R2 storage
    original_path: Mapped[str] = mapped_column(String(255), nullable=False)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(255))  # For backward compatibility
    small_thumbnail_path: Mapped[Optional[str]] = mapped_column(String(255))  # Small preview for feed
    medium_thumbnail_path: Mapped[Optional[str]] = mapped_column(String(255))  # Medium preview for viewing
    preview_path: Mapped[Optional[str]] = mapped_column(String(255))  # For PDF first page or video poster
    
    # Media classification
    media_type: Mapped[str] = mapped_column(String(10), server_default="image")  # image/video/document
    file_type: Mapped[Optional[str]] = mapped_column(String(50))  # jpg, mp4, pdf, etc.
    
    # AI processing status
    ai_status: Mapped[str] = mapped_column(String(20), server_default="pending")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="media_items")
    detected_faces: Mapped[List["DetectedFace"]] = relationship("DetectedFace", back_populates="media_item", cascade="all, delete-orphan")


class DetectedFace(Base):
    __tablename__ = "detected_faces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"))
    
    # Вектор лица, найденного на фото
    embedding: Mapped[Optional[Vector]] = mapped_column(Vector(512))
    
    # Координаты лица на фото (Bounding Boxes)
    bounding_box: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Уверенность нейросети (от 0 до 1)
    confidence: Mapped[Optional[float]] = mapped_column(Float)

    # Relationships
    media_item: Mapped["MediaItem"] = relationship("MediaItem", back_populates="detected_faces")


class EventAccess(Base):
    """
    Права фотографа на доступ к конкретному мероприятию.
    
    Фотограф может загружать медиа только в те события, к которым у него есть доступ.
    Организатор предоставляет доступ через API.
    """
    __tablename__ = "event_access"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    photographer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    granted_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))  # Кто предоставил доступ
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="photographer_access")
    photographer: Mapped["User"] = relationship("User", back_populates="event_access", foreign_keys=[photographer_id])


