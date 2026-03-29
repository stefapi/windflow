"""
Unit tests for DockerClientService.

These tests mock aiohttp to avoid real Docker connections.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.docker_client_service import (
    DEFAULT_DOCKER_SOCKET,
    DEFAULT_TIMEOUT,
    ContainerDetail,
    ContainerInfo,
    DockerClientService,
    ImageInfo,
    NetworkInfo,
    PullProgressEvent,
    SystemInfo,
    VolumeInfo,
)


class TestDockerClientServiceInit:
    """Tests for DockerClientService initialization."""

    def test_default_init(self):
        """Test default initialization parameters."""
        client = DockerClientService()
        assert client.socket_path == DEFAULT_DOCKER_SOCKET
        assert client.timeout == DEFAULT_TIMEOUT

    def test_custom_init(self):
        """Test custom initialization parameters."""
        client = DockerClientService(socket_path="/custom/socket.sock", timeout=60.0)
        assert client.socket_path == "/custom/socket.sock"
        assert client.timeout == 60.0


class TestDockerClientServicePing:
    """Tests for ping method."""

    @pytest.mark.asyncio
    async def test_ping_success(self):
        """Test successful ping."""
        client = DockerClientService()

        # Mock _request to return a successful response
        mock_response = MagicMock()
        mock_response.status = 200

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await client.ping()

        assert result is True

    @pytest.mark.asyncio
    async def test_ping_failure(self):
        """Test failed ping."""
        client = DockerClientService()

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("Connection failed")
            result = await client.ping()

        assert result is False


class TestContainerInfoFromDict:
    """Tests for ContainerInfo.from_dict parsing."""

    def test_basic_container(self):
        """Test parsing basic container data."""
        data = {
            "Id": "abc123def456",
            "Names": ["/my-container"],
            "Image": "nginx:latest",
            "ImageID": "sha256:abc123",
            "Command": "/bin/sh",
            "Created": 1700000000,
            "State": "running",
            "Status": "Up 2 hours",
            "Ports": [{"PrivatePort": 80, "PublicPort": 8080, "Type": "tcp"}],
            "Labels": {"app": "web"},
            "NetworkSettings": {"Networks": {"bridge": {}}},
            "Mounts": [],
            "RestartCount": 0,
        }

        container = ContainerInfo.from_dict(data)

        assert container.id == "abc123def456"
        assert container.name == "my-container"
        assert container.image == "nginx:latest"
        assert container.state == "running"
        assert container.labels == {"app": "web"}
        assert container.networks == ["bridge"]

    def test_container_without_name(self):
        """Test parsing container without name."""
        data = {
            "Id": "abc123def456",
            "Names": [],
            "Image": "nginx:latest",
            "ImageID": "sha256:abc123",
            "Command": "",
            "Created": 1700000000,
            "State": "exited",
            "Status": "Exited (0) 3 minutes ago",
            "Ports": [],
            "Labels": {},
            "NetworkSettings": {"Networks": {}},
            "Mounts": [],
            "RestartCount": 1,
        }

        container = ContainerInfo.from_dict(data)

        assert container.name == "abc123def456"  # Falls back to ID prefix


class TestContainerDetailFromDict:
    """Tests for ContainerDetail.from_dict parsing."""

    def test_container_detail(self):
        """Test parsing container detail data."""
        data = {
            "Id": "abc123def456",
            "Name": "/my-container",
            "Created": "2024-01-01T12:00:00Z",
            "Path": "/bin/sh",
            "Args": ["-c", "echo hello"],
            "State": {"Status": "running", "Running": True},
            "Config": {"Image": "nginx:latest"},
            "HostConfig": {},
            "NetworkSettings": {},
            "Mounts": [],
        }

        container = ContainerDetail.from_dict(data)

        assert container.id == "abc123def456"
        assert container.name == "my-container"
        assert container.image == "nginx:latest"


class TestImageInfoFromDict:
    """Tests for ImageInfo.from_dict parsing."""

    def test_image_info(self):
        """Test parsing image data."""
        data = {
            "Id": "sha256:abc123def456",
            "RepoTags": ["nginx:latest", "nginx:alpine"],
            "RepoDigests": ["nginx@sha256:dig..."],
            "Created": 1700000000,
            "Size": 1024000,
            "VirtualSize": 2048000,
            "Labels": {"maintainer": "NGINX"},
        }

        image = ImageInfo.from_dict(data)

        assert image.id == "abc123def456"
        assert image.repo_tags == ["nginx:latest", "nginx:alpine"]
        assert image.size == 1024000
        assert image.labels == {"maintainer": "NGINX"}

    def test_image_size_as_string(self):
        """Test parsing image size when it's a string."""
        data = {
            "Id": "sha256:abc123",
            "RepoTags": ["nginx:latest"],
            "RepoDigests": [],
            "Created": 1700000000,
            "Size": "1024000",
            "VirtualSize": "2048000",
            "Labels": {},
        }

        image = ImageInfo.from_dict(data)

        assert image.size == 1024000
        assert image.virtual_size == 2048000


