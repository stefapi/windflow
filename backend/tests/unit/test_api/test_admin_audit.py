"""Tests de l'endpoint `GET /api/v1/admin/audit` (STORY-125.3).

Couvre l'AC 3 — consultation paginée filtrée du journal d'audit,
strictement réservée au rôle global ``super_admin`` (spec 08 :
administration système = Super Admin) :

- **200 paginé** (STORY-128 : contrat ``{data, pagination}`` via
  ``?page=&per_page=``), ordre ``created_at`` décroissant ;
- **401** sans token ; **403** pour viewer/operator **et admin
  d'organisation** (admin d'org ≠ super_admin — le journal couvre toutes
  les organisations) ;
- **422** : ``since`` non-ISO, ``limit=0``/``101``, ``action`` > 50
  caractères (filtres bornés anti-abus) ;
- **filtres** ``user_id`` / ``action`` / ``since`` : sous-ensembles
  exacts attendus ;
- **page vide** : 200 avec ``items: []`` et ``total: 0``.

La rétention configurable (AC 4) est validée côté service dans
``test_audit_service.py`` (``TestConfigurableRetention`` — application
périodique via monkeypatch settings, sans dupliquer les tests
``test_purge_expired_*`` posés par STORY-125.1).

Sécurité (rules 40) : fixture ``_jwt_mode`` (pattern 123.4) — le ``.env``
racine porte ``DISABLE_AUTH=true`` qui court-circuiterait
``get_current_user`` ; ``reset_role_cache`` autouse (rôles variés).
"""

from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.models.audit_log import AuditLog
from app.models.user import User

ADMIN_AUDIT_URL = "/api/v1/admin/audit"


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.fixture(autouse=True)
def _clean_role_cache():
    """Cache de rôles vierge autour de chaque test (TTL 300 s — sinon
    fuite entre tests de rôles différents, pattern test_api_keys)."""
    reset_role_cache()
    yield
    reset_role_cache()


