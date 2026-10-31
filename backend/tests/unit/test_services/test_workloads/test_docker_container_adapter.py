"""Tests de DockerContainerAdapter — enveloppement sans duplication (STORY-174.1, AC 1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import WindFlowException
from app.enums.workload import WorkloadFamily
from app.services.workloads import DockerContainerAdapter, get_app_adapter
from app.services.workloads.docker_container import _DOCKER_CONTAINER_ACTIONS


@pytest.fixture(autouse=True)
def _reset_circuit_registry():
    """STORY-251 : isolation globale — le registre des circuits est vidé
    avant chaque test du fichier (les tests existants 174.1 exécutent de
    vrais verbes via le circuit docker_engine)."""
    from app.core.resilience import get_circuit_breaker_registry

    get_circuit_breaker_registry().reset_all()
    yield
    get_circuit_breaker_registry().reset_all()


def _service_mock():
    svc = MagicMock()
    svc.start_container = AsyncMock(return_value=(True, "ok"))
    svc.stop_container = AsyncMock(return_value=(True, "ok"))
    svc.restart_container = AsyncMock(return_value=(True, "ok"))
    svc.get_container_logs = AsyncMock(return_value=(True, "log line"))
    svc.deploy_container = AsyncMock(return_value=(True, "cid123"))
    return svc


def _client_mock():
    client = AsyncMock()
    client.close = AsyncMock()
    client.inspect_container = AsyncMock(
        return_value={
            "Name": "/app-web",
            "State": {
                "Running": True,
                "Status": "running",
                "Health": {"Status": "healthy"},
            },
            "Config": {"Image": "nginx:1.27", "Env": ["A=1"]},
            "HostConfig": {"PortBindings": {"80/tcp": [{"HostPort": "8080"}]}},
        }
    )
    client.recreate_container_secure = AsyncMock(return_value=("new-id", MagicMock()))
    return client


class TestIdentity:
    def test_identity_family_profile(self):
        adapter = DockerContainerAdapter(
            "cid", service=_service_mock(), client=_client_mock()
        )
        assert adapter.family() is WorkloadFamily.APP
        assert adapter.profile() == "docker_container"
        assert adapter.profile_label() == "Container Docker"


class TestContextualActions:
    def test_contextual_actions_match_spec02_catalog(self):
        """Catalogue exact spec 02 docker_container (ids)."""
        adapter = DockerContainerAdapter(
            "cid", service=_service_mock(), client=_client_mock()
        )
        ids = {a.id for a in adapter.contextual_actions()}
        assert ids == {
            "force_restart",
            "pause",
            "edit_env",
            "edit_limits",
            "volume_snapshot",
            "commit_image",
            "export",
            "inspect",
            "force_remove",
        }
        danger = [a for a in _DOCKER_CONTAINER_ACTIONS if a.danger]
        assert [a.id for a in danger] == ["force_remove"]

    def test_child_actions_empty(self):
        adapter = DockerContainerAdapter(
            "cid", service=_service_mock(), client=_client_mock()
        )
        assert adapter.child_actions("service", "web") == []


class TestDelegation:
    async def test_start_stop_restart_delegate_to_executor_service(self):
        """Les verbes délèguent au DockerService (couche d'exécution intacte)."""
        svc = _service_mock()
        adapter = DockerContainerAdapter("cid", service=svc, client=_client_mock())
        await adapter.start()
        await adapter.stop()
        await adapter.restart()
        svc.start_container.assert_awaited_once_with("cid")
        svc.stop_container.assert_awaited_once_with("cid")
        svc.restart_container.assert_awaited_once_with("cid")

    async def test_start_failure_raises_windflow_exception(self):
        svc = _service_mock()
        svc.start_container = AsyncMock(return_value=(False, "nope"))
        adapter = DockerContainerAdapter("cid", service=svc, client=_client_mock())
        with pytest.raises(WindFlowException):
            await adapter.start()

    async def test_update_delegates_to_recreate(self):
        """update() → recreate_container du client (point 174.2)."""
        client = _client_mock()
        adapter = DockerContainerAdapter("cid", service=_service_mock(), client=client)
        new_id = await adapter.update({"image": "nginx:2", "pull_image": True})
        assert new_id == "new-id"
        client.recreate_container_secure.assert_awaited_once()
        kwargs = client.recreate_container_secure.await_args.kwargs
        assert kwargs["image"] == "nginx:2"

    async def test_stream_logs_delegates(self):
        svc = _service_mock()
        adapter = DockerContainerAdapter("cid", service=svc, client=_client_mock())
        logs = await adapter.stream_logs(tail=42)
        assert logs == "log line"
        svc.get_container_logs.assert_awaited_once_with("cid", 42)


class TestCircuitBreakerWiring:
    """STORY-251 : le circuit ``docker_engine`` protège les verbes réseau.

    Sémantique d'échec : tuple ``(False, msg)`` ou exception transport.
    Seuils des settings (défaut 5) ramenés à 2 pour les tests via
    monkeypatch ; registre réinitialisé avant chaque test (R2).
    """

    @pytest.fixture(autouse=True)
    def _isolate_circuit(self, monkeypatch):
        from app.config import settings as app_settings
        from app.core.resilience import get_circuit_breaker_registry

        get_circuit_breaker_registry().reset_all()
        monkeypatch.setattr(app_settings, "circuit_breaker_enabled", True)
        monkeypatch.setattr(app_settings, "circuit_breaker_failure_threshold", 2)
        yield
        get_circuit_breaker_registry().reset_all()

    def _circuit(self):
        from app.core.resilience import get_circuit_breaker_registry

        return get_circuit_breaker_registry().get_or_create("docker_engine")

    async def test_docker_failures_open_circuit_after_threshold(self):
        """AC 1 : (False, msg) × failure_threshold → circuit OPEN → rejet."""
        from app.core.exceptions import CircuitBreakerOpenError

        svc = _service_mock()
        svc.stop_container = AsyncMock(return_value=(False, "docker down"))
        adapter = DockerContainerAdapter("cid", service=svc, client=_client_mock())

        # 2 échecs (threshold=2) : WindFlowException levée par l'adapter,
        # chaque tuple (False, msg) compte un échec côté circuit.
        for _ in range(2):
            with pytest.raises(WindFlowException):
                await adapter.stop()
        assert self._circuit().state.value == "open"

        # 3e appel : circuit ouvert → rejet typé, sans appel au service
        with pytest.raises(CircuitBreakerOpenError):
            await adapter.stop()

    async def test_open_circuit_skips_service_call(self):
        """AC 1 : circuit ouvert → lève sans nouvel appel au mock."""
        from app.core.exceptions import CircuitBreakerOpenError

        svc = _service_mock()
        svc.stop_container = AsyncMock(return_value=(False, "down"))
        adapter = DockerContainerAdapter("cid", service=svc, client=_client_mock())

        with pytest.raises(WindFlowException):
            await adapter.stop()
        with pytest.raises(WindFlowException):
            await adapter.stop()  # threshold=2 atteint → OPEN
        assert svc.stop_container.await_count == 2

        with pytest.raises(CircuitBreakerOpenError):
            await adapter.stop()
        assert svc.stop_container.await_count == 2  # aucun nouvel appel réseau

    async def test_docker_success_keeps_circuit_closed(self):
        """Verbe réussi → circuit CLOSED, compteur d'échecs à 0."""
        svc = _service_mock()
        adapter = DockerContainerAdapter("cid", service=svc, client=_client_mock())
        await adapter.start()
        circuit = self._circuit()
        assert circuit.state.value == "closed"
        assert circuit.failure_count == 0

    async def test_circuit_breaker_disabled_pass_through(self, monkeypatch):
        """Settings off → pass-through : N échecs n'ouvrent jamais le circuit."""
        from app.config import settings as app_settings

        monkeypatch.setattr(app_settings, "circuit_breaker_enabled", False)
        svc = _service_mock()
        svc.stop_container = AsyncMock(return_value=(False, "down"))
        adapter = DockerContainerAdapter("cid", service=svc, client=_client_mock())

        for _ in range(7):  # bien au-delà du threshold
            with pytest.raises(WindFlowException):
                await adapter.stop()
        # Comportement 174.1 inchangé : le service est bien appelé chaque fois
        assert svc.stop_container.await_count == 7
        from app.core.resilience import get_circuit_breaker_registry

        assert "docker_engine" not in get_circuit_breaker_registry().get_all_states()

    async def test_existing_delegation_tests_still_pass(self):
        """Non-régression : l'enveloppement ne change pas la délégation."""
        svc = _service_mock()
        adapter = DockerContainerAdapter("cid", service=svc, client=_client_mock())
        await adapter.start()
        await adapter.stop()
        await adapter.restart()
        svc.start_container.assert_awaited_once_with("cid")
        svc.stop_container.assert_awaited_once_with("cid")
        svc.restart_container.assert_awaited_once_with("cid")
        assert self._circuit().state.value == "closed"


class TestInspection:
    async def test_health_running_with_healthcheck(self):
        adapter = DockerContainerAdapter(
            "cid", service=_service_mock(), client=_client_mock()
        )
        health = await adapter.health()
        assert health.status == "healthy"

    async def test_health_unknown_when_inspect_fails(self):
        client = _client_mock()
        client.inspect_container = AsyncMock(side_effect=RuntimeError("gone"))
        adapter = DockerContainerAdapter("cid", service=_service_mock(), client=client)
        assert (await adapter.health()).status == "unknown"

    async def test_get_native_config_uses_inspect(self):
        adapter = DockerContainerAdapter(
            "cid", service=_service_mock(), client=_client_mock()
        )
        cfg = await adapter.get_native_config()
        assert cfg.format == "json"
        assert "app-web" in cfg.content  # Name "/app-web" (JSON brut)
        assert "running" in cfg.content

    async def test_get_technical_components(self):
        adapter = DockerContainerAdapter(
            "cid", service=_service_mock(), client=_client_mock()
        )
        comps = await adapter.get_technical_components()
        assert comps[0].kind == "container"
        assert comps[0].status == "running"

    async def test_get_open_url_first_published_port(self):
        adapter = DockerContainerAdapter(
            "cid", service=_service_mock(), client=_client_mock()
        )
        assert await adapter.get_open_url() == "http://localhost:8080"

    async def test_list_services_single_component(self):
        adapter = DockerContainerAdapter(
            "cid", service=_service_mock(), client=_client_mock()
        )
        apps = await adapter.list_services_or_pods()
        assert len(apps) == 1
        assert apps[0].name == "app-web"

    async def test_deploy_delegates_to_service(self):
        """Chemin background_tasks : deploy() → DockerService.deploy_container."""
        svc = _service_mock()
        adapter = DockerContainerAdapter("cid", service=svc, client=_client_mock())
        ok, out = await adapter.deploy({"image": "nginx"}, "app-web")
        assert ok and out == "cid123"
        svc.deploy_container.assert_awaited_once_with({"image": "nginx"}, "app-web")


class TestStubs:
    async def test_configure_backup_stubs_raise(self):
        from app.services.workloads.base import ActionNotImplementedError

        adapter = DockerContainerAdapter(
            "cid", service=_service_mock(), client=_client_mock()
        )
        with pytest.raises(ActionNotImplementedError):
            await adapter.backup()
        with pytest.raises(ActionNotImplementedError):
            await adapter.configure({})
        with pytest.raises(ActionNotImplementedError):
            await adapter.open_console()


class TestFactory:
    def test_factory_resolves_docker_container(self):
        adapter = get_app_adapter("docker_container", container_id="x")
        assert isinstance(adapter, DockerContainerAdapter)

    def test_factory_unknown_profile_raises(self):
        with pytest.raises(ValueError, match="non supporté"):
            get_app_adapter("vm_kvm")