class TestVolumeInfoFromDict:
    """Tests for VolumeInfo.from_dict parsing."""

    def test_volume_info(self):
        """Test parsing volume data."""
        data = {
            "Name": "my-volume",
            "Driver": "local",
            "Mountpoint": "/var/lib/docker/volumes/my-volume/_data",
            "CreatedAt": "2024-01-01T12:00:00Z",
            "Labels": {"env": "prod"},
            "Scope": "local",
        }

        volume = VolumeInfo.from_dict(data)

        assert volume.name == "my-volume"
        assert volume.driver == "local"
        assert volume.scope == "local"

    def test_volume_invalid_date(self):
        """Test parsing volume with invalid date."""
        data = {
            "Name": "my-volume",
            "Driver": "local",
            "Mountpoint": "/path",
            "CreatedAt": "invalid",
            "Labels": {},
            "Scope": "local",
        }

        volume = VolumeInfo.from_dict(data)

        # Should fall back to current time
        assert volume.name == "my-volume"


class TestNetworkInfoFromDict:
    """Tests for NetworkInfo.from_dict parsing."""

    def test_network_info(self):
        """Test parsing network data."""
        data = {
            "Id": "network123",
            "Name": "bridge",
            "Driver": "bridge",
            "Scope": "local",
            "Internal": False,
            "Attachable": False,
            "Ingress": False,
            "Created": "2024-01-01T12:00:00Z",
            "IPAM": {"Config": [{"Subnet": "172.17.0.0/16", "Gateway": "172.17.0.1"}]},
        }

        network = NetworkInfo.from_dict(data)

        assert network.id == "network123"
        assert network.name == "bridge"
        assert network.subnet == "172.17.0.0/16"
        assert network.gateway == "172.17.0.1"


class TestSystemInfoFromDict:
    """Tests for SystemInfo.from_dict parsing."""

    def test_system_info(self):
        """Test parsing system info data."""
        data = {
            "ID": "host123",
            "Name": "docker-host",
            "ServerVersion": "24.0.0",
            "Containers": 10,
            "ContainersRunning": 5,
            "ContainersPaused": 2,
            "ContainersStopped": 3,
            "Images": 20,
            "Driver": "overlay2",
            "DockerRootDir": "/var/lib/docker",
            "KernelVersion": "5.15.0",
            "OperatingSystem": "Ubuntu 22.04",
            "OSType": "linux",
            "Architecture": "x86_64",
            "NCPU": 4,
            "MemTotal": 8192000000,
        }

        system = SystemInfo.from_dict(data)

        assert system.id == "host123"
        assert system.containers == 10
        assert system.containers_running == 5
        assert system.cpus == 4


class TestPullProgressEventFromDict:
    """Tests for PullProgressEvent.from_dict parsing."""

    def test_pull_event(self):
        """Test parsing pull progress event."""
        data = {
            "status": "Pulling from library/nginx",
            "progress": "[=====>  ] 100/1000",
            "progressDetail": {"current": 100, "total": 1000},
            "id": "nginx",
        }

        event = PullProgressEvent.from_dict(data)

        assert event.status == "Pulling from library/nginx"
        assert event.progress == "[=====>  ] 100/1000"
        assert event.id == "nginx"

    def test_pull_event_with_error(self):
        """Test parsing pull event with error."""
        data = {
            "status": "Pulling image",
            "error": "connection timeout",
        }

        event = PullProgressEvent.from_dict(data)

        assert event.error == "connection timeout"


