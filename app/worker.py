import asyncio
import logging
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import async_session_maker, init_db
from app.jobs import JOB_HANDLERS
from app.models import Job, Submission, User, _utcnow

logger = logging.getLogger("app.worker")

POLL_INTERVAL_SECONDS = 2


async def _claim_next_job(db: AsyncSession) -> Optional[Job]:
    statement = (
        select(Job)
        .where(Job.status == "pending")
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await db.exec(statement)
    job = result.first()
    if job is None:
        return None

    job.status = "running"
    job.started_at = _utcnow()
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def _assign_least_loaded_reviewer(db: AsyncSession, submission: Submission) -> None:
    # TAs do routine review work; a supervisor is a fallback for when no TA
    # exists at all, not an equally-weighted candidate in the same pool —
    # pooling them together let ties resolve to whichever role happened to
    # have the lower user id, which in practice meant supervisors kept
    # getting picked over TAs.
    ta_result = await db.exec(select(User).where(User.is_ta))
    staff = ta_result.all()
    if not staff:
        supervisor_result = await db.exec(select(User).where(User.is_supervisor))
        staff = supervisor_result.all()
    if not staff:
        return

    pending_result = await db.exec(
        select(Submission).where(
            Submission.assignment_id == submission.assignment_id,
            Submission.review_status != "reviewed",
            Submission.assigned_reviewer_id.is_not(None),
        )
    )
    load_by_reviewer = {member.id: 0 for member in staff}
    for pending in pending_result.all():
        if pending.assigned_reviewer_id in load_by_reviewer:
            load_by_reviewer[pending.assigned_reviewer_id] += 1

    submission.assigned_reviewer_id = min(load_by_reviewer, key=lambda uid: (load_by_reviewer[uid], uid))


async def _mark_submission_done_if_finished(db: AsyncSession, submission_id: int) -> None:
    remaining = await db.exec(
        select(Job).where(
            Job.submission_id == submission_id,
            Job.status.in_(["pending", "running"]),
        )
    )
    if remaining.first() is not None:
        return

    submission = await db.get(Submission, submission_id)
    submission.processed_status = "done"
    if submission.assigned_reviewer_id is None:
        await _assign_least_loaded_reviewer(db, submission)
    db.add(submission)
    await db.commit()


async def _fail_job(job_id: int, submission_id: int, error: str) -> None:
    async with async_session_maker() as db:
        job = await db.get(Job, job_id)
        job.status = "failed"
        job.error_message = error
        job.finished_at = _utcnow()
        db.add(job)
        await db.commit()
        await _mark_submission_done_if_finished(db, submission_id)


async def _run_job(db: AsyncSession, job: Job) -> None:
    handler = JOB_HANDLERS.get(job.job_type)
    if handler is None:
        await _fail_job(job.id, job.submission_id, f"Unknown job type: {job.job_type}")
        return

    try:
        await handler(db, job.id)
        await db.commit()
    except Exception as exc:
        logger.exception("job %s (%s) for submission %s failed", job.id, job.job_type, job.submission_id)
        try:
            await db.rollback()
        except Exception:
            pass  # the session may already be unusable; the fresh one below is what matters
        await _fail_job(job.id, job.submission_id, str(exc))
        return

    await _mark_submission_done_if_finished(db, job.submission_id)


async def run_forever() -> None:
    await init_db()
    logger.info("worker started, polling every %ss", POLL_INTERVAL_SECONDS)
    while True:
        try:
            async with async_session_maker() as db:
                job = await _claim_next_job(db)
                if job is None:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue
                logger.info("claimed job %s (%s) for submission %s", job.id, job.job_type, job.submission_id)
                await _run_job(db, job)
        except Exception:
            logger.exception("unhandled error in worker poll loop")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run_forever())
