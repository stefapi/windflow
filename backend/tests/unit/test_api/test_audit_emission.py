"""Tests d'émission de l'audit trail sur les actions critiques (STORY-125.2).

Démontre le branchement bout-en-bout des points d'émission posés par les
Tâches 1-4 : chaque action critique du catalogue (spec 15 § Audit trail)
écrit une ligne ``audit_logs`` via ``AuditService.log_from_request`` avec
acteur, org, action, cible, IP et **correlation_id du middleware** (header
``X-Correlation-ID`` → ``request.state`` → DB, rules 45).

Contenu :

- **Test de référence P1-4** : DELETE d'une stack → ligne ``stack.deleted``
  avec user, org de la stack, action, cible et correlation_id strictement
  égal au header envoyé (critère de done de l'epic EPIC-012) ;
- émission auth (login réussi/échoué, logout, clés API) et suppressions
  (target, organization, conteneur), rôles/membres, déploiements
  (création + transitions terminales acteur système), conteneurs/plugins ;
- **résilience** : échec d'écriture injecté → l'action métier répond quand
  même (AC 4, part démonstration) ;
- **sécurité AC 5** : aucun secret (password, clé ``wf_ak_`` brute) dans
  ``details`` des lignes ni dans les logs (caplog, ``sqlalchemy.engine``
  neutralisé en WARNING — piège documenté 124.4).

Infrastructure : les endpoints n'étant pas maître de la session d'audit
(``log_from_request`` sans ``db`` ouvre une session courte via
``AsyncSessionLocal``), la fixture autouse ``_audit_db`` redirige cette
factory vers la base de test du test courant — sans elle,
``AsyncSessionLocal`` lèverait ``RuntimeError`` (``db.connect()`` n'est
jamais appelé hors lifespan) et, par best-effort, **aucune ligne ne
serait écrite** (les tests échoueraient sur ``scalar_one``).

Sécurité (rules 40) : fixture ``_jwt_mode`` (pattern 123.4) — le ``.env``
racine porte ``DISABLE_AUTH=true`` qui court-circuiterait
``get_current_user``.
"""

import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.conftest import unwrap

from app.models.audit_log import AuditLog
from app.models.deployment import Deployment
from app.models.stack import Stack
from app.models.stack_version import StackVersion
from app.models.user import User

USER_PASSWORD = "testpassword123"

STACKS_URL = "/api/v1/stacks"
API_KEYS_URL = "/api/v1/auth/api-keys"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4.

    Le ``.env`` racine du dépôt porte ``DISABLE_AUTH=true`` : sans cette
    garde, ``get_current_user`` auto-login le premier superadmin et ignore
    tout header — les 401/403 attendus seraient des 200/500 incohérents.
    """
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.fixture(autouse=True)
async def _audit_db(monkeypatch, test_session_factory: async_sessionmaker) -> None:
    """Redirige les sessions courtes d'audit vers la base de test.

    ``AuditService.log`` sans ``db`` ouvre ``AsyncSessionLocal()`` —
    la factory globale ``app.database.db`` qui, hors lifespan de
    l'application, n'est **jamais initialisée`` (RuntimeError). Le point
    étant justement de tester l'émission « session courte » telle qu'elle
    tourne en production, on redirige la factory vers celle du test :
    même fichier SQLite (``test.db`` copié du template migré), les lignes
    d'audit sont donc visibles depuis ``db_session``.
    """
    import app.services.audit_service as audit_service_module

    monkeypatch.setattr(audit_service_module, "AsyncSessionLocal", test_session_factory)


async def _auth_headers(user: User) -> dict:
    """Headers Authorization Bearer JWT pour un utilisateur (mint direct,
    pattern test_api_keys — évite le quota rate limiting du login)."""
    from app.auth.jwt import create_access_token

    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


async def _audit_lines(db_session: AsyncSession, action: str) -> list[AuditLog]:
    """Lignes d'audit d'une action, ordre d'insertion (created_at ASC)."""
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.created_at)
    )
    return list(result.scalars().all())


async def _seed_stack_version(db_session: AsyncSession, stack: Stack) -> StackVersion:
    """Version v1 jouable pour la stack (prérequis du restore)."""
    version = StackVersion(
        stack_id=stack.id,
        version_number=1,
        compose_content="services:\n  web:\n    image: nginx:latest\n",
        variables={},
        change_summary="seed",
        created_by="seed",
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)
    return version


