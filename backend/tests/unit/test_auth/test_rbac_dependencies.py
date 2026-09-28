"""Tests unitaires des dépendances RBAC ``require_role(...)`` (STORY-122.1).

Couverture (cf. story Tâche 5) :
- hiérarchie ×4 rôles : viewer passe ``require_role("viewer")`` mais 403 sur
  ``require_role("operator")`` ; operator 403 sur admin ; admin 403 sur
  super_admin ; superuser passe tout ;
- composition ``get_current_active_user`` : 401 sans token, 403 utilisateur
  inactif (avant toute vérification de rôle) ;
- ``disable_auth`` → auto-login superadmin passe ``require_super_admin`` ;
- message 403 identique à ``require_superuser`` (« Not enough permissions »).

Stratégie : mini-router de test monté à la volée sur l'app (une route par
niveau de rôle), consommé via le client HTTP async — la chaîne de
dépendances réelle (oauth2 → JWT → user actif → rôle global) est exercée
de bout en bout.
"""

import pytest
from fastapi import Depends
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.rbac import (
    require_admin,
    require_operator,
    require_role,
    require_super_admin,
    require_viewer,
)
from app.core.cache import reset_role_cache
from app.enums.rbac import Role
from app.main import app
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService
from tests.conftest import error_message

# Préfixe unique pour ne pas entrer en collision avec les routes réelles
_TEST_PREFIX = "/test-rbac-1221"


# --- Routes de test (montées au niveau module, une par niveau de rôle) ------


@app.get(f"{_TEST_PREFIX}/viewer")
async def _rbac_viewer(user: User = Depends(require_viewer)) -> dict:
    """Route protégée require_role("viewer")."""
    return {"user_id": user.id}


@app.get(f"{_TEST_PREFIX}/operator")
async def _rbac_operator(user: User = Depends(require_operator)) -> dict:
    """Route protégée require_role("operator")."""
    return {"user_id": user.id}


@app.get(f"{_TEST_PREFIX}/admin")
async def _rbac_admin(user: User = Depends(require_admin)) -> dict:
    """Route protégée require_role("admin")."""
    return {"user_id": user.id}


@app.get(f"{_TEST_PREFIX}/super-admin")
async def _rbac_super_admin(user: User = Depends(require_super_admin)) -> dict:
    """Route protégée require_role("super_admin")."""
    return {"user_id": user.id}


# --- Helpers ----------------------------------------------------------------


