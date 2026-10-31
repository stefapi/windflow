"""Tests unitaires des endpoints lecture `/compute` étendus (STORY-173, AC 1).

Couvre `GET /compute/browse`, `GET /compute/volumes`,
`GET /compute/volumes/{name}` et `GET /compute/volumes/{name}/browse` :
cas obligatoires par verbe (règle 35) + tests sécurité (règle 40 —
401/403/422/404) + enveloppe pagination STORY-126/128.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from tests.conftest import unwrap

from app.core.exceptions import NotFoundError
from app.schemas.common import PaginatedResponse


@pytest.fixture(autouse=True)
def force_real_auth(monkeypatch) -> None:
    """Force disable_auth=False — pattern test_compute_api."""
    from app.config import settings

    monkeypatch.setattr(settings, "disable_auth", False)


def _paginated(
    items: list[dict], page: int = 1, per_page: int = 20, total: int | None = None
):
    """Construit une PaginatedResponse légère (pattern helper tests)."""
    real_total = total if total is not None else len(items)
    pages = (real_total + per_page - 1) // per_page if per_page else 0
    return PaginatedResponse.model_validate(
        {
            "data": items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": real_total,
                "pages": pages,
            },
        }
    )


def _browse_item(name: str, kind: str = "standalone", status: str = "running"):
    return {
        "id": f"id-{name}",
        "name": name,
        "kind": kind,
        "status": status,
        "target_id": "local",
        "target_name": "Local Docker",
        "image": "nginx:latest",
        "technology": None,
        "stack_id": None,
    }


def _patch_org_membership():
    """Stubbe l'appartenance org (pattern test_compute_api — STORY-121.3)."""
    from contextlib import ExitStack

    from app.services.user_organization_service import UserOrganizationService

    stack = ExitStack()
    stack.enter_context(
        patch.object(
            UserOrganizationService,
            "is_member",
            new=AsyncMock(return_value=True),
        )
    )
    return stack


# =============================================================================
# GET /compute/browse
# =============================================================================


class TestComputeBrowseEndpoint:
    async def test_browse_returns_empty_list(self, authenticated_client):
        """200, data: [], pagination{page=1, total=0} (service mocké vide)."""
        with patch(
            "app.api.v1.compute.compute_service.get_compute_browse",
            new=AsyncMock(return_value=_paginated([])),
        ):
            response = await authenticated_client.get("/api/v1/compute/browse")

        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["pagination"]["page"] == 1
        assert body["pagination"]["total"] == 0

    async def test_browse_returns_items_with_filters(self, authenticated_client):
        """Filtres type/status/search/target_id passés au service ; enveloppe."""
        items = [
            _browse_item("web", "managed_service"),
            _browse_item("redis", "managed_service"),
            _browse_item("legacy", "standalone", status="exited"),
        ]
        with _patch_org_membership():
            with patch(
                "app.api.v1.compute.compute_service.get_compute_browse",
                new=AsyncMock(return_value=_paginated(items)),
            ) as mock_svc:
                response = await authenticated_client.get(
                    "/api/v1/compute/browse"
                    "?type=managed&status=running&search=web&target_id=local"
                    "&organization_id=org-123"
                )

        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 3
        assert body["pagination"]["total"] == 3
        kwargs = mock_svc.call_args.kwargs
        assert kwargs["type_filter"] == "managed"
        assert kwargs["status_filter"] == "running"
        assert kwargs["search"] == "web"
        assert kwargs["target_id_filter"] == "local"
        assert kwargs["org_ids"] == ["org-123"]

    async def test_browse_pagination_envelope(self, authenticated_client):
        """per_page=2&page=2 → slicing + métadonnées exactes ; 101 → 422."""
        items = [_browse_item(f"item-{i}") for i in range(5)]
        with patch(
            "app.api.v1.compute.compute_service.get_compute_browse",
            new=AsyncMock(
                return_value=_paginated(items[2:4], page=2, per_page=2, total=5)
            ),
        ):
            response = await authenticated_client.get(
                "/api/v1/compute/browse?page=2&per_page=2"
            )
        assert response.status_code == 200
        body = response.json()
        assert [i["name"] for i in body["data"]] == ["item-2", "item-3"]
        assert body["pagination"] == {
            "page": 2,
            "per_page": 2,
            "total": 5,
            "pages": 3,
        }

        # per_page > 100 → 422 (borne canonique, pas de clamp)
        response = await authenticated_client.get("/api/v1/compute/browse?per_page=101")
        assert response.status_code == 422

    async def test_browse_returns_401_without_token(self, client):
        """Sécurité (règle 40) : 401 sans token."""
        response = await client.get("/api/v1/compute/browse")
        assert response.status_code == 401

    async def test_browse_viewer_200(self, viewer_client):
        """RBAC lecture viewer+ : 200 pour un viewer."""
        with patch(
            "app.api.v1.compute.compute_service.get_compute_browse",
            new=AsyncMock(return_value=_paginated([])),
        ):
            response = await viewer_client.get("/api/v1/compute/browse")
        assert response.status_code == 200

    async def test_browse_returns_403_for_foreign_organization(
        self, authenticated_client
    ):
        """Isolation org : organization_id d'une org non membre → 403."""
        with patch(
            "app.services.user_organization_service.UserOrganizationService.is_member",
            new=AsyncMock(return_value=False),
        ):
            response = await authenticated_client.get(
                "/api/v1/compute/browse?organization_id=org-etrangere"
            )
        assert response.status_code == 403

    async def test_browse_returns_422_on_invalid_type(self, authenticated_client):
        """type=unknown → 422 (pattern /global)."""
        response = await authenticated_client.get("/api/v1/compute/browse?type=unknown")
        assert response.status_code == 422


