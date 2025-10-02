"""
Configuration de la base de données avec SQLAlchemy 2.0 async.

Support SQLite par défaut et PostgreSQL optionnel selon l'architecture modulaire.
"""

from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool, NullPool

from .config import settings


class Base(DeclarativeBase):
    """Base class pour tous les modèles SQLAlchemy."""
    pass


class Database:
    """
    Gestionnaire de base de données SQLAlchemy 2.0 avec support async.

    Support SQLite (défaut) et PostgreSQL avec configuration adaptative.
    """

    def __init__(self) -> None:
        """Initialise le gestionnaire de base de données."""
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None
        self._is_sqlite = settings.database_url.startswith("sqlite")

    async def connect(self) -> None:
        """Crée le moteur de base de données et configure les sessions."""
        # Configuration spécifique selon le type de base de données
        connect_args = {}
        poolclass = None

        if self._is_sqlite:
            # SQLite nécessite check_same_thread=False pour async
            connect_args = {"check_same_thread": False}
            # StaticPool pour SQLite en développement
            poolclass = StaticPool

            # Créer le répertoire data si nécessaire
            import os
            db_path = settings.database_url.replace("sqlite:///", "")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        else:
            # PostgreSQL avec pool de connexions
            poolclass = None  # Utilise le pool par défaut

        # Création du moteur async
        self.engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            connect_args=connect_args,
            poolclass=poolclass,
            pool_size=settings.database_pool_size if not self._is_sqlite else 5,
            max_overflow=settings.database_max_overflow if not self._is_sqlite else 10,
            pool_recycle=settings.database_pool_recycle,
        )

        # Factory de sessions
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    async def disconnect(self) -> None:
        """Ferme le moteur de base de données."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None

    async def create_tables(self) -> None:
        """Crée toutes les tables définies dans les modèles."""
        if not self.engine:
            raise RuntimeError("Database engine not initialized. Call connect() first.")

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager pour obtenir une session de base de données.

        Yields:
            AsyncSession: Session SQLAlchemy async

        Example:
            async with db.session() as session:
                result = await session.execute(select(User))
                users = result.scalars().all()
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call connect() first.")

        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def health_check(self) -> bool:
        """
        Vérifie que la connexion à la base de données fonctionne.

        Returns:
            bool: True si la connexion est saine
        """
        if not self.engine:
            return False

        try:
            async with self.engine.connect() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False


# Instance globale de la base de données
db = Database()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection pour FastAPI.

    Fournit une session de base de données pour les routes API.

    Example:
        @app.get("/users")
        async def get_users(session: AsyncSession = Depends(get_db)):
            result = await session.execute(select(User))
            return result.scalars().all()
    """
    async with db.session() as session:
        yield session
