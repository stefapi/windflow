"""
Tests unitaires des endpoints API des hooks lifecycle.

Couvre : GET /hooks/logs (listing), GET /hooks/logs/{log_id} (détail),
sécurité (401, 403, 404), pagination.

Note : DISABLE_AUTH=true en dev, les tests de sécurité 401/403
utilisent monkeypatch pour forcer l'authentification.
"""

import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.plugin import Plugin, PluginStatus
from app.models.plugin_hook_log import PluginHookLog


# ── Helpers ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def auth_enabled(monkeypatch):
    """Active l'authentification réelle pour les tests de sécurité."""
    monkeypatch.setattr(settings, "disable_auth", False)


# ── Tests GET /plugins/{plugin_id}/hooks/logs ───────────────────────────────


class TestGetHookLogs:
    """Tests de l'endpoint GET /plugins/{plugin_id}/hooks/logs."""

    @pytest.mark.asyncio
    async def test_get_hook_logs_returns_200_authenticated(
        self,
        admin_client: AsyncClient,
        db_session,
        test_organization,
        test_superuser,
    ) -> None:
        """Cas nominal : retourne les logs existants."""
        # Créer un plugin
        plugin = Plugin(
            name="hook-test-plugin",
            version="1.0.0",
            display_name="Hook Test Plugin",
            description="A plugin for hook tests",
            category="other",
            type="extension",
            status=PluginStatus.INSTALLED.value,
            manifest_data={
                "name": "hook-test-plugin",
                "version": "1.0.0",
                "hooks": {"on_install": "scripts/install.sh"},
            },
            config_values={},
            organization_id=test_organization.id,
            installed_by=test_superuser.id,
        )
        db_session.add(plugin)
        await db_session.commit()
        await db_session.refresh(plugin)

        # Créer un log de hook
        log = PluginHookLog(
            plugin_id=plugin.id,
            hook_name="on_install",
            script_path="scripts/install.sh",
            status="success",
            exit_code=0,
            stdout="Installation OK",
            stderr="",
            triggered_by=test_superuser.id,
        )
        db_session.add(log)
        await db_session.commit()

        response = await admin_client.get(
            f"/api/v1/plugins/{plugin.id}/hooks/logs"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["hook_name"] == "on_install"
        assert data[0]["status"] == "success"
        # Le listing ne contient pas stdout/stderr
        assert "stdout" not in data[0]
        assert "stderr" not in data[0]

    @pytest.mark.asyncio
    async def test_get_hook_logs_returns_empty_list(
        self,
        admin_client: AsyncClient,
        db_session,
        test_organization,
        test_superuser,
    ) -> None:
        """Cas nominal : aucun log → liste vide []."""
        plugin = Plugin(
            name="empty-hooks-plugin",
            version="1.0.0",
            display_name="Empty Hooks Plugin",
            description="A plugin with no hook logs",
            category="other",
            type="extension",
            status=PluginStatus.INSTALLED.value,
            manifest_data={
                "name": "empty-hooks-plugin",
                "version": "1.0.0",
            },
            config_values={},
            organization_id=test_organization.id,
            installed_by=test_superuser.id,
        )
        db_session.add(plugin)
        await db_session.commit()
        await db_session.refresh(plugin)

        response = await admin_client.get(
            f"/api/v1/plugins/{plugin.id}/hooks/logs"
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_hook_logs_returns_401_without_token(
        self,
        client: AsyncClient,
        db_session,
        test_organization,
        test_superuser,
        auth_enabled,
    ) -> None:
        """Sécurité : pas de token → 401."""
        plugin = Plugin(
            name="auth-test-plugin",
            version="1.0.0",
            display_name="Auth Test Plugin",
            description="A plugin for auth tests",
            category="other",
            type="extension",
            status=PluginStatus.INSTALLED.value,
            manifest_data={"name": "auth-test-plugin", "version": "1.0.0"},
            config_values={},
            organization_id=test_organization.id,
            installed_by=test_superuser.id,
        )
        db_session.add(plugin)
        await db_session.commit()
        await db_session.refresh(plugin)

        response = await client.get(
            f"/api/v1/plugins/{plugin.id}/hooks/logs"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_hook_logs_returns_404_plugin_not_found(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """Plugin inexistant → 404."""
        response = await admin_client.get(
            "/api/v1/plugins/nonexistent-plugin-id/hooks/logs"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_hook_logs_returns_403_for_other_org(
        self,
        admin_client: AsyncClient,
        db_session,
        test_superuser,
    ) -> None:
        """Sécurité : plugin d'une autre organisation → 403."""
        # Créer une autre organisation et un plugin dedans
        from app.models.organization import Organization

        other_org = Organization(
            name="Other Organization",
            slug="other-org",
            description="Another organization",
        )
        db_session.add(other_org)
        await db_session.commit()
        await db_session.refresh(other_org)

        plugin = Plugin(
            name="other-org-plugin",
            version="1.0.0",
            display_name="Other Org Plugin",
            description="A plugin in another org",
            category="other",
            type="extension",
            status=PluginStatus.INSTALLED.value,
            manifest_data={"name": "other-org-plugin", "version": "1.0.0"},
            config_values={},
            organization_id=other_org.id,
            installed_by=test_superuser.id,
        )
        db_session.add(plugin)
        await db_session.commit()
        await db_session.refresh(plugin)

        response = await admin_client.get(
            f"/api/v1/plugins/{plugin.id}/hooks/logs"
        )
        assert response.status_code == 403


# ── Tests GET /plugins/{plugin_id}/hooks/logs/{log_id} ──────────────────────


class TestGetHookLogDetail:
    """Tests de l'endpoint GET /plugins/{plugin_id}/hooks/logs/{log_id}."""

    @pytest.mark.asyncio
    async def test_get_hook_log_detail_returns_200(
        self,
        admin_client: AsyncClient,
        db_session,
        test_organization,
        test_superuser,
    ) -> None:
        """GET /{plugin_id}/hooks/logs/{log_id} retourne le détail avec stdout/stderr."""
        plugin = Plugin(
            name="detail-test-plugin",
            version="1.0.0",
            display_name="Detail Test Plugin",
            description="A plugin for detail tests",
            category="other",
            type="extension",
            status=PluginStatus.INSTALLED.value,
            manifest_data={
                "name": "detail-test-plugin",
                "version": "1.0.0",
                "hooks": {"on_install": "scripts/install.sh"},
            },
            config_values={},
            organization_id=test_organization.id,
            installed_by=test_superuser.id,
        )
        db_session.add(plugin)
        await db_session.commit()
        await db_session.refresh(plugin)

        log = PluginHookLog(
            plugin_id=plugin.id,
            hook_name="on_install",
            script_path="scripts/install.sh",
            status="success",
            exit_code=0,
            stdout="Installation output here",
            stderr="",
            triggered_by=test_superuser.id,
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        response = await admin_client.get(
            f"/api/v1/plugins/{plugin.id}/hooks/logs/{log.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == log.id
        assert data["hook_name"] == "on_install"
        assert data["stdout"] == "Installation output here"
        assert data["stderr"] == ""

    @pytest.mark.asyncio
    async def test_get_hook_log_detail_returns_404(
        self,
        admin_client: AsyncClient,
        db_session,
        test_organization,
        test_superuser,
    ) -> None:
        """Log inexistant → 404."""
        plugin = Plugin(
            name="detail-404-plugin",
            version="1.0.0",
            display_name="Detail 404 Plugin",
            description="A plugin for 404 detail tests",
            category="other",
            type="extension",
            status=PluginStatus.INSTALLED.value,
            manifest_data={"name": "detail-404-plugin", "version": "1.0.0"},
            config_values={},
            organization_id=test_organization.id,
            installed_by=test_superuser.id,
        )
        db_session.add(plugin)
        await db_session.commit()
        await db_session.refresh(plugin)

        response = await admin_client.get(
            f"/api/v1/plugins/{plugin.id}/hooks/logs/nonexistent-log-id"
        )
        assert response.status_code == 404


# ── Tests pagination ────────────────────────────────────────────────────────


class TestHookLogsPagination:
    """Tests de pagination des logs de hooks."""

    @pytest.mark.asyncio
    async def test_hook_logs_pagination_works(
        self,
        admin_client: AsyncClient,
        db_session,
        test_organization,
        test_superuser,
    ) -> None:
        """Paramètres skip/limit fonctionnent correctement."""
        plugin = Plugin(
            name="pagination-test-plugin",
            version="1.0.0",
            display_name="Pagination Test Plugin",
            description="A plugin for pagination tests",
            category="other",
            type="extension",
            status=PluginStatus.INSTALLED.value,
            manifest_data={
                "name": "pagination-test-plugin",
                "version": "1.0.0",
            },
            config_values={},
            organization_id=test_organization.id,
            installed_by=test_superuser.id,
        )
        db_session.add(plugin)
        await db_session.commit()
        await db_session.refresh(plugin)

        # Créer 5 logs
        for i in range(5):
            log = PluginHookLog(
                plugin_id=plugin.id,
                hook_name="on_install",
                script_path=f"scripts/install_{i}.sh",
                status="success",
                exit_code=0,
                stdout=f"Output {i}",
                stderr="",
                triggered_by=test_superuser.id,
            )
            db_session.add(log)
        await db_session.commit()

        # Tester skip=0, limit=2
        response = await admin_client.get(
            f"/api/v1/plugins/{plugin.id}/hooks/logs",
            params={"skip": 0, "limit": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Tester skip=2, limit=2
        response = await admin_client.get(
            f"/api/v1/plugins/{plugin.id}/hooks/logs",
            params={"skip": 2, "limit": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Tester skip=4, limit=10
        response = await admin_client.get(
            f"/api/v1/plugins/{plugin.id}/hooks/logs",
            params={"skip": 4, "limit": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
