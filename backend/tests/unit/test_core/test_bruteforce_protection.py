"""
Tests unitaires de la protection brute-force du login (STORY-104 / P0-5).

Couvre :
- Backend mémoire : fenêtre glissante, armature/expiration du blocage,
  normalisation du username, reset, purge amortie, clé par username (pas IP) ;
- Backend Redis (client mocké) : pipeline ZADD/EXPIRE/SETEX/DELETE, TTL,
  fallback mémoire quand ``FastAPILimiter.redis`` n'est pas initialisé ;
- Parité des deux backends (AC 3 / AC 5).

Le temps est avancé via les wrappers patchables ``_monotonic``/``_wall``
(sans patcher ``time`` globalement).
"""

from collections import deque
from unittest.mock import AsyncMock

import pytest
from fastapi_limiter import FastAPILimiter

from app.core import bruteforce_protection
from app.core.bruteforce_protection import (
    BruteforceProtector,
    normalize_username,
)


class FakeClock:
    """Horloge patchable : retourne `now`, avançable via `advance()`."""

    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# Paramètres réduits pour des scénarios courts (3 échecs / blocage 60 s / fenêtre 120 s)
MAX_ATTEMPTS = 3
LOCKOUT_SECONDS = 60
WINDOW_SECONDS = 120


def make_protector() -> BruteforceProtector:
    """Construit un protector avec des paramètres réduits (pattern test_rate_limit)."""
    return BruteforceProtector(
        max_attempts=MAX_ATTEMPTS,
        lockout_seconds=LOCKOUT_SECONDS,
        window_seconds=WINDOW_SECONDS,
    )


class TestNormalizeUsername:
    """Normalisation de la clé de compteur (anti-bypass casse/espaces)."""

    def test_strips_and_lowercases(self):
        """«  Admin  » → « admin » (lookup DB inchangé, clé du store normalisée)."""
        assert normalize_username("  Admin  ") == "admin"
        assert normalize_username("USER@Test.IO") == "user@test.io"
        assert normalize_username("bob") == "bob"


