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

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    biometrics: Mapped[List["UserBiometrics"]] = relationship("UserBiometrics", back_populates="user", cascade="all, delete-orphan")
    events: Mapped[List["Event"]] = relationship("Event", back_populates="organizer")


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
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organizer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    event_date: Mapped[Optional[date]] = mapped_column(Date)
    location: Mapped[Optional[str]] = mapped_column(String(200))
    cover_image_path: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    organizer: Mapped["User"] = relationship("User", back_populates="events")
    media_items: Mapped[List["MediaItem"]] = relationship("MediaItem", back_populates="event", cascade="all, delete-orphan")


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


