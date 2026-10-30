"""
Tests unitaires pour adoption_service.py.

Teste les helpers pures (pas de mock async) et les fonctions principales
avec mocks de DockerClientService et de la DB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.adoption import (
    AdoptionEnvVar,
    AdoptionPortMapping,
    AdoptionRequest,
    AdoptionServiceData,
    AdoptionVolume,
)
from app.services.adoption_service import (
    _generate_compose_preview,
    _is_secret_env,
    _parse_env_from_inspect,
    _parse_networks_from_inspect,
    _parse_ports_from_inspect,
    _parse_volumes_from_inspect,
)

# =============================================================================
# Helpers purs — _is_secret_env
# =============================================================================


class TestIsSecretEnv:
    @pytest.mark.parametrize(
        "key",
        [
            "PASSWORD",
            "DB_PASSWORD",
            "SECRET_KEY",
            "API_TOKEN",
            "PRIVATE_KEY",
            "ACCESS_KEY",
        ],
    )
    def test_detects_secrets(self, key: str) -> None:
        assert _is_secret_env(key) is True

    @pytest.mark.parametrize(
        "key",
        ["PORT", "HOST", "DEBUG", "NODE_ENV", "APP_NAME", "LOG_LEVEL"],
    )
    def test_non_secrets(self, key: str) -> None:
        assert _is_secret_env(key) is False

    def test_case_insensitive(self) -> None:
        assert _is_secret_env("password") is True
        assert _is_secret_env("MySecret") is True


# =============================================================================
# Helpers purs — _parse_env_from_inspect
# =============================================================================


class TestParseEnvFromInspect:
    def test_empty_list(self) -> None:
        assert _parse_env_from_inspect([]) == []

    def test_single_entry(self) -> None:
        result = _parse_env_from_inspect(["APP_NAME=myapp"])
        assert len(result) == 1
        assert result[0].key == "APP_NAME"
        assert result[0].value == "myapp"
        assert result[0].is_secret is False

    def test_secret_detection(self) -> None:
        result = _parse_env_from_inspect(["DB_PASSWORD=supersecret"])
        assert result[0].is_secret is True

    def test_entry_without_equals(self) -> None:
        """Les entrées sans '=' sont ignorées."""
        assert _parse_env_from_inspect(["NOEQUALS"]) == []

    def test_value_with_equals(self) -> None:
        """La valeur peut contenir des '='."""
        result = _parse_env_from_inspect(["CONN_STRING=host=db port=5432"])
        assert result[0].key == "CONN_STRING"
        assert result[0].value == "host=db port=5432"


# =============================================================================
# Helpers purs — _parse_volumes_from_inspect
# =============================================================================


class TestParseVolumesFromInspect:
    def test_empty(self) -> None:
        assert _parse_volumes_from_inspect([]) == []

    def test_bind_mount(self) -> None:
        mounts = [
            {
                "Type": "bind",
                "Source": "/host/path",
                "Destination": "/container/path",
                "RW": True,
            }
        ]
        result = _parse_volumes_from_inspect(mounts)
        assert len(result) == 1
        assert result[0].type == "bind"
        assert result[0].source == "/host/path"
        assert result[0].destination == "/container/path"
        assert result[0].mode == "rw"

    def test_readonly(self) -> None:
        mounts = [
            {"Type": "bind", "Source": "/host", "Destination": "/data", "RW": False}
        ]
        result = _parse_volumes_from_inspect(mounts)
        assert result[0].mode == "ro"

    def test_named_volume(self) -> None:
        mounts = [
            {"Type": "volume", "Name": "mydata", "Destination": "/data", "RW": True}
        ]
        result = _parse_volumes_from_inspect(mounts)
        assert result[0].type == "volume"
        assert result[0].source == "mydata"


# =============================================================================
# Helpers purs — _parse_networks_from_inspect
# =============================================================================


class TestParseNetworksFromInspect:
    def test_empty(self) -> None:
        assert _parse_networks_from_inspect({}) == []

    def test_bridge_is_default(self) -> None:
        ns = {"Networks": {"bridge": {}}}
        result = _parse_networks_from_inspect(ns)
        assert len(result) == 1
        assert result[0].is_default is True
        assert result[0].name == "bridge"

    def test_custom_network(self) -> None:
        ns = {"Networks": {"my-network": {"Driver": "bridge"}}}
        result = _parse_networks_from_inspect(ns)
        assert result[0].is_default is False
        assert result[0].name == "my-network"

    def test_default_in_name(self) -> None:
        ns = {"Networks": {"myproject_default": {}}}
        result = _parse_networks_from_inspect(ns)
        assert result[0].is_default is True


# =============================================================================
# Helpers purs — _parse_ports_from_inspect
# =============================================================================


class TestParsePortsFromInspect:
    def test_empty(self) -> None:
        assert _parse_ports_from_inspect({}) == []

    def test_no_bindings(self) -> None:
        ns = {"Ports": {"80/tcp": None}}
        assert _parse_ports_from_inspect(ns) == []

    def test_single_port(self) -> None:
        ns = {"Ports": {"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]}}
        result = _parse_ports_from_inspect(ns)
        assert len(result) == 1
        assert result[0].container_port == 80
        assert result[0].host_port == 8080
        assert result[0].protocol == "tcp"

    def test_multiple_bindings(self) -> None:
        ns = {
            "Ports": {
                "443/tcp": [
                    {"HostIp": "0.0.0.0", "HostPort": "8443"},
                    {"HostIp": "127.0.0.1", "HostPort": "9443"},
                ]
            }
        }
        result = _parse_ports_from_inspect(ns)
        assert len(result) == 2


# =============================================================================
# Helpers purs — _generate_compose_preview
# =============================================================================


class TestGenerateComposePreview:
    def test_empty_services(self) -> None:
        result = _generate_compose_preview([])
        assert "services: {}" in result or "services:\n" in result

    def test_single_service(self) -> None:
        services = [
            AdoptionServiceData(
                name="web",
                image="nginx:latest",
                status="running",
                ports=[
                    AdoptionPortMapping(
                        host_ip="0.0.0.0",
                        host_port=8080,
                        container_port=80,
                        protocol="tcp",
                    )
                ],
            )
        ]
        result = _generate_compose_preview(services)
        assert "nginx:latest" in result
        assert "web:" in result
        assert "8080:80" in result

    def test_service_with_env(self) -> None:
        services = [
            AdoptionServiceData(
                name="app",
                image="myapp:latest",
                status="running",
                env_vars=[
                    AdoptionEnvVar(key="NODE_ENV", value="production", is_secret=False)
                ],
            )
        ]
        result = _generate_compose_preview(services)
        assert "NODE_ENV" in result
        assert "production" in result

    def test_service_with_volumes(self) -> None:
        services = [
            AdoptionServiceData(
                name="db",
                image="postgres:15",
                status="running",
                volumes=[
                    AdoptionVolume(
                        source="pgdata",
                        destination="/var/lib/postgresql/data",
                        mode="rw",
                        type="volume",
                    )
                ],
            )
        ]
        result = _generate_compose_preview(services)
        assert "pgdata" in result
        assert "/var/lib/postgresql/data" in result


# =============================================================================
# Tests async — get_adoption_data
# =============================================================================


class TestGetAdoptionData:
    @pytest.mark.asyncio
    async def test_docker_unavailable(self) -> None:
        """Retourne 503 si Docker n'est pas accessible."""
        from app.core.exceptions import ServiceUnavailableError
        from app.services.adoption_service import get_adoption_data

        mock_db = MagicMock()

        with patch("app.services.adoption_service.DockerClientService") as MockDocker:
            mock_docker = AsyncMock()
            mock_docker.ping.return_value = False
            mock_docker.close = AsyncMock()
            MockDocker.return_value = mock_docker

            with pytest.raises(ServiceUnavailableError) as exc_info:
                await get_adoption_data(
                    mock_db, "org1", "composition", "compose:myproject@local"
                )
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_composition_not_found(self) -> None:
        """Retourne 404 si le projet compose n'existe pas."""
        from app.core.exceptions import NotFoundError
        from app.services.adoption_service import get_adoption_data

        mock_db = MagicMock()

        with patch("app.services.adoption_service.DockerClientService") as MockDocker:
            mock_docker = AsyncMock()
            mock_docker.ping.return_value = True
            mock_docker.list_containers.return_value = []  # Aucun container
            mock_docker.close = AsyncMock()
            MockDocker.return_value = mock_docker

            with pytest.raises(NotFoundError) as exc_info:
                await get_adoption_data(
                    mock_db, "org1", "composition", "compose:nonexistent@local"
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_composition_found(self) -> None:
        """Retourne les données d'adoption pour un projet compose."""
        from app.services.adoption_service import get_adoption_data
        from app.services.container_classifier import LABEL_COMPOSE_PROJECT

        mock_db = MagicMock()
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.name = "myapp-web"
        mock_container.image = "nginx:latest"
        mock_container.state = "running"
        mock_container.labels = {LABEL_COMPOSE_PROJECT: "myproject"}

        with patch("app.services.adoption_service.DockerClientService") as MockDocker:
            mock_docker = AsyncMock()
            mock_docker.ping.return_value = True
            mock_docker.list_containers.return_value = [mock_container]
            mock_docker.inspect_container.return_value = {
                "Config": {"Env": ["NODE_ENV=production"]},
                "Mounts": [],
                "NetworkSettings": {"Networks": {}, "Ports": {}},
            }
            mock_docker.close = AsyncMock()
            MockDocker.return_value = mock_docker

            result = await get_adoption_data(
                mock_db, "org1", "composition", "compose:myproject@local"
            )
            assert result.name == "myproject"
            assert result.type == "composition"
            assert len(result.services) == 1
            assert result.services[0].name == "myapp-web"
            assert result.generated_compose is not None


# =============================================================================
# Tests async — adopt_discovered_item
# =============================================================================


class TestAdoptDiscoveredItem:
    @pytest.mark.asyncio
    async def test_duplicate_name(self) -> None:
        """Retourne 409 si le nom de stack existe déjà."""
        from app.core.exceptions import ConflictError
        from app.services.adoption_service import adopt_discovered_item

        mock_db = AsyncMock()
        # Simuler une stack existante
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()  # Stack existante
        mock_db.execute.return_value = mock_result

        request = AdoptionRequest(
            discovered_id="compose:myproject@local",
            type="composition",
            stack_name="existing-stack",
        )

        with pytest.raises(ConflictError) as exc_info:
            await adopt_discovered_item(mock_db, "org1", request)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_successful_adoption(self) -> None:
        """Adoption réussie crée Stack + Deployment."""
        from app.services.adoption_service import adopt_discovered_item
        from app.services.container_classifier import LABEL_COMPOSE_PROJECT

        mock_db = AsyncMock()
        # Pas de stack existante
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.name = "myapp-web"
        mock_container.image = "nginx:latest"
        mock_container.state = "running"
        mock_container.labels = {LABEL_COMPOSE_PROJECT: "myproject"}

        request = AdoptionRequest(
            discovered_id="compose:myproject@local",
            type="composition",
            stack_name="my-new-stack",
        )

        with patch("app.services.adoption_service.DockerClientService") as MockDocker:
            mock_docker = AsyncMock()
            mock_docker.ping.return_value = True
            mock_docker.list_containers.return_value = [mock_container]
            mock_docker.close = AsyncMock()
            MockDocker.return_value = mock_docker

            result = await adopt_discovered_item(mock_db, "org1", request)
            assert result.success is True
            assert result.stack_name == "my-new-stack"
            assert result.stack_id is not None
            assert result.deployment_id is not None
            assert "1 container" in result.message

            # Vérifier que les objets DB ont été ajoutés
            assert mock_db.add.call_count == 2  # Stack + Deployment
            mock_db.commit.assert_called_once()


# =============================================================================
# STORY-166.4 — axe origin : l'adoption marque origin=adopted (stack
# uniquement — hosts.origin NON modifié, arbitrage d'analyse).
# =============================================================================


class TestAdoptionOrigin:
    """AC 1 — adoption d'un conteneur découvert → Stack.origin == 'adopted'."""

    @staticmethod
    def _make_db() -> AsyncMock:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        return mock_db

    @staticmethod
    def _make_container(labels: dict | None = None) -> MagicMock:
        from app.services.container_classifier import LABEL_COMPOSE_PROJECT

        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.name = "myapp-web"
        mock_container.image = "nginx:latest"
        mock_container.state = "running"
        mock_container.labels = labels or {LABEL_COMPOSE_PROJECT: "myproject"}
        return mock_container

    def _captured_stack(self, mock_db) -> object:
        """Retourne le Stack passé à db.add (1er appel)."""
        added = [call.args[0] for call in mock_db.add.call_args_list]
        stacks = [obj for obj in added if type(obj).__name__ == "Stack"]
        assert stacks, "Aucun Stack ajouté à la session"
        return stacks[0]

    @pytest.mark.asyncio
    async def test_adoption_marks_stack_origin_adopted(self) -> None:
        """AC 1 — la stack résultante porte origin='adopted'."""
        from app.services.adoption_service import adopt_discovered_item

        mock_db = self._make_db()
        request = AdoptionRequest(
            discovered_id="compose:myproject@local",
            type="composition",
            stack_name="adopted-stack",
        )

        with patch("app.services.adoption_service.DockerClientService") as MockDocker:
            mock_docker = AsyncMock()
            mock_docker.ping.return_value = True
            mock_docker.list_containers.return_value = [self._make_container()]
            mock_docker.close = AsyncMock()
            MockDocker.return_value = mock_docker

            result = await adopt_discovered_item(mock_db, "org1", request)
            assert result.success is True

            stack = self._captured_stack(mock_db)
            assert stack.origin == "adopted"
            # Non-régression (AC 3) : tags + category conservés
            assert stack.category == "adopted"
            assert "adopted" in stack.tags

    @pytest.mark.asyncio
    async def test_adoption_does_not_touch_host_origin(self) -> None:
        """Arbitrage T5 — hosts.origin NON modifié : aucun Host ajouté ni
        updaté à l'adoption (le host local reste managed)."""
        from app.services.adoption_service import adopt_discovered_item

        mock_db = self._make_db()
        request = AdoptionRequest(
            discovered_id="compose:myproject@local",
            type="composition",
            stack_name="adopted-stack-2",
        )

        with patch("app.services.adoption_service.DockerClientService") as MockDocker:
            mock_docker = AsyncMock()
            mock_docker.ping.return_value = True
            mock_docker.list_containers.return_value = [self._make_container()]
            mock_docker.close = AsyncMock()
            MockDocker.return_value = mock_docker

            await adopt_discovered_item(mock_db, "org1", request)

            added = [call.args[0] for call in mock_db.add.call_args_list]
            hosts = [obj for obj in added if type(obj).__name__ == "Host"]
            assert hosts == []

    @pytest.mark.asyncio
    async def test_windflow_labeled_container_adoption_refused(self) -> None:
        """T6 — garde-fou : container portant ``windflow.stack_id`` → 409
        (déjà piloté, pas « découvert »)."""
        from app.core.exceptions import ConflictError
        from app.services.adoption_service import adopt_discovered_item
        from app.services.container_classifier import (
            LABEL_COMPOSE_PROJECT,
            LABEL_WINDFLOW_STACK_ID,
        )

        mock_db = self._make_db()
        request = AdoptionRequest(
            discovered_id="compose:myproject@local",
            type="composition",
            stack_name="should-not-be-created",
        )

        labeled = self._make_container(
            {
                LABEL_COMPOSE_PROJECT: "myproject",
                LABEL_WINDFLOW_STACK_ID: "stk-existing",
            }
        )

        with patch("app.services.adoption_service.DockerClientService") as MockDocker:
            mock_docker = AsyncMock()
            mock_docker.ping.return_value = True
            mock_docker.list_containers.return_value = [labeled]
            mock_docker.close = AsyncMock()
            MockDocker.return_value = mock_docker

            with pytest.raises(ConflictError) as exc_info:
                await adopt_discovered_item(mock_db, "org1", request)
            assert exc_info.value.status_code == 409

            # Aucune écriture
            mock_db.add.assert_not_called()
            mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_deployment_created_on_adoption(self) -> None:
        """AC 3 — non-régression : le deployment est bien créé."""
        from app.services.adoption_service import adopt_discovered_item

        mock_db = self._make_db()
        request = AdoptionRequest(
            discovered_id="compose:myproject@local",
            type="composition",
            stack_name="adopted-stack-3",
        )

        with patch("app.services.adoption_service.DockerClientService") as MockDocker:
            mock_docker = AsyncMock()
            mock_docker.ping.return_value = True
            mock_docker.list_containers.return_value = [self._make_container()]
            mock_docker.close = AsyncMock()
            MockDocker.return_value = mock_docker

            await adopt_discovered_item(mock_db, "org1", request)

            added = [call.args[0] for call in mock_db.add.call_args_list]
            deployments = [obj for obj in added if type(obj).__name__ == "Deployment"]
            assert len(deployments) == 1
            assert deployments[0].status.value == "running"
