from io import StringIO
import csv
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db
from .security import hash_password, verify_password
from .models import Teacher, PasswordResetToken

from pathlib import Path
from ..media import Media

router = APIRouter(prefix="/api")


# ---------------- Password Reset ----------------

class PasswordResetRequestIn(BaseModel):
    email: EmailStr


@router.post("/auth/request-password-reset")
def request_password_reset(
    payload: PasswordResetRequestIn,
    db: Session = Depends(get_db),
):
    teacher = db.query(Teacher).filter(Teacher.email == payload.email).first()
    if not teacher:
        return {"status": "ok"}

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    reset = PasswordResetToken(
        teacher_id=teacher.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    db.add(reset)
    db.commit()

    return {"status": "ok", "reset_token": raw_token}  # NUR Demo!


class PasswordResetConfirmIn(BaseModel):
    token: str
    new_password: str


@router.post("/auth/reset-password")
def reset_password(
    payload: PasswordResetConfirmIn,
    db: Session = Depends(get_db),
):
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()

    reset = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first()
    )
    if not reset or reset.used_at is not None or reset.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    teacher = db.get(Teacher, reset.teacher_id)
    if not teacher:
        raise HTTPException(status_code=400, detail="Invalid token")

    teacher.password_hash = hash_password(payload.new_password)
    reset.used_at = datetime.utcnow()

    db.commit()
    return {"status": "ok"}


# ---------------- Teacher ----------------

