"""
Configuration pytest pour les tests WindFlow backend.

Fournit les fixtures pour:
- Base de données de test (schéma appliqué par les migrations Alembic —
  STORY-120.2 : plus aucun ``create_all`` nu)
- Sessions async SQLAlchemy
- Client de test FastAPI
- Utilisateurs de test
"""

import asyncio
import shutil
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
from alembic import command as alembic_command
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_alembic_config, get_db
from app.enums.rbac import Role
from app.main import app
from app.models.organization import Organization
from app.models.stack import Stack
from app.models.target import Target, TargetStatus, TargetType
from app.models.user import User
from app.services.user_service import UserService

# Configuration pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(autouse=True)
def _reset_rate_limit_store():
    """
    Réinitialise le limiteur mémoire entre chaque test (STORY-102).

    Le store étant module-level (process-local), les tests d'API qui
    bombardent des endpoints décorés (ex. logins via `authenticated_client`)
    dépasseraient sinon le quota de la fenêtre glissante et recevraient 429
    au-delà du 5e test du process. Chaque test repart d'un état vide.
    """
    from app.core import rate_limit as _rate_limit_module

    _rate_limit_module._memory_limiter.reset()
    yield
    _rate_limit_module._memory_limiter.reset()


@pytest.fixture(autouse=True)
def _reset_bruteforce_store():
    """
    Réinitialise le store brute-force entre chaque test (STORY-104).

    Miroir de `_reset_rate_limit_store` : le singleton `bruteforce_protector`
    est process-level ; les logins réussis des fixtures `authenticated_client`
    / `admin_client` resetent déjà le compteur, mais la fixture protège
    surtout les suites d'échecs volontaires (tests de blocage).
    """
    from app.core.bruteforce_protection import bruteforce_protector

    bruteforce_protector.reset_all()
    yield
    bruteforce_protector.reset_all()


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    Crée une event loop pour toute la session de tests.

    Nécessaire pour les tests async avec scope session.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def _migrated_schema_template(tmp_path_factory) -> Path:
    """Applique les migrations Alembic sur une base SQLite template (une fois
    par session).

    STORY-120.2 : le schéma de test provient **exclusivement des migrations**
    (``alembic upgrade head``) — plus aucun ``Base.metadata.create_all`` nu.

    Une base **fichier** (et non ``:memory:``) est requise : le
    ``backend/alembic/env.py`` construit son propre engine depuis
    ``settings.database_url`` ; une base en mémoire serait une base vide
    distincte pour ce runner. L'URL des settings est ponctuellement
    redirigée vers le fichier template, puis restaurée.

    Yields:
        Path: Chemin de la base SQLite template (schéma complet versionné).
    """
    from app.config import settings as app_settings

    template_path = tmp_path_factory.mktemp("windflow-schema") / "template.db"

    original_url = app_settings.database_url
    app_settings.database_url = f"sqlite+aiosqlite:///{template_path}"
    try:
        # env.py exécute asyncio.run() : délégué à un thread sans boucle active
        await asyncio.to_thread(alembic_command.upgrade, get_alembic_config(), "head")
    finally:
        app_settings.database_url = original_url

    return template_path


@pytest.fixture(scope="function")
async def test_db_engine(_migrated_schema_template: Path, tmp_path: Path):
    """
    Crée un moteur de base de données SQLite isolé pour le test.

    Le schéma est obtenu par copie du template migré (migrations Alembic
    uniquement — STORY-120.2), garantissant une isolation complète par test
    sans aucun ``create_all``.

    Args:
        _migrated_schema_template: Base template migrée une fois par session
        tmp_path: Répertoire temporaire unique par test

    Yields:
        AsyncEngine: Moteur de base de données de test
    """
    db_path = tmp_path / "test.db"
    shutil.copy2(_migrated_schema_template, db_path)

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    yield engine

    # Cleanup : suppression du fichier = isolation garantie (pas de drop_all)
    await engine.dispose()
    db_path.unlink(missing_ok=True)


@pytest.fixture(scope="function")
async def test_session_factory(test_db_engine):
    """
    Crée une factory de sessions pour les tests.

    Args:
        test_db_engine: Moteur de base de données de test

    Returns:
        async_sessionmaker: Factory de sessions
    """
    return async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest.fixture(scope="function")
