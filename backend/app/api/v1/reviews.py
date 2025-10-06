"""
Endpoints API pour les avis de stacks (reviews).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional

from ...database import get_db
from ...models.stack_review import StackReview
from ...models.stack import Stack
from ...models.user import User
from ...schemas.stack_review import (
    StackReviewCreate,
    StackReviewUpdate,
    StackReviewResponse,
    StackReviewListResponse,
    StackReviewStats
)
from ...auth.dependencies import get_current_user

router = APIRouter()


@router.get("/stacks/{stack_id}/reviews", response_model=StackReviewListResponse)
async def list_stack_reviews(
    stack_id: str,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    Liste tous les avis d'un stack avec pagination.

    Retourne également les statistiques (note moyenne, distribution).
    """

    # Vérifier que le stack existe
    stmt = select(Stack).where(Stack.id == stack_id)
    result = await db.execute(stmt)
    stack = result.scalar_one_or_none()

    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stack not found"
        )

    # Compter le total
    count_stmt = select(func.count()).select_from(StackReview).where(
        StackReview.stack_id == stack_id
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar()

    # Récupérer les avis avec informations utilisateur
    stmt = (
        select(StackReview, User.username, User.full_name)
        .join(User, StackReview.user_id == User.id)
        .where(StackReview.stack_id == stack_id)
        .order_by(StackReview.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Construire les réponses enrichies
    reviews = []
    for review, username, full_name in rows:
        review_dict = {
            **review.__dict__,
            "user_username": username,
            "user_full_name": full_name
        }
        reviews.append(StackReviewResponse(**review_dict))

    # Calculer statistiques
    stats_stmt = select(
        func.avg(StackReview.rating).label('avg_rating'),
        StackReview.rating,
        func.count(StackReview.id).label('count')
    ).where(
        StackReview.stack_id == stack_id
    ).group_by(StackReview.rating)

    stats_result = await db.execute(stats_stmt)
    stats_rows = stats_result.all()

    # Calculer note moyenne
    if stats_rows and stats_rows[0][0]:
        average_rating = float(stats_rows[0][0])
    else:
        average_rating = 0.0

    # Distribution des notes
    rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for _, rating, count in stats_rows:
        rating_distribution[rating] = count

    return StackReviewListResponse(
        data=reviews,
        total=total,
        page=skip // limit if limit > 0 else 0,
        page_size=limit,
        average_rating=average_rating,
        rating_distribution=rating_distribution
    )


@router.post("/stacks/{stack_id}/reviews", response_model=StackReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_stack_review(
    stack_id: str,
    review_data: StackReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Crée un nouvel avis pour un stack.

    Un utilisateur ne peut laisser qu'un seul avis par stack.
    """

    # Vérifier que le stack existe
    stmt = select(Stack).where(Stack.id == stack_id)
    result = await db.execute(stmt)
    stack = result.scalar_one_or_none()

    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stack not found"
        )

    # Vérifier qu'un avis n'existe pas déjà
    existing_stmt = select(StackReview).where(
        and_(
            StackReview.stack_id == stack_id,
            StackReview.user_id == current_user.id
        )
    )
    existing_result = await db.execute(existing_stmt)
    existing_review = existing_result.scalar_one_or_none()

    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reviewed this stack"
        )

    # Créer l'avis
    review = StackReview(
        stack_id=stack_id,
        user_id=current_user.id,
        **review_data.model_dump()
    )

    db.add(review)
    await db.commit()
    await db.refresh(review)

    # Mettre à jour la note moyenne du stack
    await update_stack_rating(stack_id, db)

    # Enrichir avec infos utilisateur
    review_dict = {
        **review.__dict__,
        "user_username": current_user.username,
        "user_full_name": current_user.full_name
    }

    return StackReviewResponse(**review_dict)


@router.get("/stacks/{stack_id}/reviews/{review_id}", response_model=StackReviewResponse)
async def get_stack_review(
    stack_id: str,
    review_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Récupère un avis spécifique."""

    stmt = (
        select(StackReview, User.username, User.full_name)
        .join(User, StackReview.user_id == User.id)
        .where(
            and_(
                StackReview.id == review_id,
                StackReview.stack_id == stack_id
            )
        )
    )
    result = await db.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    review, username, full_name = row
    review_dict = {
        **review.__dict__,
        "user_username": username,
        "user_full_name": full_name
    }

    return StackReviewResponse(**review_dict)


@router.put("/stacks/{stack_id}/reviews/{review_id}", response_model=StackReviewResponse)
async def update_stack_review(
    stack_id: str,
    review_id: str,
    review_data: StackReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Met à jour un avis existant.

    Seul l'auteur de l'avis peut le modifier.
    """

    stmt = select(StackReview).where(
        and_(
            StackReview.id == review_id,
            StackReview.stack_id == stack_id
        )
    )
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    # Vérifier que l'utilisateur est l'auteur
    if review.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own reviews"
        )

    # Mettre à jour les champs fournis
    update_data = review_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(review, field, value)

    await db.commit()
    await db.refresh(review)

    # Mettre à jour la note moyenne du stack si le rating a changé
    if 'rating' in update_data:
        await update_stack_rating(stack_id, db)

    # Enrichir avec infos utilisateur
    review_dict = {
        **review.__dict__,
        "user_username": current_user.username,
        "user_full_name": current_user.full_name
    }

    return StackReviewResponse(**review_dict)


@router.delete("/stacks/{stack_id}/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stack_review(
    stack_id: str,
    review_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Supprime un avis.

    Seul l'auteur ou un superadmin peut supprimer un avis.
    """

    stmt = select(StackReview).where(
        and_(
            StackReview.id == review_id,
            StackReview.stack_id == stack_id
        )
    )
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    # Vérifier les permissions
    if review.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own reviews"
        )

    await db.delete(review)
    await db.commit()

    # Mettre à jour la note moyenne du stack
    await update_stack_rating(stack_id, db)

    return None


@router.get("/stacks/{stack_id}/reviews/stats", response_model=StackReviewStats)
async def get_stack_review_stats(
    stack_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Récupère les statistiques d'avis d'un stack."""

    # Statistiques globales
    stats_stmt = select(
        func.count(StackReview.id).label('total'),
        func.avg(StackReview.rating).label('avg_rating'),
        StackReview.rating,
        func.count(StackReview.id).label('count')
    ).where(
        StackReview.stack_id == stack_id
    ).group_by(StackReview.rating)

    stats_result = await db.execute(stats_stmt)
    stats_rows = stats_result.all()

    total_reviews = sum(row[3] for row in stats_rows) if stats_rows else 0
    average_rating = float(stats_rows[0][1]) if stats_rows and stats_rows[0][1] else 0.0

    rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for _, _, rating, count in stats_rows:
        rating_distribution[rating] = count

    # Avis récents
    recent_stmt = (
        select(StackReview, User.username, User.full_name)
        .join(User, StackReview.user_id == User.id)
        .where(StackReview.stack_id == stack_id)
        .order_by(StackReview.created_at.desc())
        .limit(5)
    )
    recent_result = await db.execute(recent_stmt)
    recent_rows = recent_result.all()

    recent_reviews = []
    for review, username, full_name in recent_rows:
        review_dict = {
            **review.__dict__,
            "user_username": username,
            "user_full_name": full_name
        }
        recent_reviews.append(StackReviewResponse(**review_dict))

    return StackReviewStats(
        total_reviews=total_reviews,
        average_rating=average_rating,
        rating_distribution=rating_distribution,
        recent_reviews=recent_reviews
    )


async def update_stack_rating(stack_id: str, db: AsyncSession):
    """Met à jour la note moyenne d'un stack."""

    stmt = select(func.avg(StackReview.rating)).where(
        StackReview.stack_id == stack_id
    )
    result = await db.execute(stmt)
    avg_rating = result.scalar()

    # Mettre à jour le stack
    stack_stmt = select(Stack).where(Stack.id == stack_id)
    stack_result = await db.execute(stack_stmt)
    stack = stack_result.scalar_one_or_none()

    if stack:
        stack.rating = float(avg_rating) if avg_rating else 0.0
        await db.commit()
