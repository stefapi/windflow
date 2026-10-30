"""
Service LiteLLM pour l'intelligence artificielle multi-provider.

Supporte OpenAI, Claude (Anthropic), et Ollama local.
Fournit des fonctionnalités d'optimisation, génération de configurations,
et diagnostic d'erreurs assisté par IA.

STORY-168 : le cache des réponses repose sur l'interface unifiée
``core/cache.get_cache()`` — clé ``llm:{sha256(provider:prompt)}``
(**hash** : jamais de prompt en clair dans la clé, règles 40), TTL
borné ``LLM_CACHE_TTL`` (300 s) et éviction/purge du préfixe ``llm:``
(le dict non borné d'origine était une fuite mémoire potentielle).
"""

import hashlib
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from ..core.cache import get_cache

logger = logging.getLogger(__name__)

#: Préfixe des clés de cache LLM (convention STORY-168).
LLM_CACHE_PREFIX: str = "llm:"
#: TTL du cache des réponses LLM en secondes (constante — YAGNI, pas de setting).
LLM_CACHE_TTL: int = 300


class LLMProvider(str, Enum):
    """Providers LLM supportés."""

    OPENAI = "openai"
    CLAUDE = "claude"
    OLLAMA = "ollama"


class LiteLLMService:
    """
    Service d'intelligence artificielle multi-provider.

    Utilise LiteLLM pour une interface unifiée avec plusieurs providers LLM.
    Supporte OpenAI, Claude (Anthropic), et Ollama local.
    """

    def __init__(
        self,
        enabled: bool = False,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        ollama_base_url: str = "http://localhost:11434",
        default_provider: LLMProvider = LLMProvider.OLLAMA,
        default_model: str = "llama2",
    ):
        """
        Initialise le service LiteLLM.

        Args:
            enabled: Active ou désactive le service LiteLLM
            openai_api_key: Clé API OpenAI (optionnel)
            anthropic_api_key: Clé API Anthropic/Claude (optionnel)
            ollama_base_url: URL de base pour Ollama local
            default_provider: Provider par défaut à utiliser
            default_model: Modèle par défaut pour le provider
        """
        self.enabled = enabled
        self.openai_api_key = openai_api_key
        self.anthropic_api_key = anthropic_api_key
        self.ollama_base_url = ollama_base_url
        self.default_provider = default_provider
        self.default_model = default_model

        if not enabled:
            logger.info("LiteLLM service is disabled")
            return

        # Validation des configurations
        self._validate_configuration()
        logger.info(f"LiteLLM service initialized with provider: {default_provider}")

    def _validate_configuration(self) -> None:
        """Valide la configuration des providers."""
        if self.default_provider == LLMProvider.OPENAI and not self.openai_api_key:
            logger.warning("OpenAI selected but no API key provided")
        elif self.default_provider == LLMProvider.CLAUDE and not self.anthropic_api_key:
            logger.warning("Claude selected but no API key provided")
        elif self.default_provider == LLMProvider.OLLAMA:
            logger.info(f"Using Ollama at {self.ollama_base_url}")

    async def generate_docker_compose(
        self,
        description: str,
        requirements: Optional[Dict[str, Any]] = None,
        provider: Optional[LLMProvider] = None,
    ) -> Dict[str, Any]:
        """
        Génère une configuration Docker Compose assistée par IA.

        Args:
            description: Description du déploiement souhaité
            requirements: Exigences spécifiques (ressources, ports, etc.)
            provider: Provider LLM à utiliser (optionnel)

        Returns:
            Configuration Docker Compose générée

        Raises:
            RuntimeError: Si le service est désactivé
        """
        if not self.enabled:
            raise RuntimeError("LiteLLM service is not enabled")

        provider = provider or self.default_provider

        logger.info(f"Generating Docker Compose with {provider} for: {description}")

        # Construction du prompt
        prompt = self._build_compose_prompt(description, requirements)

        # Appel au LLM (simulation pour l'instant)
        # TODO: Intégrer litellm.completion() quand la dépendance sera ajoutée
        response = await self._call_llm(prompt, provider)

        return response

    async def optimize_resources(
        self,
        compose_config: Dict[str, Any],
        target_type: str,
        provider: Optional[LLMProvider] = None,
    ) -> Dict[str, Any]:
        """
        Optimise les ressources d'une configuration selon la cible.

        Args:
            compose_config: Configuration Docker Compose à optimiser
            target_type: Type de cible (docker, swarm, k8s)
            provider: Provider LLM à utiliser (optionnel)

        Returns:
            Configuration optimisée

        Raises:
            RuntimeError: Si le service est désactivé
        """
        if not self.enabled:
            raise RuntimeError("LiteLLM service is not enabled")

        provider = provider or self.default_provider

        logger.info(f"Optimizing resources for {target_type} with {provider}")

        prompt = self._build_optimization_prompt(compose_config, target_type)
        response = await self._call_llm(prompt, provider)

        return response

    async def diagnose_error(
        self,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
        provider: Optional[LLMProvider] = None,
    ) -> Dict[str, Any]:
        """
        Diagnostic d'erreur assisté par IA.

        Args:
            error_message: Message d'erreur à diagnostiquer
            context: Contexte additionnel (logs, configuration, etc.)
            provider: Provider LLM à utiliser (optionnel)

        Returns:
            Diagnostic avec suggestions de résolution

        Raises:
            RuntimeError: Si le service est désactivé
        """
        if not self.enabled:
            raise RuntimeError("LiteLLM service is not enabled")

        provider = provider or self.default_provider

        logger.info(f"Diagnosing error with {provider}")

        prompt = self._build_diagnostic_prompt(error_message, context)
        response = await self._call_llm(prompt, provider)

        return response

    async def suggest_improvements(
        self, compose_config: Dict[str, Any], provider: Optional[LLMProvider] = None
    ) -> List[Dict[str, Any]]:
        """
        Suggère des améliorations pour une configuration.

        Args:
            compose_config: Configuration à analyser
            provider: Provider LLM à utiliser (optionnel)

        Returns:
            Liste de suggestions d'amélioration

        Raises:
            RuntimeError: Si le service est désactivé
        """
        if not self.enabled:
            raise RuntimeError("LiteLLM service is not enabled")

        provider = provider or self.default_provider

        logger.info(f"Suggesting improvements with {provider}")

        prompt = self._build_improvement_prompt(compose_config)
        response = await self._call_llm(prompt, provider)

        # Format des suggestions
        return self._parse_suggestions(response)

    def _build_compose_prompt(
        self, description: str, requirements: Optional[Dict[str, Any]]
    ) -> str:
        """Construit le prompt pour la génération de Docker Compose."""
        prompt = f"""Generate a Docker Compose configuration for the following:

Description: {description}
"""
        if requirements:
            prompt += f"\nRequirements: {requirements}"

        prompt += "\n\nProvide a valid Docker Compose YAML configuration."
        return prompt

    def _build_optimization_prompt(
        self, compose_config: Dict[str, Any], target_type: str
    ) -> str:
        """Construit le prompt pour l'optimisation de ressources."""
        return f"""Optimize the following Docker Compose configuration for {target_type}:

Configuration: {compose_config}

Focus on:
- Resource limits (CPU, memory)
- Health checks
- Restart policies
- Network optimization
- Security best practices

Provide the optimized configuration."""

    def _build_diagnostic_prompt(
        self, error_message: str, context: Optional[Dict[str, Any]]
    ) -> str:
        """Construit le prompt pour le diagnostic d'erreurs."""
        prompt = f"""Diagnose the following error:

Error: {error_message}
"""
        if context:
            prompt += f"\nContext: {context}"

        prompt += """

Provide:
1. Root cause analysis
2. Step-by-step solution
3. Prevention tips
"""
        return prompt

    def _build_improvement_prompt(self, compose_config: Dict[str, Any]) -> str:
        """Construit le prompt pour les suggestions d'amélioration."""
        return f"""Analyze this Docker Compose configuration and suggest improvements:

Configuration: {compose_config}

Focus on:
- Security vulnerabilities
- Performance optimization
- Best practices compliance
- Scalability issues

Provide specific, actionable suggestions."""

    async def _call_llm(self, prompt: str, provider: LLMProvider) -> Dict[str, Any]:
        """
        Appelle le LLM provider sélectionné.

        Args:
            prompt: Prompt à envoyer au LLM
            provider: Provider à utiliser

        Returns:
            Réponse du LLM

        Note:
            Cette méthode est actuellement une simulation.
            L'intégration réelle avec litellm.completion() sera ajoutée
            quand la dépendance litellm sera installée.
        """
        # Vérification du cache unifié (STORY-168) — clé hashée : le
        # prompt ne figure JAMAIS en clair dans la clé (règles 40).
        cache_key = self._cache_key(prompt, provider)
        cache = await get_cache()
        cached = await cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for prompt with {provider}")
            return dict(cached, cached=True)

        response = await self._generate_llm_response(prompt, provider)

        # Mise en cache (TTL borné — plus de fuite mémoire)
        await cache.set(cache_key, response, ttl=LLM_CACHE_TTL)

        return response

    async def _generate_llm_response(
        self, prompt: str, provider: LLMProvider
    ) -> Dict[str, Any]:
        """Produit la réponse du LLM (appel réel — simulation en attendant).

        Séparée du chemin cache de ``_call_llm`` pour rester testable et
        substituable (l'intégration litellm.completion() viendra ici).
        """

        # TODO: Intégrer avec litellm quand disponible
        # import litellm
        # response = await litellm.acompletion(
        #     model=self._get_model_name(provider),
        #     messages=[{"role": "user", "content": prompt}],
        #     temperature=0.7,
        #     max_tokens=2000
        # )

        # Simulation pour l'instant. NB : le prompt ne figure jamais dans
        # la réponse (donc ni dans la clé ni dans la valeur du cache —
        # règles 40 / AC 4, l'ancien extrait ``prompt[:100]`` a été retiré).
        logger.info(f"Calling {provider} LLM (simulated)")
        response = {
            "provider": provider.value,
            "model": self.default_model,
            "content": "Simulated LLM response - LiteLLM dependency not yet installed",
            "cached": False,
        }

        return response

    @staticmethod
    def _cache_key(prompt: str, provider: LLMProvider) -> str:
        """Construit la clé de cache hashée pour un couple (prompt, provider).

        ``llm:{sha256("{provider}:{prompt}")}`` — déterministe (hit stable)
        sans exposer le prompt en clair dans la clé (règles 40).
        """
        digest = hashlib.sha256(f"{provider.value}:{prompt}".encode()).hexdigest()
        return f"{LLM_CACHE_PREFIX}{digest}"

    def _get_model_name(self, provider: LLMProvider) -> str:
        """Retourne le nom du modèle pour le provider."""
        model_map = {
            LLMProvider.OPENAI: "gpt-4",
            LLMProvider.CLAUDE: "claude-3-opus-20240229",
            LLMProvider.OLLAMA: f"ollama/{self.default_model}",
        }
        return model_map.get(provider, self.default_model)

    def _parse_suggestions(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse les suggestions depuis la réponse LLM."""
        # TODO: Implémenter le parsing réel des suggestions
        return [
            {
                "category": "simulated",
                "priority": "high",
                "description": "Simulated suggestion",
                "implementation": response.get("content", ""),
            }
        ]

    async def clear_cache(self) -> None:
        """Vide le cache des réponses LLM (purge du préfixe, best-effort)."""
        cache = await get_cache()
        await cache.clear_prefix(LLM_CACHE_PREFIX)
        logger.info("LLM cache cleared")

    def get_available_providers(self) -> List[str]:
        """Retourne la liste des providers disponibles."""
        available: List[str] = []
        if self.openai_api_key:
            available.append(LLMProvider.OPENAI.value)
        if self.anthropic_api_key:
            available.append(LLMProvider.CLAUDE.value)
        # Ollama est toujours disponible (local)
        available.append(LLMProvider.OLLAMA.value)
        return available