# =============================================================================
# GET /compute/volumes — liste paginée (miroir docker)
# =============================================================================


def _volume_dict(name: str):
    return {
        "name": name,
        "driver": "local",
        "mountpoint": f"/var/lib/docker/volumes/{name}",
        "created_at": "2026-10-31T12:00:00+00:00",
        "labels": {},
        "scope": "local",
    }


class _FakeVolume:
    """VolumeInfo léger pour mocker list_volumes."""

    def __init__(self, name: str):
        self.name = name
        self.driver = "local"
        self.mountpoint = f"/var/lib/docker/volumes/{name}"
        self.created_at = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
        self.labels = {}
        self.scope = "local"


class TestComputeVolumesEndpoint:
    async def test_volumes_list_paginated(self, authenticated_client):
        """200 + enveloppe pagination (client Docker mocké)."""
        fake = AsyncMock()
        fake.list_volumes.return_value = [
            _FakeVolume("data-a"),
            _FakeVolume("data-b"),
        ]
        fake.close = AsyncMock()
        with patch("app.api.v1.compute.DockerClientService", return_value=fake):
            response = await authenticated_client.get("/api/v1/compute/volumes")

        assert response.status_code == 200
        body = response.json()
        assert [v["name"] for v in body["data"]] == ["data-a", "data-b"]
        assert body["pagination"]["total"] == 2
        fake.close.assert_awaited_once()

    async def test_volumes_list_401(self, client):
        """Sécurité : 401 sans token."""
        response = await client.get("/api/v1/compute/volumes")
        assert response.status_code == 401

    async def test_volume_detail_200(self, authenticated_client):
        """Détail présent → 200 schéma complet."""
        fake = AsyncMock()
        fake.list_volumes.return_value = [_FakeVolume("data-a"), _FakeVolume("x")]
        fake.close = AsyncMock()
        with patch("app.api.v1.compute.DockerClientService", return_value=fake):
            response = await authenticated_client.get("/api/v1/compute/volumes/data-a")

        assert response.status_code == 200
        body = unwrap(response)
        assert body["name"] == "data-a"
        assert body["driver"] == "local"
        assert body["scope"] == "local"

    async def test_volume_detail_404_when_missing(self, authenticated_client):
        """NotFoundError → 404 enveloppé."""
        fake = AsyncMock()
        fake.list_volumes.return_value = [_FakeVolume("autre")]
        fake.close = AsyncMock()
        with patch("app.api.v1.compute.DockerClientService", return_value=fake):
            response = await authenticated_client.get("/api/v1/compute/volumes/inconnu")
        assert response.status_code == 404


# =============================================================================
# GET /compute/volumes/{name}/browse
# =============================================================================


class TestComputeVolumeBrowseEndpoint:
    async def test_volume_browse_200_entries(self, authenticated_client):
        """Service mocké → entrées fichier/dossier paginées."""
        entries = [
            {"name": "data", "is_dir": True, "path": "data"},
            {"name": "config.yml", "is_dir": False, "path": "config.yml"},
        ]
        with patch(
            "app.api.v1.compute.volume_browser_service.browse_volume",
            new=AsyncMock(return_value=_paginated(entries)),
        ):
            response = await authenticated_client.get(
                "/api/v1/compute/volumes/data-a/browse"
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 2
        assert body["data"][0]["is_dir"] is True
        assert body["pagination"]["total"] == 2

    async def test_volume_browse_422_invalid_name(self, authenticated_client):
        """Anti-injection : nom de volume invalide (espace) → 422 (service réel)."""
        response = await authenticated_client.get(
            "/api/v1/compute/volumes/bad%20name/browse"
        )
        assert response.status_code == 422

    async def test_volume_browse_422_invalid_subpath(self, authenticated_client):
        """Anti-traversal : subpath=../../host → 422 (service réel)."""
        response = await authenticated_client.get(
            "/api/v1/compute/volumes/data-a/browse?subpath=../../host"
        )
        assert response.status_code == 422

    async def test_volume_browse_404_unknown_volume(self, authenticated_client):
        """Volume inconnu → NotFoundError → 404."""

        async def _raise(*args, **kwargs):
            raise NotFoundError("Volume inconnu non trouvé")

        with patch(
            "app.api.v1.compute.volume_browser_service.browse_volume",
            side_effect=_raise,
        ):
            response = await authenticated_client.get(
                "/api/v1/compute/volumes/inconnu/browse"
            )
        assert response.status_code == 404
