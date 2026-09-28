"""Tests d'intégration pour les endpoints d'authentification."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import bruteforce_protection
from app.core.bruteforce_protection import bruteforce_protector
from app.core.rate_limit import _memory_limiter
from app.main import app
from app.models.user import User
from tests.conftest import error_code, unwrap


@pytest.mark.asyncio
class TestAuthAPI:
    """Tests d'intégration pour l'API d'authentification."""

    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test de login réussi."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "testpassword123"},
        )

        assert response.status_code == 200
        data = unwrap(response)
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Test de login avec mauvais mot de passe."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "wrongpassword"},
        )

        assert response.status_code == 401
        assert "error" in response.json()

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test de login avec utilisateur inexistant."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "nonexistent", "password": "password123"},
        )

        assert response.status_code == 401
        assert "error" in response.json()

    async def test_login_missing_credentials(self, client: AsyncClient):
        """Test de login avec credentials manquantes."""
        response = await client.post("/api/v1/auth/login", data={})

        assert response.status_code == 422  # Validation error

    async def test_authenticated_request(self, authenticated_client: AsyncClient):
        """Test d'une requête authentifiée."""
        response = await authenticated_client.get("/api/v1/users/me")

        assert response.status_code == 200
        data = unwrap(response)
        assert "id" in data
        assert "email" in data
        assert "username" in data

    async def test_unauthenticated_request(self, client: AsyncClient):
        """Test d'une requête non authentifiée sur route protégée."""
        response = await client.get("/api/v1/users/me")

        assert response.status_code == 401
        assert "error" in response.json()

    async def test_invalid_token(self, client: AsyncClient):
        """Test avec token JWT invalide."""
        client.headers.update({"Authorization": "Bearer invalid_token"})
        response = await client.get("/api/v1/users/me")

        assert response.status_code == 401
        assert "error" in response.json()

    async def test_superuser_access(self, admin_client: AsyncClient):
        """Test d'accès avec droits superuser."""
        response = await admin_client.get("/api/v1/users/me")

        assert response.status_code == 200
        data = unwrap(response)
        assert data["is_superuser"] is True


class FakeClock:
    """Horloge patchable : retourne `now`, avançable via `advance()`."""

    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.mark.asyncio
