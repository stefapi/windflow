"""Débogage ponctuel : reproduire le 500 du GET deployment en contexte pytest."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment, DeploymentStatus
from app.models.organization import Organization
from app.models.stack import Stack
from app.models.target import Target


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 122.2.

    Le fichier ``.env`` local (git-ignored) peut contenir ``DISABLE_AUTH=true``
    (valeur recommandée par ``env.example`` pour le dev). Sans ce forçage,
    ``get_current_user`` court-circuite le JWT pour chercher un superadmin
    en base → 500 ``INTERNAL_ERROR`` sur tous les endpoints authentifiés.
    """

    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.mark.asyncio
async def test_debug_get_deployment_500(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user,
    test_organization: Organization,
):
    stack = Stack(
        name="dbg-stack",
        template={"image": "nginx"},
        variables={},
        organization_id=test_organization.id,
        version="1.0.0",
    )
    target = Target(
        name="dbg-target",
        host="127.0.0.1",
        credentials={},
        organization_id=test_organization.id,
    )
    db_session.add_all([stack, target])
    await db_session.commit()

    deployment = Deployment(
        stack_id=stack.id,
        target_id=target.id,
        organization_id=test_organization.id,
        name="dbg-deployment",
        config={},
        variables={"db_password": "clear-secret"},
        status=DeploymentStatus.RUNNING,
    )
    db_session.add(deployment)
    await db_session.commit()
    await db_session.refresh(deployment)

    app = authenticated_client._transport.app  # noqa: SLF001
    # Rejouer la requête en propageant les exceptions applicatives
    from httpx import ASGITransport
    from httpx import AsyncClient as AC

    transport = ASGITransport(app=app, raise_app_exceptions=True)
    token = authenticated_client.headers.get("Authorization")
    headers = {"Authorization": token} if token else {}
    async with AC(transport=transport, base_url="http://test") as c:
        try:
            r = await c.get(f"/api/v1/deployments/{deployment.id}", headers=headers)
            print("STATUS:", r.status_code)
            print("BODY:", r.text[:800])
        except Exception:
            import traceback

            traceback.print_exc()
            raise
    assert r.status_code == 200