async def db_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """
    Fournit une session de base de données pour les tests.

    Args:
        test_session_factory: Factory de sessions de test

    Yields:
        AsyncSession: Session de base de données isolée
    """
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest.fixture(scope="function")
async def test_organization(db_session: AsyncSession) -> Organization:
    """
    Crée une organisation de test.

    Args:
        db_session: Session de base de données

    Returns:
        Organization: Organisation de test créée
    """
    org = Organization(
        name="Test Organization",
        slug="test-org",
        description="Organization for testing",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture(scope="function")
async def test_user(db_session: AsyncSession, test_organization: Organization) -> User:
    """
    Crée un utilisateur de test standard (association ``operator``).

    STORY-121.3 : le rattachement passe par la table d'association — le
    rôle ``operator`` est posé directement (cohérent avec le mapping de
    migration des utilisateurs pré-existants ; UserService.create ne
    rattache qu'en viewer).

    Args:
        db_session: Session de base de données
        test_organization: Organisation de test

    Returns:
        User: Utilisateur de test créé
    """
    from app.enums.rbac import Role
    from app.models.user_organization import UserOrganization
    from app.schemas.user import UserCreate

    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        password="testpassword123",
        is_superuser=False,
    )

    user = await UserService.create(db_session, user_data)

    db_session.add(
        UserOrganization(
            user_id=user.id,
            organization_id=test_organization.id,
            role=Role.OPERATOR,
        )
    )
    await db_session.commit()
    return user


@pytest.fixture(scope="function")
async def test_superuser(
    db_session: AsyncSession, test_organization: Organization
) -> User:
    """
    Crée un super-utilisateur de test (association ``admin``).

    STORY-121.3 : le rôle ``admin`` en association + flag ``is_superuser``
    inchangé — cohérent avec le mapping de migration (superuser → admin).

    Args:
        db_session: Session de base de données
        test_organization: Organisation de test

    Returns:
        User: Super-utilisateur de test créé
    """
    from app.enums.rbac import Role
    from app.models.user_organization import UserOrganization
    from app.schemas.user import UserCreate

    user_data = UserCreate(
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        password="adminpassword123",
        is_superuser=True,
    )

    user = await UserService.create(db_session, user_data)

    db_session.add(
        UserOrganization(
            user_id=user.id,
            organization_id=test_organization.id,
            role=Role.ADMIN,
        )
    )
    await db_session.commit()
    return user


# --- STORY-122.7 : helpers / fixtures rôles RBAC partagés -------------------

_ROLE_USER_PASSWORD = "rolepassword123"


async def create_user_with_role(
    db_session: AsyncSession,
    organization: Organization,
    role: Role,
    *,
    is_superuser: bool = False,
    suffix: str = "",
) -> User:
    """
    Crée un utilisateur rattaché à ``organization`` avec le rôle RBAC donné.

    STORY-122.7 (Tâche 1) : factorisation du pattern ``test_user`` —
    ``UserService.create`` puis association ``UserOrganization(role=...)``
    dans l'organisation fournie. Le paramètre ``suffix`` garantit l'unicité
    username/email lorsque plusieurs utilisateurs coexistent dans un même
    test (ex. viewer + operator + admin d'org pour la matrice consolidée).

    Args:
        db_session: Session de base de données
        organization: Organisation à laquelle rattacher l'utilisateur
        role: Rôle de l'association (viewer | operator | admin | super_admin)
        is_superuser: Flag système superadmin (tous droits, toutes orgs)
        suffix: Suffixe d'unicité username/email (optionnel)

    Returns:
        User: Utilisateur créé avec son association en base
    """
    from app.models.user_organization import UserOrganization
    from app.schemas.user import UserCreate

    unique = f"-{suffix}" if suffix else ""
    user_data = UserCreate(
        email=f"{role.value}{unique}@example.com",
        username=f"{role.value}{unique}",
        full_name=f"{role.value.title()} User {suffix}".strip(),
        password=_ROLE_USER_PASSWORD,
        is_superuser=is_superuser,
    )

    user = await UserService.create(db_session, user_data)
    db_session.add(
        UserOrganization(
            user_id=user.id,
            organization_id=organization.id,
            role=role,
        )
    )
    await db_session.commit()
    return user


async def _login_role_client(client: AsyncClient, username: str) -> None:
    """
    Authentifie le client partagé par login JWT (pattern ``authenticated_client``).

    Args:
        client: Client de test (muté : header Authorization ajouté)
        username: Identifiant de l'utilisateur à connecter
    """
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": _ROLE_USER_PASSWORD},
    )
    assert response.status_code == 200, response.text
    client.headers.update(
        {"Authorization": f"Bearer {response.json()['access_token']}"}
    )


@pytest.fixture(scope="function")
async def viewer_user(
    db_session: AsyncSession, test_organization: Organization
) -> User:
    """
    Utilisateur **viewer** rattaché à ``test_organization`` (STORY-122.7).
    """
    return await create_user_with_role(
        db_session, test_organization, Role.VIEWER, suffix="m7"
    )


@pytest.fixture(scope="function")
async def viewer_client(
    client: AsyncClient, viewer_user: User
) -> AsyncGenerator[AsyncClient, None]:
    """Client authentifié en viewer (lecture seule — matrice consolidée)."""
    await _login_role_client(client, viewer_user.username)
    yield client
    client.headers.pop("Authorization", None)


@pytest.fixture(scope="function")
async def operator_user(
    db_session: AsyncSession, test_organization: Organization
) -> User:
    """
    Utilisateur **operator** rattaché à ``test_organization`` (STORY-122.7).
    """
    return await create_user_with_role(
        db_session, test_organization, Role.OPERATOR, suffix="m7"
    )


