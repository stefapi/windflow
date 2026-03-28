"""
Tests unitaires pour les endpoints compute API.

Teste les routes GET /api/v1/compute/stats et GET /api/v1/compute/global :
- Authentification (401 sans token)
- Réponses correctes avec auth
- Validation des paramètres (422)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.compute import (
    ComputeGlobalView,
    ComputeStatsResponse,
    TargetGroup,
    TargetMetrics,
)


# =============================================================================
# Fixture module-level : désactiver le mode dev (disable_auth=False)
# pour que les tests d'authentification fonctionnent correctement.
#
# Sans cela, le middleware auth tente de trouver un superadmin en base
# de données de test (vide) et retourne HTTP 500.
# =============================================================================


@pytest.fixture(autouse=True)
def force_real_auth(monkeypatch) -> None:
    """
    Force disable_auth=False pour tous les tests de ce module.

    En mode test, l'env peut avoir DISABLE_AUTH=true, ce qui fait que
    get_current_user cherche un superadmin en base → 500 si inexistant.
    En forçant disable_auth=False, l'auth JWT s'applique normalement.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "disable_auth", False)


# =============================================================================
# Fixtures helpers
# =============================================================================


def _make_stats_response(**kwargs) -> ComputeStatsResponse:
    """Crée une ComputeStatsResponse avec des valeurs par défaut."""
    defaults = dict(
        total_containers=10,
        running_containers=7,
        stacks_count=3,
        stacks_running_count=2,
        stacks_targets_count=1,
        stacks_services_count=5,
        discovered_count=2,
        discovered_targets_count=1,
        standalone_count=1,
        standalone_targets_count=1,
        targets_count=2,
    )
    defaults.update(kwargs)
    return ComputeStatsResponse(**defaults)


def _make_global_view() -> ComputeGlobalView:
    """Crée une ComputeGlobalView vide."""
    return ComputeGlobalView()


def _make_target_groups() -> list[TargetGroup]:
    """Crée une liste de TargetGroup."""
    return [
        TargetGroup(
            target_id="t1",
            target_name="Local Docker",
            technology="docker",
            metrics=TargetMetrics(),
        )
    ]


# =============================================================================
# Tests /compute/stats
# =============================================================================


class TestComputeStatsEndpoint:
    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client) -> None:
        """Sans token JWT, l'endpoint retourne 401."""
        response = await client.get("/api/v1/compute/stats")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_authenticated_returns_200(self, authenticated_client) -> None:
        """Avec token JWT valide, l'endpoint retourne 200 + body valide."""
        mock_stats = _make_stats_response()

        with patch(
            "app.api.v1.compute.compute_service.get_compute_stats",
            new_callable=AsyncMock,
            return_value=mock_stats,
        ):
            response = await authenticated_client.get("/api/v1/compute/stats")

        assert response.status_code == 200
        body = response.json()
        assert body["total_containers"] == 10
        assert body["running_containers"] == 7
        assert body["stacks_count"] == 3
        assert body["stacks_services_count"] == 5
        assert body["discovered_count"] == 2
        assert body["standalone_count"] == 1
        assert body["targets_count"] == 2

    @pytest.mark.asyncio
    async def test_response_schema_has_all_fields(self, authenticated_client) -> None:
        """Le body contient bien tous les 7 champs du schema."""
        mock_stats = _make_stats_response()

        with patch(
            "app.api.v1.compute.compute_service.get_compute_stats",
            new_callable=AsyncMock,
            return_value=mock_stats,
        ):
            response = await authenticated_client.get("/api/v1/compute/stats")

        assert response.status_code == 200
        body = response.json()
        expected_fields = {
            "total_containers",
            "running_containers",
            "stacks_count",
            "stacks_services_count",
            "discovered_count",
            "standalone_count",
            "targets_count",
        }
        assert expected_fields.issubset(body.keys())

    @pytest.mark.asyncio
    async def test_with_organization_id_query_param(self, authenticated_client) -> None:
        """Le paramètre organization_id est accepté et passé au service."""
        mock_stats = _make_stats_response()

        with patch(
            "app.api.v1.compute.compute_service.get_compute_stats",
            new_callable=AsyncMock,
            return_value=mock_stats,
        ) as mock_svc:
            response = await authenticated_client.get(
                "/api/v1/compute/stats?organization_id=org-123"
            )

        assert response.status_code == 200
        # Le service doit avoir été appelé avec un org_id
        mock_svc.assert_called_once()
        call_kwargs = mock_svc.call_args.kwargs
        assert call_kwargs.get("org_id") == "org-123"