async def _auth_headers(user: User) -> dict:
    """Headers Authorization Bearer JWT (mint direct, pattern 123.4)."""
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_entries(
    db_session: AsyncSession, test_user: User
) -> AsyncGenerator[None, None]:
    """Trois lignes datées : ancienne / récente / très récente (user A)
    + une ligne d'un autre acteur (acteur système, ``user_id=None``)."""
    now = datetime.now(timezone.utc)
    rows = [
        AuditLog(
            user_id=test_user.id,
            action="stack.deleted",
            resource_type="stack",
            resource_id="stk-old",
            created_at=now - timedelta(days=2),
        ),
        AuditLog(
            user_id=test_user.id,
            action="user.login",
            resource_type="user",
            resource_id=str(test_user.id),
            created_at=now - timedelta(days=1),
        ),
        AuditLog(
            user_id=test_user.id,
            action="user.login",
            resource_type="user",
            resource_id=str(test_user.id),
            created_at=now,
        ),
        AuditLog(
            user_id=None,  # acteur système (deployment.failed)
            action="deployment.failed",
            resource_type="deployment",
            resource_id="dep-1",
            created_at=now,
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()


class TestListAuditEntriesAccess:
    """RBAC : super_admin seul ; 401 sans token ; 403 autres rôles."""

    async def test_list_audit_superuser_200_paginated(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_user: User,
    ):
        """super_admin → 200, contrat paginé STORY-128 ``{data, pagination}``
        respecté, ordre ``created_at`` décroissant (plus récent d'abord)."""
        await _seed_entries(db_session, test_user)

        response = await client.get(
            ADMIN_AUDIT_URL, headers=await _auth_headers(test_superuser)
        )
        assert response.status_code == 200, response.text
        # Le corps paginé passe le middleware tel quel (anti double-enveloppe)
        body = response.json()
        assert isinstance(body["data"], list)
        pagination = body["pagination"]
        assert set(pagination) == {"page", "per_page", "total", "pages"}
        assert pagination["page"] == 1
        assert pagination["per_page"] == 20
        assert pagination["total"] == 4
        assert pagination["pages"] == 1
        assert len(body["data"]) == 4
        # Ordre décroissant : les deux lignes « now » avant « -1j »
        actions = [item["action"] for item in body["data"]]
        assert actions.index("user.login") < actions.index("stack.deleted")

    async def test_list_audit_returns_401_without_token(self, client: AsyncClient):
        """Pas de header Authorization → 401 (aucune fuite du journal)."""
        response = await client.get(ADMIN_AUDIT_URL)
        assert response.status_code == 401, response.text

    async def test_list_audit_returns_403_for_org_admin(
        self, client: AsyncClient, org_admin_user: User
    ):
        """Admin d'organisation ≠ super_admin : le journal est global
        (toutes organisations) → 403 (spec 08 § Système)."""
        response = await client.get(
            ADMIN_AUDIT_URL, headers=await _auth_headers(org_admin_user)
        )
        assert response.status_code == 403, response.text

    async def test_list_audit_returns_403_for_viewer(
        self, client: AsyncClient, viewer_user: User
    ):
        """Viewer → 403 (lecture réservée super_admin)."""
        response = await client.get(
            ADMIN_AUDIT_URL, headers=await _auth_headers(viewer_user)
        )
        assert response.status_code == 403, response.text

    async def test_list_audit_returns_403_for_operator(
        self, client: AsyncClient, operator_user: User
    ):
        """Operator → 403 (lecture réservée super_admin)."""
        response = await client.get(
            ADMIN_AUDIT_URL, headers=await _auth_headers(operator_user)
        )
        assert response.status_code == 403, response.text


class TestListAuditEntriesValidation:
    """422 : filtres bornés et valeurs invalides (anti-abus)."""

    async def test_list_audit_invalid_query_422(
        self, client: AsyncClient, test_superuser: User
    ):
        """``since`` non-ISO, ``per_page=0``/``101``, ``action`` > 50,
        ``page=0`` → 422 (validation Pydantic native des Query — STORY-128)."""
        headers = await _auth_headers(test_superuser)
        invalid_queries = [
            {"since": "not-a-date"},
            {"per_page": "0"},
            {"per_page": "101"},
            {"action": "x" * 51},
            {"user_id": "x" * 37},
            {"resource_type": "x" * 31},
            {"page": "0"},
        ]
        for params in invalid_queries:
            response = await client.get(ADMIN_AUDIT_URL, params=params, headers=headers)
            assert response.status_code == 422, (params, response.text)

    async def test_list_audit_empty_returns_empty_page(
        self, client: AsyncClient, test_superuser: User
    ):
        """Aucune ligne en base → 200 avec ``data: []`` et ``total: 0``."""
        response = await client.get(
            ADMIN_AUDIT_URL, headers=await _auth_headers(test_superuser)
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["data"] == []
        assert body["pagination"]["total"] == 0
        assert body["pagination"]["pages"] == 0


class TestListAuditEntriesFiltersAndPagination:
    """Filtres exacts et pagination page/per_page (STORY-128)."""

    async def test_list_audit_filters(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_user: User,
    ):
        """Filtres ``user_id``, ``action`` et ``since`` retournent le
        sous-ensemble attendu (combinaison exacte, filtrage avant pagination)."""
        await _seed_entries(db_session, test_user)
        headers = await _auth_headers(test_superuser)

        # user_id : les 3 lignes de test_user (pas l'acteur système)
        by_user = await client.get(
            ADMIN_AUDIT_URL, params={"user_id": test_user.id}, headers=headers
        )
        assert by_user.status_code == 200, by_user.text
        user_body = by_user.json()
        assert user_body["pagination"]["total"] == 3
        assert all(item["user_id"] == test_user.id for item in user_body["data"])

        # action : 2 user.login
        by_action = await client.get(
            ADMIN_AUDIT_URL, params={"action": "user.login"}, headers=headers
        )
        assert by_action.json()["pagination"]["total"] == 2

        # since (-36h) : les lignes de moins de 36h (2 user.login récents
        # + 1 deployment.failed « now ») — stack.deleted (-2j) exclue
        since = (datetime.now(timezone.utc) - timedelta(hours=36)).isoformat()
        by_since = await client.get(
            ADMIN_AUDIT_URL, params={"since": since}, headers=headers
        )
        assert by_since.status_code == 200, by_since.text
        since_body = by_since.json()
        assert since_body["pagination"]["total"] == 3
        actions_since = {item["action"] for item in since_body["data"]}
        assert actions_since == {"user.login", "deployment.failed"}

    async def test_list_audit_pagination_page_per_page(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_user: User,
    ):
        """``page``/``per_page`` bornés : page 1 de 2 puis reste — ``total``
        reste le total filtré, pas celui de la page (STORY-128)."""
        await _seed_entries(db_session, test_user)
        headers = await _auth_headers(test_superuser)

        page1 = await client.get(
            ADMIN_AUDIT_URL, params={"page": 1, "per_page": 2}, headers=headers
        )
        assert page1.status_code == 200, page1.text
        body1 = page1.json()
        assert body1["pagination"]["total"] == 4  # total filtré inchangé
        assert len(body1["data"]) == 2
        assert body1["pagination"]["page"] == 1
        assert body1["pagination"]["per_page"] == 2
        assert body1["pagination"]["pages"] == 2

        rest = await client.get(
            ADMIN_AUDIT_URL, params={"page": 2, "per_page": 2}, headers=headers
        )
        body2 = rest.json()
        assert len(body2["data"]) == 2
        assert body2["pagination"]["page"] == 2

        # Aucun chevauchement entre les pages
        ids1 = {item["id"] for item in body1["data"]}
        ids2 = {item["id"] for item in body2["data"]}
        assert not ids1 & ids2
        assert len(ids1 | ids2) == 4
