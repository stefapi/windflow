"""
Modèle UserFavorite pour les stacks favoris des utilisateurs.
"""

from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Table, Column
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base

# Table d'association many-to-many pour les favoris
user_favorites = Table(
    'user_favorites',
    Base.metadata,
    Column('user_id', String(36), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('stack_id', String(36), ForeignKey('stacks.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow, nullable=False)
)
