"""
Schemas Pydantic V2 pour les logs d'exécution des hooks lifecycle.

Séparation Summary/Response pour le listing et le détail.
HookExecutionResult est un schema interne au service.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Response schemas ────────────────────────────────────────────────────────


class HookLogSummaryResponse(BaseModel):
    """Schema de réponse résumé pour le listing des logs de hooks."""

    id: str = Field(..., description="Identifiant unique du log")
    plugin_id: str = Field(..., description="ID du plugin concerné")
    hook_name: str = Field(..., description="Nom du hook exécuté")
    script_path: str = Field(..., description="Chemin du script exécuté")
    status: str = Field(..., description="Statut de l'exécution (pending/running/success/failed)")
    exit_code: Optional[int] = Field(None, description="Code de retour du processus")
    started_at: datetime = Field(..., description="Date/heure de début d'exécution")
    completed_at: Optional[datetime] = Field(None, description="Date/heure de fin d'exécution")
    duration_ms: Optional[int] = Field(None, description="Durée d'exécution en millisecondes")
    triggered_by: Optional[str] = Field(None, description="ID de l'utilisateur ayant déclenché le hook")

    model_config = ConfigDict(from_attributes=True)


class HookLogResponse(HookLogSummaryResponse):
    """Schema de réponse complet pour le détail d'un log de hook.

    Inclut stdout/stderr capturés lors de l'exécution.
    """

    stdout: str = Field("", description="Sortie standard capturée")
    stderr: str = Field("", description="Sortie d'erreur capturée")
    error_message: Optional[str] = Field(None, description="Message d'erreur en cas d'échec")

    model_config = ConfigDict(from_attributes=True)


# ── Internal schema ─────────────────────────────────────────────────────────


class HookExecutionResult(BaseModel):
    """Résultat interne d'une exécution de hook (utilisé par le service)."""

    success: bool = Field(..., description="Si l'exécution a réussi")
    exit_code: Optional[int] = Field(None, description="Code de retour du processus")
    stdout: str = Field("", description="Sortie standard capturée")
    stderr: str = Field("", description="Sortie d'erreur capturée")
    duration_ms: Optional[int] = Field(None, description="Durée en millisecondes")
    error_message: Optional[str] = Field(None, description="Message d'erreur en cas d'échec")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "exit_code": 0,
                    "stdout": "Installation completed successfully",
                    "stderr": "",
                    "duration_ms": 150,
                    "error_message": None,
                }
            ]
        }
    )