@router.post("/teachers/register", response_model=schemas.TeacherOut)
def register_teacher(
    payload: schemas.TeacherCreate,
    creator_id: int,
    db: Session = Depends(get_db),
):
    creator = db.query(models.Teacher).filter(models.Teacher.id == creator_id).first()
    if not creator or creator.role != "dev":
        raise HTTPException(status_code=403, detail="Only dev/admin may register teachers")

    existing = db.query(models.Teacher).filter(models.Teacher.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Teacher with this email already exists")

    teacher = models.Teacher(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="teacher",
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


@router.get("/teachers", response_model=List[schemas.TeacherOut])
def list_teachers(
    creator_id: int,
    db: Session = Depends(get_db),
):
    creator = db.query(Teacher).filter(Teacher.id == creator_id).first()
    if not creator or creator.role != "dev":
        raise HTTPException(status_code=403, detail="Only dev/admin may list teachers")

    return db.query(Teacher).filter(Teacher.role == "teacher").all()


@router.delete("/teachers/{teacher_id}")
def delete_teacher(
    teacher_id: int,
    creator_id: int,
    db: Session = Depends(get_db),
):
    creator = db.query(Teacher).filter(Teacher.id == creator_id).first()
    if not creator or creator.role != "dev":
        raise HTTPException(status_code=403, detail="Only dev/admin may delete teachers")

    if teacher_id == creator_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own dev account")

    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    if teacher.role == "dev":
        raise HTTPException(status_code=400, detail="Cannot delete dev/admin accounts")

    class_count = db.query(models.Class).filter(models.Class.teacher_id == teacher_id).count()
    if class_count > 0:
        raise HTTPException(status_code=400, detail="Teacher still owns classes. Delete classes first.")

    db.delete(teacher)
    db.commit()
    return {"status": "deleted", "id": teacher_id}


@router.post("/auth/dev-login")
def dev_login(payload: schemas.TeacherLogin, db: Session = Depends(get_db)):
    teacher = db.query(models.Teacher).filter(models.Teacher.email == payload.email).first()

    if not teacher or not verify_password(payload.password, teacher.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if teacher.role != "dev":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a dev/admin account")

    return {"dev_id": teacher.id, "role": teacher.role}


# ---------------- Student Login ----------------

@router.post("/auth/student-login")
def student_login(payload: schemas.StudentLogin, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.username == payload.username).first()
    if not student or not verify_password(payload.password, student.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return {"student_id": student.id, "class_id": student.class_id, "role": "student"}


@router.post("/auth/login")
def login_teacher(payload: schemas.TeacherLogin, db: Session = Depends(get_db)):
    teacher = db.query(models.Teacher).filter(models.Teacher.email == payload.email).first()

    if not teacher or not verify_password(payload.password, teacher.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if teacher.role != "teacher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Use /api/auth/dev-login for dev/admin accounts")

    return {"teacher_id": teacher.id, "role": teacher.role}


# ---------------- Classes ----------------

@router.post("/classes", response_model=schemas.ClassOut)
def create_class(payload: schemas.ClassCreate, db: Session = Depends(get_db)):
    teacher = db.query(models.Teacher).filter(models.Teacher.id == payload.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    cls = models.Class(
        name=payload.name,
        teacher_id=payload.teacher_id,
        grade_level=payload.grade_level,
        subject=payload.subject,
    )
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return cls


@router.get("/classes", response_model=List[schemas.ClassOut])
def list_classes(teacher_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Class)
    if teacher_id is not None:
        query = query.filter(models.Class.teacher_id == teacher_id)
    return query.all()


@router.delete("/classes/{class_id}")
def delete_class(class_id: int, teacher_id: int, db: Session = Depends(get_db)):
    cls = db.query(models.Class).filter(models.Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    if cls.teacher_id != teacher_id:
        raise HTTPException(status_code=403, detail="Not allowed to delete this class")

    media_items = db.query(Media).filter(Media.class_id == class_id).all()
    for m in media_items:
        for p in [m.path, m.thumbnail_path]:
            if p:
                try:
                    p_path = Path(p)
                    if p_path.exists():
                        p_path.unlink()
                except OSError:
                    pass
        db.delete(m)

    students = db.query(models.Student).filter(models.Student.class_id == class_id).all()
    for s in students:
        sid = s.id

        db.query(models.StudentBadge).filter(models.StudentBadge.student_id == sid).delete(synchronize_session=False)
        db.query(models.StudentInterest).filter(models.StudentInterest.student_id == sid).delete(synchronize_session=False)
        db.query(models.GamificationState).filter(models.GamificationState.student_id == sid).delete(synchronize_session=False)

        db.delete(s)

    db.delete(cls)
    db.commit()
    return {"status": "deleted", "id": class_id}


@router.post("/classes/{class_id}/students", response_model=schemas.StudentOut)
def create_student(class_id: int, payload: schemas.StudentCreate, db: Session = Depends(get_db)):
    cls = db.query(models.Class).filter(models.Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    existing_username = db.query(models.Student).filter(models.Student.username == payload.username).first()
    if existing_username:
        raise HTTPException(status_code=400, detail="Username already exists")

    student = models.Student(
        name=payload.name,
        class_id=class_id,
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/classes/{class_id}/students/export")
def export_students(class_id: int, db: Session = Depends(get_db)):
    students = db.query(models.Student).filter(models.Student.class_id == class_id).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["student_id", "name", "username", "class_id"])
    for s in students:
        writer.writerow([s.id, s.name, s.username, s.class_id])
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="class_{class_id}_students.csv"'},
    )


@router.get("/classes/{class_id}/students", response_model=List[schemas.StudentOut])
def list_students_for_class(class_id: int, teacher_id: int, db: Session = Depends(get_db)):
    cls = db.query(models.Class).filter(models.Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    if cls.teacher_id != teacher_id:
        raise HTTPException(status_code=403, detail="Not allowed to view students of this class")

    return db.query(models.Student).filter(models.Student.class_id == class_id).all()


# ---------------- Interests & Profile ----------------

@router.post("/user/interests", response_model=schemas.StudentInterestOut)
def add_interest(payload: schemas.StudentInterestCreate, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    interest = models.StudentInterest(student_id=payload.student_id, interest_text=payload.interest_text)
    db.add(interest)
    db.commit()
    db.refresh(interest)
    return interest


@router.get("/user/profile", response_model=schemas.UserProfile)
def get_user_profile(student_id: int, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    cls = student.class_
    interests = [i.interest_text for i in student.interests]

    return schemas.UserProfile(
        student_id=student.id,
        student_name=student.name,
        class_id=cls.id if cls else 0,
        class_name=cls.name if cls else "",
        interests=interests,
    )


@router.delete("/user/student/{student_id}")
def delete_student(student_id: int, teacher_id: int, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    cls = student.class_
    if not cls:
        raise HTTPException(status_code=400, detail="Student has no class assigned")

    if cls.teacher_id != teacher_id:
        raise HTTPException(status_code=403, detail="Not allowed to delete this student")

    db.query(models.StudentBadge).filter(models.StudentBadge.student_id == student_id).delete(synchronize_session=False)
    db.query(models.StudentInterest).filter(models.StudentInterest.student_id == student_id).delete(synchronize_session=False)
    db.query(models.GamificationState).filter(models.GamificationState.student_id == student_id).delete(synchronize_session=False)

    db.delete(student)
    db.commit()
    return {"status": "deleted", "id": student_id}
