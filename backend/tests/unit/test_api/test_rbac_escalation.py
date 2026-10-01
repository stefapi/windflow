"""Tests des protections anti-escalade de privilèges (STORY-122.4, AC 3).

Couverture AC 3 complète :
- **Dernier superadmin** : ni démotable (``is_superuser=False`` → 409), ni
  désactivable (``is_active=False`` → 409), ni supprimable (DELETE → 409) ;
  l'avant-dernier est démotable (200) dès qu'un second superadmin existe ;
- **Admin d'org** : ne peut pas promouvoir vers un rôle >= au sien
  (viewer→admin → 403), ni se promouvoir/rétrograder lui-même (403), ni
  modifier un autre admin (403) ; peut promouvoir viewer→operator (200) ;
- **Rôle système** : ``super_admin`` jamais attribuable via l'API membres
  (PUT/POST → 422 — enum sans super_admin) ;
- **Operator** : ne gère pas les membres du tout (403) ;
- **Invalidation cache** : après un changement de rôle par superuser,
  l'utilisateur ciblé voit ses droits modifiés immédiatement (lien AC 1).

Setup : org A avec admin-A, operator-A, viewer-A ; superadmin (unique).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService

# --- Helpers --------------------------------------------------------------


async def _create_org(db_session: AsyncSession, name: str) -> Organization:
    """Crée une organisation."""
    org = Organization(name=name, slug=name.lower().replace(" ", "-"))
    db_session.add(org)
    await db_session.commit()
    return org


async def _create_user_in_org(
    db_session: AsyncSession,
    username: str,
    org: Organization,
    role: Role,
    is_superuser: bool = False,
) -> User:
    """Crée un utilisateur rattaché à l'organisation avec le rôle donné."""
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
    db_session.add(UserOrganization(user_id=user.id, organization_id=org.id, role=role))
    await db_session.commit()
    return user


async def _create_plain_user(db_session: AsyncSession, username: str) -> User:
    """Crée un utilisateur sans appartenance (candidate aux ajouts)."""
    return await UserService.create(
        db_session,
        UserCreate(
            email=f"{username}@example.com",
            username=username,
            full_name=username.title(),
            password="password123",
        ),
    )


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 122.2."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    """Cache de rôles vierge autour de chaque test."""
    reset_role_cache()
    yield
    reset_role_cache()


@pytest.fixture
async def escalation_setup(db_session: AsyncSession):
    """Seed : org A (admin, operator, viewer) + superadmin unique."""
    org_a = await _create_org(db_session, "Org Escalation")

    admin_a = await _create_user_in_org(db_session, "esc-admin", org_a, Role.ADMIN)
    operator_a = await _create_user_in_org(
        db_session, "esc-operator", org_a, Role.OPERATOR
    )
    viewer_a = await _create_user_in_org(db_session, "esc-viewer", org_a, Role.VIEWER)
    superadmin = await UserService.create(
        db_session,
        UserCreate(
            email="esc-superadmin@example.com",
            username="esc-superadmin",
            full_name="Esc Superadmin",
            password="password123",
            is_superuser=True,
        ),
    )
    return {
        "org_a": org_a,
        "admin_a": admin_a,
        "operator_a": operator_a,
        "viewer_a": viewer_a,
        "superadmin": superadmin,
    }


# --- AC 3 : dernier superadmin indestructible -------------------------------


class TestLastSuperadminProtection:
    """Le dernier superadmin n'est ni démotable, ni désactivable, ni supprimable."""

    async def test_last_superadmin_cannot_be_demoted(
        self, client: AsyncClient, escalation_setup
    ):
        """PUT is_superuser=False sur l'unique superadmin → 409 explicite."""
        response = await client.put(
            f"/api/v1/users/{escalation_setup['superadmin'].id}",
            json={"is_superuser": False},
            headers=_auth_headers(escalation_setup["superadmin"]),
        )
        assert response.status_code == 409, response.text
        assert "last superadmin" in response.json()["error"]["message"].lower()

    async def test_last_superadmin_cannot_be_deactivated(
        self, client: AsyncClient, escalation_setup
    ):
        """PUT is_active=False sur l'unique superadmin → 409 explicite."""
        response = await client.put(
            f"/api/v1/users/{escalation_setup['superadmin'].id}",
            json={"is_active": False},
            headers=_auth_headers(escalation_setup["superadmin"]),
        )
        assert response.status_code == 409, response.text
        assert "last superadmin" in response.json()["error"]["message"].lower()

    async def test_last_superadmin_cannot_be_deleted(
        self, client: AsyncClient, db_session: AsyncSession, escalation_setup
    ):
        """DELETE du dernier superadmin → 409 « Cannot delete the last
        superadmin » et compte intact ; contrôle négatif : l'avant-dernier
        reste supprimable tant que count=2.

        Avec un acteur distinct impossible à monter (tout superadmin
        supplémentaire fait remonter count), la garde s'exerce sur le
        dernier lui-même : sa propre suppression reçoit le 409 de la
        garde count (AC 3).
        """
        db = escalation_setup
        second = await UserService.create(
            db_session,
            UserCreate(
                email="esc-second-super@example.com",
                username="esc-second-super",
                full_name="Esc Second Super",
                password="password123",
                is_superuser=True,
            ),
        )
        # Contrôle négatif : count=2 → le seed est supprimable par le second
        resp = await client.delete(
            f"/api/v1/users/{db['superadmin'].id}",
            headers=_auth_headers(second),
        )
        assert resp.status_code == 204, resp.text
        # count=1 : le dernier superadmin (second) n'est plus supprimable
        resp_self = await client.delete(
            f"/api/v1/users/{second.id}",
            headers=_auth_headers(second),
        )
        assert resp_self.status_code == 409, resp_self.text
        assert "last superadmin" in resp_self.json()["error"]["message"].lower()
        # Le compte du dernier superadmin est intact
        still = await UserService.get_by_id(db_session, second.id)
        assert still is not None
        assert still.is_superuser is True

    async def test_penultimate_superadmin_demotable(
        self, client: AsyncClient, db_session: AsyncSession, escalation_setup
    ):
        """Avec 2 superadmins, l'un est démotable (PUT is_superuser=False → 200)."""
        second = await UserService.create(
            db_session,
            UserCreate(
                email="esc-second-super2@example.com",
                username="esc-second-super2",
                full_name="Esc Second Super2",
                password="password123",
                is_superuser=True,
            ),
        )
        response = await client.put(
            f"/api/v1/users/{second.id}",
            json={"is_superuser": False},
            headers=_auth_headers(escalation_setup["superadmin"]),
        )
        assert response.status_code == 200, response.text


