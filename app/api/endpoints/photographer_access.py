"""
Endpoints для управления доступом фотографов к мероприятиям.

Организаторы могут предоставлять/отзывать доступ фотографов.
"""
import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.models import EventAccess, Event, User
from app.schemas import (
    EventAccessCreate,
    EventAccessResponse,
    PhotographerWithAccess
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/events", tags=["photographer-access"])


@router.post("/{event_id}/photographers", response_model=EventAccessResponse, status_code=status.HTTP_201_CREATED)
async def grant_photographer_access(
    event_id: uuid.UUID,
    photographer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Предоставить фотографу доступ к мероприятию.
    
    Требования:
    - Только organizer этой организации или admin
    - Фотограф должен принадлежать к той же организации
    """
    # Получение события
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
                detail="Only organizers can manage photographer access"
            )
        if current_user.organization_id != event.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage photographers for your organization's events"
            )
    
    # Получение фотографа
    result = await db.execute(select(User).where(User.id == photographer_id))
    photographer = result.scalar_one_or_none()
    
    if not photographer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photographer not found"
        )
    
    # Проверка роли фотографа
    if photographer.role != "photographer":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must have 'photographer' role"
        )
    
    # Проверка принадлежности к организации
    if photographer.organization_id != event.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photographer must belong to the same organization as the event"
        )
    
    # Проверка существующего доступа
    result = await db.execute(
        select(EventAccess).where(
            and_(
                EventAccess.event_id == event_id,
                EventAccess.photographer_id == photographer_id
            )
        )
    )
    existing_access = result.scalar_one_or_none()
    
    if existing_access:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photographer already has access to this event"
        )
    
    # Создание доступа
    access = EventAccess(
        event_id=event_id,
        photographer_id=photographer_id,
        granted_by=current_user.id
    )
    
    db.add(access)
    await db.commit()
    await db.refresh(access)
    
    return access


@router.get("/{event_id}/photographers", response_model=List[PhotographerWithAccess])
async def list_event_photographers(
    event_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Получить список фотографов с доступом к мероприятию.
    
    Требования:
    - Organizer этой организации или admin
    """
    # Получение события
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
                detail="Only organizers can view photographer access"
            )
        if current_user.organization_id != event.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view photographers for your organization's events"
            )
    
    # Получение списка с join
    query = select(EventAccess, User).join(
        User, EventAccess.photographer_id == User.id
    ).where(EventAccess.event_id == event_id)
    
    result = await db.execute(query)
    rows = result.all()
    
    photographers = []
    for access, user in rows:
        photographers.append(PhotographerWithAccess(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            granted_at=access.granted_at,
            granted_by=access.granted_by
        ))
    
    return photographers


@router.delete("/{event_id}/photographers/{photographer_id}")
async def revoke_photographer_access(
    event_id: uuid.UUID,
    photographer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Отозвать доступ фотографа к мероприятию.
    
    Требования:
    - Только organizer этой организации или admin
    """
    # Получение события
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
                detail="Only organizers can manage photographer access"
            )
        if current_user.organization_id != event.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage photographers for your organization's events"
            )
    
    # Получение доступа
    result = await db.execute(
        select(EventAccess).where(
            and_(
                EventAccess.event_id == event_id,
                EventAccess.photographer_id == photographer_id
            )
        )
    )
    access = result.scalar_one_or_none()
    
    if not access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photographer does not have access to this event"
        )
    
    await db.delete(access)
    await db.commit()
    
    return {
        "status": "success",
        "message": "Photographer access revoked",
        "event_id": event_id,
        "photographer_id": photographer_id
    }


@router.get("/my-events")
async def get_my_accessible_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Получить список событий, к которым у фотографа есть доступ.
    
    Только для роли 'photographer'.
    Возвращает полную информацию о событиях.
    """
    if current_user.role != "photographer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only for photographers"
        )
    
    # Получаем event_id из EventAccess
    access_result = await db.execute(
        select(EventAccess.event_id).where(
            EventAccess.photographer_id == current_user.id
        )
    )
    event_ids = [row[0] for row in access_result.all()]
    
    if not event_ids:
        return []
    
    # Получаем полную информацию о событиях
    events_result = await db.execute(
        select(Event).where(Event.id.in_(event_ids)).order_by(Event.event_date.desc())
    )
    events = events_result.scalars().all()
    
    # Преобразуем в словари для корректной сериализации
    from app.schemas import EventResponse
    return [EventResponse.model_validate(event) for event in events]
