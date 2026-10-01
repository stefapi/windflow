"""Tests d'intégration du contrat de pagination spec 09 — VAGUE 1 STORY-128.

Couvre les endpoints convertis par la vague 1 (socle + routers de
référence) :

- ``GET /api/v1/stacks/`` (requête unique multi-org, tri ``name``) ;
- ``GET /api/v1/organizations/`` (super_admin, tri ``name``) ;
- ``GET /api/v1/organizations/{id}/users`` (membres, tri ``joined_at``) ;
- ``GET /api/v1/stacks/{id}/versions`` (tri ``version_number desc``).

Contrat vérifié (AC 1 + AC 2, story) :
- 2xx : ``{data: [...], pagination: {page, per_page, total, pages}}``,
  ``len(data) <= per_page``, ``pages == ceil(total/per_page)`` ;
- PAS de double enveloppement (le corps paginé passe le middleware
  tel quel, ``message`` clé présente — null) ;
- liste vide → ``total: 0, pages: 0, data: []`` ;
- multi-pages sans doublon ni trou (tri stable) ;
- bornes : ``per_page=101`` → 422 ``VALIDATION_ERROR`` ; ``page=0`` → 422 ;
- page au-delà de la dernière → 200 ``data: []`` ;
- filtres existants combinables (``include_archived`` : ``total`` filtré) ;
- agrégation multi-org exacte (total = somme réelle des deux orgs).

Sécurité (rules 40 — obligatoire par endpoint) :
- 401 sans token ; 403 rôle insuffisant (organizations → non-superuser) ;
- isolation : members d'une org non membre → 403 ; versions d'un stack
  d'une autre org → 403.

Patterns : ``_jwt_mode``/``_bearer`` du ``test_api_envelope.py``
(le ``.env`` racine porte ``DISABLE_AUTH=true`` qui court-circuiterait
les 401 attendus).
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.models.organization import Organization
from app.models.stack import Stack
from app.models.user import User
from app.schemas.stack import StackCreate
from app.services.stack_service import StackService

STACKS_URL = "/api/v1/stacks/"
ORGS_URL = "/api/v1/organizations/"


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


def _bearer(user: User) -> dict:
    """Headers Authorization — mint direct (pattern test_api_keys)."""
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_stacks(
    db_session: AsyncSession, organization: Organization, count: int, prefix: str
) -> list[Stack]:
    """Crée ``count`` stacks nommés ``{prefix}-{i:02d}`` dans l'org."""
    stacks = []
    for i in range(count):
        data = StackCreate(
            name=f"{prefix}-{i:02d}",
            description=f"pagination test stack {prefix} {i}",
            template={"version": "3.8", "services": {"web": {"image": "nginx"}}},
            variables={},
            version="1.0.0",
            category="web",
            tags=[],
            is_public=False,
            organization_id=organization.id,
        )
        stacks.append(await StackService.create(db_session, data))
    return stacks


