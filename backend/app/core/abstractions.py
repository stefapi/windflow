"""
Abstractions du core — cache (STORY-250.1).

``CacheManager`` est le seul contrat vivant : consommé par
``core/cache.py`` (MemoryCache/RedisCache — STORY-168).
``DatabaseManager`` (non consommé) a été purgé par STORY-250.1.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


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

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Stocke une valeur dans le cache.

        Args:
            key: Clé de stockage
            value: Valeur à stocker
            ttl: Time to live en secondes (optionnel)

        Returns:
            bool: True si le stockage a réussi
        """

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Supprime une valeur du cache.

        Args:
            key: Clé à supprimer

        Returns:
            bool: True si la suppression a réussi
        """

    @abstractmethod
    async def clear(self) -> bool:
        """
        Vide complètement le cache.

        Returns:
            bool: True si le cache a été vidé
        """

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Vérifie si une clé existe dans le cache.

        Args:
            key: Clé à vérifier

        Returns:
            bool: True si la clé existe
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Vérifie l'état de santé du cache.

        Returns:
            bool: True si le cache est disponible
        """
