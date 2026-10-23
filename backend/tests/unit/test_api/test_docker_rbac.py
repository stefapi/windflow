"""Tests RBAC du module Docker (STORY-122.2, AC 2 volet Docker + AC 5).

Matrice rôle × endpoint conforme à la spec 08 (cf. story § Contexte
technique) — Docker local = ressources hors organisation : le rôle
**global** s'applique.

Couverture :
- **viewer** : 200 sur les lectures (conteneurs, logs, ping système),
  403 sur les POST/PUT/PATCH/DELETE de gestion (création/suppression de
  conteneur, pull d'image, suppression de volume) ;
- **operator** : 200 sur les actions opérationnelles (start, batch/start),
  403 sur la gestion (création/suppression de conteneur, PATCH resources) ;
- **admin** : 200/204 sur la gestion (création/suppression de conteneur,
  suppression de volume) ;
- **superuser** : bypass — 200 sur un échantillon de chaque catégorie ;
- **401 sans token** sur un échantillon des 3 catégories ;
- **non-régression §2.G** : 35 opérations Docker inchangées, paths stables
  (introspection du schéma OpenAPI — ``app.routes`` est lazy sur les
  versions récentes de FastAPI).

Stratégie : Docker client mocké (``patch get_docker_client``) ; les
assertions 403 portent sur le **statut HTTP avant toute E/S Docker**
(le socle ``require_role`` court-circuite la requête). Les tests 200
vérifient en plus que l'appel service a bien eu lieu.

Chaîne d'auth réelle : JWT ``create_access_token`` → ``get_current_user``
→ ``get_current_active_user`` → ``require_*`` (résolution rôle global via
``AuthorizationService``, DB de test via override ``get_db`` du conftest).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.enums.rbac import Role
from app.main import app
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService

# 35 opérations Docker attendues (spec 08, inventaire vérifié de la story)
EXPECTED_DOCKER_OPERATIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/api/v1/docker/containers"),
        ("POST", "/api/v1/docker/containers"),
        ("GET", "/api/v1/docker/containers/{container_id}"),
        ("POST", "/api/v1/docker/containers/batch/start"),
        ("POST", "/api/v1/docker/containers/batch/stop"),
        ("POST", "/api/v1/docker/containers/{container_id}/start"),
        ("POST", "/api/v1/docker/containers/{container_id}/stop"),
        ("POST", "/api/v1/docker/containers/{container_id}/restart"),
        ("POST", "/api/v1/docker/containers/{container_id}/pause"),
        ("POST", "/api/v1/docker/containers/{container_id}/unpause"),
        ("DELETE", "/api/v1/docker/containers/{container_id}"),
        ("POST", "/api/v1/docker/containers/{container_id}/recreate"),
        ("PATCH", "/api/v1/docker/containers/{container_id}/restart-policy"),
        ("PATCH", "/api/v1/docker/containers/{container_id}/resources"),
        ("POST", "/api/v1/docker/containers/{container_id}/rename"),
        ("POST", "/api/v1/docker/containers/{container_id}/networks/connect"),
        ("POST", "/api/v1/docker/containers/{container_id}/networks/disconnect"),
        ("POST", "/api/v1/docker/containers/{container_id}/promote"),
        ("GET", "/api/v1/docker/containers/{container_id}/shells"),
        ("GET", "/api/v1/docker/containers/{container_id}/stats"),
        ("GET", "/api/v1/docker/containers/{container_id}/top"),
        ("GET", "/api/v1/docker/containers/{container_id}/logs"),
        ("GET", "/api/v1/docker/images"),
        ("GET", "/api/v1/docker/images/{image_id}"),
        ("POST", "/api/v1/docker/images/pull"),
        ("DELETE", "/api/v1/docker/images/{image_id}"),
        ("POST", "/api/v1/docker/images/load"),
        ("GET", "/api/v1/docker/images/{image_id}/save"),
        ("GET", "/api/v1/docker/volumes"),
        ("POST", "/api/v1/docker/volumes"),
        ("DELETE", "/api/v1/docker/volumes/{volume_name}"),
        ("GET", "/api/v1/docker/networks"),
        ("GET", "/api/v1/docker/system/info"),
        ("GET", "/api/v1/docker/system/version"),
        ("GET", "/api/v1/docker/system/ping"),
    }
)


# --- Helpers --------------------------------------------------------------


async def _create_user_with_role(
    db_session: AsyncSession,
    username: str,
    role: Role,
    is_superuser: bool = False,
) -> User:
    """Crée un utilisateur + association du rôle donné (pattern 122.1)."""
    user = await UserService.create(
        db_session,
        UserCreate(
            email=f"{username}@example.com",
            username=username,
            full_name=username.title(),
            password="password123",
            is_superuser=is_superuser,
        ),
    )
    org = Organization(name=f"Org {username}", slug=f"org-{username}")
    db_session.add(org)
    await db_session.commit()
    db_session.add(UserOrganization(user_id=user.id, organization_id=org.id, role=role))
    await db_session.commit()
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False).

    Le ``.env`` local de développement peut porter ``DISABLE_AUTH=true``
    (auto-login superadmin) : sans ce patch, les tests 401/403 seraient
    court-circuités en local alors qu'ils passent en CI (pattern
    ``test_rbac_dependencies.py``).
    """
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    """Cache de rôles vierge autour de chaque test (pas de fuite entre rôles)."""
    reset_role_cache()
    yield
    reset_role_cache()


