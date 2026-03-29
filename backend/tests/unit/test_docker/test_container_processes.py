"""
Tests unitaires pour l'endpoint des processus de container.

Teste l'endpoint GET /api/v1/docker/containers/{container_id}/top.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.docker import router
from app.schemas.docker import ContainerProcess, ContainerProcessListResponse


class TestContainerProcessesEndpoint:
    """Tests pour l'endpoint get_container_processes."""

    @pytest.fixture
    def app(self):
        """Crée une application FastAPI de test."""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/docker")
        return app

    @pytest.fixture
    def mock_docker_client(self):
        """Mock du client Docker."""
        client = AsyncMock()
        client.list_processes = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_container_processes_success(self, app, mock_docker_client):
        """Test réussi de récupération des processus."""
        mock_docker_client.list_processes.return_value = {
            "Titles": ["PID", "USER", "%CPU", "%MEM", "TIME", "COMMAND"],
            "Processes": [
                ["1", "root", "0.0", "0.1", "00:00:01", "/bin/bash"],
                ["42", "app", "1.5", "2.3", "00:00:05", "python app.py"],
            ],
        }

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_docker_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/docker/containers/abc123/top")

        assert response.status_code == 200
        data = response.json()
        assert data["container_id"] == "abc123"
        assert data["titles"] == ["PID", "USER", "%CPU", "%MEM", "TIME", "COMMAND"]
        assert len(data["processes"]) == 2
        assert data["processes"][0]["pid"] == 1
        assert data["processes"][0]["user"] == "root"
        assert data["processes"][0]["cpu"] == 0.0
        assert data["processes"][0]["mem"] == 0.1
        assert data["processes"][0]["time"] == "00:00:01"
        assert data["processes"][0]["command"] == "/bin/bash"

    @pytest.mark.asyncio
    async def test_get_container_processes_empty(self, app, mock_docker_client):
        """Test avec aucun processus."""
        mock_docker_client.list_processes.return_value = {
            "Titles": ["PID", "USER", "%CPU", "%MEM", "TIME", "COMMAND"],
            "Processes": [],
        }

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_docker_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/docker/containers/abc123/top")

        assert response.status_code == 200
        data = response.json()
        assert len(data["processes"]) == 0

    @pytest.mark.asyncio
    async def test_get_container_processes_container_not_found(
        self, app, mock_docker_client
    ):
        """Test avec container non trouvé."""
        import aiohttp

        mock_docker_client.list_processes.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=404
        )

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_docker_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/docker/containers/notfound/top")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_container_processes_with_ps_args(self, app, mock_docker_client):
        """Test avec argument ps_args personnalisé."""
        mock_docker_client.list_processes.return_value = {
            "Titles": ["PID", "USER", "%CPU", "%MEM", "TIME", "COMMAND"],
            "Processes": [],
        }

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_docker_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/v1/docker/containers/abc123/top?ps_args=aux"
                )

        assert response.status_code == 200
        mock_docker_client.list_processes.assert_called_once_with(
            "abc123", ps_args="aux"
        )


class TestContainerProcessSchema:
    """Tests pour les schémas ContainerProcess."""

    def test_container_process_defaults(self):
        """Test les valeurs par défaut du schéma."""
        process = ContainerProcess(pid=1)
        assert process.pid == 1
        assert process.user == ""
        assert process.cpu == 0.0
        assert process.mem == 0.0
        assert process.time == ""
        assert process.command == ""

    def test_container_process_full(self):
        """Test avec toutes les valeurs."""
        process = ContainerProcess(
            pid=42,
            user="appuser",
            cpu=15.5,
            mem=23.7,
            time="00:05:30",
            command="python -m uvicorn app:main",
        )
        assert process.pid == 42
        assert process.user == "appuser"
        assert process.cpu == 15.5
        assert process.mem == 23.7
        assert process.time == "00:05:30"
        assert process.command == "python -m uvicorn app:main"


