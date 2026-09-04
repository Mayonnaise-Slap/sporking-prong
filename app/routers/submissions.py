from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_staff
from app.jobs import JOB_HANDLERS
from app.models import Assignment, Job, Submission, SubmissionFile, User
from app.parsing import parse_submission_text
from app.schemas import JobPublic, SubmissionPublic

router = APIRouter(prefix="/assignments", tags=["submissions"])
jobs_router = APIRouter(prefix="/submissions", tags=["submissions"])


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
) -> Submission:
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
    processed_text = parse_submission_text(content)

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
    return submission


@router.get("/{assignment_id}/submissions", response_model=list[SubmissionPublic])
async def list_submissions_for_assignment(
    assignment_id: int,
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[Submission]:
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    result = await db.exec(
        select(Submission).where(Submission.assignment_id == assignment_id).order_by(Submission.submitted_at.desc())
    )
    return result.all()


@jobs_router.get("/{submission_id}/jobs", response_model=list[JobPublic])
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
