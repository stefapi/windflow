"""
Service d'accès au registre officiel de plugins WindFlow.

Responsable du téléchargement, de la validation, du cache TTL
et de l'exposition des données du registre officiel.
"""

import asyncio
import logging
import time
from typing import List, Optional

import aiohttp
from pydantic import ValidationError

from ..config import Settings
from ..core.exceptions import WindFlowException
from ..schemas.plugin_registry import RegistryIndex, RegistryPluginEntry

logger = logging.getLogger(__name__)


class PluginRegistryService:
    """Service métier d'accès au registre officiel des plugins.

    Télécharge l'index JSON depuis l'URL configurée, le valide via Pydantic,
    le met en cache avec un TTL configurable, et expose des méthodes de
    recherche par nom et par texte libre.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialise le service avec la configuration donnée.

        Args:
            settings: Instance des settings de l'application.
        """
        self._settings = settings
        self._cached_index: Optional[RegistryIndex] = None
        self._cache_timestamp: float = 0.0

    def _is_cache_valid(self) -> bool:
        """Vérifie si le cache est encore valide (TTL non expiré).

        Returns:
            True si le cache est valide, False sinon.
        """
        if self._cached_index is None:
            return False
        elapsed = time.monotonic() - self._cache_timestamp
        return elapsed < self._settings.plugin_registry_cache_ttl

    def _invalidate_cache(self) -> None:
        """Invalide le cache (pour forcer le rechargement)."""
        self._cached_index = None
        self._cache_timestamp = 0.0
        logger.info("registry_cache_invalidated")

    async def fetch_index(self) -> RegistryIndex:
        """Télécharge et valide l'index JSON depuis l'URL configurée.

        Si le cache est valide, retourne les données en cache.
        Sinon, effectue un fetch HTTP avec timeout, valide le JSON
        via Pydantic, et met en cache le résultat.

        En cas d'erreur de fetch, retourne les données en cache
        même expirées si disponibles (fallback gracieux).

        Returns:
            RegistryIndex validé.

        Raises:
            WindFlowException: Si le fetch échoue et aucun cache n'est disponible.
        """
        if self._is_cache_valid() and self._cached_index is not None:
            logger.debug("registry_cache_hit")
            return self._cached_index

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._settings.plugin_registry_url,
                    timeout=aiohttp.ClientTimeout(
                        total=self._settings.plugin_registry_timeout
                    ),
                ) as response:
                    if response.status != 200:
                        raise WindFlowException(
                            f"Erreur HTTP {response.status} lors du fetch du registre",
                            details={"error_type": "registry_unavailable"},
                        )
                    data = await response.json()

        except asyncio.TimeoutError as exc:
            logger.warning("registry_fetch_timeout")
            if self._cached_index is not None:
                logger.info("registry_fallback_to_expired_cache")
                return self._cached_index
            raise WindFlowException(
                "Timeout lors du téléchargement du registre officiel",
                details={"error_type": "registry_timeout"},
            ) from exc

        except aiohttp.ClientError as exc:
            logger.warning("registry_fetch_error", extra={"error": str(exc)})
            if self._cached_index is not None:
                logger.info("registry_fallback_to_expired_cache")
                return self._cached_index
            raise WindFlowException(
                f"Erreur réseau lors du téléchargement du registre : {exc}",
                details={"error_type": "registry_unavailable"},
            ) from exc

        try:
            index = RegistryIndex.model_validate(data)
        except (ValidationError, ValueError) as exc:
            logger.warning("registry_invalid_json", extra={"error": str(exc)})
            if self._cached_index is not None:
                logger.info("registry_fallback_to_expired_cache")
                return self._cached_index
            raise WindFlowException(
                f"L'index du registre est invalide : {exc}",
                details={"error_type": "registry_invalid"},
            ) from exc

        self._cached_index = index
        self._cache_timestamp = time.monotonic()
        logger.info(
            "registry_fetched",
            extra={"plugins_count": len(index.plugins)},
        )
        return index

    async def list_plugins(self) -> List[RegistryPluginEntry]:
        """Retourne tous les plugins du registre.

        Returns:
            Liste de toutes les entrées du registre.
        """
        index = await self.fetch_index()
        return index.plugins

    async def get_plugin(self, name: str) -> Optional[RegistryPluginEntry]:
        """Recherche un plugin par nom exact.

        Args:
            name: Nom du plugin (kebab-case).

        Returns:
            L'entrée du registre si trouvée, None sinon.
        """
        plugins = await self.list_plugins()
        for plugin in plugins:
            if plugin.name == name:
                return plugin
        return None

    async def search_plugins(self, query: str) -> List[RegistryPluginEntry]:
        """Recherche des plugins par texte libre (nom, description, tags).

        La recherche est insensible à la casse et cherche dans les champs
        name, display_name, description et tags.

        Args:
            query: Texte de recherche.

        Returns:
            Liste des plugins correspondants.
        """
        plugins = await self.list_plugins()
        query_lower = query.lower()
        results: List[RegistryPluginEntry] = []
        for plugin in plugins:
            if (
                query_lower in plugin.name.lower()
                or query_lower in plugin.display_name.lower()
                or query_lower in plugin.description.lower()
                or any(query_lower in tag.lower() for tag in plugin.tags)
            ):
                results.append(plugin)
        return results