class TestContainerProcessListResponseSchema:
    """Tests pour le schéma ContainerProcessListResponse."""

    def test_response_with_processes(self):
        """Test avec une liste de processus."""
        response = ContainerProcessListResponse(
            container_id="abc123",
            titles=["PID", "USER", "%CPU", "%MEM", "TIME", "COMMAND"],
            processes=[
                ContainerProcess(
                    pid=1,
                    user="root",
                    cpu=0.0,
                    mem=0.1,
                    time="00:00:01",
                    command="/bin/bash",
                ),
            ],
        )
        assert response.container_id == "abc123"
        assert len(response.titles) == 6
        assert len(response.processes) == 1
        assert isinstance(response.timestamp, datetime)

    def test_response_timestamp_auto(self):
        """Test que le timestamp est généré automatiquement."""
        before = datetime.now(timezone.utc)
        response = ContainerProcessListResponse(
            container_id="test", titles=[], processes=[]
        )
        after = datetime.now(timezone.utc)

        assert before <= response.timestamp <= after


class TestProcessParsing:
    """Tests pour le parsing des données de processus Docker."""

    def test_parse_standard_format(self):
        """Test le parsing du format standard ps aux."""
        titles = ["PID", "USER", "%CPU", "%MEM", "TIME", "COMMAND"]
        _processes_raw = [  # noqa: F841
            ["1", "root", "0.0", "0.1", "00:00:01", "/bin/bash"],
            ["42", "app", "1.5", "2.3", "00:00:05", "python app.py"],
        ]

        # Simulation du parsing fait dans l'endpoint
        def find_index(possible_names):
            for name in possible_names:
                if name in titles:
                    return titles.index(name)
            return -1

        pid_idx = find_index(["PID", "pid"])
        user_idx = find_index(["USER", "user"])
        cpu_idx = find_index(["%CPU", "%Cpu", "cpu"])
        mem_idx = find_index(["%MEM", "%Mem", "mem"])
        time_idx = find_index(["TIME", "time"])
        cmd_idx = find_index(["COMMAND", "CMD", "command", "cmd"])

        assert pid_idx == 0
        assert user_idx == 1
        assert cpu_idx == 2
        assert mem_idx == 3
        assert time_idx == 4
        assert cmd_idx == 5

    def test_parse_alternate_format(self):
        """Test le parsing avec des titres alternatifs."""
        titles = ["PID", "USER", "CPU", "MEM", "TIME", "CMD"]
        _processes_raw = [  # noqa: F841
            ["1", "root", "0.0", "0.1", "00:00:01", "/bin/bash"],
        ]

        def find_index(possible_names):
            for name in possible_names:
                if name in titles:
                    return titles.index(name)
            return -1

        cpu_idx = find_index(["%CPU", "%Cpu", "CPU", "cpu"])
        mem_idx = find_index(["%MEM", "%Mem", "MEM", "mem"])
        cmd_idx = find_index(["COMMAND", "CMD", "command", "cmd"])

        assert cpu_idx == 2
        assert mem_idx == 3
        assert cmd_idx == 5

    def test_parse_missing_columns(self):
        """Test le parsing avec des colonnes manquantes."""
        titles = ["PID", "COMMAND"]  # Colonnes minimales
        _processes_raw = [  # noqa: F841
            ["1", "/bin/bash"],
        ]

        def find_index(possible_names):
            for name in possible_names:
                if name in titles:
                    return titles.index(name)
            return -1

        pid_idx = find_index(["PID", "pid"])
        user_idx = find_index(["USER", "user"])
        cpu_idx = find_index(["%CPU", "%Cpu", "cpu"])
        cmd_idx = find_index(["COMMAND", "CMD", "command", "cmd"])

        assert pid_idx == 0
        assert user_idx == -1
        assert cpu_idx == -1
        assert cmd_idx == 1