# =============================================================================
# Tests /compute/global
# =============================================================================


class TestComputeGlobalEndpoint:
    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client) -> None:
        """Sans token JWT, l'endpoint retourne 401."""
        response = await client.get("/api/v1/compute/global")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_default_returns_global_view(self, authenticated_client) -> None:
        """Sans group_by, retourne un ComputeGlobalView (dict avec 3 sections)."""
        mock_view = _make_global_view()

        with patch(
            "app.api.v1.compute.compute_service.get_compute_global",
            new_callable=AsyncMock,
            return_value=mock_view,
        ):
            response = await authenticated_client.get("/api/v1/compute/global")

        assert response.status_code == 200
        body = response.json()
        assert "managed_stacks" in body
        assert "discovered_items" in body
        assert "standalone_containers" in body

    @pytest.mark.asyncio
    async def test_group_by_target_returns_list(self, authenticated_client) -> None:
        """group_by=target retourne une liste de TargetGroup."""
        mock_groups = _make_target_groups()

        with patch(
            "app.api.v1.compute.compute_service.get_compute_global",
            new_callable=AsyncMock,
            return_value=mock_groups,
        ):
            response = await authenticated_client.get(
                "/api/v1/compute/global?group_by=target"
            )

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["target_id"] == "t1"

    @pytest.mark.asyncio
    async def test_group_by_invalid_returns_422(self, authenticated_client) -> None:
        """group_by avec valeur invalide retourne 422 Unprocessable Entity."""
        response = await authenticated_client.get(
            "/api/v1/compute/global?group_by=invalid_value"
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_type_filter_invalid_returns_422(self, authenticated_client) -> None:
        """type avec valeur invalide retourne 422."""
        response = await authenticated_client.get(
            "/api/v1/compute/global?type=unknown_type"
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_filters_are_passed_to_service(self, authenticated_client) -> None:
        """Les paramètres de filtre sont correctement transmis au service."""
        mock_view = _make_global_view()

        with patch(
            "app.api.v1.compute.compute_service.get_compute_global",
            new_callable=AsyncMock,
            return_value=mock_view,
        ) as mock_svc:
            response = await authenticated_client.get(
                "/api/v1/compute/global"
                "?type=managed"
                "&technology=compose"
                "&target_id=t1"
                "&status=running"
                "&search=nginx"
            )

        assert response.status_code == 200
        mock_svc.assert_called_once()
        kwargs = mock_svc.call_args.kwargs
        assert kwargs["type_filter"] == "managed"
        assert kwargs["technology"] == "compose"
        assert kwargs["target_id_filter"] == "t1"
        assert kwargs["status_filter"] == "running"
        assert kwargs["search"] == "nginx"

    @pytest.mark.asyncio
    async def test_group_by_stack_is_default(self, authenticated_client) -> None:
        """Sans group_by, la valeur par défaut est 'stack'."""
        mock_view = _make_global_view()

        with patch(
            "app.api.v1.compute.compute_service.get_compute_global",
            new_callable=AsyncMock,
            return_value=mock_view,
        ) as mock_svc:
            await authenticated_client.get("/api/v1/compute/global")

        kwargs = mock_svc.call_args.kwargs
        assert kwargs["group_by"] == "stack"
