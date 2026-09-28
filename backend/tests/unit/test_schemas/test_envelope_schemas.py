"""Tests unitaires des schémas d'enveloppe spec 09 (STORY-126.1).

Couvre :
- Sérialisation des 5 modèles (``PaginationMeta``, ``APIResponse``,
  ``PaginatedResponse``, ``ErrorDetail``, ``ErrorResponse``) ;
- Round-trips ``model_validate``/``model_dump`` ;
- Optionalité (``message``, ``details``) et types ;
- La fonction pure ``_status_to_code`` (mapping statut → code machine
  spec 09, table complète + spécialisation 401 login + défaut).
"""

import pytest
from pydantic import ValidationError

from app.middleware.api_response import _status_to_code, build_error_payload
from app.schemas.common import (
    APIResponse,
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
    PaginationMeta,
)


class TestAPIResponse:
    """APIResponse — sérialisation, types, optionalité message."""

    def test_data_dict_message_null(self):
        """data dict + message omis → null après sérialisation."""
        resp = APIResponse(data={"id": "app_1", "status": "running"})
        dumped = resp.model_dump()
        assert dumped == {"data": {"id": "app_1", "status": "running"}, "message": None}

    def test_data_list(self):
        """data liste transportée telle quelle."""
        resp = APIResponse(data=[1, 2, 3])
        assert resp.model_dump()["data"] == [1, 2, 3]

    def test_data_scalar(self):
        """data scalaire (str/int/bool) accepté."""
        assert APIResponse(data="ok").model_dump()["data"] == "ok"
        assert APIResponse(data=42).model_dump()["data"] == 42
        assert APIResponse(data=True).model_dump()["data"] is True

    def test_message_optional(self):
        """message fourni → transporté ; omis → None."""
        assert APIResponse(data={}, message="created").message == "created"
        assert APIResponse(data={}).message is None

    def test_data_defaults_to_none(self):
        """data défaut None (spec 09 : ``data: Any = None``)."""
        assert APIResponse().model_dump() == {"data": None, "message": None}

    def test_round_trip(self):
        """Round-trip model_validate/model_dump sans perte."""
        original = {"data": {"nested": [1, {"k": "v"}]}, "message": "ok"}
        assert APIResponse.model_validate(original).model_dump() == original


class TestPaginationMeta:
    """PaginationMeta — champs entiers spec 09."""

    def test_fields(self):
        """page/per_page/total/pages entiers attendus."""
        meta = PaginationMeta(page=1, per_page=20, total=87, pages=5)
        dumped = meta.model_dump()
        assert dumped == {"page": 1, "per_page": 20, "total": 87, "pages": 5}

    def test_page_must_be_positive(self):
        """page 1-indexé : 0 ou négatif rejeté."""
        with pytest.raises(ValidationError):
            PaginationMeta(page=0, per_page=20, total=0, pages=0)

    def test_per_page_must_be_positive(self):
        """per_page ≥ 1."""
        with pytest.raises(ValidationError):
            PaginationMeta(page=1, per_page=0, total=0, pages=0)

    def test_total_pages_non_negative(self):
        """total/pages ≥ 0 acceptés (liste vide : 0)."""
        meta = PaginationMeta(page=1, per_page=20, total=0, pages=0)
        assert meta.total == 0 and meta.pages == 0

    def test_rejects_non_coercible(self):
        """Champs entiers : valeur non coercible rejetée (mode lax Pydantic
        coerce ``"1"`` → 1, mais ``"abc"`` échoue)."""
        with pytest.raises(ValidationError):
            PaginationMeta(page="abc", per_page=20, total=0, pages=0)


