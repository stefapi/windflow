"""
Schemas Pydantic V2 pour les tâches planifiées.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScheduledTaskCreate(BaseModel):
    """Création d'une tâche planifiée."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    task_type: Literal[
        "cleanup_logs", "health_check", "git_sync", "retry_deployments", "custom"
    ] = Field(..., description="Type de tâche")
    cron_expression: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Expression cron (ex: '0 * * * *')",
    )
    parameters: dict = Field(default_factory=dict)
    enabled: bool = True
    organization_id: str


class ScheduledTaskUpdate(BaseModel):
    """Mise à jour d'une tâche planifiée."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    cron_expression: Optional[str] = Field(None, min_length=1, max_length=100)
    parameters: Optional[dict] = None
    enabled: Optional[bool] = None


class ScheduledTaskResponse(BaseModel):
    """Réponse pour une tâche planifiée."""

    id: str
    name: str
    description: Optional[str] = None
    task_type: str
    cron_expression: str
    parameters: dict
    enabled: bool
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    run_count: int
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