class TestBruteforceProtectorMemory:
    """Backend mémoire (paramètres réduits 3 / 60 / 120)."""

    @pytest.mark.asyncio
    async def test_is_locked_out_false_initially(self):
        """Cas nominal : aucun échec → (False, 0)."""
        protector = make_protector()
        assert await protector.is_locked_out("admin") == (False, 0)

    @pytest.mark.asyncio
    async def test_lockout_armed_after_max_failures(self, monkeypatch):
        """3 échecs → is_locked_out → (True, retry_after > 0)."""
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)
        protector = make_protector()

        counts = [await protector.register_failure("admin") for _ in range(3)]
        assert counts == [1, 2, 3]

        locked, retry_after = await protector.is_locked_out("admin")
        assert locked is True
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_lockout_retry_after_positive_and_decreasing(self, monkeypatch):
        """retry_after décroît quand _monotonic avance."""
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)
        protector = make_protector()

        for _ in range(3):
            await protector.register_failure("admin")

        _, retry_early = await protector.is_locked_out("admin")
        clock.advance(50.0)
        _, retry_late = await protector.is_locked_out("admin")

        assert retry_early > retry_late > 0

    @pytest.mark.asyncio
    async def test_lockout_expires_after_lockout_seconds(self, monkeypatch):
        """AC 2/AC 5 : bloqué puis _monotonic + 61 → (False, 0)."""
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)
        protector = make_protector()

        for _ in range(3):
            await protector.register_failure("admin")
        assert (await protector.is_locked_out("admin"))[0] is True

        clock.advance(LOCKOUT_SECONDS + 1)
        assert await protector.is_locked_out("admin") == (False, 0)

    @pytest.mark.asyncio
    async def test_failures_outside_window_are_purged(self, monkeypatch):
        """AC 2/AC 5 (test_counter_resets_after_window, volet unitaire) : fenêtre glissante."""
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)
        protector = make_protector()

        await protector.register_failure("admin")
        await protector.register_failure("admin")

        # Au-delà de la fenêtre (120 s) : les 2 échecs sont purgés, celui-ci
        # compte seul
        clock.advance(WINDOW_SECONDS + 1.0)
        count = await protector.register_failure("admin")
        assert count == 1

        # Et le blocage n'est PAS armé (1 seul échec dans la fenêtre)
        assert (await protector.is_locked_out("admin"))[0] is False

    @pytest.mark.asyncio
    async def test_reset_clears_failures_and_lockout(self, monkeypatch):
        """AC 2 : reset vide l'état du username (appelé après login réussi)."""
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)
        protector = make_protector()

        for _ in range(3):
            await protector.register_failure("admin")
        assert (await protector.is_locked_out("admin"))[0] is True

        await protector.reset("admin")
        assert await protector.is_locked_out("admin") == (False, 0)
        assert "admin" not in protector._failures
        assert "admin" not in protector._lockout_until

    @pytest.mark.asyncio
    async def test_username_normalization_same_key(self, monkeypatch):
        """« Admin », « admin », «  admin  » → même compteur (introspection du store)."""
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)
        protector = make_protector()

        await protector.register_failure("Admin")
        await protector.register_failure("  admin  ")
        count = await protector.register_failure("ADMIN")

        # 3 échecs via 3 variantes de casse → même clé → seuil atteint → blocage
        assert count == MAX_ATTEMPTS
        assert list(protector._lockout_until.keys()) == ["admin"]
        assert len(protector._failures) == 0  # deque vidée à l'armature

    @pytest.mark.asyncio
    async def test_distinct_usernames_independent(self, monkeypatch):
        """Username A bloqué → B non affecté."""
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)
        protector = make_protector()

        for _ in range(3):
            await protector.register_failure("alice")
        await protector.register_failure("bob")

        assert (await protector.is_locked_out("alice"))[0] is True
        assert await protector.is_locked_out("bob") == (False, 0)

    @pytest.mark.asyncio
    async def test_purge_expired_removes_stale_entries(self, monkeypatch):
        """Purge amortie : clés vides/périmées et lockouts expirés évacués."""
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)
        protector = make_protector()

        await protector.register_failure("stale")  # échec à t=100
        for _ in range(3):
            await protector.register_failure("locked")  # blocage armé à t=100
        # Simulation d'une deque vide résiduelle (introspection du store)
        protector._failures["empty"] = deque()

        clock.advance(WINDOW_SECONDS + 1.0)
        protector.purge_expired()

        assert "stale" not in protector._failures
        assert "empty" not in protector._failures
        # Blocage expiré (> lockout_seconds) : évacué
        assert "locked" not in protector._lockout_until

    @pytest.mark.asyncio
    async def test_counter_keyed_by_username_not_ip(self, monkeypatch):
        """AC 1/AC 5 : les clés internes contiennent le username normalisé, aucune IP."""
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)
        protector = make_protector()

        for _ in range(3):
            await protector.register_failure("alice")

        all_keys = list(protector._failures.keys()) + list(
            protector._lockout_until.keys()
        )
        assert all_keys == ["alice"]
        # Aucune IP stockée dans les clés (elle est loggée en amont par l'endpoint)
        for key in all_keys:
            assert "." not in key  # pas de forme d'adresse IP