class TestPaginatedResponse:
    """PaginatedResponse — liste + pagination imbriquée."""

    def test_shape(self):
        """data liste + pagination PaginationMeta."""
        resp = PaginatedResponse(
            data=[{"id": "a"}, {"id": "b"}],
            pagination=PaginationMeta(page=2, per_page=20, total=42, pages=3),
        )
        dumped = resp.model_dump()
        assert dumped["data"] == [{"id": "a"}, {"id": "b"}]
        assert dumped["pagination"]["page"] == 2
        assert dumped["pagination"]["pages"] == 3

    def test_data_must_be_list(self):
        """data liste requise — un dict est rejeté."""
        with pytest.raises(ValidationError):
            PaginatedResponse(
                data={"not": "a list"},
                pagination=PaginationMeta(page=1, per_page=1, total=1, pages=1),
            )

    def test_pagination_required(self):
        """pagination obligatoire."""
        with pytest.raises(ValidationError):
            PaginatedResponse(data=[])

    def test_round_trip(self):
        """Round-trip complet."""
        original = {
            "data": [1, 2],
            "pagination": {"page": 1, "per_page": 2, "total": 2, "pages": 1},
        }
        assert PaginatedResponse.model_validate(original).model_dump() == original


class TestErrorDetail:
    """ErrorDetail — code/message requis, details optional."""

    def test_minimal(self):
        """code + message suffisent ; details → None."""
        detail = ErrorDetail(code="NOT_FOUND", message="App not found: abc")
        dumped = detail.model_dump()
        assert dumped == {
            "code": "NOT_FOUND",
            "message": "App not found: abc",
            "details": None,
        }

    def test_details_optional_dict(self):
        """details dict transporté."""
        detail = ErrorDetail(
            code="VALIDATION_ERROR",
            message="Validation Error",
            details={"field": "name"},
        )
        assert detail.model_dump()["details"] == {"field": "name"}

    def test_code_message_required(self):
        """code et message obligatoires."""
        with pytest.raises(ValidationError):
            ErrorDetail(code="NOT_FOUND")
        with pytest.raises(ValidationError):
            ErrorDetail(message="missing code")


class TestErrorResponse:
    """ErrorResponse — enveloppe error imbriquée."""

    def test_shape(self):
        """error: ErrorDetail imbriqué."""
        resp = ErrorResponse(
            error=ErrorDetail(code="CONFLICT", message="Name already taken")
        )
        dumped = resp.model_dump()
        assert dumped["error"]["code"] == "CONFLICT"
        assert dumped["error"]["message"] == "Name already taken"

    def test_error_required(self):
        """error obligatoire."""
        with pytest.raises(ValidationError):
            ErrorResponse()

    def test_round_trip(self):
        """Round-trip complet avec correlation_id transporté à l'extérieur
        de ``error`` (le handler l'ajoute au payload JSON, pas au modèle)."""
        original = {"error": {"code": "NOT_FOUND", "message": "nope", "details": None}}
        assert ErrorResponse.model_validate(original).model_dump() == original


class TestStatusToCode:
    """_status_to_code — mapping statut → code machine spec 09 (table
    complète + spécialisation 401 login + défaut)."""

    @pytest.mark.parametrize(
        "status_code,expected",
        [
            (400, "INVALID_INPUT"),
            (401, "INVALID_OR_EXPIRED_TOKEN"),
            (403, "PERMISSION_DENIED"),
            (404, "NOT_FOUND"),
            (409, "CONFLICT"),
            (422, "VALIDATION_ERROR"),
            (429, "TOO_MANY_ATTEMPTS"),
            (500, "INTERNAL_ERROR"),
            (503, "SERVICE_UNAVAILABLE"),
        ],
    )
    def test_full_mapping_table(self, status_code, expected):
        """Table spec 09 complète."""
        assert _status_to_code(status_code) == expected

    def test_401_login_specialization(self):
        """401 sur /auth/login → INVALID_CREDENTIALS."""
        assert _status_to_code(401, "/api/v1/auth/login") == "INVALID_CREDENTIALS"

    def test_401_other_paths_unchanged(self):
        """401 ailleurs → INVALID_OR_EXPIRED_TOKEN."""
        assert _status_to_code(401, "/api/v1/deployments") == (
            "INVALID_OR_EXPIRED_TOKEN"
        )

    def test_unknown_status_fallback(self):
        """Statut non répertorié → ERROR_<status>."""
        assert _status_to_code(418) == "ERROR_418"
        assert _status_to_code(599) == "ERROR_599"


