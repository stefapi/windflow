"""Tests de ComposeStackAdapter — enveloppement sans duplication (STORY-174.1, AC 1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import WindFlowException
from app.enums.workload import WorkloadFamily
from app.services.workloads import ComposeStackAdapter, get_app_adapter


def _compose_service_mock():
    svc = MagicMock()
    svc.get_compose_status = AsyncMock(
        return_value=(
            True,
            [
                {"Name": "web", "State": "running", "Image": "nginx:1.27"},
                {"Name": "db", "State": "exited", "Image": "postgres:16"},
            ],
        )
    )
    svc.stop_compose = AsyncMock(return_value=(True, "stopped"))
    svc.deploy_compose = AsyncMock(return_value=(True, "deployed"))
    svc.get_compose_logs = AsyncMock(return_value=(True, "svc logs"))
    return svc


class TestIdentity:
    def test_identity_compose(self):
        adapter = ComposeStackAdapter("myproj", compose_service=_compose_service_mock())
        assert adapter.family() is WorkloadFamily.APP
        assert adapter.profile() == "docker_compose"
        assert adapter.profile_label() == "Stack Docker Compose"


class TestContextualActions:
    def test_catalogue_compose_actions(self):
        """Catalogue exact spec 02 docker_compose (ids)."""
        adapter = ComposeStackAdapter("myproj", compose_service=_compose_service_mock())
        ids = {a.id for a in adapter.contextual_actions()}
        assert ids == {
            "recreate",
            "scale_service",
            "restart_service",
            "edit_env",
            "edit_ports",
            "edit_compose_yaml",
            "pull_images",
            "logs_per_service",
            "down_v_rmi",
        }
        danger = [a for a in adapter.contextual_actions() if a.danger]
        assert [a.id for a in danger] == ["down_v_rmi"]

    def test_child_actions_service_includes_scale(self):
        adapter = ComposeStackAdapter("myproj", compose_service=_compose_service_mock())
        ids = {a.id for a in adapter.child_actions("service", "web")}
        assert "scale_service" in ids
        other = {a.id for a in adapter.child_actions("other", "x")}
        assert "scale_service" not in other


class TestHealthAndComponents:
    async def test_health_partial(self):
        adapter = ComposeStackAdapter("myproj", compose_service=_compose_service_mock())
        health = await adapter.health()
        assert health.status == "unhealthy"
        assert "1/2" in (health.detail or "")

    async def test_health_all_running(self):
        svc = _compose_service_mock()
        svc.get_compose_status = AsyncMock(
            return_value=(True, [{"Name": "web", "State": "running"}])
        )
        adapter = ComposeStackAdapter("myproj", compose_service=svc)
        assert (await adapter.health()).status == "healthy"

    async def test_health_unknown_on_error(self):
        svc = _compose_service_mock()
        svc.get_compose_status = AsyncMock(return_value=(False, {"error": "boom"}))
        adapter = ComposeStackAdapter("myproj", compose_service=svc)
        assert (await adapter.health()).status == "unknown"

    async def test_list_services_mapping(self):
        adapter = ComposeStackAdapter("myproj", compose_service=_compose_service_mock())
        apps = await adapter.list_services_or_pods()
        assert [a.name for a in apps] == ["web", "db"]
        assert apps[0].status == "running"
        assert apps[1].image == "postgres:16"

    async def test_technical_components(self):
        adapter = ComposeStackAdapter("myproj", compose_service=_compose_service_mock())
        comps = await adapter.get_technical_components()
        assert comps[0].kind == "service"
        assert comps[1].status == "exited"

    async def test_get_open_url_none(self):
        adapter = ComposeStackAdapter("myproj", compose_service=_compose_service_mock())
        assert await adapter.get_open_url() is None


class TestVerbs:
    async def test_stop_deploy_delegate(self):
        svc = _compose_service_mock()
        adapter = ComposeStackAdapter("myproj", compose_service=svc)
        await adapter.stop()
        svc.stop_compose.assert_awaited_once_with("myproj")

    async def test_deploy_with_explicit_file(self, tmp_path):
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}\n")
        svc = _compose_service_mock()
        adapter = ComposeStackAdapter(
            "myproj", compose_service=svc, compose_file=compose
        )
        ok, msg = await adapter.deploy(compose, "myproj")
        assert ok
        svc.deploy_compose.assert_awaited_once_with(compose, "myproj", None)

    async def test_deploy_without_file_fails_explicitly(self):
        adapter = ComposeStackAdapter("myproj", compose_service=_compose_service_mock())
        ok, msg = await adapter.deploy()
        assert ok is False
        assert "inconnu" in msg

    async def test_update_deploys(self, tmp_path):
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}\n")
        svc = _compose_service_mock()
        adapter = ComposeStackAdapter(
            "myproj", compose_service=svc, compose_file=compose
        )
        result = await adapter.update({})
        assert result == "deployed"
        svc.deploy_compose.assert_awaited_once()

    async def test_stop_failure_raises(self):
        svc = _compose_service_mock()
        svc.stop_compose = AsyncMock(return_value=(False, "err"))
        adapter = ComposeStackAdapter("myproj", compose_service=svc)
        with pytest.raises(WindFlowException):
            await adapter.stop()

    async def test_stream_logs_delegates(self):
        svc = _compose_service_mock()
        adapter = ComposeStackAdapter("myproj", compose_service=svc)
        assert await adapter.stream_logs(7) == "svc logs"
        svc.get_compose_logs.assert_awaited_once()


class TestStubs:
    async def test_stubs_raise(self):
        from app.services.workloads.base import ActionNotImplementedError

        adapter = ComposeStackAdapter("myproj", compose_service=_compose_service_mock())
        with pytest.raises(ActionNotImplementedError):
            await adapter.backup()
        with pytest.raises(ActionNotImplementedError):
            await adapter.configure({})
        with pytest.raises(ActionNotImplementedError):
            await adapter.open_console()


class TestFactory:
    def test_factory_resolves_compose(self):
        adapter = get_app_adapter("docker_compose", project_name="p")
        assert isinstance(adapter, ComposeStackAdapter)
