from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    is_ta: bool = False
    is_supervisor: bool = False


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    is_ta: bool
    is_supervisor: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RestoreRequest(BaseModel):
    email: EmailStr


class RestoreConfirm(BaseModel):
    email: EmailStr
    code: str
    new_password: str = Field(min_length=8)


class RubricCriterionCreate(BaseModel):
    title: str
    max_points: float
    min_points: Optional[float] = None


class RubricCriterionPublic(BaseModel):
    id: int
    assignment_id: int
    order_index: int
    title: str
    max_points: float
    min_points: Optional[float]


class AssignmentCreate(BaseModel):
    title: str
    condition_markdown: str
    deadline_at: datetime
    max_attempts: int = 3
    pass_threshold_points: float
    criteria: list[RubricCriterionCreate] = Field(min_length=1)


class AssignmentPublic(BaseModel):
    id: int
    title: str
    condition_markdown: str
    deadline_at: datetime
    max_attempts: int
    pass_threshold_points: float
    created_by_id: int
    created_at: datetime


class AssignmentWithCriteria(AssignmentPublic):
    criteria: list[RubricCriterionPublic]


class SubmissionPublic(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    attempt_number: int
    submitted_at: datetime
    original_file_id: int
    processed_text: str
    processed_status: str
    line_count: Optional[int]
    is_empty: bool
    review_status: str
    created_at: datetime
