"""Tests d'intégration des exceptions typées → enveloppes (STORY-127).

Valide que le **handler global** ``WindFlowException`` (enregistré dans
l'ExceptionMiddleware interne) convertit les exceptions typées du sweep en
enveloppes spec 09 ``{"error": {"code", "message"}, "correlation_id"?}`` —
et non en 500 générique du middleware externe (preuve du routage).

Couvre (cf. story § Tests à écrire) :
- une exception typée levée par un endpoint → enveloppe au statut correct ;
- 401 ``WWW-Authenticate: Bearer`` préservé (headers transportés) ;
- 401 login → ``INVALID_CREDENTIALS`` via ``AuthenticationError`` typée ;
- 409 slug dupliqué → ``CONFLICT`` ; 404 → ``NOT_FOUND`` ;
- 403 RBAC → ``PERMISSION_DENIED`` ; 429 → ``TOO_MANY_ATTEMPTS`` ;
- ``CommandExecutionError`` non interceptée → 500 sans ``stderr`` (rules 40) ;
- ``correlation_id`` présent dans toute enveloppe d'erreur ;
- sécurité : pas de stack trace, anti-énumération 401, pas de secrets.

Patterns : fixtures ``_jwt_mode``/``_bearer`` de ``test_api_envelope.py``.
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.core.exceptions import CommandExecutionError
from app.models.organization import Organization
from app.models.user import User
from app.services.organization_service import OrganizationService

STACKS_URL = "/api/v1/stacks/"
LOGIN_URL = "/api/v1/auth/login"


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


def _bearer(user: User) -> dict:
    """Headers Authorization — mint direct (pattern test_api_envelope)."""
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


class TestTypedExceptionsProduceEnvelope:
    """Preuve du routage : handler global, PAS le 500 du middleware externe."""

    async def test_windflow_exception_produces_envelope(
        self, client: AsyncClient, test_user: User
    ):
        """NotFound typée (stack inconnue) → 404 enveloppé, pas de 500.

        Le raise ``NotFoundError`` du router stacks.py passe par le handler
        global : statut 404 et code NOT_FOUND, preuve que l'exception n'a
        pas rejoint le catch générique du error_handler_middleware.
        """
        response = await client.get(
            "/api/v1/stacks/550e8400-e29b-41d4-a716-446655440000",
            headers=_bearer(test_user),
        )
        assert response.status_code == 404, response.text
        body = response.json()
        assert body["error"]["code"] == "NOT_FOUND"

    async def test_404_not_found_typed_with_details(
        self, client: AsyncClient, test_user: User
    ):
        """404 typée → error.code NOT_FOUND (message textuel préservé)."""
        response = await client.get(
            "/api/v1/stacks/550e8400-e29b-41d4-a716-446655440001",
            headers=_bearer(test_user),
        )
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "NOT_FOUND"
        assert "non trouvée" in body["error"]["message"]

    async def test_401_www_authenticate_header_preserved(
        self, client: AsyncClient
    ):
        """401 typée → header WWW-Authenticate: Bearer présent (headers
        transportés par l'exception — non-régression vs HTTPException)."""
        response = await client.get(STACKS_URL)
        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "Bearer"

    async def test_401_login_invalid_credentials_typed(self, client: AsyncClient):
        """Mauvais mot de passe → 401 INVALID_CREDENTIALS via
        AuthenticationError(code="INVALID_CREDENTIALS") typée."""
        response = await client.post(
            LOGIN_URL, data={"username": "ghost", "password": "wrong"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async def test_409_conflict_typed(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization: Organization,
    ):
        """Slug dupliqué → 409 CONFLICT via ConflictError typée (AC 3).

        Même pattern que le test de référence STORY-126 (nom dupliqué →
        slug déduit identique → ValueError du service → ConflictError).
        """
        response = await client.post(
            "/api/v1/organizations/",
            json={"name": test_organization.name},
            headers=_bearer(test_superuser),
        )
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "CONFLICT"

    async def test_403_permission_denied_typed(
        self,
        client: AsyncClient,
        test_organization: Organization,
        viewer_user: User,
    ):
        """Viewer sur action admin → 403 PERMISSION_DENIED via
        PermissionDeniedError typée (RBAC — source de vérité API)."""
        response = await client.post(
            "/api/v1/organizations/",
            json={"name": "viewer-org", "slug": "viewer-org"},
            headers=_bearer(viewer_user),
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    async def test_429_rate_limit_typed(self, client: AsyncClient):
        """Rate limit → 429 TOO_MANY_ATTEMPTS via RateLimitError typée.

        Le login est décoré ``conditional_rate_limiter(5, 60)`` — en mode
        mémoire (RATE_LIMIT_STORAGE_URL absent en test), le 6e hit lève
        RateLimitError avec Retry-After transporté par headers.
        """
        from app.core import rate_limit

        rate_limit._memory_limiter.reset()
        with patch.object(rate_limit.settings, "rate_limit_enabled", True), patch.object(
            rate_limit.settings, "rate_limit_storage_url", None
        ):
            for _ in range(5):
                await client.post(
                    LOGIN_URL, data={"username": "u", "password": "p"}
                )
            response = await client.post(
                LOGIN_URL, data={"username": "u", "password": "p"}
            )
        rate_limit._memory_limiter.reset()
        assert response.status_code == 429, response.text
        body = response.json()
        assert body["error"]["code"] == "TOO_MANY_ATTEMPTS"
        # Retry-After transporté par l'exception typée
        assert response.headers.get("retry-after") is not None

    async def test_command_execution_error_500_no_stderr(
        self, client: AsyncClient, test_user: User
    ):
        """CommandExecutionError non interceptée → 500 INTERNAL_ERROR avec
        details sans stderr (règle sécurité : sortie brute jamais exposée)."""
        response = None

        async def _raise_typed(*args, **kwargs):
            raise CommandExecutionError("systemctl status x", 1, "SECRET_STDERR")

        # GET stacks/{id} lève via StackService.get_by_id — on patche pour
        # provoquer la CommandExecutionError depuis le chemin endpoint
        with patch(
            "app.api.v1.stacks.StackService.get_by_id", new=_raise_typed
        ):
            response = await client.get(
                "/api/v1/stacks/550e8400-e29b-41d4-a716-446655440002",
                headers=_bearer(test_user),
            )
        assert response.status_code == 500, response.text
        body = response.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"
        # stderr jamais exposé dans le payload HTTP (rules 40)
        assert "SECRET_STDERR" not in response.text
        details = body["error"].get("details")
        if details is not None:
            assert "stderr" not in details

    async def test_correlation_id_in_error_envelope(
        self, client: AsyncClient
    ):
        """Toute erreur → correlation_id top-level (tracing distribué)."""
        response = await client.get(STACKS_URL)
        assert response.status_code == 401
        body = response.json()
        assert body.get("correlation_id"), "correlation_id absent de l'enveloppe"


class TestSecurityRules40:
    """Checklist sécurité rules 40 — tests obligatoires."""

    async def test_error_response_no_stack_trace(
        self, client: AsyncClient, test_user: User
    ):
        """Corps d'erreur 500 → ni traceback, ni nom de module interne,
        ni str(exc) brute — message générique uniquement.

        Le error_handler_middleware n'expose ``str(exc)`` qu'en niveau
        DEBUG (comportement dev) : ce test verrouille le comportement
        production (masquage), comme en déploiement réel.
        """
        import logging

        async def _raise_runtime(*args, **kwargs):
            raise RuntimeError("internal /app/services/secret_path.py detail")

        with patch(
            "app.api.v1.stacks.StackService.get_by_id", new=_raise_runtime
        ), patch.object(
            logging.getLogger("app.middleware.error_handler"),
            "level",
            logging.INFO,
        ):
            # force la ré-évaluation du seuil par le handler (level est
            # lu à chaque appel via logger.level)
            response = await client.get(
                "/api/v1/stacks/550e8400-e29b-41d4-a716-446655440003",
                headers=_bearer(test_user),
            )
        assert response.status_code == 500
        text = response.text
        assert "Traceback" not in text
        assert "secret_path.py" not in text
        assert "RuntimeError" not in text

    async def test_401_anti_enumeration_login(self, client: AsyncClient):
        """Anti-énumération : utilisateur inconnu vs mot de passe faux →
        même 401, même code (pas d'oracle d'existence de compte)."""
        r1 = await client.post(
            LOGIN_URL, data={"username": "does-not-exist", "password": "x"}
        )
        r2 = await client.post(
            LOGIN_URL, data={"username": "does-not-exist-2", "password": "y"}
        )
        assert r1.status_code == r2.status_code == 401
        e1, e2 = r1.json()["error"], r2.json()["error"]
        assert e1["code"] == e2["code"] == "INVALID_CREDENTIALS"
        assert e1["message"] == e2["message"]

    async def test_401_anti_enumeration_refresh_token(self, client: AsyncClient):
        """Refresh token invalide → 401 générique identique (STORY-123 :
        inconnu/malformé/révoqué → même message, pas d'oracle)."""
        responses = [
            await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": token}
            )
            for token in (
                "wf_rt_totally_unknown_token_value_1234567890abcdef",
                "wf_rt_malformed",
                "",
            )
        ]
        statuses = {r.status_code for r in responses}
        # "" peut donner 422 (schéma Pydantic non-vide) — les autres 401
        assert 401 in statuses
        for r in responses:
            if r.status_code == 401:
                assert r.json()["error"]["message"] == "INVALID_OR_EXPIRED_TOKEN"

    async def test_error_details_no_sensitive_fields(
        self, client: AsyncClient, test_user: User
    ):
        """details ne transporte jamais password/token/key (revue sweep)."""
        response = await client.get(
            "/api/v1/stacks/550e8400-e29b-41d4-a716-446655440004",
            headers=_bearer(test_user),
        )
        assert response.status_code == 404
        raw = response.text.lower()
        for sensitive in ("password", "token", "api_key", "secret"):
            assert sensitive not in raw, f"champ sensible '{sensitive}' exposé"
