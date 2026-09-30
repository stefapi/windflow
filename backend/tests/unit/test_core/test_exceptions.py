"""Tests unitaires de la hiérarchie d'exceptions (STORY-127).

Couvre (cf. story § Tests à écrire) :
- mapping complet exception → (statut HTTP, code machine spec 09) ;
- ``WindFlowException`` nue → 500 ``INTERNAL_ERROR`` (défaut) ;
- ``NotFoundError`` : signature historique ``(resource, resource_id)``
  (message + ``details``) et forme message-libre du sweep ;
- ``AuthenticationError`` : headers ``WWW-Authenticate: Bearer`` par défaut,
  override ``code="INVALID_CREDENTIALS"`` par instance (login) ;
- rétrocompatibilité des classes techniques (``CommandExecutionError``,
  ``InvalidApiKeyError``, ``InvalidRefreshTokenError``, ``Secret*Error``) ;
- constructeur ``APIError`` : ``details=None`` → ``{}``, override ``code``
  prime sur ``error_code`` de classe.
"""

import pytest

from app.core.exceptions import (
    APIError,
    AuthenticationError,
    CommandExecutionError,
    ConflictError,
    InvalidApiKeyError,
    InvalidInputError,
    InvalidRefreshTokenError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    SecretDecryptionError,
    SecretEncryptionError,
    ServiceUnavailableError,
    UnprocessableEntityError,
    WindFlowException,
)


class TestStatusCodeMapping:
    """Mapping exception → (statut, code) — AC 1."""

    @pytest.mark.parametrize(
        ("exc_factory", "expected_status", "expected_code"),
        [
            (lambda: NotFoundError("Stack", "abc"), 404, "NOT_FOUND"),
            (lambda: ConflictError("conflit"), 409, "CONFLICT"),
            (lambda: InvalidInputError("invalide"), 400, "INVALID_INPUT"),
            (
                lambda: UnprocessableEntityError("non traitable"),
                422,
                "VALIDATION_ERROR",
            ),
            (
                lambda: PermissionDeniedError("refusé"),
                403,
                "PERMISSION_DENIED",
            ),
            (
                lambda: AuthenticationError("non authentifié"),
                401,
                "INVALID_OR_EXPIRED_TOKEN",
            ),
            (lambda: RateLimitError("trop de requêtes"), 429, "TOO_MANY_ATTEMPTS"),
            (
                lambda: ServiceUnavailableError("indisponible"),
                503,
                "SERVICE_UNAVAILABLE",
            ),
        ],
    )
    def test_mapping(self, exc_factory, expected_status, expected_code):
        """Chaque classe porte son couple (statut, code machine)."""
        exc = exc_factory()
        assert exc.status_code == expected_status
        assert exc.code == expected_code

    def test_windflow_exception_bare_defaults_to_500(self):
        """WindFlowException nue → 500 INTERNAL_ERROR (défaut de classe)."""
        exc = WindFlowException("erreur interne")
        assert exc.status_code == 500
        assert exc.error_code == "INTERNAL_ERROR"

    def test_all_classes_inherit_windflow_exception(self):
        """Le handler global (routage MRO) attrape toutes les sous-classes."""
        for exc in (
            APIError("x"),
            NotFoundError("Stack", "1"),
            ConflictError("x"),
            InvalidInputError("x"),
            UnprocessableEntityError("x"),
            PermissionDeniedError("x"),
            AuthenticationError("x"),
            RateLimitError("x"),
            ServiceUnavailableError("x"),
        ):
            assert isinstance(exc, WindFlowException)