@pytest.fixture(scope="function")
async def operator_client(
    client: AsyncClient, operator_user: User
) -> AsyncGenerator[AsyncClient, None]:
    """Client authentifié en operator (actions opérationnelles)."""
    await _login_role_client(client, operator_user.username)
    yield client
    client.headers.pop("Authorization", None)


@pytest.fixture(scope="function")
async def org_admin_user(
    db_session: AsyncSession, test_organization: Organization
) -> User:
    """
    Utilisateur **admin d'organisation** (non-superuser) rattaché à
    ``test_organization`` (STORY-122.7) — gestion dans son organisation.
    """
    return await create_user_with_role(
        db_session, test_organization, Role.ADMIN, suffix="m7"
    )


@pytest.fixture(scope="function")
async def org_admin_client(
    client: AsyncClient, org_admin_user: User
) -> AsyncGenerator[AsyncClient, None]:
    """Client authentifié en admin d'organisation (non-superuser)."""
    await _login_role_client(client, org_admin_user.username)
    yield client
    client.headers.pop("Authorization", None)


# --- STORY-123.4 (arbitrage n°4) : fixtures login & lignes refresh_tokens ----
#
# Toutes les fixtures ci-dessous qui font un login réel (authenticated_client,
# admin_client, viewer_client, operator_client, org_admin_client) appellent
# ``POST /auth/login``, qui depuis STORY-123.3 **persiste le hash du refresh
# token opaque émis** → chaque test utilisant ces fixtures crée une ligne
# ``refresh_tokens`` en base.
#
# Position (arbitrage n°4 de la découpe STORY-123) : c'est une NON-RÉGRESSION
# GRATUITE — la table grandit en base de test sans casser aucune assertion
# (la base est recréée par test via copie du template migré, cf.
# ``test_db_engine``). Ne pas contrer ce comportement. Si un test isolé exige
# une base sans refresh tokens (ex. comptage exact de lignes), purger
# explicitement dans CE test (``DELETE FROM refresh_tokens`` ou
# ``RefreshTokenService.purge_expired``) plutôt qu'ici.


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Crée un client de test FastAPI avec base de données de test.

    Args:
        db_session: Session de base de données de test

    Yields:
        AsyncClient: Client HTTP async pour tester l'API
    """

    # Override de la dépendance get_db pour utiliser la session de test
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def authenticated_client(
    client: AsyncClient, test_user: User
) -> AsyncGenerator[AsyncClient, None]:
    """
    Crée un client authentifié avec token JWT.

    Args:
        client: Client de test
        test_user: Utilisateur de test

    Yields:
        AsyncClient: Client authentifié avec headers JWT
    """
    # Login pour obtenir le token
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "testpassword123"},
    )

    assert response.status_code == 200
    token_data = response.json()
    access_token = token_data["access_token"]

    # Ajouter le token aux headers
    client.headers.update({"Authorization": f"Bearer {access_token}"})

    yield client

    # Cleanup
    client.headers.pop("Authorization", None)


@pytest.fixture(scope="function")
async def admin_client(
    client: AsyncClient, test_superuser: User
) -> AsyncGenerator[AsyncClient, None]:
    """
    Crée un client authentifié avec un super-utilisateur.

    Args:
        client: Client de test
        test_superuser: Super-utilisateur de test

    Yields:
        AsyncClient: Client authentifié avec droits admin
    """
    # Login admin pour obtenir le token
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_superuser.username, "password": "adminpassword123"},
    )

    assert response.status_code == 200
    token_data = response.json()
    access_token = token_data["access_token"]

    # Ajouter le token aux headers
    client.headers.update({"Authorization": f"Bearer {access_token}"})

    yield client

    # Cleanup
    client.headers.pop("Authorization", None)


@pytest.fixture(scope="function")
async def test_target(
    db_session: AsyncSession, test_organization: Organization
) -> Target:
    """
    Crée une cible de déploiement de test.

    Args:
        db_session: Session de base de données
        test_organization: Organisation de test

    Returns:
        Target: Cible de test créée
    """
    target = Target(
        name="Test Docker Target",
        host="localhost",
        port=2375,
        type=TargetType.DOCKER,
        status=TargetStatus.ONLINE,
        credentials={},
        organization_id=test_organization.id,
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)
    return target


@pytest.fixture(scope="function")
async def test_stack(
    db_session: AsyncSession, test_organization: Organization
) -> Stack:
    """
    Crée un stack de test.

    Args:
        db_session: Session de base de données
        test_organization: Organisation de test

    Returns:
        Stack: Stack de test créé
    """
    stack = Stack(
        name="Test Stack",
        description="A test stack for unit testing",
        template={
            "version": "3.8",
            "services": {"web": {"image": "nginx:latest", "ports": ["80:80"]}},
        },
        variables={"port": {"type": "integer", "default": 80}},
        organization_id=test_organization.id,
    )
    db_session.add(stack)
    await db_session.commit()
    await db_session.refresh(stack)
    return stack
