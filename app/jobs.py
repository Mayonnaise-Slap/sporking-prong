from typing import Awaitable, Callable, Sequence

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import get_settings
from app.critic import CriticConfig, Finding
from app.crosscheck import CrossCheckConfig, build_document, cross_check
from app.grader import Criterion, GraderConfig, Verdict
from app.review import review_submission
from app.llm import build_llm_client
from app.models import (
    Assignment,
    Comment,
    CriterionGrade,
    Job,
    PlagiarismMatch,
    RubricCriterion,
    Submission,
    _utcnow,
)

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
        config=CrossCheckConfig.from_settings(get_settings()),
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


async def _load_criteria(db: AsyncSession, assignment_id: int) -> list[Criterion]:
    rows = await db.exec(
        select(RubricCriterion)
        .where(RubricCriterion.assignment_id == assignment_id)
        .order_by(RubricCriterion.order_index)
    )
    return [Criterion.from_row(row) for row in rows.all()]


async def _replace_draft_comments(
    db: AsyncSession, job: Job, submission: Submission, findings: Sequence[Finding]
) -> int:
    stale = await db.exec(
        select(Comment).where(
            Comment.submission_id == submission.id,
            Comment.source_job_id.is_not(None),
            Comment.author_id.is_(None),
            Comment.status == "draft",
        )
    )
    for row in stale.all():
        await db.delete(row)

    written = 0
    for finding in findings:
        if not finding.located:
            continue
        body = finding.problem
        if finding.why_it_matters:
            body += f"\n\n{finding.why_it_matters}"
        db.add(
            Comment(
                submission_id=submission.id,
                start_line=finding.start_line,
                end_line=finding.end_line,
                body=body,
                source_job_id=job.id,
                status="draft",
            )
        )
        written += 1
    return written


async def _apply_grades(
    db: AsyncSession, submission: Submission, verdicts: Sequence[Verdict]
) -> set[int]:
    existing = await db.exec(
        select(CriterionGrade).where(CriterionGrade.submission_id == submission.id)
    )
    rows = {row.criterion_id: row for row in existing.all()}

    applied: set[int] = set()
    for verdict in verdicts:
        row = rows.get(verdict.criterion_id)
        if row and row.source != "ai":
            continue
        row = row or CriterionGrade(
            submission_id=submission.id,
            criterion_id=verdict.criterion_id,
            source="ai",
        )
        row.status = verdict.status
        row.points = verdict.points
        row.comment = verdict.comment
        row.evidence = verdict.evidence
        row.evidence_start_line = verdict.evidence_start_line
        row.evidence_end_line = verdict.evidence_end_line
        row.updated_at = _utcnow()
        db.add(row)
        applied.add(verdict.criterion_id)
    return applied


async def run_grader_job(db: AsyncSession, job_id: int) -> None:
    job = await db.get(Job, job_id)
    submission = await db.get(Submission, job.submission_id)
    assignment = await db.get(Assignment, submission.assignment_id)

    job.started_at = _utcnow()
    criteria = await _load_criteria(db, assignment.id)

    settings = get_settings()
    review = await review_submission(
        build_llm_client(settings),
        assignment.condition_markdown,
        criteria,
        submission.processed_text,
        CriticConfig.from_settings(settings),
        GraderConfig.from_settings(settings),
    )

    comments_written = await _replace_draft_comments(db, job, submission, review.findings)
    applied = await _apply_grades(db, submission, review.verdicts)

    job.result = review.as_dict(applied=applied, comments_written=comments_written)
    job.status = "succeeded"
    job.finished_at = _utcnow()
    db.add(job)


JOB_HANDLERS: dict[str, Callable[[AsyncSession, int], Awaitable[None]]] = {
    "heuristics": run_heuristics_job,
    "cross_check": run_cross_check_job,
    "grader": run_grader_job,
}
