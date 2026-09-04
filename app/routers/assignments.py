from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_db
from app.deps import require_supervisor
from app.models import Assignment, RubricCriterion, User
from app.schemas import (
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentWithCriteria,
    RubricCriterionCreate,
    RubricCriterionPublic,
    RubricCriterionUpdate,
)

router = APIRouter(prefix="/assignments", tags=["assignments"])


async def _fetch_criteria(db: AsyncSession, assignment_id: int) -> list[RubricCriterion]:
    result = await db.exec(
        select(RubricCriterion)
        .where(RubricCriterion.assignment_id == assignment_id)
        .order_by(RubricCriterion.order_index)
    )
    return result.all()


def _validate_pass_threshold(pass_threshold_points: float, total_max_points: float) -> None:
    if pass_threshold_points > total_max_points:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"pass_threshold_points ({pass_threshold_points}) cannot exceed "
                f"the rubric's total max points ({total_max_points})"
            ),
        )


@router.get("", response_model=list[AssignmentWithCriteria])
async def list_assignments(
    search: Optional[str] = Query(default=None, description="Case-insensitive substring match on title"),
    db: AsyncSession = Depends(get_db),
) -> list[AssignmentWithCriteria]:
    statement = select(Assignment).order_by(Assignment.created_at.desc())
    if search:
        statement = statement.where(Assignment.title.ilike(f"%{search}%"))
    result = await db.exec(statement)
    assignments = result.all()
    if not assignments:
        return []

    criteria_result = await db.exec(
        select(RubricCriterion)
        .where(RubricCriterion.assignment_id.in_([a.id for a in assignments]))
        .order_by(RubricCriterion.order_index)
    )
    criteria_by_assignment: dict[int, list[RubricCriterion]] = defaultdict(list)
    for criterion in criteria_result.all():
        criteria_by_assignment[criterion.assignment_id].append(criterion)

    return [
        AssignmentWithCriteria(
            **assignment.model_dump(),
            criteria=[
                RubricCriterionPublic(**criterion.model_dump())
                for criterion in criteria_by_assignment[assignment.id]
            ],
        )
        for assignment in assignments
    ]


@router.post("", response_model=AssignmentWithCriteria, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    payload: AssignmentCreate,
    current_user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
) -> AssignmentWithCriteria:
    _validate_pass_threshold(payload.pass_threshold_points, sum(item.max_points for item in payload.criteria))

    assignment = Assignment(
        title=payload.title,
        condition_markdown=payload.condition_markdown,
        deadline_at=payload.deadline_at,
        max_attempts=payload.max_attempts,
        pass_threshold_points=payload.pass_threshold_points,
        created_by_id=current_user.id,
    )
    db.add(assignment)
    await db.flush()

    criteria = [
        RubricCriterion(
            assignment_id=assignment.id,
            order_index=index,
            title=item.title,
            max_points=item.max_points,
            min_points=item.min_points,
        )
        for index, item in enumerate(payload.criteria)
    ]
    db.add_all(criteria)
    await db.commit()

    await db.refresh(assignment)
    for criterion in criteria:
        await db.refresh(criterion)

    return AssignmentWithCriteria(
        **assignment.model_dump(),
        criteria=[RubricCriterionPublic(**criterion.model_dump()) for criterion in criteria],
    )


@router.patch("/{assignment_id}", response_model=AssignmentWithCriteria)
async def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    current_user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
) -> AssignmentWithCriteria:
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(assignment, field, value)

    criteria = await _fetch_criteria(db, assignment_id)
    _validate_pass_threshold(assignment.pass_threshold_points, sum(c.max_points for c in criteria))

    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    return AssignmentWithCriteria(
        **assignment.model_dump(),
        criteria=[RubricCriterionPublic(**criterion.model_dump()) for criterion in criteria],
    )


@router.post(
    "/{assignment_id}/criteria",
    response_model=RubricCriterionPublic,
    status_code=status.HTTP_201_CREATED,
)
async def add_rubric_criterion(
    assignment_id: int,
    payload: RubricCriterionCreate,
    current_user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
) -> RubricCriterion:
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    next_order_index = len(await _fetch_criteria(db, assignment_id))

    criterion = RubricCriterion(
        assignment_id=assignment_id,
        order_index=next_order_index,
        title=payload.title,
        max_points=payload.max_points,
        min_points=payload.min_points,
    )
    db.add(criterion)
    await db.commit()
    await db.refresh(criterion)
    return criterion


@router.patch("/{assignment_id}/criteria/{criterion_id}", response_model=RubricCriterionPublic)
async def update_rubric_criterion(
    assignment_id: int,
    criterion_id: int,
    payload: RubricCriterionUpdate,
    current_user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
) -> RubricCriterion:
    criterion = await db.get(RubricCriterion, criterion_id)
    if criterion is None or criterion.assignment_id != assignment_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rubric criterion not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(criterion, field, value)

    assignment = await db.get(Assignment, assignment_id)
    criteria = await _fetch_criteria(db, assignment_id)
    _validate_pass_threshold(assignment.pass_threshold_points, sum(c.max_points for c in criteria))

    db.add(criterion)
    await db.commit()
    await db.refresh(criterion)
    return criterion


@router.delete("/{assignment_id}/criteria/{criterion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rubric_criterion(
    assignment_id: int,
    criterion_id: int,
    current_user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
) -> None:
    criterion = await db.get(RubricCriterion, criterion_id)
    if criterion is None or criterion.assignment_id != assignment_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rubric criterion not found")

    assignment = await db.get(Assignment, assignment_id)
    criteria = await _fetch_criteria(db, assignment_id)
    remaining_max_points = sum(c.max_points for c in criteria if c.id != criterion_id)
    _validate_pass_threshold(assignment.pass_threshold_points, remaining_max_points)

    await db.delete(criterion)
    await db.commit()
