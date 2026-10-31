"""Tests unitaires de `POST /compute/prune` (STORY-173, AC 2/AC 3).

Sécurité lourde (règles 40/35) : RBAC superadmin seul, confirmation
explicite (400), dry-run sans suppression, audit de l'exécution réelle,
validation stricte du body, aucune valeur fabriquée.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from tests.conftest import unwrap

from app.services.docker_client_service import PruneResult


@pytest.fixture(autouse=True)
def force_real_auth(monkeypatch) -> None:
    """Force disable_auth=False — pattern test_compute_api."""
    from app.config import settings

    monkeypatch.setattr(settings, "disable_auth", False)


def _prune_result(resource: str = "volumes", dry_run: bool = False) -> PruneResult:
    """PruneResult réaliste avec les champs étendus STORY-173."""
    return PruneResult(
        resource=resource,
        dry_run=dry_run,
        pruned_count=2,
        space_reclaimed_bytes=0 if resource == "volumes" else 2048,
        spared_count=1,
        pruned_names=["data-orphan", "cache-old"],
        spared_names=["windflow-plugin-trivy-cache"],
        failed_names=[],
        failed_count=0,
    )


def _fake_docker_client(result: PruneResult = None):
    """Client Docker factice — les trois wrappers renvoient le résultat."""
    result = result or _prune_result()
    fake = AsyncMock()
    fake.prune_images = AsyncMock(return_value=result)
    fake.prune_volumes = AsyncMock(return_value=result)
    fake.prune_stopped_containers = AsyncMock(return_value=result)
    fake.remove_volume = AsyncMock()
    fake.remove_image = AsyncMock()
    fake.remove_container = AsyncMock()
    fake.close = AsyncMock()
    return fake


# =============================================================================
# RBAC (AC 3 — règle 40)
# =============================================================================


class TestComputePruneRbac:
    async def test_prune_returns_401_without_token(self, client):
        """Obligatoire règle 40 : 401 sans token."""
        response = await client.post(
            "/api/v1/compute/prune", json={"resource": "volumes", "dry_run": True}
        )
        assert response.status_code == 401

    async def test_prune_returns_403_for_admin_operator_viewer(
        self, viewer_client, operator_client, org_admin_client
    ):
        """require_superuser (flag is_superuser) : 403 pour les autres rôles."""
        for cli in (viewer_client, operator_client, org_admin_client):
            response = await cli.post(
                "/api/v1/compute/prune",
                json={"resource": "volumes", "dry_run": True},
            )
            assert (
                response.status_code == 403
            ), f"403 attendu pour un rôle non-superadmin : {response.text}"


# =============================================================================
# Confirmation & dry-run (AC 3)
# =============================================================================


class TestComputePruneConfirmation:
    async def test_prune_returns_400_without_confirm(self, admin_client):
        """resource=volumes sans confirm ni dry_run → 400 actionnable."""
        response = await admin_client.post(
            "/api/v1/compute/prune", json={"resource": "volumes"}
        )
        assert response.status_code == 400
        body = response.json()
        assert "confirm" in body["error"]["message"].lower()

    async def test_prune_dry_run_returns_report_without_confirm(self, admin_client):
        """dry_run=true sans confirm → 200 rapport prévisionnel, aucun delete."""
        fake = _fake_docker_client(_prune_result(dry_run=True))
        with patch("app.api.v1.compute.DockerClientService", return_value=fake):
            response = await admin_client.post(
                "/api/v1/compute/prune",
                json={"resource": "volumes", "dry_run": True},
            )

        assert response.status_code == 200
        body = unwrap(response)
        assert body["dry_run"] is True
        assert body["pruned"] == ["data-orphan", "cache-old"]
        fake.prune_volumes.assert_awaited_once_with(dry_run=True, force=False)
        # Aucun appel suppressif direct
        fake.remove_volume.assert_not_awaited()

    async def test_prune_real_with_confirm_returns_report(self, admin_client):
        """confirm=true, dry_run=false → 200 rapport supprimés/épargnés/échecs."""
        fake = _fake_docker_client(_prune_result(dry_run=False))
        with patch("app.api.v1.compute.DockerClientService", return_value=fake):
            response = await admin_client.post(
                "/api/v1/compute/prune",
                json={"resource": "volumes", "confirm": True},
            )

        assert response.status_code == 200
        body = unwrap(response)
        assert body["dry_run"] is False
        assert body["pruned_count"] == 2
        assert body["spared"] == ["windflow-plugin-trivy-cache"]
        assert body["failed"] == []
        assert body["failed_count"] == 0
        fake.prune_volumes.assert_awaited_once_with(dry_run=False, force=False)

    async def test_prune_dispatches_images_and_containers(self, admin_client):
        """resource=images/containers → wrapper correspondant (dispatch)."""
        fake = _fake_docker_client(_prune_result("images", dry_run=True))
        with patch("app.api.v1.compute.DockerClientService", return_value=fake):
            response = await admin_client.post(
                "/api/v1/compute/prune",
                json={"resource": "images", "dry_run": True},
            )
        assert response.status_code == 200
        fake.prune_images.assert_awaited_once_with(dry_run=True, force=False)
        fake.prune_volumes.assert_not_awaited()

        fake2 = _fake_docker_client(_prune_result("containers", dry_run=True))
        with patch("app.api.v1.compute.DockerClientService", return_value=fake2):
            response = await admin_client.post(
                "/api/v1/compute/prune",
                json={"resource": "containers", "dry_run": True},
            )
        assert response.status_code == 200
        fake2.prune_stopped_containers.assert_awaited_once_with(
            dry_run=True, force=False
        )


# =============================================================================
# Audit (AC 3 — STORY-125)
# =============================================================================


class TestComputePruneAudit:
    async def test_prune_real_audited(self, admin_client, test_superuser):
        """confirm=true → AuditService avec action=compute.prune, acteur user."""
        fake = _fake_docker_client(_prune_result(dry_run=False))
        with patch("app.api.v1.compute.DockerClientService", return_value=fake):
            with patch(
                "app.api.v1.compute.AuditService.log_from_request",
                new=AsyncMock(),
            ) as mock_audit:
                response = await admin_client.post(
                    "/api/v1/compute/prune",
                    json={"resource": "volumes", "confirm": True},
                )

        assert response.status_code == 200
        mock_audit.assert_awaited_once()
        args, kwargs = mock_audit.await_args
        assert args[1] == "compute.prune" or kwargs.get("action") == "compute.prune"
        assert kwargs.get("user") is not None
        assert kwargs["details"]["dry_run"] is False

    async def test_prune_dry_run_not_audited(self, admin_client):
        """Dry-run = lecture → aucun appel d'audit."""
        fake = _fake_docker_client(_prune_result(dry_run=True))
        with patch("app.api.v1.compute.DockerClientService", return_value=fake):
            with patch(
                "app.api.v1.compute.AuditService.log_from_request",
                new=AsyncMock(),
            ) as mock_audit:
                response = await admin_client.post(
                    "/api/v1/compute/prune",
                    json={"resource": "volumes", "dry_run": True},
                )

        assert response.status_code == 200
        mock_audit.assert_not_awaited()

    async def test_prune_audit_details_contain_no_names_nor_force(self, admin_client):
        """L'audit ne persiste que comptages/préfixe — ni noms ni force."""
        fake = _fake_docker_client(_prune_result(dry_run=False))
        with patch("app.api.v1.compute.DockerClientService", return_value=fake):
            with patch(
                "app.api.v1.compute.AuditService.log_from_request",
                new=AsyncMock(),
            ) as mock_audit:
                await admin_client.post(
                    "/api/v1/compute/prune",
                    json={
                        "resource": "volumes",
                        "confirm": True,
                        "force": True,
                    },
                )

        mock_audit.assert_awaited_once()
        details = mock_audit.await_args.kwargs["details"]
        assert set(details.keys()) == {
            "dry_run",
            "pruned_count",
            "spared_count",
            "failed_count",
            "space_reclaimed_bytes",
            "protected_prefix",
        }
        assert "data-orphan" not in str(details)  # jamais de noms complets
        assert "force" not in details  # jamais le paramètre brut


# =============================================================================
# Validation & sémantique (AC 2 / règle 35)
# =============================================================================


class TestComputePruneValidation:
    async def test_prune_returns_422_on_invalid_body(self, admin_client):
        """resource=networks → 422 ; champ inconnu (extra=forbid) → 422."""
        response = await admin_client.post(
            "/api/v1/compute/prune",
            json={"resource": "networks", "dry_run": True},
        )
        assert response.status_code == 422

        response = await admin_client.post(
            "/api/v1/compute/prune",
            json={"resource": "volumes", "dry_run": True, "champ_inconnu": 1},
        )
        assert response.status_code == 422

    async def test_prune_response_contains_no_fabricated_volume_sizes(
        self, admin_client
    ):
        """resource=volumes → space_reclaimed_bytes == 0 (aucune valeur inventée)."""
        fake = _fake_docker_client(_prune_result("volumes", dry_run=True))
        with patch("app.api.v1.compute.DockerClientService", return_value=fake):
            response = await admin_client.post(
                "/api/v1/compute/prune",
                json={"resource": "volumes", "dry_run": True},
            )
        assert response.status_code == 200
        assert unwrap(response)["space_reclaimed_bytes"] == 0
