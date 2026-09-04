import asyncio
import logging
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import async_session_maker, init_db
from app.jobs import JOB_HANDLERS
from app.models import Job, Submission, _utcnow

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
    db.add(submission)
    await db.commit()


async def _run_job(db: AsyncSession, job: Job) -> None:
    handler = JOB_HANDLERS.get(job.job_type)
    if handler is None:
        job.status = "failed"
        job.error_message = f"Unknown job type: {job.job_type}"
        job.finished_at = _utcnow()
        db.add(job)
        await db.commit()
    else:
        try:
            await handler(db, job.id)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            failed_job = await db.get(Job, job.id)
            failed_job.status = "failed"
            failed_job.error_message = str(exc)
            failed_job.finished_at = _utcnow()
            db.add(failed_job)
            await db.commit()

    await _mark_submission_done_if_finished(db, job.submission_id)


async def run_forever() -> None:
    await init_db()
    logger.info("worker started, polling every %ss", POLL_INTERVAL_SECONDS)
    while True:
        async with async_session_maker() as db:
            job = await _claim_next_job(db)
            if job is None:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                continue
            logger.info("claimed job %s (%s) for submission %s", job.id, job.job_type, job.submission_id)
            await _run_job(db, job)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run_forever())