# --- Viewer : lectures OK, gestion 403 --------------------------------------


class TestViewerMatrix:
    """Viewer : 200 lectures / 403 gestion (échantillon par catégorie)."""

    async def test_viewer_403_delete_container(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """AC 2 littéral : DELETE /docker/containers/{id} avec viewer → 403."""
        user = await _create_user_with_role(db_session, "view-del", Role.VIEWER)
        response = await client.delete(
            "/api/v1/docker/containers/abc123", headers=_auth_headers(user)
        )
        assert response.status_code == 403
        assert response.json()["error"]["message"] == "Not enough permissions"

    async def test_viewer_403_create_container(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /docker/containers avec viewer → 403."""
        user = await _create_user_with_role(db_session, "view-create", Role.VIEWER)
        response = await client.post(
            "/api/v1/docker/containers",
            json={"name": "forbidden", "image": "nginx:latest"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403

    async def test_viewer_403_pull_image(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /docker/images/pull avec viewer → 403."""
        user = await _create_user_with_role(db_session, "view-pull", Role.VIEWER)
        response = await client.post(
            "/api/v1/docker/images/pull",
            json={"name": "nginx", "tag": "latest"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403

    async def test_viewer_403_delete_volume(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : DELETE /docker/volumes/{name} avec viewer → 403."""
        user = await _create_user_with_role(db_session, "view-vol", Role.VIEWER)
        response = await client.delete(
            "/api/v1/docker/volumes/mydata", headers=_auth_headers(user)
        )
        assert response.status_code == 403

    async def test_viewer_200_list_containers(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /docker/containers avec viewer → 200 (Docker mocké)."""
        from unittest.mock import AsyncMock, patch

        user = await _create_user_with_role(db_session, "view-list", Role.VIEWER)
        docker = AsyncMock()
        docker.list_containers.return_value = []
        docker.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            response = await client.get(
                "/api/v1/docker/containers", headers=_auth_headers(user)
            )

        assert response.status_code == 200
        assert unwrap(response) == []

    async def test_viewer_200_container_logs(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /docker/containers/{id}/logs avec viewer → 200."""
        from unittest.mock import AsyncMock, patch

        user = await _create_user_with_role(db_session, "view-logs", Role.VIEWER)

        async def _logs_stream(**_kwargs):
            yield "line1"

        docker = AsyncMock()
        docker.container_logs = _logs_stream
        docker.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            response = await client.get(
                "/api/v1/docker/containers/abc123/logs", headers=_auth_headers(user)
            )

        assert response.status_code == 200
        assert unwrap(response)["logs"] == "line1"

    async def test_viewer_200_system_ping(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /docker/system/ping avec viewer → 200."""
        from unittest.mock import AsyncMock, patch

        user = await _create_user_with_role(db_session, "view-ping", Role.VIEWER)
        docker = AsyncMock()
        docker.ping.return_value = True
        docker.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            response = await client.get(
                "/api/v1/docker/system/ping", headers=_auth_headers(user)
            )

        assert response.status_code == 200
        assert unwrap(response)["available"] is True


# --- Operator : opérationnel OK, gestion 403 ---------------------------------


class TestOperatorMatrix:
    """Operator : 200 actions opérationnelles / 403 gestion."""

    async def test_operator_200_start_stop_restart(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Opération : start (l. 408) + batch/start (l. 288) → 204/200."""
        from unittest.mock import AsyncMock, patch

        user = await _create_user_with_role(db_session, "op-start", Role.OPERATOR)
        headers = _auth_headers(user)
        docker = AsyncMock()
        docker.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            resp_start = await client.post(
                "/api/v1/docker/containers/abc123/start", headers=headers
            )
            resp_batch = await client.post(
                "/api/v1/docker/containers/batch/start",
                json={"container_ids": ["abc123"]},
                headers=headers,
            )

        assert resp_start.status_code == 204

        assert resp_batch.status_code == 200
        assert unwrap(resp_batch)["affected"] == 1
        # start direct + batch partagent le mock : 2 appels au total
        assert docker.start_container.await_count == 2
        docker.start_container.assert_any_await("abc123")

    async def test_operator_403_create_container(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /docker/containers avec operator → 403."""
        user = await _create_user_with_role(db_session, "op-create", Role.OPERATOR)
        response = await client.post(
            "/api/v1/docker/containers",
            json={"name": "forbidden", "image": "nginx:latest"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403

    async def test_operator_403_delete_container(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : DELETE /docker/containers/{id} avec operator → 403."""
        user = await _create_user_with_role(db_session, "op-del", Role.OPERATOR)
        response = await client.delete(
            "/api/v1/docker/containers/abc123", headers=_auth_headers(user)
        )
        assert response.status_code == 403

    async def test_operator_403_patch_resources(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : PATCH /docker/containers/{id}/resources → 403."""
        user = await _create_user_with_role(db_session, "op-res", Role.OPERATOR)
        response = await client.patch(
            "/api/v1/docker/containers/abc123/resources",
            json={"memory_limit": 536870912},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403


# --- Admin : gestion OK ------------------------------------------------------


class TestAdminMatrix:
    """Admin (association) : 200/204 sur les opérations de gestion."""

    async def test_admin_200_create_container(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /docker/containers avec admin → 201 (chemin HTTP réel).

        BUG-003 : plus de contournement (mini-app + mutation
        ``response_model = None``) — le contrat déclaré est désormais
        ``ContainerDetailResponse``, cohérent avec l'objet construit par
        le handler ; la validation de réponse FastAPI passe sur le chemin
        nominal. Chaîne d'auth réelle préservée (JWT → require_admin →
        AuthorizationService sur la session de test) ; réponse 201 lue via
        l'enveloppe spec 09 (``body["data"]``).
        """
        from unittest.mock import AsyncMock, MagicMock, patch

        user = await _create_user_with_role(db_session, "adm-create", Role.ADMIN)

        container = MagicMock()
        container.id = "abc123def456"
        container.name = "created"
        container.created = "2025-01-15T10:30:00Z"
        container.path = "/usr/local/bin"
        container.args = []
        container.state = {}
        container.image = "nginx:latest"
        container.config = {}
        container.host_config = {}
        container.network_settings = {}
        container.mounts = []

        docker = AsyncMock()
        docker.create_container.return_value = "abc123def456"
        docker.get_container.return_value = container
        docker.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            response = await client.post(
                "/api/v1/docker/containers",
                json={"name": "created", "image": "nginx:latest"},
                headers=_auth_headers(user),
            )

        assert response.status_code == 201, response.text
        # Enveloppe spec 09 : charge utile dans body["data"]
        assert response.json()["data"]["id"] == "abc123def456"
        docker.create_container.assert_awaited_once()

    async def test_admin_200_delete_container(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : DELETE /docker/containers/{id} avec admin → 204."""
        from unittest.mock import AsyncMock, patch

        user = await _create_user_with_role(db_session, "adm-del", Role.ADMIN)
        docker = AsyncMock()
        docker.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            response = await client.delete(
                "/api/v1/docker/containers/abc123", headers=_auth_headers(user)
            )

        assert response.status_code == 204
        docker.remove_container.assert_awaited_once_with("abc123", force=False)

    async def test_admin_200_delete_volume(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : DELETE /docker/volumes/{name} avec admin → 204."""
        from unittest.mock import AsyncMock, patch

        user = await _create_user_with_role(db_session, "adm-vol", Role.ADMIN)
        docker = AsyncMock()
        docker.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            response = await client.delete(
                "/api/v1/docker/volumes/mydata", headers=_auth_headers(user)
            )

        assert response.status_code == 204
        docker.remove_volume.assert_awaited_once_with("mydata", force=False)


# --- Superuser : bypass toutes catégories ------------------------------------


class TestSuperuserBypass:
    """Superuser (is_superuser) : super_admin → passe tout require_role."""

    async def test_superuser_passes_all_categories(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Bypass : 200 sur lecture, opération ET gestion (échantillon)."""
        from unittest.mock import AsyncMock, patch

        user = await _create_user_with_role(
            db_session, "super-all", Role.ADMIN, is_superuser=True
        )
        headers = _auth_headers(user)

        list_docker = AsyncMock()
        list_docker.list_containers.return_value = []
        list_docker.close = AsyncMock()
        op_docker = AsyncMock()
        op_docker.close = AsyncMock()
        adm_docker = AsyncMock()
        adm_docker.close = AsyncMock()

        with patch(
            "app.api.v1.docker.get_docker_client",
            side_effect=[list_docker, op_docker, adm_docker],
        ):
            read_resp = await client.get("/api/v1/docker/containers", headers=headers)
            op_resp = await client.post(
                "/api/v1/docker/containers/abc123/start", headers=headers
            )
            adm_resp = await client.delete(
                "/api/v1/docker/containers/abc123", headers=headers
            )

        assert (
            read_resp.status_code == 200
        ), f"lecture: {read_resp.status_code} — {read_resp.text}"
        assert (
            op_resp.status_code == 204
        ), f"opération: {op_resp.status_code} — {op_resp.text}"
        assert (
            adm_resp.status_code == 204
        ), f"gestion: {adm_resp.status_code} — {adm_resp.text}"


# --- Sécurité : 401 sans token ------------------------------------------------


class TestNoToken:
    """Sans Authorization : 401 avant toute vérification de rôle."""

    async def test_no_token_401_sample(self, client: AsyncClient):
        """401 sur un échantillon des 3 catégories (lecture/opération/gestion)."""
        read_resp = await client.get("/api/v1/docker/containers")
        op_resp = await client.post("/api/v1/docker/containers/abc123/start")
        adm_resp = await client.delete("/api/v1/docker/containers/abc123")

        assert read_resp.status_code == 401
        assert op_resp.status_code == 401
        assert adm_resp.status_code == 401


# --- Non-régression §2.G : aucune route supprimée ------------------------------


class TestDockerRouterIntegrity:
    """Garde-fou §2.G : 35 opérations Docker, paths et méthodes stables."""

    def test_docker_router_route_count_unchanged(self):
        """L'introspection OpenAPI compte exactement 35 opérations /docker/."""
        spec = app.openapi()
        operations = {
            (method.upper(), path)
            for path, ops in spec["paths"].items()
            if path.startswith("/api/v1/docker/")
            for method in ops
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }
        assert len(operations) == 35, (
            f"Attendu 35 opérations Docker, trouvé {len(operations)} — "
            "garde-fou §2.G : aucune suppression d'endpoint autorisée"
        )

    def test_no_endpoint_removed_paths_stable(self):
        """L'ensemble des opérations Docker correspond exactement à la
        matrice attendue (comparaison frozenset)."""
        spec = app.openapi()
        operations = {
            (method.upper(), path)
            for path, ops in spec["paths"].items()
            if path.startswith("/api/v1/docker/")
            for method in ops
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }
        assert operations == EXPECTED_DOCKER_OPERATIONS, (
            "Manquantes : "
            f"{sorted(EXPECTED_DOCKER_OPERATIONS - operations)} / "
            f"Inattendues : {sorted(operations - EXPECTED_DOCKER_OPERATIONS)}"
        )