# --- AC 3 : admin d'org — anti-promotion ------------------------------------


class TestOrgAdminEscalationGuards:
    """Un admin d'org ne modifie pas un rôle >= au sien ni ne se promeut."""

    async def test_admin_cannot_promote_to_admin(
        self, client: AsyncClient, escalation_setup
    ):
        """Admin A : viewer→admin interdit (rôle cible >= sien) → 403."""
        db = escalation_setup
        response = await client.put(
            f"/api/v1/organizations/{db['org_a'].id}/users/{db['viewer_a'].id}",
            json={"role": "admin"},
            headers=_auth_headers(db["admin_a"]),
        )
        assert response.status_code == 403, response.text

    async def test_admin_cannot_promote_self(
        self, client: AsyncClient, escalation_setup
    ):
        """Admin A modifie son propre rôle → 403 (rôle actuel cible >=
        sien — l'auto-promotion/rétrogradation est couverte)."""
        db = escalation_setup
        response = await client.put(
            f"/api/v1/organizations/{db['org_a'].id}/users/{db['admin_a'].id}",
            json={"role": "operator"},
            headers=_auth_headers(db["admin_a"]),
        )
        assert response.status_code == 403, response.text

    async def test_admin_cannot_modify_equal_or_higher_role(
        self, client: AsyncClient, db_session: AsyncSession, escalation_setup
    ):
        """Admin A modifie un autre admin → 403 (rôle actuel cible >= sien)."""
        db = escalation_setup
        other_admin = await _create_user_in_org(
            db_session, "esc-admin-two", db["org_a"], Role.ADMIN
        )
        response = await client.put(
            f"/api/v1/organizations/{db['org_a'].id}/users/{other_admin.id}",
            json={"role": "viewer"},
            headers=_auth_headers(db["admin_a"]),
        )
        assert response.status_code == 403, response.text

    async def test_admin_can_promote_viewer_to_operator(
        self, client: AsyncClient, escalation_setup
    ):
        """Admin A : viewer→operator autorisé (rôle cible < sien) → 200."""
        db = escalation_setup
        response = await client.put(
            f"/api/v1/organizations/{db['org_a'].id}/users/{db['viewer_a'].id}",
            json={"role": "operator"},
            headers=_auth_headers(db["admin_a"]),
        )
        assert response.status_code == 200, response.text
        assert unwrap(response)["role"] == "operator"

    async def test_admin_cannot_add_member_with_equal_role(
        self, client: AsyncClient, db_session: AsyncSession, escalation_setup
    ):
        """Admin A ajoute un membre directement admin → 403 (rôle >= sien)."""
        db = escalation_setup
        candidate = await _create_plain_user(db_session, "esc-candidate")
        response = await client.post(
            f"/api/v1/organizations/{db['org_a'].id}/users",
            json={"user_id": str(candidate.id), "role": "admin"},
            headers=_auth_headers(db["admin_a"]),
        )
        assert response.status_code == 403, response.text

    async def test_admin_can_add_member_with_lower_role(
        self, client: AsyncClient, db_session: AsyncSession, escalation_setup
    ):
        """Admin A ajoute un membre operator → 201 (rôle < sien)."""
        db = escalation_setup
        candidate = await _create_plain_user(db_session, "esc-candidate-ok")
        response = await client.post(
            f"/api/v1/organizations/{db['org_a'].id}/users",
            json={"user_id": str(candidate.id), "role": "operator"},
            headers=_auth_headers(db["admin_a"]),
        )
        assert response.status_code == 201, response.text