# ---------------------------------------------------------------------------
# Test de référence P1-4 — DELETE stack
# ---------------------------------------------------------------------------


class TestReferenceDeleteStack:
    """Critère de done P1-4 de l'epic : DELETE stack → ligne complète."""

    async def test_delete_stack_writes_audit_line(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_stack: Stack,
        test_organization,
    ):
        """DELETE /stacks/{id} → 204 + ligne ``stack.deleted`` avec acteur,
        org de la stack, action, cible et correlation_id **strictement égal**
        au header ``X-Correlation-ID`` envoyé (assertion middleware → DB).

        DELETE stack requiert admin d'org minimum (spec 08) — un admin
        d'organisation dédié porte l'action ; c'est lui l'acteur attendu
        dans la ligne d'audit."""
        from app.enums.rbac import Role
        from app.models.user_organization import UserOrganization
        from app.schemas.user import UserCreate
        from app.services.user_service import UserService

        admin = await UserService.create(
            db_session,
            UserCreate(
                email=f"stackadmin-{uuid.uuid4().hex[:8]}@example.com",
                username=f"stackadmin{uuid.uuid4().hex[:8]}",
                full_name="Stack Admin",
                password="adminpassword123",
                is_superuser=False,
            ),
        )
        db_session.add(
            UserOrganization(
                user_id=admin.id,
                organization_id=test_organization.id,
                role=Role.ADMIN,
            )
        )
        await db_session.commit()

        correlation_id = "corr-p14-reference-0001"
        response = await client.delete(
            f"{STACKS_URL}/{test_stack.id}",
            headers={
                **(await _auth_headers(admin)),
                "X-Correlation-ID": correlation_id,
            },
        )
        assert response.status_code == 204, response.text

        lines = await _audit_lines(db_session, "stack.deleted")
        assert len(lines) == 1, "une seule ligne stack.deleted attendue"
        line = lines[0]
        # Acteur = admin ayant porté le DELETE
        assert line.user_id == admin.id
        # Org de la ressource supprimée (org de la stack, pas celle de
        # l'acteur a priori — ici identiques, mais sémantique « ressource »)
        assert line.organization_id == test_stack.organization_id
        assert line.action == "stack.deleted"
        assert line.resource_type == "stack"
        assert line.resource_id == str(test_stack.id)
        # Assertion stricte P1-4 : correlation_id du header → middleware → DB
        assert line.correlation_id == correlation_id
        assert line.created_at is not None
        assert line.ip_address is not None


# ---------------------------------------------------------------------------
# Auth + clés API (Tâche 1)
# ---------------------------------------------------------------------------


