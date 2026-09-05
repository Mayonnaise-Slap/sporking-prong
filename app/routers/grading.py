from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_db
from app.deps import require_staff
from app.models import CriterionGrade, FinalGrade, PlagiarismMatch, RubricCriterion, Submission, User, _utcnow
from app.schemas import (
    CriterionGradeView,
    FinalGradePublic,
    FinalGradeUpsert,
    PlagiarismMatchPublic,
)

router = APIRouter(prefix="/submissions", tags=["grading"])


async def _get_submission_or_404(db: AsyncSession, submission_id: int) -> Submission:
    submission = await db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission


@router.get("/{submission_id}/criterion_grades", response_model=list[CriterionGradeView])
async def list_criterion_grades(
    submission_id: int,
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[CriterionGradeView]:
    submission = await _get_submission_or_404(db, submission_id)

    criteria_result = await db.exec(
        select(RubricCriterion)
        .where(RubricCriterion.assignment_id == submission.assignment_id)
        .order_by(RubricCriterion.order_index)
    )
    criteria = criteria_result.all()

    grades_result = await db.exec(select(CriterionGrade).where(CriterionGrade.submission_id == submission_id))
    grades_by_criterion = {grade.criterion_id: grade for grade in grades_result.all()}

    views = []
    for criterion in criteria:
        grade = grades_by_criterion.get(criterion.id)
        views.append(
            CriterionGradeView(
                criterion_id=criterion.id,
                order_index=criterion.order_index,
                title=criterion.title,
                max_points=criterion.max_points,
                min_points=criterion.min_points,
                status=grade.status if grade else "unmarked",
                points=grade.points if grade else None,
                source=grade.source if grade else "reviewer",
                comment=grade.comment if grade else None,
                evidence=grade.evidence if grade else None,
                evidence_start_line=grade.evidence_start_line if grade else None,
                evidence_end_line=grade.evidence_end_line if grade else None,
                updated_at=grade.updated_at if grade else None,
            )
        )
    return views


@router.get("/{submission_id}/plagiarism-matches", response_model=list[PlagiarismMatchPublic])
async def list_plagiarism_matches(
    submission_id: int,
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[PlagiarismMatch]:
    await _get_submission_or_404(db, submission_id)

    result = await db.exec(
        select(PlagiarismMatch)
        .where(PlagiarismMatch.submission_id == submission_id)
        .order_by(PlagiarismMatch.similarity_pct.desc())
    )
    return result.all()


@router.get("/{submission_id}/final-grade", response_model=FinalGradePublic | None)
async def get_final_grade(
    submission_id: int,
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> FinalGrade | None:
    await _get_submission_or_404(db, submission_id)

    result = await db.exec(select(FinalGrade).where(FinalGrade.submission_id == submission_id))
    return result.first()


@router.put("/{submission_id}/final-grade", response_model=FinalGradePublic)
async def upsert_final_grade(
    submission_id: int,
    payload: FinalGradeUpsert,
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> FinalGrade:
    submission = await _get_submission_or_404(db, submission_id)

    criteria_result = await db.exec(
        select(RubricCriterion).where(RubricCriterion.assignment_id == submission.assignment_id)
    )
    total_max_points = sum(criterion.max_points for criterion in criteria_result.all())
    if payload.points > total_max_points:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"points ({payload.points}) cannot exceed the rubric's total max points ({total_max_points})",
        )

    existing_result = await db.exec(select(FinalGrade).where(FinalGrade.submission_id == submission_id))
    final_grade = existing_result.first()
    if final_grade is None:
        final_grade = FinalGrade(
            submission_id=submission_id,
            points=payload.points,
            assigned_by_id=current_user.id,
            next_step=payload.next_step,
        )
    else:
        final_grade.points = payload.points
        final_grade.next_step = payload.next_step
        final_grade.assigned_by_id = current_user.id
        final_grade.assigned_at = _utcnow()

    if payload.next_step == "grade":
        submission.review_status = "reviewed"
        submission.reviewed_at = _utcnow()
        db.add(submission)

    db.add(final_grade)
    await db.commit()
    await db.refresh(final_grade)
    return final_grade
