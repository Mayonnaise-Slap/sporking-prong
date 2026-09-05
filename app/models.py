from datetime import datetime, timezone
from typing import Optional, Union

from sqlalchemy import Column, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, nullable=False)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_ta: bool = Field(default=False)
    is_supervisor: bool = Field(default=False)
    full_name: Optional[str] = Field(default=None)
    group_label: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)

    restore_code: Optional[str] = Field(default=None)
    restore_code_expires_at: Optional[datetime] = Field(default=None)


class Assignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    condition_markdown: str = Field(sa_column=Column(Text, nullable=False))
    deadline_at: datetime
    max_attempts: int = Field(default=3)
    pass_threshold_points: float
    created_by_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=_utcnow)


class RubricCriterion(SQLModel, table=True):
    __tablename__ = "rubric_criterion"

    id: Optional[int] = Field(default=None, primary_key=True)
    assignment_id: int = Field(foreign_key="assignment.id", index=True)
    order_index: int
    title: str
    max_points: float
    # None = free partial credit from 0 up to max_points; == max_points = all-or-nothing.
    min_points: Optional[float] = Field(default=None)


class SubmissionFile(SQLModel, table=True):
    __tablename__ = "submission_file"

    id: Optional[int] = Field(default=None, primary_key=True)
    original_filename: str
    content_type: Optional[str] = Field(default=None)
    size_bytes: int
    content: bytes
    created_at: datetime = Field(default_factory=_utcnow)


class Submission(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", "attempt_number"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    assignment_id: int = Field(foreign_key="assignment.id", index=True)
    student_id: int = Field(foreign_key="user.id", index=True)
    attempt_number: int
    submitted_at: datetime = Field(default_factory=_utcnow)
    original_file_id: int = Field(foreign_key="submission_file.id")
    processed_text: str = Field(sa_column=Column(Text, nullable=False))
    processed_status: str = Field(default="pending")
    line_count: Optional[int] = Field(default=None)
    is_empty: bool = Field(default=False)
    assigned_reviewer_id: Optional[int] = Field(default=None, foreign_key="user.id")
    review_status: str = Field(default="pending")
    reviewed_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    submission_id: int = Field(foreign_key="submission.id", index=True)
    job_type: str
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=_utcnow)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))
    # Shape is job_type-specific: "heuristics" stores a list of debrief
    # items, "cross_check" stores its report dict (see app/crosscheck.py).
    result: Optional[Union[list, dict]] = Field(default=None, sa_column=Column(JSONB))


class PlagiarismMatch(SQLModel, table=True):
    __tablename__ = "plagiarism_match"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    submission_id: int = Field(foreign_key="submission.id", index=True)
    matched_submission_id: int = Field(foreign_key="submission.id")
    similarity_pct: float
    matched_spans: Optional[list] = Field(default=None, sa_column=Column(JSONB))
    note: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)


class CriterionGrade(SQLModel, table=True):
    __tablename__ = "criterion_grade"
    __table_args__ = (UniqueConstraint("submission_id", "criterion_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    submission_id: int = Field(foreign_key="submission.id", index=True)
    criterion_id: int = Field(foreign_key="rubric_criterion.id", index=True, ondelete="CASCADE")
    status: str = Field(default="unmarked")
    points: Optional[float] = Field(default=None)
    source: str = Field(default="reviewer")
    comment: Optional[str] = Field(default=None, sa_column=Column(Text))
    evidence: Optional[str] = Field(default=None, sa_column=Column(Text))
    evidence_start_line: Optional[int] = Field(default=None)
    evidence_end_line: Optional[int] = Field(default=None)
    updated_at: datetime = Field(default_factory=_utcnow)


class Comment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    submission_id: int = Field(foreign_key="submission.id", index=True)
    start_line: int
    end_line: int
    body: str = Field(sa_column=Column(Text, nullable=False))
    author_id: Optional[int] = Field(default=None, foreign_key="user.id")
    source_comment_id: Optional[int] = Field(default=None, foreign_key="comment.id", ondelete="SET NULL")
    source_job_id: Optional[int] = Field(default=None, foreign_key="job.id")
    status: str = Field(default="draft")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    sent_at: Optional[datetime] = Field(default=None)


class FinalGrade(SQLModel, table=True):
    __tablename__ = "final_grade"

    id: Optional[int] = Field(default=None, primary_key=True)
    submission_id: int = Field(foreign_key="submission.id", unique=True)
    points: float
    assigned_by_id: int = Field(foreign_key="user.id")
    assigned_at: datetime = Field(default_factory=_utcnow)
    next_step: str = Field(default="grade")
