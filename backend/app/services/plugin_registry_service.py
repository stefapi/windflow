"""
Service d'accès au registre officiel de plugins WindFlow.

Responsable du téléchargement, de la validation, du cache TTL
et de l'exposition des données du registre officiel.

STORY-168 : le cache TTL repose sur l'interface unifiée
``core/cache.get_cache()`` (clé ``registry:index``, TTL
``plugin_registry_cache_ttl`` — 300 s par défaut). La sémantique
stale-while-error est conservée : le cache unifié expire ses entrées,
le service garde donc une copie locale last-known-good (``_last_good_index``)
servie si le fetch échoue alors que l'entrée a expiré.
"""

import asyncio
import logging
from typing import List, Optional

import aiohttp
from pydantic import ValidationError

from ..config import Settings
from ..core.cache import get_cache
from ..core.exceptions import WindFlowException
from ..core.resilience import (
    get_circuit_breaker_registry,
    is_circuit_breaker_enabled,
)
from ..schemas.plugin_registry import RegistryIndex, RegistryPluginEntry

logger = logging.getLogger(__name__)

#: Clé du cache unifié pour l'index du registre (convention STORY-168).
REGISTRY_INDEX_CACHE_KEY = "registry:index"


class PluginRegistryService:
    """Service métier d'accès au registre officiel des plugins.

    Télécharge l'index JSON depuis l'URL configurée, le valide via Pydantic,
    le met en cache avec un TTL configurable (interface unifiée
    ``core/cache``), et expose des méthodes de recherche par nom et par
    texte libre.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialise le service avec la configuration donnée.

        Args:
            settings: Instance des settings de l'application.
        """
        self._settings = settings
        # Copie locale last-known-good (stale-while-error) : servie si le
        # fetch échoue alors que l'entrée du cache unifié a expiré.
        self._last_good_index: Optional[RegistryIndex] = None

    async def _invalidate_cache(self) -> None:
        """Invalide le cache (pour forcer le rechargement).

        Supprime l'entrée du cache unifié **et** la copie locale
        last-known-good (plus aucun fallback possible ensuite).
        """
        cache = await get_cache()
        await cache.delete(REGISTRY_INDEX_CACHE_KEY)
        self._last_good_index = None
        logger.info("registry_cache_invalidated")

    async def _fetch_index_http(self) -> dict:
        """Effectue le fetch HTTP de l'index brut (timeout configuré).

        STORY-251 : sous circuit breaker ``plugin_registry``. Un échec
        (HTTP != 200, timeout, réseau) alimente le circuit ; circuit
        ouvert → :class:`CircuitBreakerOpenError` levée **sans requête
        HTTP**, interceptée par le fallback stale-while-error de
        :meth:`fetch_index` (comportement STORY-168 préservé).

        Returns:
            Données JSON brutes de l'index.

        Raises:
            WindFlowException: erreur HTTP (statut != 200), timeout ou
                circuit ouvert (CircuitBreakerOpenError, sous-classe).
        """
        if not is_circuit_breaker_enabled():
            return await self._fetch_index_http_unguarded()

        circuit = get_circuit_breaker_registry().get_or_create("plugin_registry")
        return await circuit.call(
            self._fetch_index_http_unguarded,
            failure_filter=lambda exc: isinstance(exc, WindFlowException),
        )

    async def _fetch_index_http_unguarded(self) -> dict:
        """Fetch HTTP brut (sans circuit breaker — cible du garde)."""
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
                    return await response.json()

        except asyncio.TimeoutError as exc:
            logger.warning("registry_fetch_timeout")
            raise WindFlowException(
                "Timeout lors du téléchargement du registre officiel",
                details={"error_type": "registry_timeout"},
            ) from exc

        except aiohttp.ClientError as exc:
            logger.warning("registry_fetch_error", extra={"error": str(exc)})
            raise WindFlowException(
                f"Erreur réseau lors du téléchargement du registre : {exc}",
                details={"error_type": "registry_unavailable"},
            ) from exc

    async def fetch_index(self) -> RegistryIndex:
        """Télécharge et valide l'index JSON depuis l'URL configurée.

        Cache unifié (STORY-168) : hit ``registry:index`` → revalidation
        Pydantic et retour sans fetch HTTP. Miss → fetch (timeout 10 s)
        + validation Pydantic + ``set`` avec TTL
        ``plugin_registry_cache_ttl``.

        Stale-while-error : en cas d'échec du fetch (timeout / réseau /
        JSON invalide), la copie locale last-known-good est servie si
        disponible (l'entrée du cache unifié peut avoir expiré entre-temps).

        Returns:
            RegistryIndex validé.

        Raises:
            WindFlowException: Si le fetch échoue et aucun cache n'est disponible.
        """
        cache = await get_cache()
        cached_payload = await cache.get(REGISTRY_INDEX_CACHE_KEY)
        if cached_payload is not None:
            try:
                index = RegistryIndex.model_validate(cached_payload)
            except (ValidationError, ValueError):
                # Entrée corrompue (écriture antérieure ?) → purge + refetch
                logger.warning("registry_cache_payload_invalid")
                await cache.delete(REGISTRY_INDEX_CACHE_KEY)
            else:
                logger.debug("registry_cache_hit")
                self._last_good_index = index
                return index

        try:
            data = await self._fetch_index_http()
        except WindFlowException:
            if self._last_good_index is not None:
                logger.info("registry_fallback_to_expired_cache")
                return self._last_good_index
            raise

        try:
            index = RegistryIndex.model_validate(data)
        except (ValidationError, ValueError) as exc:
            logger.warning("registry_invalid_json", extra={"error": str(exc)})
            if self._last_good_index is not None:
                logger.info("registry_fallback_to_expired_cache")
                return self._last_good_index
            raise WindFlowException(
                f"L'index du registre est invalide : {exc}",
                details={"error_type": "registry_invalid"},
            ) from exc

        await cache.set(
            REGISTRY_INDEX_CACHE_KEY,
            index.model_dump(mode="json"),
            ttl=self._settings.plugin_registry_cache_ttl,
        )
        self._last_good_index = index
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
