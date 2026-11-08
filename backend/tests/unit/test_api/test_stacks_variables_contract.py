"""Tests du contrat ``GET /stacks/{id}`` — variables sérialisées (STORY-171).

AC 3 (backend) + AC 4 (rendu) : un stack créé via le chemin unifié
(``to_stack_create`` + ``StackService.create``) avec une variable ``integer``
bornée + un groupe + une macro password doit exposer à la lecture :
- ``minimum``/``maximum`` **servis** sur les variables numériques (AC 3) ;
- le groupe sérialisé **imbriqué** (sous-variables présentes) ;
- la macro **rendue** (``default`` != template, ``has_macro: true``,
  ``macro_template`` préservé) — comportement existant requis.

Sécurité obligatoire (rules 40) : 401 sans token, isolation organisation
(stack d'une autre organisation → 404).
"""

import pytest
from httpx import AsyncClient
from tests.conftest import unwrap

from app.auth.jwt import create_access_token
from app.models.organization import Organization
from app.models.stack import Stack
from app.schemas.stack import StackCreate
from app.services.stack_service import StackService


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4.

    Immunise le test contre un éventuel ``DISABLE_AUTH=true`` du ``.env``
    local (le fallback dev-mode exigerait un superadmin en base → 500)."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


def _auth_headers(user) -> dict[str, str]:
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


def _build_stack_create(organization_id: str) -> StackCreate:
    """StackCreate au format dump : integer bornée + groupe + macro password."""
    return StackCreate(
        name="Contract Stack 171",
        description="Stack de contrat variables",
        version="1.0.0",
        category="test",
        template={"image": "postgres:16"},
        organization_id=organization_id,
        target_type="docker",
        variables={
            "host_port": {
                "type": "integer",
                "label": "Port hôte",
                "default": 5432,
                "required": True,
                "visible": True,
                "minimum": 1,
                "maximum": 65535,
            },
            "admin_password": {
                "type": "password",
                "label": "Mot de passe admin",
                "default": "{{ generate_password(24) }}",
                "required": True,
                "visible": True,
                "has_macro": True,
                "macro_template": "{{ generate_password(24) }}",
            },
            "performance": {
                "type": "group",
                "label": "Performance",
                "visible": True,
                "variables": {
                    "max_connections": {
                        "type": "integer",
                        "label": "Connexions max",
                        "default": 100,
                        "required": False,
                        "visible": True,
                        "minimum": 10,
                        "maximum": 1000,
                    }
                },
            },
        },
    )


async def _create_contract_stack(db_session, organization_id: str) -> Stack:
    stack_create = _build_stack_create(organization_id)
    return await StackService.create(db_session, stack_create)


# --- Contrat AC 3 : bornes minimum/maximum servies ----------------------------


class TestVariablesContract:
    """AC 3 backend : ``minimum``/``maximum`` exposés sur GET /stacks/{id}."""

    async def test_get_stack_exposes_minimum_maximum(
        self, client: AsyncClient, db_session, test_user, test_organization
    ):
        """200 + variables numériques portant ``minimum``/``maximum`` (AC 3)."""
        stack = await _create_contract_stack(db_session, test_organization.id)

        response = await client.get(
            f"/api/v1/stacks/{stack.id}", headers=_auth_headers(test_user)
        )
        assert response.status_code == 200

        body = unwrap(response)
        variables = body["variables"]

        host_port = variables["host_port"]
        assert host_port["minimum"] == 1
        assert host_port["maximum"] == 65535
        assert host_port["type"] == "integer"

    async def test_group_serialized_nested(
        self, client: AsyncClient, db_session, test_user, test_organization
    ):
        """Groupe sérialisé imbriqué : sous-variables avec leurs bornes."""
        stack = await _create_contract_stack(db_session, test_organization.id)

        response = await client.get(
            f"/api/v1/stacks/{stack.id}", headers=_auth_headers(test_user)
        )
        assert response.status_code == 200

        body = unwrap(response)
        performance = body["variables"]["performance"]
        assert performance["type"] == "group"
        assert "variables" in performance

        max_conn = performance["variables"]["max_connections"]
        assert max_conn["minimum"] == 10
        assert max_conn["maximum"] == 1000

    async def test_macro_rendered_with_template_preserved(
        self, client: AsyncClient, db_session, test_user, test_organization
    ):
        """AC 4 : macro rendue à la volée — default != template + has_macro."""
        stack = await _create_contract_stack(db_session, test_organization.id)

        response = await client.get(
            f"/api/v1/stacks/{stack.id}", headers=_auth_headers(test_user)
        )
        assert response.status_code == 200

        body = unwrap(response)
        password = body["variables"]["admin_password"]

        # Macro rendue : valeur concrète, différente du template
        assert password["default"] != "{{ generate_password(24) }}"
        assert password["has_macro"] is True
        assert password["macro_template"] == "{{ generate_password(24) }}"

    async def test_target_type_from_unified_import(
        self, client: AsyncClient, db_session, test_user, test_organization
    ):
        """Parité n°6 : ``target_type`` du mapping complet persisté en DB."""
        stack = await _create_contract_stack(db_session, test_organization.id)
        assert stack.target_type == "docker"

        response = await client.get(
            f"/api/v1/stacks/{stack.id}", headers=_auth_headers(test_user)
        )
        assert response.status_code == 200


# --- Sécurité obligatoire (rules 40) ------------------------------------------


class TestStackSecurity:
    """401 sans token + isolation organisation (404 pour stack étrangère)."""

    async def test_get_stack_returns_401_without_token(
        self, client: AsyncClient, db_session, test_organization
    ):
        """Sécurité : GET /stacks/{id} sans token → 401."""
        stack = await _create_contract_stack(db_session, test_organization.id)

        response = await client.get(f"/api/v1/stacks/{stack.id}")
        assert response.status_code == 401

    async def test_get_stack_other_organization_forbidden(
        self, client: AsyncClient, db_session, test_user, test_organization
    ):
        """Isolation org : stack d'une AUTRE organisation → 403 (comportement
        existant conservé — l'accès est refusé, jamais 200)."""
        # Organisation étrangère + stack dedans
        other_org = Organization(name="Other Org", slug="other-org-171")
        db_session.add(other_org)
        await db_session.commit()
        other_stack = await _create_contract_stack(db_session, other_org.id)

        # test_user appartient à test_organization, pas à other_org
        response = await client.get(
            f"/api/v1/stacks/{other_stack.id}", headers=_auth_headers(test_user)
        )
        assert response.status_code == 403
        # Le corps de la réponse ne divulgue pas les variables du stack étranger
        assert "variables" not in response.text

    async def test_get_stack_not_found_404(
        self, client: AsyncClient, db_session, test_user
    ):
        """Cas d'erreur : ID inexistant → 404."""
        response = await client.get(
            "/api/v1/stacks/nonexistent-id", headers=_auth_headers(test_user)
        )
        assert response.status_code == 404