class TestDockerStreamDemux:
    """Tests for Docker stream demultiplexing."""

    def test_demux_single_frame_stdout(self):
        """Test demultiplexing a single stdout frame."""
        client = DockerClientService()

        # Frame header: stream_type(1) + reserved(3) + size(4) + payload
        # stream_type = 1 (stdout), size = 5, payload = "hello"
        frame = bytes([1, 0, 0, 0, 0, 0, 0, 5]) + b"hello"

        lines = client._demux_docker_stream(frame)

        assert lines == ["hello"]

    def test_demux_multiple_frames(self):
        """Test demultiplexing multiple frames."""
        client = DockerClientService()

        # Frame 1: stdout, "line1"
        frame1 = bytes([1, 0, 0, 0, 0, 0, 0, 5]) + b"line1"
        # Frame 2: stdout, "line2"
        frame2 = bytes([1, 0, 0, 0, 0, 0, 0, 5]) + b"line2"

        lines = client._demux_docker_stream(frame1 + frame2)

        assert lines == ["line1", "line2"]

    def test_demux_stderr_prefixed(self):
        """Test that stderr is prefixed with [ERR]."""
        client = DockerClientService()

        # Frame with stderr (stream_type = 2)
        frame = bytes([2, 0, 0, 0, 0, 0, 0, 5]) + b"error"

        lines = client._demux_docker_stream(frame)

        assert lines == ["[ERR] error"]  # stderr is prefixed with [ERR]

    def test_demux_invalid_frame(self):
        """Test demultiplexing with invalid frame (too short)."""
        client = DockerClientService()

        # Too short to be a valid frame
        frame = b"short"

        lines = client._demux_docker_stream(frame)

        assert lines == []


class TestDockerClientServiceListContainers:
    """Tests for list_containers method."""

    @pytest.mark.asyncio
    async def test_list_containers(self):
        """Test listing containers."""
        client = DockerClientService()

        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value=[
                {
                    "Id": "abc123",
                    "Names": ["/container1"],
                    "Image": "nginx:latest",
                    "ImageID": "sha256:abc",
                    "Command": "/bin/sh",
                    "Created": 1700000000,
                    "State": "running",
                    "Status": "Up 2 hours",
                    "Ports": [],
                    "Labels": {},
                    "NetworkSettings": {"Networks": {}},
                    "Mounts": [],
                    "RestartCount": 0,
                }
            ]
        )

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            containers = await client.list_containers()

        assert len(containers) == 1
        assert containers[0].name == "container1"
        assert containers[0].image == "nginx:latest"

    @pytest.mark.asyncio
    async def test_list_containers_with_filters(self):
        """Test listing containers with filters."""
        client = DockerClientService()

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=[])

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            await client.list_containers(filters={"status": ["running"]})

        # Verify that filters were passed
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert "filters" in call_args.kwargs["params"]


class TestDockerClientServiceListImages:
    """Tests for list_images method."""

    @pytest.mark.asyncio
    async def test_list_images(self):
        """Test listing images."""
        client = DockerClientService()

        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value=[
                {
                    "Id": "sha256:abc123",
                    "RepoTags": ["nginx:latest"],
                    "RepoDigests": [],
                    "Created": 1700000000,
                    "Size": 1024000,
                    "VirtualSize": 1024000,
                    "Labels": {},
                }
            ]
        )

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            images = await client.list_images()

        assert len(images) == 1
        assert images[0].repo_tags == ["nginx:latest"]


class TestDockerClientServiceListVolumes:
    """Tests for list_volumes method."""

    @pytest.mark.asyncio
    async def test_list_volumes(self):
        """Test listing volumes."""
        client = DockerClientService()

        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "Volumes": [
                    {
                        "Name": "volume1",
                        "Driver": "local",
                        "Mountpoint": "/path",
                        "CreatedAt": "2024-01-01T12:00:00Z",
                        "Labels": {},
                        "Scope": "local",
                    }
                ]
            }
        )

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            volumes = await client.list_volumes()

        assert len(volumes) == 1
        assert volumes[0].name == "volume1"


class TestDockerClientServiceListNetworks:
    """Tests for list_networks method."""

    @pytest.mark.asyncio
    async def test_list_networks(self):
        """Test listing networks."""
        client = DockerClientService()

        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value=[
                {
                    "Id": "net123",
                    "Name": "bridge",
                    "Driver": "bridge",
                    "Scope": "local",
                    "Internal": False,
                    "Attachable": False,
                    "Ingress": False,
                    "Created": "2024-01-01T12:00:00Z",
                    "IPAM": {
                        "Config": [{"Subnet": "172.17.0.0/16", "Gateway": "172.17.0.1"}]
                    },
                }
            ]
        )

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            networks = await client.list_networks()

        assert len(networks) == 1
        assert networks[0].name == "bridge"