async def _create_user_with_role(
    db_session: AsyncSession,
    username: str,
    role: Role | None,
    is_superuser: bool = False,
) -> User:
    """Crée un utilisateur + appartenance optionnelle (rôle donné)."""
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
    if role is not None:
        org = Organization(name=f"Org {username}", slug=f"org-{username}")
        db_session.add(org)
        await db_session.commit()
        db_session.add(
            UserOrganization(user_id=user.id, organization_id=org.id, role=role)
        )
        await db_session.commit()
    return user


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token_for(user: User) -> str:
    return create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False).

    Le ``.env`` local de développement peut porter ``DISABLE_AUTH=true``
    (auto-login superadmin) : sans ce patch, les tests 401/403 hiérarchie
    seraient court-circuités en local alors qu'ils passent en CI (sans
    ``.env``). Le mode dev est couvert explicitement par
    ``TestRequireRoleDisableAuth``.
    """
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    """Cache de rôles vierge autour de chaque test."""
    reset_role_cache()
    yield
    reset_role_cache()


# --- Tests hiérarchie --------------------------------------------------------


class TestRequireRoleHierarchy:
    """Hiérarchie viewer < operator < admin < super_admin via HTTP."""

    async def test_viewer_passes_viewer_but_403_on_operator(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """viewer : 200 sur require_role("viewer"), 403 sur operator/admin/super."""
        user = await _create_user_with_role(db_session, "role-viewer", Role.VIEWER)
        headers = _auth_headers(_token_for(user))

        resp_v = await client.get(f"{_TEST_PREFIX}/viewer", headers=headers)
        assert resp_v.status_code == 200

        resp_o = await client.get(f"{_TEST_PREFIX}/operator", headers=headers)
        assert resp_o.status_code == 403
        assert error_message(resp_o) == "Not enough permissions"

        assert (
            await client.get(f"{_TEST_PREFIX}/admin", headers=headers)
        ).status_code == 403
        assert (
            await client.get(f"{_TEST_PREFIX}/super-admin", headers=headers)
        ).status_code == 403

    async def test_operator_403_on_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """operator : 200 sur operator, 403 sur admin (borne exacte)."""
        user = await _create_user_with_role(db_session, "role-operator", Role.OPERATOR)
        headers = _auth_headers(_token_for(user))

        assert (
            await client.get(f"{_TEST_PREFIX}/operator", headers=headers)
        ).status_code == 200
        assert (
            await client.get(f"{_TEST_PREFIX}/admin", headers=headers)
        ).status_code == 403

    async def test_admin_403_on_super_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """admin (association) : 200 sur admin, 403 sur super_admin — le rôle
        système n'est jamais atteignable via association."""
        user = await _create_user_with_role(db_session, "role-admin", Role.ADMIN)
        headers = _auth_headers(_token_for(user))

        assert (
            await client.get(f"{_TEST_PREFIX}/admin", headers=headers)
        ).status_code == 200
        assert (
            await client.get(f"{_TEST_PREFIX}/super-admin", headers=headers)
        ).status_code == 403

    async def test_superuser_passes_everything(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Superuser (is_superuser) : 200 sur les 4 niveaux."""
        user = await _create_user_with_role(
            db_session, "role-super", Role.ADMIN, is_superuser=True
        )
        headers = _auth_headers(_token_for(user))

        for path in ("viewer", "operator", "admin", "super-admin"):
            resp = await client.get(f"{_TEST_PREFIX}/{path}", headers=headers)
            assert resp.status_code == 200, f"{path}: {resp.status_code}"

    async def test_user_without_membership_is_viewer(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sans appartenance : rôle global conservateur viewer → 200 viewer, 403 operator."""
        user = await _create_user_with_role(db_session, "no-membership", None)
        headers = _auth_headers(_token_for(user))

        assert (
            await client.get(f"{_TEST_PREFIX}/viewer", headers=headers)
        ).status_code == 200
        assert (
            await client.get(f"{_TEST_PREFIX}/operator", headers=headers)
        ).status_code == 403


# --- Tests sécurité : 401 / 403 inactif --------------------------------------


class TestRequireRoleAuthChain:
    """Composition avec get_current_active_user (chaîne existante inchangée)."""

    async def test_401_without_token(self, client: AsyncClient):
        """Sécurité : sans Authorization → 401 avant toute vérification de rôle."""
        resp = await client.get(f"{_TEST_PREFIX}/viewer")
        assert resp.status_code == 401

    async def test_401_with_garbage_token(self, client: AsyncClient):
        """Sécurité : token invalide → 401."""
        resp = await client.get(
            f"{_TEST_PREFIX}/viewer", headers=_auth_headers("not.a.jwt")
        )
        assert resp.status_code == 401

    async def test_403_inactive_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Utilisateur inactif → 403 (« Inactive user ») avant la vérification de rôle."""
        user = await _create_user_with_role(db_session, "inactive-user", Role.ADMIN)
        user.is_active = False
        await db_session.commit()

        resp = await client.get(
            f"{_TEST_PREFIX}/viewer", headers=_auth_headers(_token_for(user))
        )
        assert resp.status_code == 403
        assert error_message(resp) == "Inactive user"


# --- Tests disable_auth -------------------------------------------------------


class TestRequireRoleDisableAuth:
    """Mode dev : superadmin auto-login passe tous les require_role."""

    async def test_disable_auth_superadmin_passes_super_admin(
        self, client: AsyncClient, test_superuser, monkeypatch
    ):
        """DISABLE_AUTH=true → auto-login superadmin → require_super_admin OK
        sans code dédié (l'utilisateur résolu est super_admin par construction)."""
        from app.auth import dependencies as auth_deps

        monkeypatch.setattr(auth_deps.settings, "disable_auth", True)
        resp = await client.get(f"{_TEST_PREFIX}/super-admin")
        assert resp.status_code == 200


# --- Tests de construction (paramètre code-only) ------------------------------


class TestRequireRoleConstruction:
    """Validation de minimum_role à la construction (erreur dev, pas HTTP)."""

    def test_unknown_role_raises_assertion_error(self):
        """Rôle inconnu → AssertionError (paramètre code-only)."""
        with pytest.raises(AssertionError, match="Unknown minimum role"):
            require_role("root")

    def test_aliases_are_callables(self):
        """Les 4 aliases prédéfinis existent et sont appelables."""
        for alias in (
            require_viewer,
            require_operator,
            require_admin,
            require_super_admin,
        ):
            assert callable(alias)
