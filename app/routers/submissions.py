from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_staff
from app.jobs import JOB_HANDLERS
from app.models import Assignment, Job, Submission, SubmissionFile, User

from app.parsing import UnsupportedSubmissionFormat, parse_submission_text
from app.schemas import JobPublic, SubmissionPublic

from app.parsing import parse_submission_text
from app.schemas import JobPublic, SubmissionPublic, SubmissionUpdate


router = APIRouter(prefix="/assignments", tags=["submissions"])
submission_router = APIRouter(prefix="/submissions", tags=["submissions"])


async def _build_submission_public(
    db: AsyncSession, submission: Submission, student: Optional[User] = None
) -> SubmissionPublic:
    if student is None:
        student = await db.get(User, submission.student_id)
    return SubmissionPublic(
        **submission.model_dump(),
        student_full_name=student.full_name if student else None,
    )


@router.post(
    "/{assignment_id}/submissions",
    response_model=SubmissionPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_submission(
    assignment_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionPublic:
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    existing = await db.exec(
        select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.student_id == current_user.id,
        )
    )
    attempt_number = len(existing.all()) + 1
    if attempt_number > assignment.max_attempts:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Maximum attempts exceeded")

    content = await file.read()
    try:
        processed_text = parse_submission_text(content)
    except UnsupportedSubmissionFormat as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc

    submission_file = SubmissionFile(
        original_filename=file.filename or "upload.txt",
        content_type=file.content_type,
        size_bytes=len(content),
        content=content,
    )
    db.add(submission_file)
    await db.flush()

    submission = Submission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        attempt_number=attempt_number,
        original_file_id=submission_file.id,
        processed_text=processed_text,
        processed_status="pending",
        line_count=len(processed_text.splitlines()),
        is_empty=len(processed_text.strip()) == 0,
    )
    db.add(submission)
    await db.flush()

    for job_type in JOB_HANDLERS:
        db.add(Job(submission_id=submission.id, job_type=job_type, status="pending"))

    await db.commit()
    await db.refresh(submission)
    return await _build_submission_public(db, submission, current_user)


@router.get("/{assignment_id}/submissions", response_model=list[SubmissionPublic])
async def list_submissions_for_assignment(
    assignment_id: int,
    assigned_reviewer_id: Optional[int] = Query(default=None),
    reviewed: Optional[bool] = Query(default=None, description="True = review_status=='reviewed', False = not yet"),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[SubmissionPublic]:
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    statement = select(Submission).where(Submission.assignment_id == assignment_id)
    if assigned_reviewer_id is not None:
        statement = statement.where(Submission.assigned_reviewer_id == assigned_reviewer_id)
    if reviewed is not None:
        if reviewed:
            statement = statement.where(Submission.review_status == "reviewed")
        else:
            statement = statement.where(Submission.review_status != "reviewed")

    result = await db.exec(statement.order_by(Submission.submitted_at.desc()))
    submissions = result.all()
    if not submissions:
        return []

    students_result = await db.exec(select(User).where(User.id.in_({s.student_id for s in submissions})))
    students_by_id = {student.id: student for student in students_result.all()}

    return [await _build_submission_public(db, s, students_by_id.get(s.student_id)) for s in submissions]


@submission_router.get("", response_model=list[SubmissionPublic])
async def list_my_submissions(
    student_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubmissionPublic]:
    target_id = student_id if student_id is not None else current_user.id

    if target_id != current_user.id and not (current_user.is_ta or current_user.is_supervisor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="TA or supervisor access required")

    if target_id == current_user.id:
        student = current_user
    else:
        student = await db.get(User, target_id)
        if student is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    result = await db.exec(
        select(Submission).where(Submission.student_id == target_id).order_by(Submission.submitted_at.desc())
    )
    return [await _build_submission_public(db, s, student) for s in result.all()]


@submission_router.get("/{submission_id}", response_model=SubmissionPublic)
async def get_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionPublic:
    submission = await db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    return await _build_submission_public(db, submission)


@submission_router.patch("/{submission_id}", response_model=SubmissionPublic)
async def update_submission(
    submission_id: int,
    payload: SubmissionUpdate,
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> SubmissionPublic:
    submission = await db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    updates = payload.model_dump(exclude_unset=True)
    if "assigned_reviewer_id" in updates and updates["assigned_reviewer_id"] is not None:
        reviewer = await db.get(User, updates["assigned_reviewer_id"])
        if reviewer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewer not found")

    for field, value in updates.items():
        setattr(submission, field, value)

    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return await _build_submission_public(db, submission)


@submission_router.get("/{submission_id}/jobs", response_model=list[JobPublic])
async def list_submission_jobs(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Job]:
    submission = await db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    result = await db.exec(select(Job).where(Job.submission_id == submission_id).order_by(Job.created_at))
    return result.all()
