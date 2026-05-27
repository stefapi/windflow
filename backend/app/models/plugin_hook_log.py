"""
Modèle PluginHookLog pour le stockage des exécutions de hooks lifecycle.

Chaque exécution de hook (on_install, on_configure, on_start, on_stop, on_uninstall)
est tracée avec son résultat : statut, exit_code, stdout, stderr, durée.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base

# Limite de troncature pour stdout/stderr (sécurité : éviter les abus de stockage)
OUTPUT_MAX_LENGTH = 10_000


class PluginHookLog(Base):
    """
    Journal d'exécution d'un hook lifecycle de plugin.

    Enregistre chaque exécution avec son résultat (succès/échec),
    les sorties capturées, la durée et l'utilisateur ayant déclenché le hook.
    """

    __tablename__ = "plugin_hook_logs"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Relation vers le plugin
    plugin_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("plugins.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID du plugin concerné",
    )

    # Nom du hook exécuté
    hook_name: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Nom du hook (on_install, on_configure, on_start, on_stop, on_uninstall)",
    )

    # Chemin du script exécuté
    script_path: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment="Chemin du script shell exécuté",
    )

    # Statut de l'exécution
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="Statut : pending, running, success, failed",
    )

    # Code de retour du processus
    exit_code: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Code de retour du processus (null si timeout ou non exécuté)",
    )

    # Sorties capturées (tronquées à OUTPUT_MAX_LENGTH)
    stdout: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="Sortie standard capturée (tronquée à 10 000 caractères)",
    )

    stderr: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="Sortie d'erreur capturée (tronquée à 10 000 caractères)",
    )

    # Timestamps d'exécution
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
        comment="Date/heure de début d'exécution",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True,
        comment="Date/heure de fin d'exécution",
    )

    # Durée en millisecondes
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Durée d'exécution en millisecondes",
    )

    # Utilisateur ayant déclenché le hook
    triggered_by: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True,
        comment="ID de l'utilisateur ayant déclenché le hook",
    )

    # Message d'erreur (en cas d'échec)
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Message d'erreur en cas d'échec",
    )

    # Index composites pour les requêtes fréquentes
    __table_args__ = (
        Index("ix_plugin_hook_logs_plugin_id_hook_name", "plugin_id", "hook_name"),
        Index("ix_plugin_hook_logs_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<PluginHookLog(id={self.id}, plugin_id={self.plugin_id}, "
            f"hook_name={self.hook_name}, status={self.status})>"
        )
