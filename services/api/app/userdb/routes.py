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

router = APIRouter(prefix="/api")

class PasswordResetRequestIn(BaseModel):
    email: EmailStr


@router.post("/auth/request-password-reset")
def request_password_reset(
    payload: PasswordResetRequestIn,
    db: Session = Depends(get_db),
):
    # Immer 200 zurückgeben -> kein User-Enumeration
    teacher = (
        db.query(Teacher)
        .filter(Teacher.email == payload.email)
        .first()
    )
    if not teacher:
        return {"status": "ok"}

    # zufälligen Token generieren (raw) und gehasht speichern
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    reset = PasswordResetToken(
        teacher_id=teacher.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    db.add(reset)
    db.commit()

    # TODO: In echt -> E-Mail über n8n verschicken.
    # Für Demo/Entwicklung: Token in der Response zurückgeben
    return {
        "status": "ok",
        "reset_token": raw_token,  # NUR für Demo!
    }

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
    if (
        not reset
        or reset.used_at is not None
        or reset.expires_at < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    teacher = db.get(Teacher, reset.teacher_id)
    if not teacher:
        raise HTTPException(status_code=400, detail="Invalid token")

    # vorhandene Hilfsfunktion nutzen
    teacher.password_hash = hash_password(payload.new_password)
    reset.used_at = datetime.utcnow()

    db.commit()
    return {"status": "ok"}

# ---------- Teacher ----------

@router.post("/teachers/register", response_model=schemas.TeacherOut)
def register_teacher(
        payload: schemas.TeacherCreate,
        db: Session = Depends(get_db),
):
    existing = (
        db.query(models.Teacher)
        .filter(models.Teacher.email == payload.email)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Teacher with this email already exists"
        )

    teacher = models.Teacher(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher

# ---------- Student ----------
@router.post("/auth/student-login")
def student_login(
    payload: schemas.StudentLogin,
    db: Session = Depends(get_db),
):
    student = (
        db.query(models.Student)
        .filter(models.Student.username == payload.username)
        .first()
    )
    if not student or not verify_password(payload.password, student.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return {
        "student_id": student.id,
        "class_id": student.class_id,
        "role": "student",
    }
@router.post("/auth/login")
def login_teacher(
        payload: schemas.TeacherLogin,
        db: Session = Depends(get_db),
):
    teacher = (
        db.query(models.Teacher)
        .filter(models.Teacher.email == payload.email)
        .first()
    )
    if not teacher or not verify_password(payload.password, teacher.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return {
        "teacher_id": teacher.id,
        "role": "teacher",
    }


# ---------- Classes ----------

@router.post("/classes", response_model=schemas.ClassOut)
def create_class(
        payload: schemas.ClassCreate,
        db: Session = Depends(get_db),
):
    teacher = db.query(models.Teacher).filter(
        models.Teacher.id == payload.teacher_id
    ).first()
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
def list_classes(
        teacher_id: int | None = None,
        db: Session = Depends(get_db),
):
        query = db.query(models.Class)
        if teacher_id is not None:
            query = query.filter(models.Class.teacher_id == teacher_id)
        return query.all()


@router.post("/classes/{class_id}/students", response_model=schemas.StudentOut)
def create_student(
        class_id: int,
        payload: schemas.StudentCreate,
        db: Session = Depends(get_db),
):
    cls = db.query(models.Class).filter(models.Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    existing_username = (
        db.query(models.Student)
        .filter(models.Student.username == payload.username)
        .first()
    )
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
def export_students(
        class_id: int,
        db: Session = Depends(get_db),
):
    students = (
        db.query(models.Student)
        .filter(models.Student.class_id == class_id)
        .all()
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["student_id", "name", "username", "class_id"])
    for s in students:
        writer.writerow([s.id, s.name, s.username, s.class_id])
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="class_{class_id}_students.csv"'
        },
    )

@router.get(
    "/classes/{class_id}/students",
    response_model=List[schemas.StudentOut],
)
def list_students_for_class(
    class_id: int,
    teacher_id: int,
    db: Session = Depends(get_db),
):
    """
    Gibt die Schüler einer Klasse zurück (nur für den passenden Lehrer).

    Mini-RBAC:
    - teacher_id muss zu class.teacher_id passen.
    """
    cls = (
        db.query(models.Class)
        .filter(models.Class.id == class_id)
        .first()
    )
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    if cls.teacher_id != teacher_id:
        raise HTTPException(
            status_code=403,
            detail="Not allowed to view students of this class",
        )

    students = (
        db.query(models.Student)
        .filter(models.Student.class_id == class_id)
        .all()
    )
    return students
"""
Request:
    GET /classes/<class_id>/students/<student_id>
Response:
    [
      { "id": 1, "name": "Max", "class_id": 1, "username": "max1" },
      { "id": 2, "name": "Lena", "class_id": 1, "username": "lena1" }
    ]
"""
# ---------- Interests & Profile ----------

@router.post("/user/interests", response_model=schemas.StudentInterestOut)
def add_interest(
        payload: schemas.StudentInterestCreate,
        db: Session = Depends(get_db),
):
    student = (
        db.query(models.Student)
        .filter(models.Student.id == payload.student_id)
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    interest = models.StudentInterest(
        student_id=payload.student_id,
        interest_text=payload.interest_text,
    )
    db.add(interest)
    db.commit()
    db.refresh(interest)
    return interest


@router.get("/user/profile", response_model=schemas.UserProfile)
def get_user_profile(
        student_id: int,
        db: Session = Depends(get_db),
):
    student = (
        db.query(models.Student)
        .filter(models.Student.id == student_id)
        .first()
    )
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
def delete_student(
    student_id: int,
    teacher_id: int,
    db: Session = Depends(get_db),
):
    """
    Löscht einen Schüler wenn der aufrufende Lehrer
    auch der Klassenlehrer dieses Schülers ist.
    """
    student = (
        db.query(models.Student)
        .filter(models.Student.id == student_id)
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    cls = student.class_
    if not cls:
        raise HTTPException(status_code=400, detail="Student has no class assigned")

    if cls.teacher_id != teacher_id:
        raise HTTPException(status_code=403, detail="Not allowed to delete this student")

    db.delete(student)
    db.commit()

    return {"status": "deleted", "id": student_id}
