"""
Unit tests for DockerExecutor.

These tests mock subprocess and httpx to avoid real Docker operations.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from app.services.docker_executor import (
    CLIDockerExecutor,
    SocketDockerExecutor,
    DockerExecutor,
    ComposeExecutor,
    get_docker_executor,
    DockerExecutorBase,
)
from app.services.docker_client_service import DockerClientService


class TestCLIDockerExecutor:
    """Tests for CLIDockerExecutor."""

    def test_init_default(self):
        """Test default initialization."""
        executor = CLIDockerExecutor()
        assert executor.docker_path == "docker"

    def test_init_custom(self):
        """Test custom initialization."""
        executor = CLIDockerExecutor(docker_path="/usr/bin/docker")
        assert executor.docker_path == "/usr/bin/docker"

    def test_build_run_command_basic(self):
        """Test building basic docker run command."""
        executor = CLIDockerExecutor()

        config = {
            "image": "nginx:latest",
            "container_name": "my-container",
        }

        cmd = executor._build_run_command(config, "my-container")

        assert cmd[0] == "docker"
        assert cmd[1] == "run"
        assert cmd[2] == "-d"
        assert "--name" in cmd
        assert "my-container" in cmd
        assert "nginx:latest" in cmd

    def test_build_run_command_with_env(self):
        """Test building command with environment variables."""
        executor = CLIDockerExecutor()

        config = {
            "image": "nginx:latest",
            "environment": {"KEY1": "value1", "KEY2": "value2"},
        }

        cmd = executor._build_run_command(config)

        assert "-e" in cmd
        assert "KEY1=value1" in cmd
        assert "KEY2=value2" in cmd

    def test_build_run_command_with_ports(self):
        """Test building command with port mappings."""
        executor = CLIDockerExecutor()

        config = {
            "image": "nginx:latest",
            "ports": ["8080:80", "443:443"],
        }

        cmd = executor._build_run_command(config)

        assert "-p" in cmd
        assert "8080:80" in cmd
        assert "443:443" in cmd

    def test_build_run_command_with_volumes(self):
        """Test building command with volume mounts."""
        executor = CLIDockerExecutor()

        config = {
            "image": "nginx:latest",
            "volumes": ["/data:/data", "/logs:/var/log/nginx"],
        }

        cmd = executor._build_run_command(config)

        assert "-v" in cmd
        assert "/data:/data" in cmd

    def test_build_run_command_with_labels(self):
        """Test building command with labels."""
        executor = CLIDockerExecutor()

        config = {
            "image": "nginx:latest",
            "labels": {"app": "web", "env": "prod"},
        }

        cmd = executor._build_run_command(config)

        assert "--label" in cmd
        assert "app=web" in cmd
        assert "env=prod" in cmd

    def test_build_run_command_with_healthcheck(self):
        """Test building command with healthcheck."""
        executor = CLIDockerExecutor()

        config = {
            "image": "nginx:latest",
            "healthcheck": {
                "test": ["CMD", "curl", "-f", "http://localhost"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
            },
        }

        cmd = executor._build_run_command(config)

        assert "--health-cmd" in cmd
        assert "--health-interval" in cmd
        assert "--health-timeout" in cmd
        assert "--health-retries" in cmd

    @pytest.mark.asyncio
    async def test_deploy_container_success(self):
        """Test successful container deployment."""
        executor = CLIDockerExecutor()

        config = {"image": "nginx:latest"}

        # Mock subprocess
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(b"abc123def456", b"")
        )

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, result = await executor.deploy_container(config)

        assert success is True
        assert result == "abc123def456"

    @pytest.mark.asyncio
    async def test_deploy_container_failure(self):
        """Test failed container deployment."""
        executor = CLIDockerExecutor()

        config = {"image": "nonexistent:latest"}

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Error: image not found")
        )

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, result = await executor.deploy_container(config)

        assert success is False
        assert "image not found" in result

    @pytest.mark.asyncio
    async def test_start_container(self):
        """Test starting a container."""
        executor = CLIDockerExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, result = await executor.start_container("my-container")

        assert success is True
        assert "démarré" in result.lower()

    @pytest.mark.asyncio
    async def test_stop_container(self):
        """Test stopping a container."""
        executor = CLIDockerExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, result = await executor.stop_container("my-container")

        assert success is True

    @pytest.mark.asyncio
    async def test_restart_container(self):
        """Test restarting a container."""
        executor = CLIDockerExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, result = await executor.restart_container("my-container")

        assert success is True

    @pytest.mark.asyncio
    async def test_remove_container(self):
        """Test removing a container."""
        executor = CLIDockerExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, result = await executor.remove_container("my-container")

        assert success is True

    @pytest.mark.asyncio
    async def test_get_container_status(self):
        """Test getting container status."""
        executor = CLIDockerExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(
                b'[{"Id": "abc123", "Name": "/my-container", "Config": {"Image": "nginx"}, "State": {"Status": "running", "Running": true, "StartedAt": "2024-01-01"}, "RestartCount": 0}]',
                b""
            )
        )

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, status = await executor.get_container_status("my-container")

        assert success is True
        assert status["state"] == "running"
        assert status["running"] is True

    @pytest.mark.asyncio
    async def test_get_container_logs(self):
        """Test getting container logs."""
        executor = CLIDockerExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(b"Log line 1\nLog line 2", b"")
        )

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, logs = await executor.get_container_logs("my-container")

        assert success is True
        assert "Log line 1" in logs

    @pytest.mark.asyncio
    async def test_remove_volume(self):
        """Test removing a volume."""
        executor = CLIDockerExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, result = await executor.remove_volume("my-volume")

        assert success is True

    @pytest.mark.asyncio
    async def test_remove_volume_not_found(self):
        """Test removing a non-existent volume."""
        executor = CLIDockerExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Error: no such volume")
        )

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            # Should still return True for "not found"
            success, result = await executor.remove_volume("my-volume")

        assert success is True


class TestSocketDockerExecutor:
    """Tests for SocketDockerExecutor."""

    def test_init(self):
        """Test initialization."""
        executor = SocketDockerExecutor(socket_path="/custom/socket")
        assert executor.socket_path == "/custom/socket"

    @pytest.mark.asyncio
    async def test_get_client_connection_error(self):
        """Test client connection error handling."""
        executor = SocketDockerExecutor()

        with patch(
            "app.services.docker_executor.get_docker_client",
            new_callable=AsyncMock
        ) as mock_get_client:
            mock_get_client.side_effect = Exception("Connection refused")
            client = await executor._get_client()

        assert client is None

    @pytest.mark.asyncio
    async def test_deploy_container_no_client(self):
        """Test deploy when client is unavailable."""
        executor = SocketDockerExecutor()

        with patch.object(executor, '_get_client', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            success, result = await executor.deploy_container({"image": "nginx"})

        assert success is False
        assert "non accessible" in result.lower()

    @pytest.mark.asyncio
    async def test_remove_volume_not_found(self):
        """Test removing non-existent volume via socket."""
        executor = SocketDockerExecutor()

        mock_client = MagicMock()
        mock_client.remove_volume = AsyncMock(side_effect=Exception("no such volume"))

        with patch.object(executor, '_get_client', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_client
            success, result = await executor.remove_volume("nonexistent")

        assert success is True


class TestDockerExecutor:
    """Tests for DockerExecutor with fallback."""

    def test_init(self):
        """Test initialization."""
        executor = DockerExecutor(prefer_cli=True)
        assert executor._prefer_cli is True
        assert isinstance(executor._cli, CLIDockerExecutor)
        assert isinstance(executor._socket, SocketDockerExecutor)

    @pytest.mark.asyncio
    async def test_get_executor_cli_available(self):
        """Test getting CLI executor when available."""
        executor = DockerExecutor(prefer_cli=True)

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_exec:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"Docker version 24.0.0", b""))
            mock_exec.return_value = mock_process

            executor_obj = await executor._get_executor()

        assert isinstance(executor_obj, CLIDockerExecutor)

    @pytest.mark.asyncio
    async def test_get_executor_fallback_to_socket(self):
        """Test fallback to socket when CLI unavailable."""
        executor = DockerExecutor(prefer_cli=True)
        executor._cli_available = False

        executor_obj = await executor._get_executor()

        assert isinstance(executor_obj, SocketDockerExecutor)

    @pytest.mark.asyncio
    async def test_deploy_container(self):
        """Test deploy_container delegates to executor."""
        executor = DockerExecutor(prefer_cli=False)

        with patch.object(executor._socket, 'deploy_container', new_callable=AsyncMock) as mock_deploy:
            mock_deploy.return_value = (True, "container_id")
            success, result = await executor.deploy_container({"image": "nginx"})

        assert success is True
        assert result == "container_id"


class TestComposeExecutor:
    """Tests for ComposeExecutor."""

    def test_init(self):
        """Test initialization."""
        executor = ComposeExecutor(docker_compose_path="docker")
        assert executor.docker_path == "docker"

    @pytest.mark.asyncio
    async def test_deploy_compose_success(self):
        """Test successful compose deployment."""
        executor = ComposeExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(b"Container started", b"")
        )

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, result = await executor.deploy_compose(
                Path("/tmp/docker-compose.yml"),
                "my-project"
            )

        assert success is True

    @pytest.mark.asyncio
    async def test_deploy_compose_failure(self):
        """Test failed compose deployment."""
        executor = ComposeExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Error: file not found")
        )

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, result = await executor.deploy_compose(
                Path("/tmp/docker-compose.yml"),
                "my-project"
            )

        assert success is False

    @pytest.mark.asyncio
    async def test_stop_compose(self):
        """Test stopping compose project."""
        executor = ComposeExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, result = await executor.stop_compose("my-project")

        assert success is True

    @pytest.mark.asyncio
    async def test_remove_compose(self):
        """Test removing compose project."""
        executor = ComposeExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, result = await executor.remove_compose("my-project")

        assert success is True

    @pytest.mark.asyncio
    async def test_get_compose_logs(self):
        """Test getting compose logs."""
        executor = ComposeExecutor()

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(b"Service logs here", b"")
        )

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock
        ) as mock_subprocess:
            mock_subprocess.return_value = mock_process
            success, logs = await executor.get_compose_logs("my-project")

        assert success is True
        assert "logs" in logs.lower()


class TestGetDockerExecutorFactory:
    """Tests for get_docker_executor factory function."""

    def test_get_docker_executor_cli_preferred(self):
        """Test factory with CLI preferred."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            executor = get_docker_executor(prefer_cli=True)

        assert isinstance(executor, CLIDockerExecutor)

    def test_get_docker_executor_fallback(self):
        """Test factory falls back to socket."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Not found")
            executor = get_docker_executor(prefer_cli=True)

        assert isinstance(executor, SocketDockerExecutor)

    def test_get_docker_executor_socket_preferred(self):
        """Test factory with socket preferred."""
        executor = get_docker_executor(prefer_cli=False)
        assert isinstance(executor, SocketDockerExecutor)