# --- AC 3 : super_admin jamais attribuable via l'API membres ----------------


class TestSuperAdminRoleNotAssignable:
    """``super_admin`` est un rôle système (enum sans cette valeur) → 422."""

    async def test_put_role_super_admin_returns_422(
        self, client: AsyncClient, escalation_setup
    ):
        """PUT role=super_admin → 422 (enum Role borné viewer/operator/admin)."""
        db = escalation_setup
        response = await client.put(
            f"/api/v1/organizations/{db['org_a'].id}/users/{db['viewer_a'].id}",
            json={"role": "super_admin"},
            headers=_auth_headers(db["superadmin"]),
        )
        assert response.status_code == 422, response.text

    async def test_post_role_super_admin_returns_422(
        self, client: AsyncClient, db_session: AsyncSession, escalation_setup
    ):
        """POST role=super_admin → 422 (double barrière Pydantic + modèle)."""
        db = escalation_setup
        candidate = await _create_plain_user(db_session, "esc-candidate-422")
        response = await client.post(
            f"/api/v1/organizations/{db['org_a'].id}/users",
            json={"user_id": str(candidate.id), "role": "super_admin"},
            headers=_auth_headers(db["superadmin"]),
        )
        assert response.status_code == 422, response.text


# --- Operator : aucune gestion des membres ----------------------------------


class TestOperatorCannotManageMembers:
    """Operator (même membre) → 403 sur toutes les écritures membres."""

    async def test_operator_cannot_manage_members_at_all(
        self, client: AsyncClient, escalation_setup
    ):
        """PUT rôle par operator → 403 (require_admin en amont)."""
        db = escalation_setup
        response = await client.put(
            f"/api/v1/organizations/{db['org_a'].id}/users/{db['viewer_a'].id}",
            json={"role": "viewer"},
            headers=_auth_headers(db["operator_a"]),
        )
        assert response.status_code == 403


# --- AC 1 (lien) : invalidation du cache de rôle -----------------------------


class TestRoleChangeInvalidatesCache:
    """Après un PUT rôle par superuser, les droits changent immédiatement."""

    async def test_role_change_invalidation_cache_effective(
        self, client: AsyncClient, db_session: AsyncSession, escalation_setup
    ):
        """Viewer promu admin par superuser → peut écrire les membres
        immédiatement, sans attendre la TTL de 300 s (lien AC 1/122.1)."""
        db = escalation_setup
        org_id = db["org_a"].id

        # Avant : viewer ne peut pas écrire les membres (403 require_admin)
        before = await client.put(
            f"/api/v1/organizations/{org_id}/users/{db['viewer_a'].id}",
            json={"role": "operator"},
            headers=_auth_headers(db["viewer_a"]),
        )
        assert before.status_code == 403, before.text

        # Amorcer le cache du rôle global du viewer (403 l'a déjà fait
        # via require_admin → get_global_role) : la promotion par
        # superuser doit invalider cette entrée.
        promote = await client.put(
            f"/api/v1/organizations/{org_id}/users/{db['viewer_a'].id}",
            json={"role": "admin"},
            headers=_auth_headers(db["superadmin"]),
        )
        assert promote.status_code == 200, promote.text

        # Après : le promu (admin, cache invalidé) peut écrire — le
        # role_data est valide (operator < admin pour lui-même ? oui :
        # son propre rôle actuel est admin >= admin → garde escalade !
        # Il modifie donc un autre membre : operator_a → viewer (OK :
        # rôle actuel operator < admin, cible viewer < admin).
        after = await client.put(
            f"/api/v1/organizations/{org_id}/users/{db['operator_a'].id}",
            json={"role": "viewer"},
            headers=_auth_headers(db["viewer_a"]),
        )
        assert after.status_code == 200, after.text
        assert unwrap(after)["role"] == "viewer"