def _assert_pagination_contract(body: dict) -> dict:
    """Vérifie le contrat PaginatedResponse{data, pagination} + message.

    Le corps paginé ne doit PAS être ré-enveloppé : ``data`` reste la
    liste, ``pagination`` au même niveau, ``message`` complété à ``None``
    par le middleware (anti double-enveloppement STORY-128).
    """
    assert isinstance(body.get("data"), list), f"data doit être une liste : {body}"
    pagination = body.get("pagination")
    assert isinstance(pagination, dict), f"pagination manquant : {body}"
    for key in ("page", "per_page", "total", "pages"):
        assert key in pagination, f"pagination.{key} manquant : {pagination}"
    assert "message" in body, "message (null) doit être présent (middleware)"
    assert body["message"] is None
    assert len(body["data"]) <= pagination["per_page"]
    if pagination["total"] > 0:
        expected_pages = -(-pagination["total"] // pagination["per_page"])  # ceil
    else:
        expected_pages = 0
    assert (
        pagination["pages"] == expected_pages
    ), f"pages attendu {expected_pages}, obtenu {pagination['pages']}"
    return pagination


class TestStacksPagination:
    """GET /stacks/ — pagination canonique multi-org."""

    async def test_2xx_returns_pagination_envelope(
        self, client: AsyncClient, test_user: User
    ):
        """Contrat : {data, pagination{...}, message: null} — pas de double
        enveloppement (le corps paginé passe le middleware tel quel)."""
        response = await client.get(STACKS_URL, headers=_bearer(test_user))
        assert response.status_code == 200, response.text
        _assert_pagination_contract(response.json())

    async def test_empty_list_page_meta(self, client: AsyncClient, test_user: User):
        """Liste vide → total: 0, pages: 0, data: []."""
        response = await client.get(STACKS_URL, headers=_bearer(test_user))
        assert response.status_code == 200
        body = response.json()
        pagination = _assert_pagination_contract(body)
        assert pagination["total"] == 0
        assert pagination["pages"] == 0
        assert body["data"] == []

    async def test_multi_page_consistency(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """25 stacks, per_page=20 → page 1 (20) + page 2 (5), aucun
        doublon ni trou (tri stable ORDER BY name)."""
        await _seed_stacks(db_session, test_organization, 25, "multi")

        page1 = await client.get(
            STACKS_URL, params={"page": 1, "per_page": 20}, headers=_bearer(test_user)
        )
        assert page1.status_code == 200
        body1 = page1.json()
        p1 = _assert_pagination_contract(body1)
        assert p1["total"] == 25
        assert p1["pages"] == 2
        assert len(body1["data"]) == 20

        page2 = await client.get(
            STACKS_URL, params={"page": 2, "per_page": 20}, headers=_bearer(test_user)
        )
        assert page2.status_code == 200
        body2 = page2.json()
        assert len(body2["data"]) == 5

        ids1 = {s["id"] for s in body1["data"]}
        ids2 = {s["id"] for s in body2["data"]}
        assert not (ids1 & ids2), "doublon entre pages 1 et 2"
        assert len(ids1 | ids2) == 25, "trou entre pages 1 et 2"

    async def test_multi_org_total_exact(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """User membre de 2 orgs avec 10+15 stacks → total=25 exact
        (requête unique IN — cible l'ancien bug d'agrégation par-org)."""
        from app.models.user_organization import UserOrganization

        other_org = Organization(
            name="Pagination Second Org", slug="pagination-second-org"
        )
        db_session.add(other_org)
        await db_session.commit()
        await db_session.refresh(other_org)
        db_session.add(
            UserOrganization(
                user_id=test_user.id,
                organization_id=other_org.id,
                role="viewer",
            )
        )
        await db_session.commit()

        await _seed_stacks(db_session, test_organization, 10, "orga")
        await _seed_stacks(db_session, other_org, 15, "orgb")

        response = await client.get(
            STACKS_URL, params={"page": 1, "per_page": 20}, headers=_bearer(test_user)
        )
        assert response.status_code == 200
        pagination = _assert_pagination_contract(response.json())
        assert pagination["total"] == 25, "total multi-org doit être exact"
        assert pagination["pages"] == 2

    async def test_per_page_bounds_422(self, client: AsyncClient, test_user: User):
        """per_page=101 → 422 VALIDATION_ERROR (pas de clamp silencieux)."""
        response = await client.get(
            STACKS_URL, params={"per_page": 101}, headers=_bearer(test_user)
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_page_zero_422(self, client: AsyncClient, test_user: User):
        """page=0 → 422 (pagination 1-indexée)."""
        response = await client.get(
            STACKS_URL, params={"page": 0}, headers=_bearer(test_user)
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_beyond_last_page_returns_empty(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """page = pages+1 → 200 data: [] + métadonnées exactes."""
        await _seed_stacks(db_session, test_organization, 3, "beyond")

        response = await client.get(
            STACKS_URL, params={"page": 2, "per_page": 20}, headers=_bearer(test_user)
        )
        assert response.status_code == 200
        body = response.json()
        pagination = _assert_pagination_contract(body)
        assert body["data"] == []
        assert pagination["total"] == 3
        assert pagination["page"] == 2

    async def test_include_archived_filter_combinable(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """include_archived=true → total inclut les archivées (filtre AVANT
        pagination, total filtré exact — AC 3)."""
        stacks = await _seed_stacks(db_session, test_organization, 5, "arch")
        await StackService.archive(db_session, stacks[0].id)

        without = await client.get(STACKS_URL, headers=_bearer(test_user))
        assert without.status_code == 200
        pagination = _assert_pagination_contract(without.json())
        assert pagination["total"] == 4

        with_archived = await client.get(
            STACKS_URL, params={"include_archived": "true"}, headers=_bearer(test_user)
        )
        assert with_archived.status_code == 200
        pagination_all = _assert_pagination_contract(with_archived.json())
        assert pagination_all["total"] == 5

    async def test_returns_401_without_token(self, client: AsyncClient):
        """Sécurité (rules 40) : 401 sans token."""
        response = await client.get(STACKS_URL)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_OR_EXPIRED_TOKEN"


class TestOrganizationsPagination:
    """GET /organizations/ — super_admin uniquement, tri name."""

    async def test_superuser_gets_pagination_envelope(
        self,
        client: AsyncClient,
        test_superuser: User,
        test_organization: Organization,
    ):
        """Contrat paginé pour la liste globale (superuser)."""
        response = await client.get(ORGS_URL, headers=_bearer(test_superuser))
        assert response.status_code == 200, response.text
        pagination = _assert_pagination_contract(response.json())
        assert pagination["total"] >= 1

    async def test_returns_401_without_token(self, client: AsyncClient):
        """Sécurité : 401 sans token."""
        response = await client.get(ORGS_URL)
        assert response.status_code == 401

    async def test_returns_403_for_insufficient_role(
        self, client: AsyncClient, viewer_user: User
    ):
        """Sécurité RBAC : viewer → 403 PERMISSION_DENIED (RBAC inchangé)."""
        response = await client.get(ORGS_URL, headers=_bearer(viewer_user))
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    async def test_per_page_bounds_422(self, client: AsyncClient, test_superuser: User):
        """per_page=101 → 422 (bornes cohérentes sur tous les endpoints)."""
        response = await client.get(
            ORGS_URL, params={"per_page": 101}, headers=_bearer(test_superuser)
        )
        assert response.status_code == 422

    async def test_sorted_by_name_stable(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization: Organization,
    ):
        """Tri stable ORDER BY name — pages ordonnées sans chevauchement."""
        for i in range(3):
            db_session.add(Organization(name=f"Sort Org {i}", slug=f"sort-org-{i}"))
        await db_session.commit()

        response = await client.get(
            ORGS_URL, params={"per_page": 3}, headers=_bearer(test_superuser)
        )
        assert response.status_code == 200
        body = response.json()
        names = [o["name"] for o in body["data"]]
        assert names == sorted(names), "la page doit être triée par nom"

        page2 = await client.get(
            ORGS_URL, params={"per_page": 3, "page": 2}, headers=_bearer(test_superuser)
        )
        assert page2.status_code == 200
        names2 = [o["name"] for o in page2.json()["data"]]
        assert not (set(names) & set(names2)), "chevauchement entre pages"


class TestOrganizationMembersPagination:
    """GET /organizations/{id}/users — isolation conservée."""

    async def test_members_pagination_envelope(
        self,
        client: AsyncClient,
        test_user: User,
        test_organization: Organization,
    ):
        """Membre de l'org → contrat paginé (data + pagination + message)."""
        response = await client.get(
            f"{ORGS_URL}{test_organization.id}/users", headers=_bearer(test_user)
        )
        assert response.status_code == 200, response.text
        _assert_pagination_contract(response.json())

    async def test_returns_403_for_foreign_resource(
        self,
        client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Isolation : non-membre → 403 (conservé par la pagination)."""
        foreign = Organization(name="Foreign Org", slug="foreign-org-pg")
        db_session.add(foreign)
        await db_session.commit()
        await db_session.refresh(foreign)

        response = await client.get(
            f"{ORGS_URL}{foreign.id}/users", headers=_bearer(test_user)
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    async def test_returns_401_without_token(
        self, client: AsyncClient, test_organization: Organization
    ):
        """Sécurité : 401 sans token."""
        response = await client.get(f"{ORGS_URL}{test_organization.id}/users")
        assert response.status_code == 401


class TestStackVersionsPagination:
    """GET /stacks/{id}/versions — isolation par appartenance org."""

    async def test_versions_pagination_envelope(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Membre de l'org du stack → contrat paginé."""
        stack = (await _seed_stacks(db_session, test_organization, 1, "vers"))[0]

        response = await client.get(
            f"{STACKS_URL}{stack.id}/versions", headers=_bearer(test_user)
        )
        assert response.status_code == 200, response.text
        pagination = _assert_pagination_contract(response.json())
        assert pagination["total"] == 0  # aucune version créée

    async def test_versions_multi_page_desc_order(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """3 versions, per_page=2 → page 1 = versions 3,2 (desc)."""
        from app.models.stack_version import StackVersion

        stack = (await _seed_stacks(db_session, test_organization, 1, "vpage"))[0]
        for n in (1, 2, 3):
            db_session.add(
                StackVersion(
                    stack_id=stack.id,
                    version_number=n,
                    compose_content="services: {}",
                    variables={},
                    change_summary=f"v{n}",
                    created_by=test_user.id,
                )
            )
        await db_session.commit()

        response = await client.get(
            f"{STACKS_URL}{stack.id}/versions",
            params={"page": 1, "per_page": 2},
            headers=_bearer(test_user),
        )
        assert response.status_code == 200
        body = response.json()
        pagination = _assert_pagination_contract(body)
        assert pagination["total"] == 3
        assert pagination["pages"] == 2
        numbers = [v["version_number"] for v in body["data"]]
        assert numbers == [3, 2], "tri version_number desc conservé"

    async def test_versions_isolated_per_organization(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Isolation : stack d'une autre org → 403."""
        foreign_org = Organization(name="Foreign V Org", slug="foreign-v-org")
        db_session.add(foreign_org)
        await db_session.commit()
        await db_session.refresh(foreign_org)
        stack = (await _seed_stacks(db_session, foreign_org, 1, "iso"))[0]

        response = await client.get(
            f"{STACKS_URL}{stack.id}/versions", headers=_bearer(test_user)
        )
        assert response.status_code == 403

    async def test_versions_404_unknown_stack(
        self, client: AsyncClient, test_user: User
    ):
        """404 : stack inexistant."""
        response = await client.get(
            f"{STACKS_URL}00000000-0000-0000-0000-000000000099/versions",
            headers=_bearer(test_user),
        )
        assert response.status_code == 404
