from datetime import datetime, timezone
from typing import Optional, Union

from pydantic import BaseModel, EmailStr, Field, field_validator


def _naive_utc(value: datetime) -> datetime:
    # Every other datetime in the app is naive-UTC (models._utcnow()), and
    # asyncpg refuses to insert a tz-aware value into a TIMESTAMP WITHOUT
    # TIME ZONE column. A standards-compliant client sends an offset (e.g.
    # trailing "Z"), so normalize rather than requiring callers to know
    # this column is naive.
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = None
    is_ta: bool = False
    is_supervisor: bool = False


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    is_active: bool
    is_ta: bool
    is_supervisor: bool
    created_at: datetime


class UserListItem(BaseModel):
    id: int
    full_name: Optional[str]
    email: EmailStr


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


class RubricCriterionUpdate(BaseModel):
    title: Optional[str] = None
    max_points: Optional[float] = None
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

    @field_validator("deadline_at")
    @classmethod
    def _validate_deadline(cls, value: datetime) -> datetime:
        return _naive_utc(value)


class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    condition_markdown: Optional[str] = None
    deadline_at: Optional[datetime] = None
    max_attempts: Optional[int] = None
    pass_threshold_points: Optional[float] = None

    @field_validator("deadline_at")
    @classmethod
    def _validate_deadline(cls, value: Optional[datetime]) -> Optional[datetime]:
        return _naive_utc(value) if value is not None else None


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
    student_full_name: Optional[str]
    attempt_number: int
    submitted_at: datetime
    original_file_id: int
    processed_text: str
    processed_status: str
    line_count: Optional[int]
    is_empty: bool
    assigned_reviewer_id: Optional[int]
    review_status: str
    created_at: datetime


class SubmissionUpdate(BaseModel):
    review_status: Optional[str] = None
    assigned_reviewer_id: Optional[int] = None


class JobPublic(BaseModel):
    id: int
    job_type: str
    status: str
    result: Optional[Union[list, dict]]


class CommentCreate(BaseModel):
    start_line: int
    end_line: int
    body: str
    status: str = "draft"
    author_id: Optional[int] = None
    source_comment_id: Optional[int] = None


class CommentUpdate(BaseModel):
    body: Optional[str] = None
    status: Optional[str] = None


class CommentPublic(BaseModel):
    id: int
    submission_id: int
    start_line: int
    end_line: int
    body: str
    author_id: Optional[int]
    source_comment_id: Optional[int]
    source_job_id: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime]


class CriterionGradeView(BaseModel):
    criterion_id: int
    order_index: int
    title: str
    max_points: float
    min_points: Optional[float]
    status: str
    comment: Optional[str]
    updated_at: Optional[datetime]


class PlagiarismMatchPublic(BaseModel):
    id: int
    matched_submission_id: int
    similarity_pct: float
    matched_spans: Optional[list]
    note: Optional[str]
    created_at: datetime


class FinalGradeUpsert(BaseModel):
    points: float
    next_step: str = "grade"


class FinalGradePublic(BaseModel):
    id: int
    submission_id: int
    points: float
    assigned_by_id: int
    assigned_at: datetime
    next_step: str
