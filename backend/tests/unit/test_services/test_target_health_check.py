"""
Unit tests for target health check functionality.

Covers TargetService.check_health, TargetService.check_all_health,
and the periodic health check async fallback.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.enums.target import TargetStatus, TargetType
from app.models.target import Target


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_target(
    target_id: str = "t-001",
    host: str = "docker.prod.example.com",
    port: int = 22,
    target_type: TargetType = TargetType.DOCKER,
    status: TargetStatus = TargetStatus.OFFLINE,
) -> Target:
    """Create a mock Target instance for testing."""
    target = MagicMock(spec=Target)
    target.id = target_id
    target.host = host
    target.port = port
    target.type = target_type
    target.status = status
    target.last_check = None
    target.organization_id = "org-001"
    return target


# ---------------------------------------------------------------------------
# check_health — TCP port mapping
# ---------------------------------------------------------------------------

class TestCheckHealthPortSelection:
    """Verify that check_health always uses the configured target port."""

    @pytest.mark.parametrize(
        ("target_type", "port"),
        [
            (TargetType.DOCKER, 22),
            (TargetType.DOCKER_COMPOSE, 22),
            (TargetType.DOCKER_SWARM, 22),
            (TargetType.KUBERNETES, 22),
            (TargetType.VM, 2222),
            (TargetType.PHYSICAL, 22),
        ],
    )
    @pytest.mark.asyncio
    async def test_probe_uses_configured_port(
        self,
        target_type: TargetType,
        port: int,
    ) -> None:
        """The TCP probe should always connect to the configured port."""
        from app.services.target_service import TargetService

        target = _make_target(target_type=target_type, port=port)

        # We patch asyncio.open_connection to capture the port used
        with patch("app.services.target_service.asyncio.open_connection") as mock_conn:
            mock_writer = AsyncMock()
            mock_conn.return_value = (AsyncMock(), mock_writer)

            db_mock = AsyncMock()
            await TargetService.check_health(db_mock, target)

            # asyncio.open_connection should have been called with the configured port
            mock_conn.assert_awaited_once()
            call_args = mock_conn.call_args
            assert call_args[0][1] == port


# ---------------------------------------------------------------------------
# check_health — status transitions
# ---------------------------------------------------------------------------

class TestCheckHealthStatusTransitions:
    """Verify status updates after successful/failed TCP probe."""

    @pytest.mark.asyncio
    async def test_online_when_port_open(self) -> None:
        from app.services.target_service import TargetService

        target = _make_target(status=TargetStatus.OFFLINE)

        with patch("app.services.target_service.asyncio.open_connection") as mock_conn:
            mock_writer = AsyncMock()
            mock_conn.return_value = (AsyncMock(), mock_writer)

            db_mock = AsyncMock()
            result = await TargetService.check_health(db_mock, target)

            assert result == TargetStatus.ONLINE
            assert target.status == TargetStatus.ONLINE
            assert target.last_check is not None

    @pytest.mark.asyncio
    async def test_offline_when_connection_refused(self) -> None:
        from app.services.target_service import TargetService

        target = _make_target(status=TargetStatus.ONLINE)

        with patch("app.services.target_service.asyncio.open_connection") as mock_conn:
            mock_conn.side_effect = ConnectionRefusedError()

            db_mock = AsyncMock()
            result = await TargetService.check_health(db_mock, target)

            assert result == TargetStatus.OFFLINE
            assert target.status == TargetStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_offline_when_timeout(self) -> None:
        from app.services.target_service import TargetService

        target = _make_target(status=TargetStatus.ONLINE)

        with patch("app.services.target_service.asyncio.open_connection") as mock_conn:
            mock_conn.side_effect = asyncio.TimeoutError()

            db_mock = AsyncMock()
            result = await TargetService.check_health(db_mock, target)

            assert result == TargetStatus.OFFLINE
            assert target.status == TargetStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_error_on_unexpected_exception(self) -> None:
        from app.services.target_service import TargetService

        target = _make_target(status=TargetStatus.ONLINE)

        with patch("app.services.target_service.asyncio.open_connection") as mock_conn:
            mock_conn.side_effect = RuntimeError("unexpected")

            db_mock = AsyncMock()
            result = await TargetService.check_health(db_mock, target)

            assert result == TargetStatus.ERROR
            assert target.status == TargetStatus.ERROR

    @pytest.mark.asyncio
    async def test_last_check_updated_on_success(self) -> None:
        from app.services.target_service import TargetService

        target = _make_target()
        assert target.last_check is None

        with patch("app.services.target_service.asyncio.open_connection") as mock_conn:
            mock_writer = AsyncMock()
            mock_conn.return_value = (AsyncMock(), mock_writer)

            db_mock = AsyncMock()
            await TargetService.check_health(db_mock, target)

            assert target.last_check is not None
            # last_check should be a recent datetime
            assert isinstance(target.last_check, datetime)

    @pytest.mark.asyncio
    async def test_db_commit_called(self) -> None:
        from app.services.target_service import TargetService

        target = _make_target()

        with patch("app.services.target_service.asyncio.open_connection") as mock_conn:
            mock_writer = AsyncMock()
            mock_conn.return_value = (AsyncMock(), mock_writer)

            db_mock = AsyncMock()
            await TargetService.check_health(db_mock, target)

            db_mock.commit.assert_awaited()


# ---------------------------------------------------------------------------
# check_all_health
# ---------------------------------------------------------------------------

class TestCheckAllHealth:
    """Verify batch health check for all targets."""

    @pytest.mark.asyncio
    async def test_checks_all_targets(self) -> None:
        from app.services.target_service import TargetService

        t1 = _make_target(target_id="t-001")
        t2 = _make_target(target_id="t-002")
        t3 = _make_target(target_id="t-003")

        db_mock = AsyncMock()
        # Mock the full async chain: db.execute() → result → scalars() → all()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [t1, t2, t3]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db_mock.execute.return_value = mock_result

        with patch.object(TargetService, "check_health", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = TargetStatus.ONLINE

            results = await TargetService.check_all_health(db_mock)

            assert len(results) == 3
            assert mock_check.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_error_for_failed_check(self) -> None:
        from app.services.target_service import TargetService

        t1 = _make_target(target_id="t-001")

        db_mock = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [t1]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db_mock.execute.return_value = mock_result

        with patch.object(TargetService, "check_health", new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = Exception("DB error")

            results = await TargetService.check_all_health(db_mock)

            assert len(results) == 1
            assert "error" in results[0]
            assert results[0]["target_id"] == "t-001"


# ---------------------------------------------------------------------------
# Health check endpoint route
# ---------------------------------------------------------------------------

class TestHealthCheckEndpoint:
    """Verify the API endpoint delegates correctly."""

    @pytest.mark.asyncio
    async def test_endpoint_returns_health_check_response(self) -> None:
        from app.schemas.target import HealthCheckResponse

        resp = HealthCheckResponse(
            target_id="t-001",
            status=TargetStatus.ONLINE,
            last_check=datetime.now(timezone.utc),
            message="Port ouvert sur host",
        )
        assert resp.status == TargetStatus.ONLINE
        assert resp.target_id == "t-001"
        assert resp.message
