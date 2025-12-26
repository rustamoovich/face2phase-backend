from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Event, User
from app.schemas import EventCreate, EventResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/events", tags=["events"])

@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_in: EventCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Создать новое мероприятие.
    organizer_id устанавливается автоматически из текущего пользователя.
    
    Требуется роль: organizer или admin
    """
    # Проверка прав доступа
    if current_user.role not in ['organizer', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges"
        )
    
    db_event = Event(
        title=event_in.title,
        description=event_in.description,
        event_date=event_in.event_date,
        location=event_in.location,
        organizer_id=current_user.id
    )
    
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    
    return db_event

@router.get("/", response_model=List[EventResponse])
async def get_my_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Получить список мероприятий текущего пользователя.
    """
    result = await db.execute(
        select(Event).where(Event.organizer_id == current_user.id)
    )
    events = result.scalars().all()
    return events

