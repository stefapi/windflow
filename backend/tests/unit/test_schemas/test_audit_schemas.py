"""Tests unitaires des schemas d'audit (STORY-125.1).

Vérifie :
- ``AuditLogResponse`` : lecture depuis un modèle ORM
  (``from_attributes=True``), champs complets, ``details`` restitué
  tel que persisté (le masquage est structurel à l'écriture) ;
- ``AuditLogListResponse`` : forme paginée ``{items, total, skip,
  limit}`` et bornes de validation ;
- les exemples OpenAPI sont des payloads valides (documentation
  toujours synchronisée).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogListResponse, AuditLogResponse


def _orm_entry() -> AuditLog:
    """Ligne ORM réaliste (details déjà sanitizé à l'écriture)."""
    return AuditLog(
        id="3f1c9e2a-7b4d-4e8f-9a0b-1c2d3e4f5a6b",
        user_id="9d2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
        organization_id=None,
        action="stack.deleted",
        resource_type="stack",
        resource_id="5a4b3c2d-1e0f-4a9b-8c7d-6e5f4a3b2c1d",
        details={"stack_name": "production-nginx", "api_key": "***"},
        ip_address="203.0.113.10",
        correlation_id="f0e1d2c3-b4a5-4968-8776-5544332211ff",
        created_at=datetime(2026, 9, 25, 14, 22, 5, tzinfo=timezone.utc),
    )


class TestAuditLogResponse:
    """Lecture ORM → réponse API."""

    def test_from_attributes_reads_orm_entry(self) -> None:
        """from_attributes=True : construction directe depuis AuditLog."""
        response = AuditLogResponse.model_validate(_orm_entry())

        assert response.id == "3f1c9e2a-7b4d-4e8f-9a0b-1c2d3e4f5a6b"
        assert response.action == "stack.deleted"
        assert response.user_id == "9d2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b"
        assert response.organization_id is None
        assert response.resource_type == "stack"
        assert response.details == {"stack_name": "production-nginx", "api_key": "***"}
        assert response.ip_address == "203.0.113.10"
        assert response.correlation_id == "f0e1d2c3-b4a5-4968-8776-5544332211ff"
        assert response.created_at is not None

    def test_details_restituted_as_persisted(self) -> None:
        """La lecture est fidèle : la valeur masquée à l'écriture
        (``***``) est restituée telle quelle — aucun re-masquage ici."""
        response = AuditLogResponse.model_validate(_orm_entry())
        assert response.details is not None
        assert response.details["api_key"] == "***"

    def test_minimal_fields_required(self) -> None:
        """id, action et created_at sont obligatoires."""
        with pytest.raises(ValidationError):
            AuditLogResponse(action="user.login")  # type: ignore[call-arg]


class TestAuditLogListResponse:
    """Forme paginée {items, total, skip, limit}."""

    def test_valid_paginated_shape(self) -> None:
        """Construction valide : items, total >= 0, skip >= 0, limit >= 1."""
        response = AuditLogListResponse(
            items=[AuditLogResponse.model_validate(_orm_entry())],
            total=128,
            skip=0,
            limit=100,
        )
        assert len(response.items) == 1
        assert response.total == 128
        assert response.skip == 0
        assert response.limit == 100

    @pytest.mark.parametrize(
        "field,value",
        [("total", -1), ("skip", -1), ("limit", 0)],
    )
    def test_bounds_rejected(self, field: str, value: int) -> None:
        """Bornes : total/skip >= 0, limit >= 1 rejetés sinon."""
        payload: dict = {"items": [], "total": 0, "skip": 0, "limit": 10}
        payload[field] = value
        with pytest.raises(ValidationError):
            AuditLogListResponse(**payload)  # type: ignore[arg-type]


class TestOpenApiExamples:
    """Les exemples documentés restent des payloads valides."""

    def test_audit_log_response_example_is_valid(self) -> None:
        example = AuditLogResponse.model_config["json_schema_extra"]["example"]
        assert AuditLogResponse.model_validate(example).action == "stack.deleted"

    def test_audit_log_list_response_example_is_valid(self) -> None:
        example = AuditLogListResponse.model_config["json_schema_extra"]["example"]
        validated = AuditLogListResponse.model_validate(example)
        assert validated.total == 128
        assert len(validated.items) == 1
