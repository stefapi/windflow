"""
Tests unitaires du service PluginLifecycleService.

Couvre : exécution nominale de chaque hook, hook en échec, timeout,
hook non déclaré (no-op), validation anti path traversal, logging des résultats,
masquage des secrets dans les env vars.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import WindFlowException
from app.models.organization import Organization
from app.models.plugin import Plugin, PluginStatus
from app.models.plugin_hook_log import PluginHookLog
from app.models.user import User
from app.services.plugin_lifecycle_service import PluginLifecycleService


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def service() -> PluginLifecycleService:
    """Instance du service PluginLifecycle."""
    return PluginLifecycleService()


def _make_plugin(
    db_session: AsyncSession,
    test_organization: Organization,
    test_superuser: User,
    hooks: dict | None = None,
    config_values: dict | None = None,
    config_fields: list | None = None,
) -> Plugin:
    """Crée un plugin en base avec les hooks spécifiés dans le manifest."""
    manifest_data = {
        "name": "test-hook-plugin",
        "version": "1.0.0",
        "display_name": "Test Hook Plugin",
        "description": "A plugin for testing hooks",
        "category": "other",
        "type": "extension",
        "config": config_fields or [],
    }
    if hooks:
        manifest_data["hooks"] = hooks

    plugin = Plugin(
        name="test-hook-plugin",
        version="1.0.0",
        display_name="Test Hook Plugin",
        description="A plugin for testing hooks",
        category="other",
        type="extension",
        status=PluginStatus.INSTALLED.value,
        manifest_data=manifest_data,
        config_values=config_values or {},
        organization_id=test_organization.id,
        installed_by=test_superuser.id,
    )
    return plugin


@pytest.fixture()
async def plugin_with_hooks(
    db_session: AsyncSession,
    test_organization: Organization,
    test_superuser: User,
) -> Plugin:
    """Plugin avec tous les hooks déclarés dans le manifest."""
    plugin = _make_plugin(
        db_session,
        test_organization,
        test_superuser,
        hooks={
            "on_install": "scripts/install.sh",
            "on_configure": "scripts/configure.sh",
            "on_uninstall": "scripts/uninstall.sh",
            "on_start": "scripts/start.sh",
            "on_stop": "scripts/stop.sh",
        },
    )
    db_session.add(plugin)
    await db_session.commit()
    await db_session.refresh(plugin)
    return plugin


@pytest.fixture()
async def plugin_without_hooks(
    db_session: AsyncSession,
    test_organization: Organization,
    test_superuser: User,
) -> Plugin:
    """Plugin sans hooks déclarés dans le manifest."""
    plugin = _make_plugin(
        db_session,
        test_organization,
        test_superuser,
    )
    db_session.add(plugin)
    await db_session.commit()
    await db_session.refresh(plugin)
    return plugin


@pytest.fixture()
async def plugin_with_password_config(
    db_session: AsyncSession,
    test_organization: Organization,
    test_superuser: User,
) -> Plugin:
    """Plugin avec config de type password."""
    plugin = _make_plugin(
        db_session,
        test_organization,
        test_superuser,
        config_values={"api_key": "super-secret-key", "host": "localhost", "port": 8080},
        config_fields=[
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
            {"key": "host", "label": "Host", "type": "string", "required": True},
            {"key": "port", "label": "Port", "type": "integer", "required": False},
        ],
    )
    db_session.add(plugin)
    await db_session.commit()
    await db_session.refresh(plugin)
    return plugin


def _mock_subprocess_success(stdout: str = "OK", stderr: str = ""):
    """Crée un mock de subprocess qui réussit."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(
        return_value=(stdout.encode(), stderr.encode())
    )
    return mock_proc


def _mock_subprocess_failure(exit_code: int = 1, stdout: str = "", stderr: str = "Error occurred"):
    """Crée un mock de subprocess qui échoue."""
    mock_proc = MagicMock()
    mock_proc.returncode = exit_code
    mock_proc.communicate = AsyncMock(
        return_value=(stdout.encode(), stderr.encode())
    )
    return mock_proc


# ── Tests execute_hook — succès nominal ─────────────────────────────────────


