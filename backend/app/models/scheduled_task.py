"""
Modèle ScheduledTask pour les tâches planifiées (Celery Beat).
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .organization import Organization


class TaskType(str, Enum):
    """Types de tâches planifiées."""

    CLEANUP_LOGS = "cleanup_logs"
    HEALTH_CHECK = "health_check"
    GIT_SYNC = "git_sync"
    RETRY_DEPLOYMENTS = "retry_deployments"
    CUSTOM = "custom"


class ScheduledTask(Base):
    """
    Tâche planifiée avec expression cron.

    Stocke la configuration des tâches récurrentes gérées par Celery Beat.
    """

    __tablename__ = "scheduled_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    task_type: Mapped[TaskType] = mapped_column(
        SQLEnum(TaskType), nullable=False, default=TaskType.CUSTOM
    )
    cron_expression: Mapped[str] = mapped_column(
        String(100), nullable=False, default="0 * * * *"
    )
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_count: Mapped[int] = mapped_column(default=0)

    # Relations
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False
    )
    organization: Mapped["Organization"] = relationship(lazy="selectin")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ScheduledTask(id={self.id}, name={self.name}, type={self.task_type}, enabled={self.enabled})>"