class TestNotFoundError:
    """Signature historique + forme message-libre du sweep."""

    def test_resource_signature(self):
        """(resource, resource_id) → message et details historiques."""
        exc = NotFoundError("Stack", "550e8400")
        assert exc.message == "Stack not found: 550e8400"
        assert exc.details == {"resource": "Stack", "resource_id": "550e8400"}
        assert exc.resource == "Stack"
        assert exc.resource_id == "550e8400"

    def test_resource_signature_unchanged_for_services(self):
        """Rétrocompatibilité : raise/catch comme STORY-124 (api_key_service)."""
        with pytest.raises(NotFoundError) as exc_info:
            raise NotFoundError("APIKey", "wf_ak_x")
        assert exc_info.value.details["resource"] == "APIKey"

    def test_free_message_form_preserves_text(self):
        """Forme message-libre (sweep) : le texte historique est préservé."""
        exc = NotFoundError("Container abc123 non trouvé")
        assert exc.message == "Container abc123 non trouvé"
        assert exc.status_code == 404
        assert exc.code == "NOT_FOUND"


class TestAuthenticationError:
    """Headers WWW-Authenticate + override code par instance."""

    def test_default_headers_www_authenticate(self):
        """401 typé → WWW-Authenticate: Bearer transporté (non-régression)."""
        exc = AuthenticationError("Could not validate credentials")
        assert exc.http_headers == {"WWW-Authenticate": "Bearer"}
        assert exc.status_code == 401

    def test_code_override_for_login(self):
        """Override d'instance : INVALID_CREDENTIALS prime sur le code classe."""
        exc = AuthenticationError(
            "Incorrect username or password", code="INVALID_CREDENTIALS"
        )
        assert exc.code == "INVALID_CREDENTIALS"
        assert exc.error_code == "INVALID_OR_EXPIRED_TOKEN"


class TestAPIErrorConstructor:
    """Constructeur APIError — défauts et override."""

    def test_details_none_becomes_empty_dict(self):
        """details=None → {} (jamais None — handler et logs sûrs)."""
        exc = APIError("message")
        assert exc.details == {}

    def test_code_override_takes_precedence(self):
        """code explicite > error_code de classe."""
        exc = ConflictError("x", code="CUSTOM_CODE")
        assert exc.code == "CUSTOM_CODE"
        assert exc.error_code == "CONFLICT"

    def test_custom_headers_override_class_defaults(self):
        """headers explicites (ex. Retry-After) remplacent ceux de classe."""
        exc = RateLimitError("x", headers={"Retry-After": "30"})
        assert exc.http_headers == {"Retry-After": "30"}


class TestLegacyClassesRetrocompatibility:
    """Classes techniques : attributs et signatures inchangés (AC story)."""

    def test_command_execution_error_signature(self):
        """(command, exit_status, stderr) → message et details complets."""
        exc = CommandExecutionError("docker ps", 1, "boom\n")
        assert exc.command == "docker ps"
        assert exc.exit_status == 1
        assert exc.stderr == "boom"  # strippé
        assert exc.details == {
            "command": "docker ps",
            "exit_status": 1,
            "stderr": "boom",
        }
        # hérite de WindFlowException → handler global (500 par défaut)
        assert isinstance(exc, WindFlowException)

    def test_invalid_api_key_error_default_reason(self):
        """Anti-énumération : message par défaut générique (STORY-124)."""
        exc = InvalidApiKeyError()
        assert exc.reason == "Invalid API key"
        assert exc.message == "Invalid API key"

    def test_invalid_refresh_token_error_default_reason(self):
        """Anti-énumération : message par défaut générique (STORY-123)."""
        exc = InvalidRefreshTokenError()
        assert exc.reason == "Invalid or expired refresh token"

    def test_secret_errors_no_crypto_material(self):
        """Secret*Error : instanciation sans matériel cryptographique."""
        for exc in (SecretEncryptionError("echec"), SecretDecryptionError("echec")):
            assert exc.message == "echec"
            assert isinstance(exc, WindFlowException)


class TestRaiseFromChaining:
    """Chaînage ``raise ... from exc`` préservé par la hiérarchie."""

    def test_chained_raise_preserved(self):
        """Le pattern sweep ``except X: raise Typée(...) from exc`` fonctionne."""
        original = ValueError("cause")
        with pytest.raises(NotFoundError) as exc_info:
            try:
                raise original
            except ValueError as exc:
                raise NotFoundError("API key not found") from exc
        assert exc_info.value.__cause__ is original