class TestBuildErrorPayload:
    """build_error_payload — construction de l'enveloppe d'erreur."""

    def test_minimal_payload(self):
        """Sans message → phrase HTTP standard ; code mappé."""
        payload = build_error_payload(404, path="/api/v1/stacks/xyz")
        assert payload == {"error": {"code": "NOT_FOUND", "message": "Not Found"}}

    def test_explicit_message_and_details(self):
        """Message + details + correlation_id transportés."""
        payload = build_error_payload(
            422,
            message="Validation Error",
            details=[{"loc": ["body", "name"]}],
            path="/api/v1/organizations",
            correlation_id="corr-123",
        )
        assert payload["error"]["code"] == "VALIDATION_ERROR"
        assert payload["error"]["details"] == [{"loc": ["body", "name"]}]
        assert payload["correlation_id"] == "corr-123"

    def test_code_override(self):
        """Override explicite du code (ex. DB_ERROR SQLAlchemy)."""
        payload = build_error_payload(500, code="DB_ERROR")
        assert payload["error"]["code"] == "DB_ERROR"

    def test_401_login_invalid_credentials(self):
        """Spécialisation login propagée au payload."""
        payload = build_error_payload(401, path="/api/v1/auth/login")
        assert payload["error"]["code"] == "INVALID_CREDENTIALS"


# --- STORY-126.2 : helpers d'unwrap du conftest --------------------------------


class TestUnwrapHelper:
    """``tests.conftest.unwrap`` — enveloppé vs legacy."""

    def _response(self, payload: dict):
        """Construit une Response httpx factice portant le payload."""
        import json as _json

        from httpx import Response as _Response

        return _Response(
            200, content=_json.dumps(payload).encode(), headers={"content-type": "application/json"}
        )

    def test_unwrap_enveloped_returns_data(self):
        """Body enveloppé → retourne strictement le contenu de ``data``."""
        from tests.conftest import unwrap

        resp = self._response({"data": {"items": [1, 2]}, "message": None})
        assert unwrap(resp) == {"items": [1, 2]}

    def test_unwrap_list_data(self):
        """``data`` liste → la liste est retournée telle quelle."""
        from tests.conftest import unwrap

        resp = self._response({"data": [], "message": None})
        assert unwrap(resp) == []

    def test_unwrap_legacy_nu_body_passthrough(self):
        """Body nu legacy (flag OFF) → retourné à l'identique (transition)."""
        from tests.conftest import unwrap

        resp = self._response({"items": [], "total": 0})
        assert unwrap(resp) == {"items": [], "total": 0}

    def test_unwrap_data_null(self):
        """``data: null`` (204-like) → None (la clé existe)."""
        from tests.conftest import unwrap

        resp = self._response({"data": None, "message": "done"})
        assert unwrap(resp) is None


class TestErrorCodeHelper:
    """``tests.conftest.error_code`` / ``error_message`` — strict spec 09."""

    def _error_response(self, payload: dict, status: int = 404):
        import json as _json

        from httpx import Response as _Response

        return _Response(
            status,
            content=_json.dumps(payload).encode(),
            headers={"content-type": "application/json"},
        )

    def test_error_code_reads_machine_code(self):
        """Body d'erreur enveloppé → code machine exact."""
        from tests.conftest import error_code

        resp = self._error_response(
            {"error": {"code": "NOT_FOUND", "message": "pas trouvé"},
             "correlation_id": "c-1"}
        )
        assert error_code(resp) == "NOT_FOUND"

    def test_error_message_reads_readable_message(self):
        """``error.message`` lisible via le helper dédié."""
        from tests.conftest import error_message

        resp = self._error_response(
            {"error": {"code": "PERMISSION_DENIED", "message": "Not enough permissions"}}
        )
        assert error_message(resp) == "Not enough permissions"

    def test_error_code_fails_without_envelope(self):
        """Body nu legacy → KeyError : régression du contrat détectée (strict)."""
        import pytest as _pytest

        from tests.conftest import error_code

        resp = self._error_response({"detail": "Not Found"})
        with _pytest.raises(KeyError):
            error_code(resp)
