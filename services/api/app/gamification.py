from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .userdb.database import get_db
from .userdb.models import (
    Badge,
    GamificationEventType,
    GamificationState,
    StudentBadge,
)

router = APIRouter(prefix="/gamification", tags=["gamification"])


class GamificationEventIn(BaseModel):
    student_id: int
    event_type: str


class GamificationEventOut(BaseModel):
    student_id: int
    points: int
    level: int
    new_badges: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True

@router.post("/event", response_model=GamificationEventOut)
def handle_event(payload: GamificationEventIn, db: Session = Depends(get_db)):
    event = (
        db.query(GamificationEventType)
        .filter(GamificationEventType.key == payload.event_type)
        .first()
    )
    if not event:
        raise HTTPException(status_code=400, detail="Unknown event_type")

    state = (
        db.query(GamificationState)
        .filter(GamificationState.student_id == payload.student_id)
        .first()
    )
    if not state:
        state = GamificationState(student_id=payload.student_id, points=0, level=1)
        db.add(state)

    # Punkte anwenden
    state.points += event.base_points
    # optional: simple Level-Logik
    # state.level = 1 + state.points

    new_badges: list[str] = [] # TODO Badges

    if event.badge_id is not None:
        already = (
            db.query(StudentBadge)
            .filter(
                StudentBadge.student_id == payload.student_id,
                StudentBadge.badge_id == event.badge_id,
            )
            .first()
        )
        if not already:
            sb = StudentBadge(
                student_id=payload.student_id,
                badge_id=event.badge_id,
                source_event_key=event.key,
            )
            db.add(sb)
            badge = db.query(Badge).get(event.badge_id)
            if badge:
                new_badges.append(badge.key)

    db.commit()
    db.refresh(state)

    return GamificationEventOut(
        student_id=payload.student_id,
        points=state.points,
        level=state.level,
        new_badges=new_badges,
    )
class GamificationStateOut(BaseModel):
    student_id: int
    points: int
    level: int
    badges: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True

@router.get("/state", response_model=GamificationStateOut)
def get_state(student_id: int, db: Session = Depends(get_db)):
    state = (
        db.query(GamificationState)
        .filter(GamificationState.student_id == student_id)
        .first()
    )
    if not state:
        return GamificationStateOut(
            student_id=student_id,
            points=0,
            level=1,
            badges=[],
        )

    # Badges holen
    joins = (
        db.query(StudentBadge, Badge)
        .join(Badge, StudentBadge.badge_id == Badge.id)
        .filter(StudentBadge.student_id == student_id)
        .all()
    )
    badge_keys = [b.key for (_, b) in joins]

    return GamificationStateOut(
        student_id=student_id,
        points=state.points,
        level=state.level,
        badges=badge_keys,
    )
