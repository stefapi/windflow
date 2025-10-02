"""
Configuration pytest pour les tests WindFlow backend.

Fournit les fixtures pour:
- Base de données de test (SQLite in-memory)
- Sessions async SQLAlchemy
- Client de test FastAPI
- Utilisateurs de test
"""

import asyncio
from typing import AsyncGenerator, Generator
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.organization import Organization
from app.models.stack import Stack
from app.models.target import Target, TargetType, TargetStatus
from app.services.user_service import UserService


# Configuration pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    Crée une event loop pour toute la session de tests.

    Nécessaire pour les tests async avec scope session.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db_engine():
    """
    Crée un moteur de base de données SQLite en mémoire pour les tests.

    Yields:
        AsyncEngine: Moteur de base de données de test
    """
    # Base de données SQLite en mémoire pour isolation complète
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Créer toutes les tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


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
        description="Organization for testing"
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture(scope="function")
async def test_user(db_session: AsyncSession, test_organization: Organization) -> User:
    """
    Crée un utilisateur de test standard.

    Args:
        db_session: Session de base de données
        test_organization: Organisation de test

    Returns:
        User: Utilisateur de test créé
    """
    from app.schemas.user import UserCreate

    user_data = UserCreate(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        password="testpassword123",
        organization_id=test_organization.id,
        is_superuser=False
    )

    user = await UserService.create(db_session, user_data)
    return user


@pytest.fixture(scope="function")
async def test_superuser(db_session: AsyncSession, test_organization: Organization) -> User:
    """
    Crée un super-utilisateur de test.

    Args:
        db_session: Session de base de données
        test_organization: Organisation de test

    Returns:
        User: Super-utilisateur de test créé
    """
    from app.schemas.user import UserCreate

    user_data = UserCreate(
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        password="adminpassword123",
        organization_id=test_organization.id,
        is_superuser=True
    )

    user = await UserService.create(db_session, user_data)
    return user


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
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def authenticated_client(
    client: AsyncClient,
    test_user: User
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
        data={
            "username": test_user.username,
            "password": "testpassword123"
        }
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
    client: AsyncClient,
    test_superuser: User
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
        data={
            "username": test_superuser.username,
            "password": "adminpassword123"
        }
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
async def test_target(db_session: AsyncSession, test_organization: Organization) -> Target:
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
        slug="test-docker",
        type=TargetType.DOCKER,
        status=TargetStatus.READY,
        connection_config={
            "host": "localhost",
            "port": 2375
        },
        organization_id=test_organization.id
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)
    return target


@pytest.fixture(scope="function")
async def test_stack(db_session: AsyncSession, test_organization: Organization) -> Stack:
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
        slug="test-stack",
        description="A test stack for unit testing",
        compose_content="""
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
""",
        variables_schema={
            "port": {"type": "integer", "default": 80}
        },
        organization_id=test_organization.id
    )
    db_session.add(stack)
    await db_session.commit()
    await db_session.refresh(stack)
    return stack
