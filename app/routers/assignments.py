from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_db
from app.deps import require_supervisor
from app.models import Assignment, RubricCriterion, User
from app.schemas import AssignmentCreate, AssignmentPublic, AssignmentWithCriteria, RubricCriterionPublic

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.get("", response_model=list[AssignmentPublic])
async def list_assignments(
    search: Optional[str] = Query(default=None, description="Case-insensitive substring match on title"),
    db: AsyncSession = Depends(get_db),
) -> list[Assignment]:
    statement = select(Assignment).order_by(Assignment.created_at.desc())
    if search:
        statement = statement.where(Assignment.title.ilike(f"%{search}%"))
    result = await db.exec(statement)
    return result.all()


@router.post("", response_model=AssignmentWithCriteria, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    payload: AssignmentCreate,
    current_user: User = Depends(require_supervisor),
    db: AsyncSession = Depends(get_db),
) -> AssignmentWithCriteria:
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
