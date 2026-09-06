from typing import Awaitable, Callable, Sequence

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import get_settings
from app.critic import CriticConfig
from app.cross_commentor import CrossCommentorConfig, Match, SourceMistake, extract_context, find_cross_matches
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


async def _replace_stale_job_comments(
    db: AsyncSession, submission_id: int, job_type: str, keep_job_id: int
) -> None:
    """Clear this job type's own previous draft comments for a submission.

    Scoped to `job_type` (not just "any job") so that a rerun of one job type
    never deletes another job type's rows for the same submission.
    """
    stale = await db.exec(
        select(Comment)
        .join(Job, Comment.source_job_id == Job.id)
        .where(
            Comment.submission_id == submission_id,
            Comment.status == "draft",
            Job.job_type == job_type,
            Job.id != keep_job_id,
        )
    )
    for row in stale.all():
        await db.delete(row)


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

    applied = await _apply_grades(db, submission, review.verdicts)

    job.result = review.as_dict(applied=applied)
    job.status = "succeeded"
    job.finished_at = _utcnow()
    db.add(job)


async def _load_cross_commentor_sources(
    db: AsyncSession, assignment_id: int, config: CrossCommentorConfig
) -> list[SourceMistake]:
    rows = await db.exec(
        select(Comment, Submission.processed_text)
        .join(Submission, Comment.submission_id == Submission.id)
        .where(Submission.assignment_id == assignment_id, Comment.status == "sent")
        .order_by(Comment.created_at.desc())
        .limit(config.max_source_comments)
    )
    return [
        SourceMistake(
            comment_id=comment.id,
            body=comment.body,
            author_id=comment.author_id,
            context=extract_context(text, comment.start_line, comment.end_line, config.context_lines),
        )
        for comment, text in rows.all()
    ]


def _match_as_dict(match: Match) -> dict:
    return {
        "comment_id": match.comment_id,
        "quote": match.quote,
        "start_line": match.start_line,
        "end_line": match.end_line,
    }


async def run_cross_commentor_job(db: AsyncSession, job_id: int) -> None:
    job = await db.get(Job, job_id)
    submission = await db.get(Submission, job.submission_id)
    assignment = await db.get(Assignment, submission.assignment_id)

    job.started_at = _utcnow()
    await _replace_stale_job_comments(db, submission.id, "cross_commentor", job.id)

    settings = get_settings()
    config = CrossCommentorConfig.from_settings(settings)
    mistakes = await _load_cross_commentor_sources(db, assignment.id, config)
    by_id = {mistake.comment_id: mistake for mistake in mistakes}

    matches: Sequence[Match] = ()
    if mistakes:
        matches = await find_cross_matches(
            build_llm_client(settings),
            assignment.condition_markdown,
            submission.processed_text,
            mistakes,
            config,
        )

    written = 0
    for match in matches:
        source = by_id.get(match.comment_id)
        if not match.located or source is None:
            continue
        db.add(
            Comment(
                submission_id=submission.id,
                start_line=match.start_line,
                end_line=match.end_line,
                body=source.body,
                author_id=source.author_id,
                source_comment_id=source.comment_id,
                source_job_id=job.id,
                status="draft",
            )
        )
        written += 1

    job.result = {"comments_written": written, "matches": [_match_as_dict(match) for match in matches]}
    job.status = "succeeded"
    job.finished_at = _utcnow()
    db.add(job)


JOB_HANDLERS: dict[str, Callable[[AsyncSession, int], Awaitable[None]]] = {
    "heuristics": run_heuristics_job,
    "cross_check": run_cross_check_job,
    "grader": run_grader_job,
    "cross_commentor": run_cross_commentor_job,
}
