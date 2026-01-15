import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.database import get_db
from app.models import Event, User, Organization, EventAccess
from app.schemas import EventCreate, EventUpdate, EventResponse
from app.api.deps import get_current_user
from app.services.storage_service import get_storage_service
from app.services.media_processing_service import MediaProcessingService

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_in: EventCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Создать новое мероприятие.
    
    Требования:
    - Роль organizer или admin
    - Organizer может создавать события только для своей организации
    - Admin может создавать для любой организации
    """
    # Проверка роли
    if current_user.role not in ['organizer', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers and admins can create events"
        )
    
    # Проверка организации для organizer
    if current_user.role == 'organizer':
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organizer must be assigned to an organization"
            )
        if current_user.organization_id != event_in.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create events for your own organization"
            )
    
    # Проверка существования организации
    result = await db.execute(
        select(Organization).where(Organization.id == event_in.organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    if not organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization is not active"
        )
    
    # Создание события
    db_event = Event(
        organization_id=event_in.organization_id,
        organizer_id=current_user.id,
        title=event_in.title,
        description=event_in.description,
        event_date=event_in.event_date,
        location=event_in.location,
        status=event_in.status or "draft"
    )
    
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    
    return db_event


@router.get("/", response_model=List[EventResponse])
async def list_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    organization_id: uuid.UUID | None = None
):
    """
    Получить список мероприятий.
    
    - Organizer: Видит события своей организации
    - Photographer: Видит события, к которым у него есть доступ
    - User: Видит только опубликованные события
    - Admin: Видит все события
    
    Параметры:
    - organization_id: Фильтр по организации (optional)
    """
    query = select(Event)
    
    if current_user.role == "admin":
        # Admin видит все
        pass
    elif current_user.role == "organizer":
        # Organizer видит события своей организации
        if not current_user.organization_id:
            return []
        query = query.where(Event.organization_id == current_user.organization_id)
    elif current_user.role == "photographer":
        # Photographer видит события, к которым у него есть доступ
        accessible_events = await db.execute(
            select(EventAccess.event_id).where(
                EventAccess.photographer_id == current_user.id
            )
        )
        event_ids = [row[0] for row in accessible_events.all()]
        if not event_ids:
            return []
        query = query.where(Event.id.in_(event_ids))
    else:
        # User видит только опубликованные
        query = query.where(Event.status == "published")
    
    # Фильтр по организации
    if organization_id:
        query = query.where(Event.organization_id == organization_id)
    
    result = await db.execute(query.order_by(Event.event_date.desc()))
    events = result.scalars().all()
    
    return events


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Получить информацию о мероприятии"""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Проверка прав просмотра
    if current_user.role == "user":
        if event.status != "published":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This event is not published"
            )
    
    return event


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    event_update: EventUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Обновить мероприятие.
    
    Требования:
    - Только organizer этой организации или admin
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Проверка прав
    if current_user.role != "admin":
        if current_user.role != "organizer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organizers can update events"
            )
        if current_user.organization_id != event.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update events for your own organization"
            )
    
    # Обновление полей
    update_data = event_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)
    
    await db.commit()
    await db.refresh(event)
    
    return event


@router.post("/{event_id}/assets/cover")
async def upload_event_cover(
    event_id: uuid.UUID,
    file: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Загрузить обложку мероприятия.
    
    Сохраняется в: events/{event_id}/assets/cover.{ext}
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Проверка прав
    if current_user.role != "admin":
        if current_user.role != "organizer" or current_user.organization_id != event.organization_id:
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
    
    storage_service = get_storage_service()
    media_processor = MediaProcessingService()
    
    # Определение расширения
    extension = "jpg"
    if file.content_type == "image/png":
        extension = "png"
    
    cover_key = f"events/{event_id}/assets/cover.{extension}"
    
    try:
        contents = await file.read()
        await storage_service.upload_file(contents, cover_key, file.content_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload cover: {str(e)}"
        )
    
    event.cover_image_path = cover_key
    await db.commit()
    
    return {
        "status": "success",
        "cover_path": cover_key,
        "cover_url": storage_service.get_public_url(cover_key)
    }


@router.post("/{event_id}/assets/map")
async def upload_event_map(
    event_id: uuid.UUID,
    file: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Загрузить карту местоположения.
    
    Сохраняется в: events/{event_id}/assets/map.{ext}
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Проверка прав
    if current_user.role != "admin":
        if current_user.role != "organizer" or current_user.organization_id != event.organization_id:
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
    
    storage_service = get_storage_service()
    
    extension = "jpg"
    if file.content_type == "image/png":
        extension = "png"
    
    map_key = f"events/{event_id}/assets/map.{extension}"
    
    try:
        contents = await file.read()
        await storage_service.upload_file(contents, map_key, file.content_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload map: {str(e)}"
        )
    
    event.map_image_path = map_key
    await db.commit()
    
    return {
        "status": "success",
        "map_path": map_key,
        "map_url": storage_service.get_public_url(map_key)
    }


@router.delete("/{event_id}")
async def delete_event(
    event_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Удалить мероприятие (только organizer/admin).
    
    ⚠️ Все медиафайлы события тоже будут удалены!
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Проверка прав
    if current_user.role != "admin":
        if current_user.role != "organizer" or current_user.organization_id != event.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough privileges"
            )
    
    # TODO: Удалить все медиафайлы из R2
    
    await db.delete(event)
    await db.commit()
    
    return {
        "status": "success",
        "message": f"Event '{event.title}' has been deleted",
        "event_id": event_id
    }

