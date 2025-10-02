"""
Abstractions pour la gestion de base de données et cache.

Architecture modulaire permettant le support de SQLite (défaut) ou PostgreSQL,
et cache optionnel avec Redis.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, AsyncContextManager
from contextlib import asynccontextmanager


class DatabaseManager(ABC):
    """
    Interface abstraite pour la gestion de base de données.

    Permet de supporter différents backends (SQLite, PostgreSQL)
    avec la même interface.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Établit la connexion à la base de données."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Ferme la connexion à la base de données."""
        pass

    @abstractmethod
    async def create_tables(self) -> None:
        """Crée les tables de la base de données."""
        pass

    @abstractmethod
    @asynccontextmanager
    async def session(self) -> AsyncContextManager:
        """
        Context manager pour une session de base de données.

        Yields:
            AsyncSession: Session SQLAlchemy async
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Vérifie l'état de santé de la connexion.

        Returns:
            bool: True si la connexion est saine
        """
        pass


class CacheManager(ABC):
    """
    Interface abstraite pour la gestion du cache.

    Permet de supporter différents backends (Memory cache, Redis)
    avec la même interface.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Récupère une valeur du cache.

        Args:
            key: Clé de la valeur à récupérer

        Returns:
            Optional[Any]: Valeur ou None si non trouvée
        """
        pass

    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Stocke une valeur dans le cache.

        Args:
            key: Clé de stockage
            value: Valeur à stocker
            ttl: Time to live en secondes (optionnel)

        Returns:
            bool: True si le stockage a réussi
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Supprime une valeur du cache.

        Args:
            key: Clé à supprimer

        Returns:
            bool: True si la suppression a réussi
        """
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """
        Vide complètement le cache.

        Returns:
            bool: True si le cache a été vidé
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Vérifie si une clé existe dans le cache.

        Args:
            key: Clé à vérifier

        Returns:
            bool: True si la clé existe
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Vérifie l'état de santé du cache.

        Returns:
            bool: True si le cache est disponible
        """
        pass
