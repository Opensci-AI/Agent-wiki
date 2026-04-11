import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.project import Project
from app.models.review_item import ReviewItem
from app.schemas.review import ReviewResponse, ReviewUpdate
from app.api.deps import require_project_owner

router = APIRouter(prefix="/api/v1/projects/{project_id}/reviews", tags=["reviews"])


@router.get("", response_model=list[ReviewResponse])
async def list_reviews(
    project_id: uuid.UUID,
    resolved: bool | None = Query(None),
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    q = select(ReviewItem).where(ReviewItem.project_id == project.id)
    if resolved is not None:
        q = q.where(ReviewItem.resolved == resolved)
    q = q.order_by(ReviewItem.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


@router.patch("/{review_id}", response_model=ReviewResponse)
async def update_review(
    project_id: uuid.UUID,
    review_id: uuid.UUID,
    req: ReviewUpdate,
    project: Project = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ReviewItem).where(ReviewItem.id == review_id, ReviewItem.project_id == project.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Review item not found")
    if req.resolved is not None:
        review.resolved = req.resolved
    await db.commit()
    await db.refresh(review)
    return review
