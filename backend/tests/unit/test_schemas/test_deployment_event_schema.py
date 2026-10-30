"""Tests unitaires du schéma DeploymentEventResponse (STORY-167 — Tâche 4).

Domaines fermés via Literal : accepte les 6 ``event_type`` / 4 ``level``
spec 06, rejette (ValidationError) toute valeur hors domaine (→ 422 côté
API). ``data`` arbitraire sérialisé tel quel (non sensible par
construction).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.deployment import (
    DEPLOYMENT_EVENT_LEVELS,
    DEPLOYMENT_EVENT_TYPES,
    DeploymentEventResponse,
)

_BASE_KWARGS: dict = {
    "id": "aa1e8400-e29b-41d4-a716-446655440010",
    "deployment_id": "990e8400-e29b-41d4-a716-446655440000",
    "created_at": datetime(2026, 1, 2, 22, 31, 1),
}


class TestDeploymentEventResponseAccepts:
    """Cas nominaux : domaines complets spec 06."""

    @pytest.mark.parametrize("event_type", sorted(DEPLOYMENT_EVENT_TYPES))
    def test_accepts_all_event_types(self, event_type: str):
        response = DeploymentEventResponse(
            **_BASE_KWARGS, event_type=event_type, level="info", message="m"
        )
        assert response.event_type == event_type

    @pytest.mark.parametrize("level", sorted(DEPLOYMENT_EVENT_LEVELS))
    def test_accepts_all_levels(self, level: str):
        response = DeploymentEventResponse(
            **_BASE_KWARGS, event_type="deploying", level=level, message="m"
        )
        assert response.level == level

    def test_data_arbitrary_payload_serialized(self):
        """``data`` arbitraire (identifiants/métriques) renvoyé tel quel."""
        payload = {
            "old_status": "deploying",
            "new_status": "running",
            "container_id": "abc123",
            "duration_seconds": 12.5,
        }
        response = DeploymentEventResponse(
            **_BASE_KWARGS,
            event_type="success",
            level="info",
            message="[SUCCESS] up",
            data=payload,
        )
        assert response.data == payload

    def test_message_and_data_optional(self):
        response = DeploymentEventResponse(
            **_BASE_KWARGS, event_type="deploying", level="info"
        )
        assert response.message is None
        assert response.data is None


class TestDeploymentEventResponseRejects:
    """Cas d'erreur : valeurs hors domaine → ValidationError (422 API)."""

    def test_rejects_unknown_event_type(self):
        with pytest.raises(ValidationError):
            DeploymentEventResponse(**_BASE_KWARGS, event_type="stopped", level="info")

    def test_rejects_empty_event_type(self):
        with pytest.raises(ValidationError):
            DeploymentEventResponse(**_BASE_KWARGS, event_type="", level="info")

    def test_rejects_unknown_level(self):
        with pytest.raises(ValidationError):
            DeploymentEventResponse(
                **_BASE_KWARGS, event_type="deploying", level="critical"
            )

    def test_rejects_missing_required_fields(self):
        with pytest.raises(ValidationError):
            DeploymentEventResponse(  # type: ignore[call-arg]
                event_type="deploying", level="info"
            )
