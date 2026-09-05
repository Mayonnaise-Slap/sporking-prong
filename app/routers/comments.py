from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_db
from app.deps import require_staff
from app.models import Comment, Submission, User, _utcnow
from app.schemas import CommentCreate, CommentPublic, CommentUpdate

router = APIRouter(prefix="/submissions", tags=["comments"])
comment_router = APIRouter(prefix="/comments", tags=["comments"])


@router.get("/{submission_id}/comments", response_model=list[CommentPublic])
async def list_comments(
    submission_id: int,
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[Comment]:
    submission = await db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    result = await db.exec(
        select(Comment).where(Comment.submission_id == submission_id).order_by(Comment.start_line, Comment.created_at)
    )
    return result.all()


@router.post("/{submission_id}/comments", response_model=CommentPublic, status_code=status.HTTP_201_CREATED)
async def create_comment(
    submission_id: int,
    payload: CommentCreate,
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> Comment:
    submission = await db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    author_id = payload.author_id if payload.author_id is not None else current_user.id
    if payload.author_id is not None:
        author = await db.get(User, payload.author_id)
        if author is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")

    comment = Comment(
        submission_id=submission_id,
        start_line=payload.start_line,
        end_line=payload.end_line,
        body=payload.body,
        author_id=author_id,
        source_comment_id=payload.source_comment_id,
        status=payload.status,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@comment_router.patch("/{comment_id}", response_model=CommentPublic)
async def update_comment(
    comment_id: int,
    payload: CommentUpdate,
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> Comment:
    comment = await db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(comment, field, value)
    comment.updated_at = _utcnow()
    if updates.get("status") == "sent" and comment.sent_at is None:
        comment.sent_at = _utcnow()

    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@comment_router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> None:
    comment = await db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    await db.delete(comment)
    await db.commit()
