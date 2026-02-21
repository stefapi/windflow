"""
Schemas Pydantic V2 pour le versioning des stacks.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class StackVersionResponse(BaseModel):
    """Réponse pour une version de stack."""

    id: str
    stack_id: str
    version_number: int
    compose_content: str
    variables: dict = Field(default_factory=dict)
    change_summary: Optional[str] = None
    created_by: Optional[str] = None
    author_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StackVersionCreate(BaseModel):
    """Création manuelle d'une version (snapshot)."""

    change_summary: Optional[str] = Field(None, max_length=500, description="Résumé des modifications")
