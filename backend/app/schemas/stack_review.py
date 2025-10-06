"""
Schémas Pydantic pour les avis de stacks (reviews).
"""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class StackReviewBase(BaseModel):
    """Schéma de base pour un avis de stack."""

    rating: int = Field(..., ge=1, le=5, description="Note de 1 à 5 étoiles")
    title: str = Field(..., min_length=1, max_length=200, description="Titre de l'avis")
    comment: str = Field(..., min_length=10, description="Commentaire détaillé")


class StackReviewCreate(StackReviewBase):
    """Schéma pour créer un nouvel avis."""
    pass


class StackReviewUpdate(BaseModel):
    """Schéma pour mettre à jour un avis."""

    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    comment: Optional[str] = Field(None, min_length=10)


class StackReviewResponse(StackReviewBase):
    """Schéma de réponse pour un avis."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    stack_id: str
    user_id: str
    helpful_count: int
    created_at: datetime
    updated_at: datetime

    # Informations utilisateur enrichies
    user_username: Optional[str] = None
    user_full_name: Optional[str] = None


class StackReviewListResponse(BaseModel):
    """Réponse pour une liste d'avis."""

    data: list[StackReviewResponse]
    total: int
    page: int
    page_size: int
    average_rating: float
    rating_distribution: dict[int, int]  # {1: count, 2: count, ...}


class StackReviewStats(BaseModel):
    """Statistiques des avis d'un stack."""

    total_reviews: int
    average_rating: float
    rating_distribution: dict[int, int]
    recent_reviews: list[StackReviewResponse]