class TestAuthAudit:
    """user.login / user.login_failed / user.logout / api_key.*."""

    async def test_login_success_and_failure_audited(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Login OK → ``user.login`` (ip renseignée) ; mauvais password →
        ``user.login_failed`` avec reason ; user inconnu → ``user_id=None``."""
        ok = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": USER_PASSWORD},
        )
        assert ok.status_code == 200, ok.text

        bad = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "wrong-password"},
        )
        assert bad.status_code == 401, bad.text

        unknown = await client.post(
            "/api/v1/auth/login",
            data={"username": "ghost-user", "password": "whatever"},
        )
        assert unknown.status_code == 401, unknown.text

        logins = await _audit_lines(db_session, "user.login")
        assert len(logins) == 1
        assert logins[0].user_id == test_user.id
        assert logins[0].ip_address is not None
        assert logins[0].resource_id == str(test_user.id)

        failures = await _audit_lines(db_session, "user.login_failed")
        assert len(failures) == 2
        reasons = {line.details.get("reason") for line in failures}
        assert reasons == {"invalid_credentials"}
        # user connu : acteur résolu ; user inconnu : user_id=None
        by_user = {line.user_id for line in failures}
        assert by_user == {test_user.id, None}

    async def test_logout_audited(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """POST /auth/logout → ``user.logout`` avec acteur."""
        response = await client.post(
            "/api/v1/auth/logout", headers=await _auth_headers(test_user)
        )
        assert response.status_code == 200, response.text

        lines = await _audit_lines(db_session, "user.logout")
        assert len(lines) == 1
        assert lines[0].user_id == test_user.id
        assert lines[0].resource_id == str(test_user.id)

    async def test_api_key_created_and_revoked_audited(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """POST/DELETE /auth/api-keys → ``api_key.created`` puis
        ``api_key.revoked`` avec resource_id = key_id (STORY-124 non
        régressé)."""
        headers = await _auth_headers(test_user)

        created = await client.post(
            API_KEYS_URL, json={"name": "audit-emission-key"}, headers=headers
        )
        assert created.status_code == 201, created.text
        key_id = unwrap(created)["id"]

        revoked = await client.delete(f"{API_KEYS_URL}/{key_id}", headers=headers)
        assert revoked.status_code == 200, revoked.text

        created_lines = await _audit_lines(db_session, "api_key.created")
        assert len(created_lines) == 1
        assert created_lines[0].resource_id == key_id
        assert created_lines[0].user_id == test_user.id

        revoked_lines = await _audit_lines(db_session, "api_key.revoked")
        assert len(revoked_lines) == 1
        assert revoked_lines[0].resource_id == key_id


# ---------------------------------------------------------------------------
# Suppressions + rôles/membres (Tâche 2)
# ---------------------------------------------------------------------------


class TestDeletionsAudit:
    """host.removed / organization.deleted / container.deleted."""

    async def test_target_and_organization_deletion_audited(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_target,
        test_organization,
    ):
        """DELETE host → ``host.removed`` (org du host — STORY-166.2, action
        alignée sur la nomenclature canonique) ; DELETE
                organization (superuser) → ``organization.deleted``."""
        headers = await _auth_headers(test_superuser)

        target_response = await client.delete(
            f"/api/v1/hosts/{test_target.id}", headers=headers
        )
        assert target_response.status_code == 204, target_response.text

        target_lines = await _audit_lines(db_session, "host.removed")
        assert len(target_lines) == 1
        assert target_lines[0].organization_id == test_target.organization_id
        assert target_lines[0].resource_id == str(test_target.id)
        assert target_lines[0].user_id == test_superuser.id

        org_response = await client.delete(
            f"/api/v1/organizations/{test_organization.id}", headers=headers
        )
        assert org_response.status_code == 204, org_response.text

        org_lines = await _audit_lines(db_session, "organization.deleted")
        assert len(org_lines) == 1
        assert org_lines[0].resource_id == str(test_organization.id)
        assert org_lines[0].user_id == test_superuser.id

    async def test_container_started_stopped_deleted_audited(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
    ):
        """start/stop/delete conteneur → ``container.started`` /
        ``container.stopped`` / ``container.deleted`` (endpoint global —
        ``organization_id`` NULL)."""
        headers = await _auth_headers(test_superuser)

        docker = AsyncMock()
        docker.close = AsyncMock()
        container_id = "audit-emission-container"

        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            started = await client.post(
                f"/api/v1/docker/containers/{container_id}/start", headers=headers
            )
            stopped = await client.post(
                f"/api/v1/docker/containers/{container_id}/stop", headers=headers
            )
            deleted = await client.delete(
                f"/api/v1/docker/containers/{container_id}", headers=headers
            )

        assert started.status_code == 204, started.text
        assert stopped.status_code == 204, stopped.text
        assert deleted.status_code == 204, deleted.text

        for action, mock_name in (
            ("container.started", "start_container"),
            ("container.stopped", "stop_container"),
            ("container.deleted", "remove_container"),
        ):
            lines = await _audit_lines(db_session, action)
            assert len(lines) == 1, action
            line = lines[0]
            assert line.resource_type == "container"
            assert line.resource_id == container_id
            assert line.organization_id is None  # endpoint global
            assert line.user_id == test_superuser.id

        docker.start_container.assert_awaited_once_with(container_id)
        docker.stop_container.assert_awaited_once_with(container_id, timeout=10)
        docker.remove_container.assert_awaited_once_with(container_id, force=False)


class TestRolesAndMembersAudit:
    """user.role_changed / member.added / member.removed."""

    async def test_role_change_member_added_removed_audited(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """Cycle complet membres : ajout (viewer), promotion operator
        (``user.role_changed`` avec ``{previous_role, new_role}``), retrait
        — une ligne par action, acteur = superuser."""
        from app.schemas.user import UserCreate
        from app.services.user_service import UserService

        member = await UserService.create(
            db_session,
            UserCreate(
                email=f"member-{uuid.uuid4().hex[:8]}@example.com",
                username=f"member{uuid.uuid4().hex[:8]}",
                full_name="Audit Member",
                password="memberpassword123",
                is_superuser=False,
            ),
        )
        await db_session.commit()

        headers = await _auth_headers(test_superuser)
        base = f"/api/v1/organizations/{test_organization.id}"

        # Ajout — superuser bypass l'escalation guard
        added = await client.post(
            f"{base}/users",
            json={"user_id": str(member.id), "role": "viewer"},
            headers=headers,
        )
        assert added.status_code == 201, added.text

        added_lines = await _audit_lines(db_session, "member.added")
        assert len(added_lines) == 1
        assert added_lines[0].organization_id == str(test_organization.id)
        assert added_lines[0].resource_id == str(member.id)
        assert added_lines[0].details == {"role": "viewer"}

        # Promotion viewer → operator
        promoted = await client.put(
            f"{base}/users/{member.id}",
            json={"role": "operator"},
            headers=headers,
        )
        assert promoted.status_code == 200, promoted.text

        role_lines = await _audit_lines(db_session, "user.role_changed")
        assert len(role_lines) == 1
        assert role_lines[0].details == {
            "previous_role": "viewer",
            "new_role": "operator",
        }

        # Retrait
        removed = await client.delete(f"{base}/users/{member.id}", headers=headers)
        assert removed.status_code == 204, removed.text

        removed_lines = await _audit_lines(db_session, "member.removed")
        assert len(removed_lines) == 1
        assert removed_lines[0].resource_id == str(member.id)


# ---------------------------------------------------------------------------
# Déploiements (Tâche 3)
# ---------------------------------------------------------------------------


class TestDeploymentsAudit:
    """deployment.created / deployment.succeeded|failed / stack.rollback."""

    async def test_deployment_created_audited(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        operator_user: User,
        test_stack: Stack,
        test_target,
        test_organization,
    ):
        """POST /deployments → 201 + ``deployment.created`` avec acteur =
        initiateur (les transitions service émettent en acteur système)."""
        headers = await _auth_headers(operator_user)

        with patch(
            "app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment",
            new_callable=AsyncMock,
        ):
            response = await client.post(
                "/api/v1/deployments",
                json={
                    "stack_id": str(test_stack.id),
                    "target_id": str(test_target.id),
                    "name": "audit-emission-deployment",
                },
                headers=headers,
            )
        assert response.status_code == 201, response.text

        lines = await _audit_lines(db_session, "deployment.created")
        assert len(lines) == 1
        line = lines[0]
        assert line.user_id == operator_user.id
        assert line.resource_type == "deployment"
        assert line.resource_id == unwrap(response)["id"]
        assert line.organization_id == test_organization.id

    async def test_deployment_terminal_transitions_system_actor(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_stack: Stack,
        test_target,
        test_organization,
    ):
        """``DeploymentService.update_status`` sur transition terminale →
        ``deployment.succeeded`` / ``deployment.failed`` avec
        ``user_id=None`` (acteur système — le modèle Deployment n'a pas de
        colonne acteur ; l'initiateur reste traçable via
        ``deployment.created``)."""
        from app.models.deployment import DeploymentStatus as Status
        from app.services.deployment_service import DeploymentService

        # Déploiement créé directement en base (statut initial PENDING) —
        # on teste les transitions terminales du service, pas la création
        # HTTP (couverte par test_deployment_created_audited).
        deployment = Deployment(
            stack_id=str(test_stack.id),
            target_id=str(test_target.id),
            organization_id=test_organization.id,
            name="audit-terminal-deployment",
            status=Status.PENDING,
            config={},
            variables={},
        )
        db_session.add(deployment)
        await db_session.commit()
        await db_session.refresh(deployment)

        with patch("app.services.deployment_service.deployment_events") as events:
            events.emit_status_change = AsyncMock()
            events.emit_logs_update = AsyncMock()
            await DeploymentService.update_status(
                db_session, deployment.id, Status.RUNNING
            )
            await DeploymentService.update_status(
                db_session, deployment.id, Status.FAILED, error_message="boom"
            )

        succeeded = await _audit_lines(db_session, "deployment.succeeded")
        assert len(succeeded) == 1
        assert succeeded[0].user_id is None  # acteur système
        assert succeeded[0].resource_id == deployment.id
        assert succeeded[0].organization_id == test_organization.id

        failed = await _audit_lines(db_session, "deployment.failed")
        assert len(failed) == 1
        assert failed[0].user_id is None
        assert failed[0].details is not None
        assert failed[0].details.get("error") == "boom"

    async def test_stack_rollback_audited(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        operator_user: User,
        test_stack: Stack,
    ):
        """POST /stacks/{id}/versions/{version_id}/restore →
        ``stack.rollback`` avec org de la stack."""
        version = await _seed_stack_version(db_session, test_stack)
        headers = await _auth_headers(operator_user)

        response = await client.post(
            f"{STACKS_URL}/{test_stack.id}/versions/{version.id}/restore",
            headers=headers,
        )
        assert response.status_code == 200, response.text

        lines = await _audit_lines(db_session, "stack.rollback")
        assert len(lines) == 1
        line = lines[0]
        assert line.user_id == operator_user.id
        assert line.organization_id == test_stack.organization_id
        assert line.resource_id == str(test_stack.id)
        assert line.details == {"restored_version_id": str(version.id)}


# ---------------------------------------------------------------------------
# Plugins (Tâche 4) — représentatif de la famille install/remove
# ---------------------------------------------------------------------------


class TestPluginsAudit:
    """plugin.installed / plugin.removed."""

    async def test_plugin_installed_and_removed_audited(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """Install/uninstall mockés au niveau ``_plugin_service`` → lignes
        ``plugin.installed`` puis ``plugin.removed`` avec org du plugin."""
        headers = await _auth_headers(test_superuser)

        # Fake plugin (SimpleNamespace — l'ORM n'est pas sollicité : le
        # service est intégralement mocké, seule la ligne d'audit compte).
        plugin_id = str(uuid.uuid4())
        fake_plugin = SimpleNamespace(
            id=plugin_id,
            name="audit-test-plugin",
            version="1.0.0",
            status="installed",
            organization_id=test_organization.id,
        )

        install_service = AsyncMock()
        install_service.install_plugin = AsyncMock(return_value=fake_plugin)
        uninstall_service = AsyncMock()
        uninstall_service.get_plugin = AsyncMock(return_value=fake_plugin)
        uninstall_service.uninstall_plugin = AsyncMock(return_value=None)

        with patch("app.api.v1.plugins._plugin_service", install_service):
            installed = await client.post(
                "/api/v1/plugins/install",
                json={"source": "registry://audit-test-plugin"},
                headers=headers,
            )
        assert installed.status_code == 202, installed.text

        with patch("app.api.v1.plugins._plugin_service", uninstall_service):
            removed = await client.delete(
                f"/api/v1/plugins/{fake_plugin.id}/uninstall", headers=headers
            )
        assert removed.status_code == 204, removed.text

        installed_lines = await _audit_lines(db_session, "plugin.installed")
        assert len(installed_lines) == 1
        assert installed_lines[0].organization_id == test_organization.id
        assert installed_lines[0].resource_id == str(fake_plugin.id)
        assert installed_lines[0].details == {"name": "audit-test-plugin"}

        removed_lines = await _audit_lines(db_session, "plugin.removed")
        assert len(removed_lines) == 1
        assert removed_lines[0].resource_id == str(fake_plugin.id)


# ---------------------------------------------------------------------------
# Résilience (AC 4) + sécurité (AC 5)
# ---------------------------------------------------------------------------


class TestResilienceAndSecrets:
    """L'audit ne doit jamais casser l'action ; jamais fuiter de secret."""

    async def test_audit_failure_does_not_break_business_action(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_stack: Stack,
        test_organization,
    ):
        """Échec d'écriture injecté (session courte en erreur) → le DELETE
        stack répond quand même 204 et la stack est bien supprimée (AC 4 —
        part démonstration : le service attrape tout)."""
        from app.enums.rbac import Role
        from app.models.user_organization import UserOrganization
        from app.schemas.user import UserCreate
        from app.services.user_service import UserService

        admin = await UserService.create(
            db_session,
            UserCreate(
                email=f"resilience-{uuid.uuid4().hex[:8]}@example.com",
                username=f"resilience{uuid.uuid4().hex[:8]}",
                full_name="Resilience Admin",
                password="adminpassword123",
                is_superuser=False,
            ),
        )
        db_session.add(
            UserOrganization(
                user_id=admin.id,
                organization_id=test_organization.id,
                role=Role.ADMIN,
            )
        )
        await db_session.commit()

        def _exploding_factory():
            raise RuntimeError("audit database unavailable")

        with patch("app.services.audit_service.AsyncSessionLocal", _exploding_factory):
            response = await client.delete(
                f"{STACKS_URL}/{test_stack.id}",
                headers=await _auth_headers(admin),
            )

        assert response.status_code == 204, response.text
        # La ligne est perdue (best-effort) — aucune trace en base
        lines = await _audit_lines(db_session, "stack.deleted")
        assert lines == []
        # L'action métier a bien eu lieu
        remaining = await db_session.get(Stack, test_stack.id)
        assert remaining is None

    async def test_no_secrets_in_audit_details(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        """AC 5 : parcours login (password transit) + création clé API
        (``wf_ak_`` brute en réponse 201) → aucune ligne d'audit ne
        contient le password ni la clé brute dans ``details``.

        Le login échoué volontaire porte un password distinct et secret
        (il est bien audité — ``user.login_failed`` — sans jamais
        apparaître dans les ``details``) ; le login réussi utilise le
        password réel du compte."""
        wrong_password = "SuperSecretPassword123!"
        failed = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": wrong_password},
        )
        assert failed.status_code == 401, failed.text
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": USER_PASSWORD},
        )
        assert login.status_code == 200, login.text

        headers = await _auth_headers(test_user)
        created = await client.post(
            API_KEYS_URL, json={"name": "secret-hygiene-key"}, headers=headers
        )
        assert created.status_code == 201, created.text
        raw_key = unwrap(created)["key"]
        assert raw_key.startswith("wf_ak_")

        entries = (
            (await db_session.execute(select(AuditLog).order_by(AuditLog.created_at)))
            .scalars()
            .all()
        )
        assert entries, "des lignes d'audit doivent exister"

        assert wrong_password != USER_PASSWORD  # garde : secrets distincts
        for entry in entries:
            serialized = str(entry.details) if entry.details else ""
            assert (
                wrong_password not in serialized
            ), f"password trouvé dans details de {entry.action}"
            assert (
                USER_PASSWORD not in serialized
            ), f"password du compte trouvé dans details de {entry.action}"
            assert (
                raw_key not in serialized
            ), f"clé API brute trouvée dans details de {entry.action}"

    async def test_no_secrets_in_logs_caplog(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        caplog,
    ):
        """AC 5 : parcours d'émission sous caplog → password et clé brute
        absents de tous les enregistrements.

        Défense du piège documenté (124.4) : ``sqlalchemy.engine`` est
        bridé à WARNING (ses logs INFO échappent les paramètres bindés).
        Depuis BUG-004, ce bridage est systématique (fixture autouse du
        ``conftest.py`` + ``main.py``) : plus besoin d'imposer
        ``LOG_LEVEL=WARNING`` en tête de commande.
        """
        caplog.set_level(logging.DEBUG)
        caplog.set_level(logging.WARNING, logger="sqlalchemy.engine")

        wrong_password = "CaplogSecretPassword123!"
        failed = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": wrong_password},
        )
        assert failed.status_code == 401, failed.text
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": USER_PASSWORD},
        )
        assert login.status_code == 200, login.text

        headers = await _auth_headers(test_user)
        created = await client.post(
            API_KEYS_URL, json={"name": "caplog-hygiene-key"}, headers=headers
        )
        assert created.status_code == 201, created.text
        raw_key = unwrap(created)["key"]

        assert wrong_password not in caplog.text
        assert USER_PASSWORD not in caplog.text
        assert raw_key not in caplog.text
