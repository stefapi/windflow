"""Tests unitaires du service système — health & readiness (STORY-129).

Couvre (story Tâche 6, rules 35) :
- ``get_health`` : DB saine → healthy + services.database ; DB down →
  unhealthy ; rate limiter sondé uniquement si configuré ;
- ``get_readiness`` : tout sain → (ready, 200) ; DB down → 503 ;
  migrations ``current != head`` → pending + 503 ; base sans
  ``alembic_version`` (``current: null``) → 503 ; Redis configuré down →
  503 ; Redis non configuré → check absent ;
- AC 4 (anti-fingerprinting) : payload de readiness **sans** clé
  ``version``/``environment`` ;
- résilience : une exception d'un check produit un check unhealthy sans
  jamais lever (le endpoint doit toujours répondre).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import system_service as system_service_module
from app.services.system_service import SystemService


@pytest.fixture(autouse=True)
def _redis_not_configured(monkeypatch):
    """Rate limiting désactivé par défaut — check redis absent."""
    monkeypatch.setattr(system_service_module.settings, "rate_limit_enabled", False)
    monkeypatch.setattr(system_service_module.settings, "rate_limit_storage_url", None)


def _engine_mock() -> MagicMock:
    """Engine async factice : ``connect()`` → context manager async."""
    engine = MagicMock()
    context_manager = MagicMock()
    engine.connect.return_value = context_manager
    context_manager.__aenter__ = AsyncMock(return_value=MagicMock())
    context_manager.__aexit__ = AsyncMock(return_value=False)
    return engine


class TestGetHealth:
    """Health historique — comportement du /health racine préservé."""

    async def test_healthy_when_db_up(self):
        """DB saine → status healthy + services.database présent."""
        with patch.object(
            system_service_module.db,
            "health_check",
            new=AsyncMock(return_value=True),
        ):
            payload = await SystemService.get_health()

        assert payload["status"] == "healthy"
        assert payload["services"]["database"]["status"] == "healthy"
        assert payload["services"]["database"]["type"] in ("sqlite", "postgresql")
        assert "version" in payload  # contrat historique conservé

    async def test_unhealthy_when_db_down(self):
        """DB down → status unhealthy."""
        with patch.object(
            system_service_module.db,
            "health_check",
            new=AsyncMock(return_value=False),
        ):
            payload = await SystemService.get_health()

        assert payload["status"] == "unhealthy"
        assert payload["services"]["database"]["status"] == "unhealthy"

    async def test_rate_limiter_checked_only_when_configured(self, monkeypatch):
        """Redis sondé uniquement si rate limit + storage URL configurés."""
        monkeypatch.setattr(system_service_module.settings, "rate_limit_enabled", True)
        monkeypatch.setattr(
            system_service_module.settings,
            "rate_limit_storage_url",
            "redis://localhost:6379/0",
        )
        with patch.object(
            system_service_module.db,
            "health_check",
            new=AsyncMock(return_value=True),
        ), patch.object(
            SystemService, "_check_redis", new=AsyncMock(return_value=True)
        ):
            payload = await SystemService.get_health()

        assert payload["services"]["rate_limiter"]["status"] == "healthy"


class TestGetReadiness:
    """Readiness — signal orchestrateurs (200 prêt / 503 causes)."""

    async def test_ready_when_all_checks_healthy(self):
        """Tout sain → (status ready, 200)."""
        with patch.object(
            SystemService,
            "_database_check",
            new=AsyncMock(return_value={"status": "healthy"}),
        ), patch.object(
            SystemService,
            "_migrations_check",
            new=AsyncMock(
                return_value={
                    "status": "ok",
                    "current": "rev1",
                    "head": "rev1",
                }
            ),
        ):
            payload, code = await SystemService.get_readiness()

        assert code == 200
        assert payload["status"] == "ready"
        assert payload["checks"]["database"]["status"] == "healthy"
        assert payload["checks"]["migrations"]["status"] == "ok"

    async def test_unready_503_when_db_down(self):
        """DB down → 503 avec cause database unhealthy."""
        with patch.object(
            SystemService,
            "_database_check",
            new=AsyncMock(return_value={"status": "unhealthy"}),
        ), patch.object(
            SystemService,
            "_migrations_check",
            new=AsyncMock(
                return_value={
                    "status": "ok",
                    "current": "rev1",
                    "head": "rev1",
                }
            ),
        ):
            payload, code = await SystemService.get_readiness()

        assert code == 503
        assert payload["status"] == "unready"
        assert payload["checks"]["database"]["status"] == "unhealthy"

    async def test_unready_503_when_migrations_pending(self):
        """``current != head`` → check migrations pending + 503."""
        with patch.object(
            SystemService,
            "_database_check",
            new=AsyncMock(return_value={"status": "healthy"}),
        ), patch.object(
            SystemService,
            "_migrations_check",
            new=AsyncMock(
                return_value={
                    "status": "pending",
                    "current": "old-rev",
                    "head": "new-rev",
                }
            ),
        ):
            payload, code = await SystemService.get_readiness()

        assert code == 503
        assert payload["checks"]["migrations"]["status"] == "pending"

    async def test_payload_has_no_version_or_environment(self):
        """AC 4 — anti-fingerprinting : ni version ni environnement."""
        with patch.object(
            SystemService,
            "_database_check",
            new=AsyncMock(return_value={"status": "healthy"}),
        ), patch.object(
            SystemService,
            "_migrations_check",
            new=AsyncMock(
                return_value={
                    "status": "ok",
                    "current": "rev1",
                    "head": "rev1",
                }
            ),
        ):
            payload, _code = await SystemService.get_readiness()

        assert "version" not in payload
        assert "environment" not in payload

    async def test_no_redis_check_when_not_configured(self):
        """Redis non configuré → check absent, readiness possible (200)."""
        with patch.object(
            SystemService,
            "_database_check",
            new=AsyncMock(return_value={"status": "healthy"}),
        ), patch.object(
            SystemService,
            "_migrations_check",
            new=AsyncMock(
                return_value={
                    "status": "ok",
                    "current": "rev1",
                    "head": "rev1",
                }
            ),
        ):
            payload, code = await SystemService.get_readiness()

        assert "redis" not in payload["checks"]
        assert code == 200

    async def test_unready_503_when_redis_down_and_configured(self, monkeypatch):
        """Redis configuré mais down → 503 (dépendance optionnelle réelle)."""
        monkeypatch.setattr(system_service_module.settings, "rate_limit_enabled", True)
        monkeypatch.setattr(
            system_service_module.settings,
            "rate_limit_storage_url",
            "redis://localhost:6379/0",
        )
        with patch.object(
            SystemService,
            "_database_check",
            new=AsyncMock(return_value={"status": "healthy"}),
        ), patch.object(
            SystemService,
            "_migrations_check",
            new=AsyncMock(
                return_value={
                    "status": "ok",
                    "current": "rev1",
                    "head": "rev1",
                }
            ),
        ), patch.object(
            SystemService, "_check_redis", new=AsyncMock(return_value=False)
        ):
            payload, code = await SystemService.get_readiness()

        assert code == 503
        assert payload["checks"]["redis"]["status"] == "unhealthy"


class TestMigrationsCheck:
    """Check « migrations appliquées » — current == head (arbitrage n°7)."""

    async def test_current_equals_head_is_ok(self, monkeypatch):
        """current == head → status ok."""
        monkeypatch.setattr(system_service_module.db, "engine", _engine_mock())
        script_dir = MagicMock()
        script_dir.get_current_head.return_value = "rev1"
        with patch.object(
            SystemService,
            "_current_revision",
            new=AsyncMock(return_value="rev1"),
        ), patch(
            "app.services.system_service.ScriptDirectory.from_config",
            return_value=script_dir,
        ):
            result = await SystemService._migrations_check()

        assert result["status"] == "ok"
        assert result["current"] == "rev1"
        assert result["head"] == "rev1"

    async def test_unversioned_db_is_pending(self, monkeypatch):
        """Base sans alembic_version → current None → pending (unready)."""
        monkeypatch.setattr(system_service_module.db, "engine", _engine_mock())
        script_dir = MagicMock()
        script_dir.get_current_head.return_value = "rev1"
        with patch.object(
            SystemService,
            "_current_revision",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.services.system_service.ScriptDirectory.from_config",
            return_value=script_dir,
        ):
            result = await SystemService._migrations_check()

        assert result["status"] == "pending"
        assert result["current"] is None

    async def test_engine_none_is_pending(self, monkeypatch):
        """Engine non initialisé (hors lifespan) → pending, sans lever."""
        monkeypatch.setattr(system_service_module.db, "engine", None)
        result = await SystemService._migrations_check()
        assert result["status"] == "pending"


class TestCheckResilience:
    """Erreur inattendue d'un check → unhealthy, jamais d'exception."""

    async def test_db_check_exception_is_contained(self):
        """``db.health_check`` qui lève → check unhealthy sans propager."""
        with patch.object(
            system_service_module.db,
            "health_check",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await SystemService._database_check()

        assert result["status"] == "unhealthy"

    async def test_migrations_check_exception_is_contained(self, monkeypatch):
        """Erreur Alembic → check pending, sans propager."""
        monkeypatch.setattr(system_service_module.db, "engine", _engine_mock())
        with patch.object(
            SystemService,
            "_current_revision",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await SystemService._migrations_check()

        assert result["status"] == "pending"
