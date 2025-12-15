from io import StringIO
import csv
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db
from .security import hash_password, verify_password

router = APIRouter(prefix="/api")

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

    return {"teacher_id": teacher.id}


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
def list_classes(db: Session = Depends(get_db)):
    return db.query(models.Class).all()


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
