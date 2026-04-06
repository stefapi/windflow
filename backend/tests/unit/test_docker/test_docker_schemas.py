"""
Unit tests for Docker schemas (Pydantic models).

These tests validate the Pydantic schemas used in the Docker API.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.docker import (
    ContainerConfigInfo,
    ContainerCreateRequest,
    ContainerDetailResponse,
    ContainerHealthInfo,
    ContainerHealthLogEntry,
    ContainerHostConfigInfo,
    ContainerLogConfigInfo,
    ContainerLogsRequest,
    ContainerLogsResponse,
    ContainerNetworkEndpointInfo,
    ContainerNetworkSettingsInfo,
    ContainerRestartPolicyInfo,
    ContainerResourcesInfo,
    ContainerResponse,
    ContainerStateInfo,
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
    """Tests for ContainerStatsResponse schema — format pré-calculé."""

    def test_response(self):
        """Test stats response with pre-calculated format."""
        resp = ContainerStatsResponse(
            container_id="abc123",
            timestamp="2026-04-05T14:50:31.373476",
            cpu={"percent": 1.5},
            memory={"percent": 50.0, "used": 536870912, "limit": 1073741824},
            network={"rx_bytes": 894296, "tx_bytes": 126},
            block_io={"read_bytes": 177963008, "write_bytes": 1269760},
        )
        assert resp.container_id == "abc123"
        assert resp.type == "stats"
        assert resp.cpu["percent"] == 1.5
        assert resp.memory["percent"] == 50.0

    def test_default_type(self):
        """Test that type defaults to 'stats'."""
        resp = ContainerStatsResponse(
            container_id="xyz",
            timestamp="2026-01-01T00:00:00",
            cpu={"percent": 0.0},
            memory={"percent": 0.0, "used": 0, "limit": 0},
            network={"rx_bytes": 0, "tx_bytes": 0},
            block_io={"read_bytes": 0, "write_bytes": 0},
        )
        assert resp.type == "stats"


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


class TestContainerHealthLogEntry:
    """Tests for ContainerHealthLogEntry schema."""

    def test_from_docker_dict_complete(self):
        """Test creation from a complete Docker API dict."""
        data = {
            "Start": "2024-01-01T00:00:00Z",
            "End": "2024-01-01T00:00:01Z",
            "ExitCode": 0,
            "Output": "healthy",
        }
        entry = ContainerHealthLogEntry.from_docker_dict(data)
        assert entry.start == "2024-01-01T00:00:00Z"
        assert entry.end == "2024-01-01T00:00:01Z"
        assert entry.exit_code == 0
        assert entry.output == "healthy"

    def test_from_docker_dict_empty(self):
        """Test creation from an empty dict."""
        entry = ContainerHealthLogEntry.from_docker_dict({})
        assert entry.start is None
        assert entry.exit_code is None

    def test_from_docker_dict_none(self):
        """Test creation from None (empty data)."""
        entry = ContainerHealthLogEntry.from_docker_dict(None)
        assert entry.start is None


class TestContainerHealthInfo:
    """Tests for ContainerHealthInfo schema."""

    def test_from_docker_dict_complete(self):
        """Test creation with status, failing_streak and log entries."""
        data = {
            "Status": "healthy",
            "FailingStreak": 0,
            "Log": [
                {"Start": "2024-01-01T00:00:00Z", "End": "2024-01-01T00:00:01Z", "ExitCode": 0, "Output": "OK"},
            ],
        }
        health = ContainerHealthInfo.from_docker_dict(data)
        assert health.status == "healthy"
        assert health.failing_streak == 0
        assert len(health.log) == 1
        assert health.log[0].exit_code == 0

    def test_from_docker_dict_no_log(self):
        """Test health without log entries."""
        data = {"Status": "unhealthy", "FailingStreak": 3}
        health = ContainerHealthInfo.from_docker_dict(data)
        assert health.status == "unhealthy"
        assert health.failing_streak == 3
        assert health.log == []

    def test_from_docker_dict_empty(self):
        """Test creation from empty dict."""
        health = ContainerHealthInfo.from_docker_dict({})
        assert health.status is None
        assert health.log == []


class TestContainerStateInfo:
    """Tests for ContainerStateInfo schema."""

    def test_from_docker_dict_running(self):
        """Test running container with health info."""
        data = {
            "Status": "running",
            "Running": True,
            "Paused": False,
            "Restarting": False,
            "OOMKilled": False,
            "Dead": False,
            "ExitCode": 0,
            "Error": "",
            "StartedAt": "2024-01-01T00:00:00Z",
            "FinishedAt": "0001-01-01T00:00:00Z",
            "Health": {"Status": "healthy", "FailingStreak": 0, "Log": []},
        }
        state = ContainerStateInfo.from_docker_dict(data)
        assert state.status == "running"
        assert state.running is True
        assert state.paused is False
        assert state.health is not None
        assert state.health.status == "healthy"

    def test_from_docker_dict_exited(self):
        """Test exited container with exit_code and error."""
        data = {
            "Status": "exited",
            "Running": False,
            "Paused": False,
            "Restarting": False,
            "OOMKilled": False,
            "Dead": False,
            "ExitCode": 137,
            "Error": "OOM killed",
            "StartedAt": "2024-01-01T00:00:00Z",
            "FinishedAt": "2024-01-01T00:01:00Z",
        }
        state = ContainerStateInfo.from_docker_dict(data)
        assert state.status == "exited"
        assert state.running is False
        assert state.exit_code == 137
        assert state.error == "OOM killed"
        assert state.health is None

    def test_from_docker_dict_empty(self):
        """Test creation from empty dict — all fields None."""
        state = ContainerStateInfo.from_docker_dict({})
        assert state.status is None
        assert state.running is None
        assert state.health is None

    def test_from_docker_dict_oom_killed(self):
        """Test container killed by OOM."""
        data = {
            "Status": "dead",
            "OOMKilled": True,
            "Dead": True,
            "ExitCode": 137,
        }
        state = ContainerStateInfo.from_docker_dict(data)
        assert state.oom_killed is True
        assert state.dead is True


class TestContainerConfigInfo:
    """Tests for ContainerConfigInfo schema."""

    def test_from_docker_dict_complete(self):
        """Test creation with all fields."""
        data = {
            "Hostname": "my-container",
            "Domainname": "",
            "User": "nginx",
            "AttachStdin": False,
            "AttachStdout": False,
            "AttachStderr": False,
            "Tty": False,
            "OpenStdin": False,
            "StdinOnce": False,
            "Env": ["PATH=/usr/local/bin:/usr/bin", "NGINX_VERSION=1.25"],
            "Cmd": ["nginx", "-g", "daemon off;"],
            "Entrypoint": ["/docker-entrypoint.sh"],
            "Image": "nginx:latest",
            "WorkingDir": "",
            "Labels": {"maintainer": "NGINX", "version": "1.0"},
            "StopSignal": "SIGQUIT",
            "StopTimeout": 10,
        }
        config = ContainerConfigInfo.from_docker_dict(data)
        assert config.hostname == "my-container"
        assert config.user == "nginx"
        assert config.env == ["PATH=/usr/local/bin:/usr/bin", "NGINX_VERSION=1.25"]
        assert config.cmd == ["nginx", "-g", "daemon off;"]
        assert config.labels == {"maintainer": "NGINX", "version": "1.0"}
        assert config.stop_signal == "SIGQUIT"
        assert config.stop_timeout == 10

    def test_from_docker_dict_empty(self):
        """Test creation from empty dict."""
        config = ContainerConfigInfo.from_docker_dict({})
        assert config.hostname is None
        assert config.env is None

    def test_from_docker_dict_with_env_cmd(self):
        """Test creation focusing on env/cmd/entrypoint lists."""
        data = {
            "Env": ["FOO=bar"],
            "Cmd": ["/bin/sh"],
            "Entrypoint": None,
        }
        config = ContainerConfigInfo.from_docker_dict(data)
        assert config.env == ["FOO=bar"]
        assert config.cmd == ["/bin/sh"]
        assert config.entrypoint is None


class TestContainerLogConfigInfo:
    """Tests for ContainerLogConfigInfo schema."""

    def test_from_docker_dict_complete(self):
        """Test with type and config dict."""
        data = {"Type": "json-file", "Config": {}}
        log_config = ContainerLogConfigInfo.from_docker_dict(data)
        assert log_config.type == "json-file"
        assert log_config.config == {}

    def test_from_docker_dict_empty(self):
        """Test from empty dict."""
        log_config = ContainerLogConfigInfo.from_docker_dict({})
        assert log_config.type is None
        assert log_config.config is None


class TestContainerRestartPolicyInfo:
    """Tests for ContainerRestartPolicyInfo schema."""

    def test_from_docker_dict_always(self):
        """Test restart policy always."""
        data = {"Name": "always", "MaximumRetryCount": 0}
        policy = ContainerRestartPolicyInfo.from_docker_dict(data)
        assert policy.name == "always"
        assert policy.maximum_retry_count == 0

    def test_from_docker_dict_on_failure(self):
        """Test restart policy on-failure with retry count."""
        data = {"Name": "on-failure", "MaximumRetryCount": 5}
        policy = ContainerRestartPolicyInfo.from_docker_dict(data)
        assert policy.name == "on-failure"
        assert policy.maximum_retry_count == 5

    def test_from_docker_dict_empty(self):
        """Test from empty dict."""
        policy = ContainerRestartPolicyInfo.from_docker_dict({})
        assert policy.name is None
        assert policy.maximum_retry_count is None


class TestContainerResourcesInfo:
    """Tests for ContainerResourcesInfo schema."""

    def test_from_docker_dict_complete(self):
        """Test with memory and CPU limits."""
        data = {
            "Memory": 536870912,
            "MemoryReservation": 268435456,
            "MemorySwap": -1,
            "MemorySwappiness": 50,
            "CpuShares": 1024,
            "CpuPeriod": 100000,
            "CpuQuota": 50000,
            "NanoCpus": 2,
            "CpusetCpus": "0-3",
            "CpusetMems": "0",
            "PidsLimit": 100,
        }
        resources = ContainerResourcesInfo.from_docker_dict(data)
        assert resources.memory == 536870912
        assert resources.memory_swap == -1
        assert resources.cpus == 2
        assert resources.cpuset_cpus == "0-3"
        assert resources.pids_limit == 100

    def test_from_docker_dict_empty(self):
        """Test from empty dict."""
        resources = ContainerResourcesInfo.from_docker_dict({})
        assert resources.memory is None
        assert resources.cpu_shares is None


class TestContainerHostConfigInfo:
    """Tests for ContainerHostConfigInfo schema."""

    def test_from_docker_dict_complete(self):
        """Test with all fields present."""
        data = {
            "Binds": ["/host/data:/data:rw"],
            "ContainerIDFile": "",
            "LogConfig": {"Type": "json-file", "Config": {}},
            "NetworkMode": "bridge",
            "PortBindings": {"80/tcp": [{"HostIp": "", "HostPort": "8080"}]},
            "RestartPolicy": {"Name": "always", "MaximumRetryCount": 0},
            "AutoRemove": False,
            "VolumeDriver": "",
            "VolumesFrom": None,
            "CapAdd": None,
            "CapDrop": None,
            "CgroupnsMode": "private",
            "Dns": None,
            "DnsOptions": None,
            "DnsSearch": None,
            "ExtraHosts": None,
            "GroupAdd": None,
            "IpcMode": "private",
            "Cgroup": "",
            "Links": None,
            "OomScoreAdj": 0,
            "PidMode": "",
            "Privileged": False,
            "PublishAllPorts": False,
            "ReadonlyRootfs": False,
            "SecurityOpt": None,
            "StorageOpt": None,
            "Tmpfs": None,
            "UTSMode": "",
            "UsernsMode": "",
            "ShmSize": 67108864,
            "Sysctls": None,
            "Runtime": "runc",
            "ConsoleSize": [0, 0],
            "Isolation": "",
            "Resources": {
                "Memory": 0,
                "MemoryReservation": 0,
                "MemorySwap": 0,
                "MemorySwappiness": None,
                "CpuShares": 0,
                "CpuPeriod": 0,
                "CpuQuota": 0,
                "NanoCpus": 0,
                "CpusetCpus": "",
                "CpusetMems": "",
                "Devices": None,
                "Ulimits": None,
                "PidsLimit": None,
            },
            "MountLabel": "",
        }
        hc = ContainerHostConfigInfo.from_docker_dict(data)
        assert hc.binds == ["/host/data:/data:rw"]
        assert hc.network_mode == "bridge"
        assert hc.log_config is not None
        assert hc.log_config.type == "json-file"
        assert hc.restart_policy is not None
        assert hc.restart_policy.name == "always"
        assert hc.resources is not None
        assert hc.shm_size == 67108864
        assert hc.runtime == "runc"

    def test_from_docker_dict_empty(self):
        """Test from empty dict."""
        hc = ContainerHostConfigInfo.from_docker_dict({})
        assert hc.binds is None
        assert hc.log_config is None
        assert hc.restart_policy is None
        assert hc.resources is None

    def test_from_docker_dict_with_restart_policy(self):
        """Test that RestartPolicy sub-object is correctly mapped."""
        data = {"RestartPolicy": {"Name": "on-failure", "MaximumRetryCount": 3}}
        hc = ContainerHostConfigInfo.from_docker_dict(data)
        assert hc.restart_policy is not None
        assert hc.restart_policy.name == "on-failure"
        assert hc.restart_policy.maximum_retry_count == 3

    def test_from_docker_dict_with_resources(self):
        """Test that Resources sub-object is correctly mapped."""
        data = {"Resources": {"Memory": 536870912, "CpuShares": 512}}
        hc = ContainerHostConfigInfo.from_docker_dict(data)
        assert hc.resources is not None
        assert hc.resources.memory == 536870912
        assert hc.resources.cpu_shares == 512


class TestContainerNetworkEndpointInfo:
    """Tests for ContainerNetworkEndpointInfo schema."""

    def test_from_docker_dict_complete(self):
        """Test with all IP/MAC fields."""
        data = {
            "IPAddress": "172.17.0.2",
            "Gateway": "172.17.0.1",
            "MacAddress": "02:42:ac:11:00:02",
            "NetworkID": "net123abc",
            "EndpointID": "ep456def",
            "IPv6Gateway": "",
            "GlobalIPv6Address": "",
            "GlobalIPv6PrefixLen": 0,
            "IPPrefixLen": 16,
            "Driver": "bridge",
        }
        ep = ContainerNetworkEndpointInfo.from_docker_dict(data)
        assert ep.ip_address == "172.17.0.2"
        assert ep.gateway == "172.17.0.1"
        assert ep.mac_address == "02:42:ac:11:00:02"
        assert ep.network_id == "net123abc"
        assert ep.ip_prefix_len == 16

    def test_from_docker_dict_empty(self):
        """Test from empty dict."""
        ep = ContainerNetworkEndpointInfo.from_docker_dict({})
        assert ep.ip_address is None
        assert ep.gateway is None


class TestContainerNetworkSettingsInfo:
    """Tests for ContainerNetworkSettingsInfo schema."""

    def test_from_docker_dict_with_networks(self):
        """Test with bridge and custom network."""
        data = {
            "Networks": {
                "bridge": {
                    "IPAddress": "172.17.0.2",
                    "Gateway": "172.17.0.1",
                    "MacAddress": "02:42:ac:11:00:02",
                    "NetworkID": "bridge123",
                    "EndpointID": "ep1",
                    "IPPrefixLen": 16,
                },
                "my-network": {
                    "IPAddress": "10.0.0.5",
                    "Gateway": "10.0.0.1",
                    "MacAddress": "02:42:0a:00:00:05",
                    "NetworkID": "mynet456",
                    "EndpointID": "ep2",
                    "IPPrefixLen": 24,
                },
            }
        }
        ns = ContainerNetworkSettingsInfo.from_docker_dict(data)
        assert len(ns.networks) == 2
        assert "bridge" in ns.networks
        assert ns.networks["bridge"].ip_address == "172.17.0.2"
        assert ns.networks["my-network"].ip_address == "10.0.0.5"

    def test_from_docker_dict_empty(self):
        """Test from empty dict."""
        ns = ContainerNetworkSettingsInfo.from_docker_dict({})
        assert ns.networks == {}


class TestContainerDetailResponse:
    """Tests for ContainerDetailResponse schema with typed sub-models."""

    def test_response_with_typed_submodels(self):
        """Test container detail response with typed sub-models."""
        now = datetime.now(timezone.utc)
        resp = ContainerDetailResponse(
            id="abc123",
            name="my-container",
            created=now,
            path="/bin/sh",
            args=["-c", "echo hello"],
            state=ContainerStateInfo.from_docker_dict({
                "Status": "running",
                "Running": True,
                "Paused": False,
                "Restarting": False,
                "OOMKilled": False,
                "Dead": False,
                "ExitCode": 0,
                "StartedAt": "2024-01-01T00:00:00Z",
                "FinishedAt": "0001-01-01T00:00:00Z",
            }),
            image="nginx:latest",
            config=ContainerConfigInfo.from_docker_dict({
                "Image": "nginx:latest",
                "Env": ["PATH=/usr/local/bin"],
                "Cmd": ["nginx"],
            }),
            host_config=ContainerHostConfigInfo.from_docker_dict({
                "NetworkMode": "bridge",
                "RestartPolicy": {"Name": "always"},
            }),
            network_settings=ContainerNetworkSettingsInfo.from_docker_dict({
                "Networks": {
                    "bridge": {"IPAddress": "172.17.0.2", "Gateway": "172.17.0.1"},
                },
            }),
            mounts=[],
        )
        assert resp.name == "my-container"
        assert resp.state.status == "running"
        assert resp.state.running is True
        assert resp.config.image == "nginx:latest"
        assert resp.host_config.network_mode == "bridge"
        assert resp.host_config.restart_policy.name == "always"
        assert "bridge" in resp.network_settings.networks
        assert resp.network_settings.networks["bridge"].ip_address == "172.17.0.2"

    def test_response_from_docker_data(self):
        """Test full construction from simulated Docker inspect data."""
        now = datetime.now(timezone.utc)
        docker_state = {
            "Status": "running",
            "Running": True,
            "Paused": False,
            "Restarting": False,
            "OOMKilled": False,
            "Dead": False,
            "ExitCode": 0,
            "StartedAt": "2024-01-01T00:00:00Z",
            "FinishedAt": "0001-01-01T00:00:00Z",
        }
        docker_config = {
            "Hostname": "my-container",
            "Image": "nginx:latest",
            "Env": ["PATH=/usr/local/bin"],
            "Cmd": ["nginx", "-g", "daemon off;"],
            "Labels": {"app": "web"},
        }
        docker_host_config = {
            "Binds": None,
            "NetworkMode": "bridge",
            "RestartPolicy": {"Name": "unless-stopped", "MaximumRetryCount": 0},
            "LogConfig": {"Type": "json-file", "Config": {}},
            "Resources": {"Memory": 0},
            "ShmSize": 67108864,
            "Runtime": "runc",
        }
        docker_network_settings = {
            "Networks": {
                "bridge": {
                    "IPAddress": "172.17.0.5",
                    "Gateway": "172.17.0.1",
                    "MacAddress": "02:42:ac:11:00:05",
                },
            }
        }

        resp = ContainerDetailResponse(
            id="abc123def456",
            name="my-container",
            created=now,
            path="/docker-entrypoint.sh",
            args=["nginx", "-g", "daemon off;"],
            state=ContainerStateInfo.from_docker_dict(docker_state),
            image="nginx:latest",
            config=ContainerConfigInfo.from_docker_dict(docker_config),
            host_config=ContainerHostConfigInfo.from_docker_dict(docker_host_config),
            network_settings=ContainerNetworkSettingsInfo.from_docker_dict(docker_network_settings),
            mounts=[{"Type": "bind", "Source": "/host", "Destination": "/data"}],
        )

        # Verify serialization works
        json_data = resp.model_dump()
        assert json_data["state"]["status"] == "running"
        assert json_data["config"]["hostname"] == "my-container"
        assert json_data["host_config"]["restart_policy"]["name"] == "unless-stopped"
        assert json_data["network_settings"]["networks"]["bridge"]["ip_address"] == "172.17.0.5"
        assert len(json_data["mounts"]) == 1

    def _make_minimal_detail(self, **overrides):
        """Helper to build a minimal ContainerDetailResponse with required fields."""
        now = datetime.now(timezone.utc)
        defaults = dict(
            id="abc123",
            name="my-container",
            created=now,
            path="/bin/sh",
            args=[],
            state=ContainerStateInfo.from_docker_dict({"Status": "running", "Running": True}),
            image="nginx:latest",
            config=ContainerConfigInfo.from_docker_dict({}),
            host_config=ContainerHostConfigInfo.from_docker_dict({}),
            network_settings=ContainerNetworkSettingsInfo.from_docker_dict({}),
            mounts=[],
        )
        defaults.update(overrides)
        return ContainerDetailResponse(**defaults)

    def test_response_with_size_fields(self):
        """Test container detail response with size_rw and size_root_fs."""
        resp = self._make_minimal_detail(size_rw=536870912, size_root_fs=2147483648)
        assert resp.size_rw == 536870912
        assert resp.size_root_fs == 2147483648

        json_data = resp.model_dump()
        assert json_data["size_rw"] == 536870912
        assert json_data["size_root_fs"] == 2147483648

    def test_response_with_null_size_fields(self):
        """Test container detail response with null size fields (default)."""
        resp = self._make_minimal_detail()
        assert resp.size_rw is None
        assert resp.size_root_fs is None

        json_data = resp.model_dump()
        assert json_data["size_rw"] is None
        assert json_data["size_root_fs"] is None

    def test_response_with_large_size_fields(self):
        """Test container detail response with size values > 1GB."""
        resp = self._make_minimal_detail(size_rw=3221225472, size_root_fs=10737418240)
        assert resp.size_rw == 3221225472  # ~3 GB
        assert resp.size_root_fs == 10737418240  # ~10 GB


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