class TestBruteforceProtection:
    """
    Protection brute-force du login (STORY-104 / P0-5) — AC 1 à 5.

    Isolation des couches obligatoire : le rate limit volumétrique IP 5/min
    (STORY-102, résolu à l'import des routers) déclencherait son propre 429
    au 6e appel même-IP AVANT la logique brute-force. On reset son store
    mémoire avant chaque POST login ; son comportement propre est déjà couvert
    par test_rate_limiting.py. Le temps brute-force est avancé via le wrapper
    patchable `_monotonic` (le singleton consomme les settings 5/300/600).
    """

    LOGIN_URL = "/api/v1/auth/login"

    @staticmethod
    def _reset_volumetric_layer() -> None:
        """Isolation des couches : reset du RL volumétrique IP (STORY-102)."""
        _memory_limiter.reset()

    async def _login(self, client: AsyncClient, username: str, password: str):
        """POST /auth/login avec reset préalable de la couche volumétrique IP."""
        self._reset_volumetric_layer()
        return await client.post(
            self.LOGIN_URL, data={"username": username, "password": password}
        )

    async def _fail(self, client: AsyncClient, username: str) -> None:
        """Un échec de login (mauvais mot de passe) — attendu 401."""
        response = await self._login(client, username, "wrong-password")
        assert response.status_code == 401

    async def test_sixth_attempt_returns_429_with_retry_after(
        self, client: AsyncClient, test_user: User
    ):
        """AC 1/AC 5 : 5 échecs puis 6e essai avec le BON mot de passe → 429."""
        for _ in range(5):
            await self._fail(client, test_user.username)

        response = await self._login(client, test_user.username, "testpassword123")

        assert response.status_code == 429
        assert error_code(response) == "TOO_MANY_ATTEMPTS"
        retry_after = response.headers.get("Retry-After")
        assert retry_after is not None
        assert int(retry_after) > 0

    async def test_counter_resets_after_window(
        self, client: AsyncClient, test_user: User, monkeypatch
    ):
        """AC 2/AC 5 : au-delà de fenêtre+lockout (600+300 s), le login réussit."""
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)

        for _ in range(5):
            await self._fail(client, test_user.username)
        blocked = await self._login(client, test_user.username, "testpassword123")
        assert blocked.status_code == 429

        clock.advance(600 + 300 + 1)
        response = await self._login(client, test_user.username, "testpassword123")
        assert response.status_code == 200

    async def test_counter_reset_on_successful_login(
        self, client: AsyncClient, test_user: User
    ):
        """AC 2/AC 5 : login réussi → compteur remis à zéro (il faut à nouveau 5 échecs)."""
        # 4 échecs (sous le seuil)
        for _ in range(4):
            await self._fail(client, test_user.username)
        # Login réussi → reset du compteur
        ok = await self._login(client, test_user.username, "testpassword123")
        assert ok.status_code == 200

        # 4 nouveaux échecs post-reset : le 5e essai (bon mot de passe)
        # n'est PAS bloqué — le compteur était reparti de zéro
        for _ in range(4):
            await self._fail(client, test_user.username)
        response = await self._login(client, test_user.username, "testpassword123")
        assert response.status_code == 200

    async def test_counter_per_username_not_ip_only(
        self, client: AsyncClient, test_user: User, db_session
    ):
        """AC 1/AC 5 : échecs depuis 2 IP différentes → même compteur (par username)."""
        # Deux clients à IP source distincte (httpx ASGITransport supporte
        # `client=(host, port)`), même override get_db que la fixture `client`
        # (l'override est posé sur `app` pendant la durée du test)
        async with (
            AsyncClient(
                transport=ASGITransport(app=app, client=("1.1.1.1", 111)),
                base_url="http://test",
            ) as ip_a,
            AsyncClient(
                transport=ASGITransport(app=app, client=("2.2.2.2", 222)),
                base_url="http://test",
            ) as ip_b,
        ):
            for _ in range(3):
                await self._fail(ip_a, test_user.username)
            for _ in range(2):
                await self._fail(ip_b, test_user.username)

            # 6e essai avec le BON mot de passe depuis l'IP A → 429 :
            # le compteur est par username, pas par IP seule
            response = await self._login(ip_a, test_user.username, "testpassword123")

        assert response.status_code == 429
        assert error_code(response) == "TOO_MANY_ATTEMPTS"

    async def test_lockout_expires_after_5_minutes(
        self, client: AsyncClient, test_user: User, monkeypatch
    ):
        """AC 2/AC 5 : 5 échecs → 429 ; _monotonic + 301 s → login correct 200."""
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)

        for _ in range(5):
            await self._fail(client, test_user.username)
        blocked = await self._login(client, test_user.username, "testpassword123")
        assert blocked.status_code == 429

        clock.advance(301)
        response = await self._login(client, test_user.username, "testpassword123")
        assert response.status_code == 200

    async def test_storage_memory_and_redis_paths(
        self, client: AsyncClient, test_user: User
    ):
        """AC 3/AC 5 (volet intégration) : sans Redis, les échecs peuplent le store mémoire.

        Sans RATE_LIMIT_STORAGE_URL en tests, ``FastAPILimiter.redis`` n'est pas
        initialisé (None) → le singleton utilise la branche mémoire (introspection
        après POST). Le chemin Redis est couvert unitairement via client mocké
        (test_bruteforce_protection.py::TestBruteforceProtectorRedis).
        """
        assert bruteforce_protector._redis() is None  # branche mémoire active

        for _ in range(5):
            await self._fail(client, test_user.username)
        response = await self._login(client, test_user.username, "testpassword123")

        assert response.status_code == 429
        key = test_user.username.strip().lower()
        assert key in bruteforce_protector._lockout_until  # store mémoire peuplé
        assert key not in bruteforce_protector._failures  # deque vidée à l'armature

    # ------------------------------------------------------------------ #
    # Compléments sécurité / non-régression (AC 4)                       #
    # ------------------------------------------------------------------ #

    async def test_login_401_message_unchanged_under_threshold(
        self, client: AsyncClient, test_user: User
    ):
        """AC 4 : sous le seuil → 401 exactement « Incorrect username or password »."""
        response = await self._login(client, test_user.username, "wrongpassword")

        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Incorrect username or password"

    async def test_lockout_applies_to_unknown_username(self, client: AsyncClient):
        """Anti-énumération : username inexistant → même comportement (429 au 6e)."""
        for _ in range(5):
            await self._fail(client, "ghost-user")

        response = await self._login(client, "ghost-user", "whatever")

        assert response.status_code == 429
        assert error_code(response) == "TOO_MANY_ATTEMPTS"

    async def test_locked_response_does_not_leak_info(
        self, client: AsyncClient, test_user: User
    ):
        """AC 4 : le 429 ne divulgue ni username cible ni compteur ; Retry-After numérique."""
        for _ in range(5):
            await self._fail(client, test_user.username)

        response = await self._login(client, test_user.username, "testpassword123")
        body = response.text

        assert response.status_code == 429
        assert set(response.json().keys()) == {"error", "correlation_id"}  # aucun champ additionnel
        assert test_user.username not in body  # pas de username cible divulgué
        assert "testpassword123" not in body  # jamais le mot de passe soumis
        assert error_code(response) == "TOO_MANY_ATTEMPTS"
        retry_after = response.headers.get("Retry-After")
        assert retry_after is not None
        assert retry_after.isdigit()

    async def test_login_missing_credentials_still_422(self, client: AsyncClient):
        """AC 4 : non-régression validation — credentials manquantes → 422."""
        self._reset_volumetric_layer()
        response = await client.post(self.LOGIN_URL, data={})

        assert response.status_code == 422
