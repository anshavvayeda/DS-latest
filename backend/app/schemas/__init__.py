"""Shared Pydantic request/response models."""
from pydantic import BaseModel, validator
from typing import Optional, List


class CreateSubjectRequest(BaseModel):
    name: str
    standard: int
    description: Optional[str] = None

class UpdateSubjectRequest(BaseModel):
    name: Optional[str] = None
    standard: Optional[int] = None
    description: Optional[str] = None

class CreateChapterRequest(BaseModel):
    subject_id: str
    name: str
    description: Optional[str] = None

class GenerateQuizRequest(BaseModel):
    subject_id: str
    chapter_ids: List[str]
    difficulty: str
    question_count: int
    question_types: List[str]
    content_source: str

class SubmitQuizRequest(BaseModel):
    quiz_id: str
    answers: List[dict]

class GenerateContentRequest(BaseModel):
    subject_id: str
    chapter_id: str
    feature_type: str
    language: str = 'english'
    content_source: str = 'ncert'
    additional_params: Optional[dict] = None

class CreateStudentProfileRequest(BaseModel):
    name: str
    roll_no: str
    school_name: str
    standard: int
    gender: str
    email: Optional[str] = None
    login_phone: str
    parent_phone: Optional[str] = None

class StudentExamScoreRequest(BaseModel):
    subject: str
    exam_name: str
    exam_date: str
    score: float
    max_score: float

class StudentPracticeProgressRequest(BaseModel):
    subject: str
    chapter: str
    practice_test_number: int
    score: Optional[float] = None

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminRegisterStudentRequest(BaseModel):
    name: str
    school_name: Optional[str] = None
    standard: Optional[int] = None
    roll_no: Optional[str] = None
    gender: Optional[str] = 'other'
    phone: str
    email: Optional[str] = None
    parent_phone: Optional[str] = None
    password: str
    is_active: bool = True
    role: str = 'student'

    @validator('standard')
    def validate_standard(cls, v, values):
        if v is not None and not 1 <= v <= 12:
            raise ValueError('Standard must be between 1 and 12')
        return v

    @validator('gender')
    def validate_gender(cls, v):
        if v is None:
            return 'other'
        if v.lower() not in ['male', 'female', 'other']:
            raise ValueError('Gender must be male, female, or other')
        return v.lower()

    @validator('role')
    def validate_role(cls, v):
        if v.lower() not in ['student', 'teacher', 'maintenance']:
            raise ValueError('Role must be student, teacher, or maintenance')
        return v.lower()

class AdminBulkRegisterRequest(BaseModel):
    students: List[AdminRegisterStudentRequest]

class AdminResetPasswordRequest(BaseModel):
    roll_no: str
    new_password: str

class AdminImpersonateRequest(BaseModel):
    roll_no: str

class RollNoLoginRequest(BaseModel):
    roll_no: str
    password: str

class CreateHomeworkRequest(BaseModel):
    title: str
    subject_id: str
    standard: int
    instructions: Optional[str] = None
    deadline: Optional[str] = None