class TestBruteforceProtectorRedis:
    """Backend Redis (client AsyncMock injecté via _redis)."""

    @pytest.fixture
    def redis_mock(self) -> AsyncMock:
        mock = AsyncMock()
        mock.ttl.return_value = 42
        mock.zcard.return_value = 0
        return mock

    @staticmethod
    def _with_redis(protector: BruteforceProtector, redis_mock: AsyncMock) -> None:
        protector._redis = lambda: redis_mock  # type: ignore[method-assign]

    @pytest.mark.asyncio
    async def test_is_locked_out_uses_ttl(self, redis_mock):
        """ttl > 0 → (True, ttl) ; ttl <= 0 → (False, 0)."""
        protector = make_protector()
        self._with_redis(protector, redis_mock)

        redis_mock.ttl.return_value = 42
        assert await protector.is_locked_out("admin") == (True, 42)

        redis_mock.ttl.return_value = 0
        assert await protector.is_locked_out("admin") == (False, 0)

        redis_mock.ttl.return_value = -2  # clé inexistante (sémantique Redis)
        assert await protector.is_locked_out("admin") == (False, 0)

    @pytest.mark.asyncio
    async def test_register_failure_pipeline(self, redis_mock, monkeypatch):
        """Vérifie zremrangebyscore + zadd + expire + zcard ; au seuil → setex + delete."""
        wall = FakeClock(start=1_000.0)
        monkeypatch.setattr(bruteforce_protection, "_wall", wall)
        protector = make_protector()
        self._with_redis(protector, redis_mock)

        # Sous le seuil : pipeline de comptage uniquement
        redis_mock.zcard.return_value = 1
        count = await protector.register_failure("admin")
        assert count == 1

        redis_mock.zremrangebyscore.assert_called_once_with(
            "wf:bf:fail:admin", 0, wall.now - WINDOW_SECONDS
        )
        redis_mock.zadd.assert_called_once_with(
            "wf:bf:fail:admin", {str(wall.now): wall.now}
        )
        redis_mock.expire.assert_called_once_with("wf:bf:fail:admin", WINDOW_SECONDS)
        redis_mock.setex.assert_not_called()
        redis_mock.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_failure_arms_lockout_at_threshold(
        self, redis_mock, monkeypatch
    ):
        """Au seuil (zcard >= max_attempts) → setex(lock, lockout) + delete(fail)."""
        wall = FakeClock(start=1_000.0)
        monkeypatch.setattr(bruteforce_protection, "_wall", wall)
        protector = make_protector()
        self._with_redis(protector, redis_mock)

        redis_mock.zcard.return_value = MAX_ATTEMPTS
        count = await protector.register_failure("admin")

        assert count == MAX_ATTEMPTS
        redis_mock.setex.assert_called_once_with(
            "wf:bf:lock:admin", LOCKOUT_SECONDS, "1"
        )
        redis_mock.delete.assert_called_once_with("wf:bf:fail:admin")

    @pytest.mark.asyncio
    async def test_reset_deletes_both_keys(self, redis_mock):
        """reset → delete sur les clés fail et lock."""
        protector = make_protector()
        self._with_redis(protector, redis_mock)

        await protector.reset("admin")
        redis_mock.delete.assert_awaited_once_with(
            "wf:bf:fail:admin", "wf:bf:lock:admin"
        )

    @pytest.mark.asyncio
    async def test_falls_back_to_memory_when_redis_uninitialized(self, monkeypatch):
        """AC 3 : FastAPILimiter.redis non initialisé (None) → stratégie mémoire."""
        monkeypatch.setattr(FastAPILimiter, "redis", None)
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)
        protector = make_protector()

        assert protector._redis() is None  # bien la branche mémoire

        for _ in range(MAX_ATTEMPTS):
            await protector.register_failure("admin")
        locked, _ = await protector.is_locked_out("admin")

        assert locked is True
        assert "admin" in protector._lockout_until  # état mémoire peuplé

    @pytest.mark.asyncio
    async def test_storage_memory_and_redis_paths(self, redis_mock, monkeypatch):
        """AC 5 : même scénario 3-échecs sur les deux backends → mêmes verdicts."""
        clock = FakeClock(start=100.0)
        monkeypatch.setattr(bruteforce_protection, "_monotonic", clock)

        # Backend mémoire
        memory_protector = make_protector()
        for _ in range(MAX_ATTEMPTS):
            await memory_protector.register_failure("admin")
        memory_verdict = await memory_protector.is_locked_out("admin")

        # Backend Redis
        monkeypatch.setattr(bruteforce_protection, "_wall", FakeClock(start=1_000.0))
        redis_protector = make_protector()
        self._with_redis(redis_protector, redis_mock)
        redis_mock.ttl.return_value = LOCKOUT_SECONDS
        for _ in range(MAX_ATTEMPTS):
            await redis_protector.register_failure("admin")
        redis_verdict = await redis_protector.is_locked_out("admin")

        assert memory_verdict[0] is True
        assert redis_verdict[0] is True
        # retry_after > 0 sur les deux chemins (durée exacte dépend du backend)
        assert memory_verdict[1] > 0
        assert redis_verdict[1] > 0


class TestSingleton:
    """Le singleton module-level lit les settings (Tâche 2, point 5)."""

    def test_singleton_parameters_from_settings(self):
        """Le singleton expose les valeurs configurées (5 / 300 / 600 par défaut)."""
        from app.core.bruteforce_protection import bruteforce_protector as singleton
        from app.config import settings

        assert singleton.max_attempts == settings.auth_max_attempts
        assert singleton.lockout_seconds == settings.auth_lockout_seconds
        assert singleton.window_seconds == settings.auth_attempt_window_seconds
        assert settings.auth_max_attempts == 5
        assert settings.auth_lockout_seconds == 300
        assert settings.auth_attempt_window_seconds == 600

    def test_reset_all_clears_memory_state(self):
        """reset_all() vide l'état (utilisé par la fixture conftest)."""
        from app.core.bruteforce_protection import bruteforce_protector as singleton

        singleton._failures["someone"] = deque([1.0])
        singleton._lockout_until["someone"] = 2.0
        singleton.reset_all()

        assert singleton._failures == {}
        assert singleton._lockout_until == {}