class TestExecuteHookSuccess:
    """Tests d'exécution nominale des hooks."""

    @pytest.mark.asyncio
    async def test_execute_on_install_hook_success(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """Hook on_install s'exécute avec succès, log enregistré en BDD avec status=success."""
        with patch("app.services.plugin_lifecycle_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess_success("Installation done")

            result = await service.execute_hook(
                db_session, plugin_with_hooks, "on_install", test_superuser.id
            )

        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "Installation done"

        # Vérifier le log en BDD
        from sqlalchemy import select

        log_result = await db_session.execute(
            select(PluginHookLog).where(
                PluginHookLog.plugin_id == plugin_with_hooks.id,
                PluginHookLog.hook_name == "on_install",
            )
        )
        log = log_result.scalar_one()
        assert log.status == "success"
        assert log.exit_code == 0
        assert log.stdout == "Installation done"
        assert log.triggered_by == test_superuser.id

    @pytest.mark.asyncio
    async def test_execute_on_configure_hook_success(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """Hook on_configure s'exécute avec succès."""
        with patch("app.services.plugin_lifecycle_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess_success("Configured")

            result = await service.execute_hook(
                db_session, plugin_with_hooks, "on_configure", test_superuser.id
            )

        assert result.success is True
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_execute_on_uninstall_hook_success(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """Hook on_uninstall s'exécute avant suppression."""
        with patch("app.services.plugin_lifecycle_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess_success("Uninstalled")

            result = await service.execute_hook(
                db_session, plugin_with_hooks, "on_uninstall", test_superuser.id
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_on_start_hook_success(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """Hook on_start s'exécute avec succès (méthode exposée, non câblée)."""
        with patch("app.services.plugin_lifecycle_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess_success("Started")

            result = await service.execute_hook(
                db_session, plugin_with_hooks, "on_start", test_superuser.id
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_on_stop_hook_success(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """Hook on_stop s'exécute avec succès (méthode exposée, non câblée)."""
        with patch("app.services.plugin_lifecycle_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess_success("Stopped")

            result = await service.execute_hook(
                db_session, plugin_with_hooks, "on_stop", test_superuser.id
            )

        assert result.success is True


# ── Tests execute_hook — erreurs ────────────────────────────────────────────


class TestExecuteHookFailure:
    """Tests d'exécution de hooks en échec."""

    @pytest.mark.asyncio
    async def test_execute_hook_failure_sets_plugin_error(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """Hook en échec → plugin status ERROR, log avec exit_code et stderr."""
        with patch("app.services.plugin_lifecycle_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess_failure(
                exit_code=1, stderr="Something went wrong"
            )

            with pytest.raises(WindFlowException) as exc_info:
                await service.execute_lifecycle_transition(
                    db_session, plugin_with_hooks, "install", test_superuser.id
                )

        assert "hook_failed" in str(exc_info.value.details.get("error_type"))
        assert plugin_with_hooks.status == PluginStatus.ERROR.value

        # Vérifier le log en BDD
        from sqlalchemy import select

        log_result = await db_session.execute(
            select(PluginHookLog).where(
                PluginHookLog.plugin_id == plugin_with_hooks.id,
            )
        )
        log = log_result.scalar_one()
        assert log.status == "failed"
        assert log.exit_code == 1
        assert "Something went wrong" in log.stderr

    @pytest.mark.asyncio
    async def test_execute_hook_timeout(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """Hook qui dépasse le timeout (30s) → échec avec message approprié."""
        with patch("app.services.plugin_lifecycle_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = MagicMock()
            mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_proc.kill = MagicMock()
            mock_exec.return_value = mock_proc

            with pytest.raises(WindFlowException):
                await service.execute_lifecycle_transition(
                    db_session, plugin_with_hooks, "install", test_superuser.id
                )

        assert plugin_with_hooks.status == PluginStatus.ERROR.value

        # Vérifier le log en BDD
        from sqlalchemy import select

        log_result = await db_session.execute(
            select(PluginHookLog).where(
                PluginHookLog.plugin_id == plugin_with_hooks.id,
            )
        )
        log = log_result.scalar_one()
        assert log.status == "failed"
        assert "timeout" in (log.error_message or "").lower()

    @pytest.mark.asyncio
    async def test_execute_hook_script_not_found(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """Script inexistant → hook en échec avec exit_code et stderr capturés."""
        with patch("app.services.plugin_lifecycle_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = FileNotFoundError("No such file")

            with pytest.raises(WindFlowException):
                await service.execute_lifecycle_transition(
                    db_session, plugin_with_hooks, "install", test_superuser.id
                )

        assert plugin_with_hooks.status == PluginStatus.ERROR.value

        # Vérifier le log en BDD
        from sqlalchemy import select

        log_result = await db_session.execute(
            select(PluginHookLog).where(
                PluginHookLog.plugin_id == plugin_with_hooks.id,
            )
        )
        log = log_result.scalar_one()
        assert log.status == "failed"
        assert log.exit_code == 127
        assert "not found" in log.stderr.lower()


# ── Tests no-op (hook non déclaré) ──────────────────────────────────────────


class TestExecuteHookNoOp:
    """Tests quand aucun hook n'est déclaré dans le manifest."""

    @pytest.mark.asyncio
    async def test_execute_hook_not_declared_is_noop(
        self,
        db_session: AsyncSession,
        plugin_without_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """Pas de hook déclaré dans le manifest → aucune exécution, pas de log, pas d'erreur."""
        result = await service.execute_hook(
            db_session, plugin_without_hooks, "on_install", test_superuser.id
        )

        assert result.success is True
        assert result.exit_code is None
        assert result.stdout == ""

        # Vérifier qu'aucun log n'a été créé
        from sqlalchemy import select

        log_result = await db_session.execute(
            select(PluginHookLog).where(
                PluginHookLog.plugin_id == plugin_without_hooks.id,
            )
        )
        logs = list(log_result.scalars().all())
        assert len(logs) == 0

    @pytest.mark.asyncio
    async def test_execute_lifecycle_transition_noop(
        self,
        db_session: AsyncSession,
        plugin_without_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """Transition lifecycle sans hook → no-op, plugin retourné sans changement."""
        plugin = await service.execute_lifecycle_transition(
            db_session, plugin_without_hooks, "install", test_superuser.id
        )

        assert plugin.status == PluginStatus.INSTALLED.value


# ── Tests sécurité — path traversal ─────────────────────────────────────────


class TestPathValidation:
    """Tests de validation des chemins de scripts (anti path traversal)."""

    @pytest.mark.asyncio
    async def test_execute_hook_path_traversal_rejected(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginLifecycleService,
    ) -> None:
        """Chemin avec '..' → WindFlowException."""
        plugin = _make_plugin(
            db_session,
            test_organization,
            test_superuser,
            hooks={"on_install": "../../etc/passwd"},
        )
        db_session.add(plugin)
        await db_session.commit()
        await db_session.refresh(plugin)

        with pytest.raises(WindFlowException) as exc_info:
            await service.execute_hook(
                db_session, plugin, "on_install", test_superuser.id
            )

        assert "path_traversal" in str(exc_info.value.details.get("error_type"))

    @pytest.mark.asyncio
    async def test_execute_hook_absolute_path_rejected(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginLifecycleService,
    ) -> None:
        """Chemin absolu (/etc/passwd) → WindFlowException."""
        plugin = _make_plugin(
            db_session,
            test_organization,
            test_superuser,
            hooks={"on_install": "/etc/passwd"},
        )
        db_session.add(plugin)
        await db_session.commit()
        await db_session.refresh(plugin)

        with pytest.raises(WindFlowException) as exc_info:
            await service.execute_hook(
                db_session, plugin, "on_install", test_superuser.id
            )

        assert "invalid_script_path" in str(exc_info.value.details.get("error_type"))


# ── Tests capture stdout/stderr et durée ────────────────────────────────────


class TestOutputCapture:
    """Tests de capture des sorties et calcul de durée."""

    @pytest.mark.asyncio
    async def test_execute_hook_captures_stdout_stderr(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """Stdout et stderr capturés dans le log."""
        with patch("app.services.plugin_lifecycle_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess_success(
                stdout="Line 1\nLine 2", stderr="Warning message"
            )

            result = await service.execute_hook(
                db_session, plugin_with_hooks, "on_install", test_superuser.id
            )

        assert "Line 1" in result.stdout
        assert "Warning message" in result.stderr

        # Vérifier le log en BDD
        from sqlalchemy import select

        log_result = await db_session.execute(
            select(PluginHookLog).where(
                PluginHookLog.plugin_id == plugin_with_hooks.id,
            )
        )
        log = log_result.scalar_one()
        assert "Line 1" in log.stdout
        assert "Warning message" in log.stderr

    @pytest.mark.asyncio
    async def test_execute_hook_duration_calculated(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """duration_ms calculé correctement (started_at → completed_at)."""
        with patch("app.services.plugin_lifecycle_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess_success("OK")

            result = await service.execute_hook(
                db_session, plugin_with_hooks, "on_install", test_superuser.id
            )

        assert result.duration_ms is not None
        assert result.duration_ms >= 0

        # Vérifier le log en BDD
        from sqlalchemy import select

        log_result = await db_session.execute(
            select(PluginHookLog).where(
                PluginHookLog.plugin_id == plugin_with_hooks.id,
            )
        )
        log = log_result.scalar_one()
        assert log.duration_ms is not None
        assert log.duration_ms >= 0
        assert log.started_at is not None
        assert log.completed_at is not None
        assert log.completed_at >= log.started_at


# ── Tests env vars sécurisées ───────────────────────────────────────────────


class TestSafeEnvVars:
    """Tests de construction des variables d'environnement sécurisées."""

    def test_build_safe_env_vars_masks_passwords(
        self,
        plugin_with_password_config: Plugin,
        service: PluginLifecycleService,
    ) -> None:
        """Les config_values de type password sont masquées avec '***' dans les env vars."""
        env_vars = service._build_safe_env_vars(plugin_with_password_config)

        assert env_vars["PLUGIN_CONFIG_API_KEY"] == "***"
        assert env_vars["PLUGIN_CONFIG_HOST"] == "localhost"
        assert env_vars["PLUGIN_CONFIG_PORT"] == "8080"

    def test_build_safe_env_vars_exposes_non_secrets(
        self,
        plugin_with_password_config: Plugin,
        service: PluginLifecycleService,
    ) -> None:
        """Les config_values non-password sont exposées avec préfixe 'PLUGIN_CONFIG_'."""
        env_vars = service._build_safe_env_vars(plugin_with_password_config)

        assert env_vars["PLUGIN_NAME"] == "test-hook-plugin"
        assert env_vars["PLUGIN_VERSION"] == "1.0.0"
        assert env_vars["PLUGIN_CONFIG_HOST"] == "localhost"
        assert env_vars["PLUGIN_CONFIG_PORT"] == "8080"
        # Le password est masqué
        assert env_vars["PLUGIN_CONFIG_API_KEY"] == "***"


# ── Tests list_hook_logs et get_hook_log ────────────────────────────────────


class TestHookLogQueries:
    """Tests des requêtes de listing et détail des logs."""

    @pytest.mark.asyncio
    async def test_list_hook_logs_returns_logs(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
        service: PluginLifecycleService,
        test_superuser: User,
    ) -> None:
        """list_hook_logs retourne les logs existants."""
        # Créer un log manuellement
        log = PluginHookLog(
            plugin_id=plugin_with_hooks.id,
            hook_name="on_install",
            script_path="scripts/install.sh",
            status="success",
            exit_code=0,
            stdout="OK",
            stderr="",
            triggered_by=test_superuser.id,
        )
        db_session.add(log)
        await db_session.commit()

        logs = await PluginLifecycleService.list_hook_logs(
            db_session, plugin_with_hooks.id
        )

        assert len(logs) == 1
        assert logs[0].hook_name == "on_install"
        assert logs[0].status == "success"

    @pytest.mark.asyncio
    async def test_list_hook_logs_returns_empty(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
    ) -> None:
        """list_hook_logs retourne une liste vide si aucun log."""
        logs = await PluginLifecycleService.list_hook_logs(
            db_session, plugin_with_hooks.id
        )
        assert logs == []

    @pytest.mark.asyncio
    async def test_get_hook_log_returns_log(
        self,
        db_session: AsyncSession,
        plugin_with_hooks: Plugin,
        test_superuser: User,
    ) -> None:
        """get_hook_log retourne le log par son ID."""
        log = PluginHookLog(
            plugin_id=plugin_with_hooks.id,
            hook_name="on_install",
            script_path="scripts/install.sh",
            status="success",
            exit_code=0,
            stdout="OK",
            stderr="",
            triggered_by=test_superuser.id,
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        found = await PluginLifecycleService.get_hook_log(db_session, log.id)
        assert found is not None
        assert found.id == log.id

    @pytest.mark.asyncio
    async def test_get_hook_log_returns_none_when_not_found(
        self,
        db_session: AsyncSession,
    ) -> None:
        """get_hook_log retourne None si le log n'existe pas."""
        found = await PluginLifecycleService.get_hook_log(db_session, "nonexistent-id")
        assert found is None
