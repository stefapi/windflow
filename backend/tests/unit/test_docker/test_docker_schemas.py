"""
Unit tests for Docker schemas (Pydantic models).

These tests validate the Pydantic schemas used in the Docker API.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.docker import (
    ContainerCreateRequest,
    ContainerDetailResponse,
    ContainerLogsRequest,
    ContainerLogsResponse,
    ContainerResponse,
    ContainerStatsResponse,
    DockerErrorResponse,
    ImagePullRequest,
    ImagePullResponse,
    ImageResponse,
    MountPoint,
    NetworkResponse,
    PingResponse,
    PortBinding,
    SystemInfoResponse,
    SystemVersionResponse,
    VolumeCreateRequest,
    VolumeResponse,
)


class TestContainerCreateRequest:
    """Tests for ContainerCreateRequest schema."""

    def test_valid_request(self):
        """Test valid container creation request."""
        req = ContainerCreateRequest(name="my-container", image="nginx:latest")
        assert req.name == "my-container"
        assert req.image == "nginx:latest"

    def test_with_all_fields(self):
        """Test container creation with all optional fields."""
        req = ContainerCreateRequest(
            name="my-container",
            image="nginx:latest",
            command=["nginx", "-g", "daemon off;"],
            env=["NGINX_PORT=80"],
            ports={"80/tcp": {"HostPort": "8080"}},
            labels={"app": "web"},
            restart_policy="always",
            network_mode="bridge",
            privileged=False,
        )
        assert req.restart_policy == "always"
        assert req.network_mode == "bridge"

    def test_invalid_name(self):
        """Test invalid container name."""
        with pytest.raises(ValidationError):
            ContainerCreateRequest(name="-invalid-name", image="nginx:latest")

    def test_default_values(self):
        """Test default values."""
        req = ContainerCreateRequest(name="my-container", image="nginx:latest")
        assert req.restart_policy == "no"
        assert req.network_mode == "bridge"
        assert req.privileged is False


class TestContainerLogsRequest:
    """Tests for ContainerLogsRequest schema."""

    def test_valid_request(self):
        """Test valid logs request."""
        req = ContainerLogsRequest()
        assert req.tail == 100
        assert req.timestamps is False

    def test_custom_parameters(self):
        """Test custom log parameters."""
        req = ContainerLogsRequest(
            tail=500,
            timestamps=True,
            since=1700000000,
            until=1700100000,
        )
        assert req.tail == 500
        assert req.timestamps is True
        assert req.since == 1700000000
        assert req.until == 1700100000

    def test_tail_limits(self):
        """Test tail parameter limits."""
        # Should pass - minimum
        req = ContainerLogsRequest(tail=1)
        assert req.tail == 1

        # Should pass - maximum
        req = ContainerLogsRequest(tail=10000)
        assert req.tail == 10000

        # Should fail - below minimum
        with pytest.raises(ValidationError):
            ContainerLogsRequest(tail=0)

        # Should fail - above maximum
        with pytest.raises(ValidationError):
            ContainerLogsRequest(tail=10001)


class TestContainerLogsResponse:
    """Tests for ContainerLogsResponse schema."""

    def test_response(self):
        """Test logs response."""
        now = datetime.now(timezone.utc)
        resp = ContainerLogsResponse(
            logs="Line 1\nLine 2",
            container_id="abc123",
            timestamp=now,
        )
        assert resp.logs == "Line 1\nLine 2"
        assert resp.container_id == "abc123"

    def test_default_timestamp(self):
        """Test default timestamp."""
        resp = ContainerLogsResponse(
            logs="test",
            container_id="abc",
        )
        assert resp.timestamp is not None


class TestImagePullRequest:
    """Tests for ImagePullRequest schema."""

    def test_default_tag(self):
        """Test default tag is latest."""
        req = ImagePullRequest(name="nginx")
        assert req.tag == "latest"

    def test_custom_tag(self):
        """Test custom tag."""
        req = ImagePullRequest(name="nginx", tag="alpine")
        assert req.tag == "alpine"


class TestImagePullResponse:
    """Tests for ImagePullResponse schema."""

    def test_response(self):
        """Test pull response."""
        resp = ImagePullResponse(
            status="Pulling image",
            progress="50%",
            id="nginx",
        )
        assert resp.status == "Pulling image"
        assert resp.progress == "50%"

    def test_optional_fields(self):
        """Test optional fields can be None."""
        resp = ImagePullResponse(status="Complete")
        assert resp.progress is None
        assert resp.id is None


class TestVolumeCreateRequest:
    """Tests for VolumeCreateRequest schema."""

    def test_valid_request(self):
        """Test valid volume creation."""
        req = VolumeCreateRequest(
            name="my-volume",
            driver="local",
        )
        assert req.name == "my-volume"
        assert req.driver == "local"

    def test_with_labels(self):
        """Test volume with labels."""
        req = VolumeCreateRequest(
            name="my-volume",
            labels={"env": "prod"},
        )
        assert req.labels == {"env": "prod"}

    def test_invalid_name(self):
        """Test invalid volume name."""
        with pytest.raises(ValidationError):
            VolumeCreateRequest(name="-invalid")


class TestVolumeResponse:
    """Tests for VolumeResponse schema."""

    def test_response(self):
        """Test volume response."""
        now = datetime.now(timezone.utc)
        resp = VolumeResponse(
            name="my-volume",
            driver="local",
            Mountpoint="/var/lib/docker/volumes/my-volume/_data",
            CreatedAt=now,
            labels={"env": "prod"},
            scope="local",
        )
        assert resp.name == "my-volume"
        assert resp.scope == "local"


class TestNetworkResponse:
    """Tests for NetworkResponse schema."""

    def test_response(self):
        """Test network response."""
        now = datetime.now(timezone.utc)
        resp = NetworkResponse(
            id="net123",
            name="bridge",
            driver="bridge",
            scope="local",
            internal=False,
            attachable=False,
            ingress=False,
            created=now,
            subnet="172.17.0.0/16",
            gateway="172.17.0.1",
        )
        assert resp.name == "bridge"
        assert resp.subnet == "172.17.0.0/16"


class TestSystemInfoResponse:
    """Tests for SystemInfoResponse schema."""

    def test_response(self):
        """Test system info response."""
        resp = SystemInfoResponse(
            ID="host123",
            Name="docker-host",
            ServerVersion="24.0.0",
            Containers=10,
            ContainersRunning=5,
            ContainersPaused=2,
            ContainersStopped=3,
            Images=20,
            Driver="overlay2",
            DockerRootDir="/var/lib/docker",
            KernelVersion="5.15.0",
            OperatingSystem="Ubuntu 22.04",
            OSType="linux",
            Architecture="x86_64",
            NCPU=4,
            MemTotal=8192000000,
        )
        assert resp.containers_running == 5
        assert resp.cpus == 4


class TestSystemVersionResponse:
    """Tests for SystemVersionResponse schema."""

    def test_response(self):
        """Test version response."""
        resp = SystemVersionResponse(
            version="24.0.0",
            ApiVersion="1.43",
            MinAPIVersion="1.12",
            GitCommit="abc123",
            GoVersion="go1.20",
            Os="linux",
            Arch="amd64",
            KernelVersion="5.15.0",
            BuildTime="2024-01-01",
        )
        assert resp.version == "24.0.0"


class TestPingResponse:
    """Tests for PingResponse schema."""

    def test_available(self):
        """Test Docker available."""
        resp = PingResponse(available=True, message="Docker is running")
        assert resp.available is True

    def test_unavailable(self):
        """Test Docker unavailable."""
        resp = PingResponse(available=False)
        assert resp.available is False


class TestDockerErrorResponse:
    """Tests for DockerErrorResponse schema."""

    def test_error_response(self):
        """Test error response."""
        resp = DockerErrorResponse(
            error="connection_failed",
            message="Cannot connect to Docker daemon",
            details={"socket": "/var/run/docker.sock"},
        )
        assert resp.error == "connection_failed"

    def test_minimal_error(self):
        """Test minimal error response."""
        resp = DockerErrorResponse(
            error="unknown",
            message="An error occurred",
        )
        assert resp.details is None


class TestContainerStatsResponse:
    """Tests for ContainerStatsResponse schema."""

    def test_response(self):
        """Test stats response."""
        now = datetime.now(timezone.utc)
        resp = ContainerStatsResponse(
            container_id="abc123",
            cpu_stats={"cpu_usage": 100},
            pre_cpu_stats={"cpu_usage": 50},
            memory_stats={"usage": 1024},
            networks={"eth0": {"rx_bytes": 100}},
            blkio_stats={},
            timestamp=now,
        )
        assert resp.container_id == "abc123"

    def test_from_docker_stats(self):
        """Test creating from Docker stats."""
        data = {
            "cpu_stats": {"cpu_usage": 100},
            "precpu_stats": {"cpu_usage": 50},
            "memory_stats": {"usage": 1024},
            "networks": {"eth0": {"rx_bytes": 100}},
            "blkio_stats": {},
        }

        resp = ContainerStatsResponse.from_docker_stats("abc123", data)
        assert resp.container_id == "abc123"
        assert resp.cpu_stats["cpu_usage"] == 100


class TestPortBinding:
    """Tests for PortBinding schema."""

    def test_full_binding(self):
        """Test full port binding."""
        binding = PortBinding(HostIp="0.0.0.0", HostPort="8080")
        assert binding.host_ip == "0.0.0.0"
        assert binding.host_port == "8080"

    def test_partial_binding(self):
        """Test partial port binding."""
        binding = PortBinding(HostPort="8080")
        assert binding.host_ip is None


class TestMountPoint:
    """Tests for MountPoint schema."""

    def test_mount_point(self):
        """Test mount point."""
        mount = MountPoint(
            type="bind",
            source="/host/path",
            destination="/container/path",
            mode="rw",
            propagation="",
        )
        assert mount.type == "bind"
        assert mount.source == "/host/path"


class TestContainerResponse:
    """Tests for ContainerResponse schema."""

    def test_response(self):
        """Test container response."""
        now = datetime.now(timezone.utc)
        resp = ContainerResponse(
            id="abc123def456",
            name="my-container",
            image="nginx:latest",
            imageId="sha256:abc123",
            command="/bin/sh",
            created=now,
            state="running",
            status="Up 2 hours",
            ports=[],
            labels={"app": "web"},
            networks=["bridge"],
            mounts=[],
            restart_count=0,
        )
        assert resp.id == "abc123def456"
        assert resp.state == "running"


class TestContainerDetailResponse:
    """Tests for ContainerDetailResponse schema."""

    def test_response(self):
        """Test container detail response."""
        now = datetime.now(timezone.utc)
        resp = ContainerDetailResponse(
            id="abc123",
            name="my-container",
            created=now,
            path="/bin/sh",
            args=["-c", "echo hello"],
            state={"Status": "running"},
            image="nginx:latest",
            config={"Image": "nginx:latest"},
            host_config={},
            network_settings={},
            mounts=[],
        )
        assert resp.name == "my-container"
        assert resp.image == "nginx:latest"


class TestImageResponse:
    """Tests for ImageResponse schema."""

    def test_response(self):
        """Test image response."""
        now = datetime.now(timezone.utc)
        resp = ImageResponse(
            id="abc123",
            repoTags=["nginx:latest"],
            repoDigests=["nginx@sha256:abc"],
            created=now,
            size=1024000,
            virtualSize=2048000,
            labels={"maintainer": "NGINX"},
        )
        assert resp.repo_tags == ["nginx:latest"]
