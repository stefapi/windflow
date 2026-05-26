"""
Modèle Plugin pour la gestion des plugins installés.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base

if TYPE_CHECKING:
    pass


class PluginStatus(str, Enum):
    """Statuts possibles d'un plugin installé."""

    INSTALLED = "installed"
    INSTALLING = "installing"
    RUNNING = "running"
    STOPPED = "stopped"
    UPDATING = "updating"
    ERROR = "error"


class Plugin(Base):
    """
    Modèle plugin pour la gestion du cycle de vie des plugins.

    Représente un plugin installé dans le système WindFlow.
    """

    __tablename__ = "plugins"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Informations de base
    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True,
        comment="Identifiant unique du plugin (kebab-case)",
    )
    version: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Version du plugin (semver)",
    )
    display_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Nom affiché dans l'UI",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Description du plugin",
    )

    # Catégorie et type
    category: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Catégorie du plugin (PluginCategory value)",
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Type de plugin (PluginType value)",
    )

    # Statut
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PluginStatus.INSTALLED.value,
        comment="Statut du plugin (PluginStatus value)",
    )

    # Données du manifest validé
    manifest_data: Mapped[dict] = mapped_column(
        JSON, nullable=False,
        comment="Manifest validé complet (JSON)",
    )

    # Configuration utilisateur
    config_values: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict,
        comment="Valeurs de configuration saisies par l'utilisateur",
    )

    # Organisation (multi-tenant)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Utilisateur ayant installé le plugin
    installed_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID de l'utilisateur ayant installé le plugin",
    )

    # Timestamps
    installed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Plugin(id={self.id}, name={self.name}, version={self.version}, status={self.status})>"
