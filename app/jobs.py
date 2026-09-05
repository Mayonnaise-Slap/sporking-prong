from typing import Awaitable, Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Assignment, Job, Submission, _utcnow

GREEN = "#22c55e"
YELLOW = "#eab308"


async def run_heuristics_job(db: AsyncSession, job_id: int) -> None:
    job = await db.get(Job, job_id)
    submission = await db.get(Submission, job.submission_id)
    assignment = await db.get(Assignment, submission.assignment_id)

    on_time = submission.submitted_at <= assignment.deadline_at
    is_empty = len(submission.processed_text.strip()) == 0

    job.started_at = _utcnow()
    job.result = [
        {
            "rubric": "On time",
            "color": GREEN if on_time else YELLOW,
            "comment": "Submitted on time" if on_time else "Submitted late",
        },
        {
            "rubric": "Empty check",
            "color": YELLOW if is_empty else GREEN,
            "comment": "Submission is empty" if is_empty else "Not empty",
        },
    ]
    job.status = "succeeded"
    job.finished_at = _utcnow()
    db.add(job)


JOB_HANDLERS: dict[str, Callable[[AsyncSession, int], Awaitable[None]]] = {
    "heuristics": run_heuristics_job,
}
