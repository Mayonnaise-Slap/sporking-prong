from typing import Awaitable, Callable

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crosscheck import build_document, cross_check
from app.models import Assignment, Job, PlagiarismMatch, Submission, _utcnow


async def run_heuristics_job(db: AsyncSession, job_id: int) -> None:
    job = await db.get(Job, job_id)
    submission = await db.get(Submission, job.submission_id)
    assignment = await db.get(Assignment, submission.assignment_id)

    job.started_at = _utcnow()
    job.result = {
        "on_time": submission.submitted_at <= assignment.deadline_at,
        "is_empty": len(submission.processed_text.strip()) == 0,
    }
    job.status = "succeeded"
    job.finished_at = _utcnow()
    db.add(job)


async def run_cross_check_job(db: AsyncSession, job_id: int) -> None:
    job = await db.get(Job, job_id)
    submission = await db.get(Submission, job.submission_id)
    assignment = await db.get(Assignment, submission.assignment_id)

    job.started_at = _utcnow()

    result = await db.exec(
        select(Submission)
        .where(
            Submission.assignment_id == submission.assignment_id,
            Submission.student_id != submission.student_id,
        )
        .order_by(Submission.attempt_number)
    )

    latest_by_student = {other.student_id: other for other in result.all()}
    target = build_document(submission.id, submission.processed_text)
    cohort = [
        build_document(other.id, other.processed_text)
        for other in latest_by_student.values()
    ]
    report = cross_check(
        target,
        cohort,
        reference_texts=[assignment.condition_markdown],
        cohort_complete=_utcnow() >= assignment.deadline_at,
    )

    for match in report.matches:
        db.add(
            PlagiarismMatch(
                job_id=job.id,
                submission_id=submission.id,
                matched_submission_id=match.matched_submission_id,
                similarity_pct=match.similarity_pct,
                matched_spans=[span.as_dict() for span in match.spans],
                note=match.note,
            )
        )

    job.result = report.as_dict()
    job.status = "succeeded"
    job.finished_at = _utcnow()
    db.add(job)


JOB_HANDLERS: dict[str, Callable[[AsyncSession, int], Awaitable[None]]] = {
    "heuristics": run_heuristics_job,
    "cross_check": run_cross_check_job,
}
