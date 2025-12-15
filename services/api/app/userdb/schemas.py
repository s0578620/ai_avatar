from typing import List, Optional

from pydantic import BaseModel, EmailStr


# ---------- Teacher ----------

class TeacherBase(BaseModel):
    name: str
    email: EmailStr


class TeacherCreate(TeacherBase):
    password: str


class TeacherOut(TeacherBase):
    id: int

    class Config:
        from_attributes = True


class TeacherLogin(BaseModel):
    email: EmailStr
    password: str


# ---------- Class ----------

class ClassBase(BaseModel):
    name: str
    teacher_id: int
    grade_level: Optional[str] = None
    subject: Optional[str] = None


class ClassCreate(ClassBase):
    pass


class ClassOut(ClassBase):
    id: int

    class Config:
        from_attributes = True


# ---------- Student ----------

class StudentBase(BaseModel):
    name: str
    class_id: int
    username: str


class StudentCreate(StudentBase):
    password: str


class StudentOut(StudentBase):
    id: int

    class Config:
        from_attributes = True


# ---------- Interests ----------

class StudentInterestCreate(BaseModel):
    student_id: int
    interest_text: str


class StudentInterestOut(StudentInterestCreate):
    id: int

    class Config:
        from_attributes = True


# ---------- Profile for RAG ----------

class UserProfile(BaseModel):
    student_id: int
    student_name: str
    class_id: int
    class_name: str
    interests: List[str]
