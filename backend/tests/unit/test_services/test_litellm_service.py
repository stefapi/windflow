"""Tests unitaires du service LiteLLM (STORY-168 — aucun test n'existait).

Couverture ciblée cache unifié :
- hit/miss du cache sur ``generate_docker_compose`` (provider mocké) ;
- TTL expiré → régénération (miss) ;
- ``clear_cache()`` purge le préfixe ``llm:`` ;
- **sécurité (rules 40 / AC 4)** : la clé de cache ne contient jamais le
  prompt en clair (hash sha256), la valeur non plus.
"""

import logging
from unittest.mock import patch

import pytest

from app.core import cache as cache_module
from app.core.cache import MemoryCache, get_cache, reset_cache
from app.services.litellm_service import (
    LLM_CACHE_PREFIX,
    LLM_CACHE_TTL,
    LiteLLMService,
    LLMProvider,
)


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Cache unifié vierge (mode mémoire forcé) autour de chaque test."""
    reset_cache()
    with patch.object(cache_module.settings, "cache_url", None), patch.object(
        cache_module.settings, "rate_limit_storage_url", None
    ):
        yield
    reset_cache()


@pytest.fixture
def service() -> LiteLLMService:
    """Service activé sur Ollama (aucune clé API requise)."""
    return LiteLLMService(enabled=True, default_provider=LLMProvider.OLLAMA)


PROMPT_TEXT = "Un serveur web nginx avec TLS"


def _keys_in_cache() -> list:
    """Liste les clés présentes dans le cache mémoire singleton."""
    instance = cache_module._cache
    assert isinstance(instance, MemoryCache)
    return list(instance._store.keys())


class TestGenerateDockerComposeCache:
    """Cache unifié du chemin generate_docker_compose."""

    @pytest.mark.asyncio
    async def test_first_call_misses_and_populates_cache(self, service):
        """Premier appel : miss → génération + entrée llm:* posée."""
        result = await service.generate_docker_compose(PROMPT_TEXT)
        assert result["provider"] == "ollama"
        keys = _keys_in_cache()
        assert len([k for k in keys if k.startswith(LLM_CACHE_PREFIX)]) == 1

    @pytest.mark.asyncio
    async def test_second_call_hits_cache_without_llm_call(self, service):
        """Hit : 2e appel servi depuis le cache, génération LLM non réexécutée."""
        first = await service.generate_docker_compose(PROMPT_TEXT)

        with patch.object(
            service,
            "_generate_llm_response",
            side_effect=AssertionError("should hit cache"),
        ):
            second = await service.generate_docker_compose(PROMPT_TEXT)

        assert second["content"] == first["content"]
        assert second["cached"] is True  # marqué servi du cache

    @pytest.mark.asyncio
    async def test_expired_ttl_triggers_regeneration(self, service):
        """TTL expiré → miss → régénération (l'entrée expire au tick)."""
        await service.generate_docker_compose(PROMPT_TEXT)

        # Simule l'expiration de toutes les entrées llm:
        instance = cache_module._cache
        assert isinstance(instance, MemoryCache)
        for key, (value, expires_at) in list(instance._store.items()):
            instance._store[key] = (value, expires_at - LLM_CACHE_TTL - 10)

        regenerated = await service.generate_docker_compose(PROMPT_TEXT)
        assert regenerated["cached"] is False  # nouvelle génération

    @pytest.mark.asyncio
    async def test_distinct_prompts_have_distinct_keys(self, service):
        """Deux prompts distincts → deux entrées distinctes."""
        await service.generate_docker_compose(PROMPT_TEXT)
        await service.generate_docker_compose("Une base PostgreSQL avec backup")
        llm_keys = [k for k in _keys_in_cache() if k.startswith(LLM_CACHE_PREFIX)]
        assert len(llm_keys) == 2

    @pytest.mark.asyncio
    async def test_clear_cache_purges_llm_prefix_only(self, service):
        """clear_cache purge le préfixe llm:, épargne les autres clés."""
        await service.generate_docker_compose(PROMPT_TEXT)
        cache = await get_cache()
        await cache.set("rbac:role:someone", "admin", ttl=300)

        await service.clear_cache()

        remaining = _keys_in_cache()
        assert not [k for k in remaining if k.startswith(LLM_CACHE_PREFIX)]
        assert "rbac:role:someone" in remaining


class TestLLMCacheSecurity:
    """Sécurité (rules 40 / AC 4) — jamais de prompt en clair."""

    def test_cache_key_is_hashed_and_deterministic(self):
        """Clé = llm:{sha256(provider:prompt)} : hashée, déterministe."""
        key1 = LiteLLMService._cache_key(PROMPT_TEXT, LLMProvider.OLLAMA)
        key2 = LiteLLMService._cache_key(PROMPT_TEXT, LLMProvider.OLLAMA)
        assert key1 == key2  # déterministe (hit stable)
        assert key1.startswith("llm:")
        digest = key1[len(LLM_CACHE_PREFIX) :]
        assert len(digest) == 64  # sha256 hex
        assert PROMPT_TEXT not in key1  # jamais de prompt en clair dans la clé

    def test_cache_key_varies_by_provider(self):
        """Le provider participe au hash (réponses par provider distinctes)."""
        key_ollama = LiteLLMService._cache_key(PROMPT_TEXT, LLMProvider.OLLAMA)
        key_openai = LiteLLMService._cache_key(PROMPT_TEXT, LLMProvider.OPENAI)
        assert key_ollama != key_openai

    @pytest.mark.asyncio
    async def test_cache_key_and_value_do_not_leak_prompt(self, service):
        """AC 4 : le prompt n'apparaît ni dans les clés ni dans les valeurs."""
        await service.generate_docker_compose(PROMPT_TEXT)

        instance = cache_module._cache
        assert isinstance(instance, MemoryCache)
        for key, (value, _) in instance._store.items():
            assert PROMPT_TEXT not in key, f"prompt leaked in key: {key}"
            assert PROMPT_TEXT not in str(value), f"prompt leaked in value: {value!r}"

    @pytest.mark.asyncio
    async def test_cache_entry_has_bounded_ttl(self, service):
        """TTL borné : l'entrée expire (LLM_CACHE_TTL, pas de permanence)."""
        await service.generate_docker_compose(PROMPT_TEXT)
        instance = cache_module._cache
        assert isinstance(instance, MemoryCache)
        for _, (_, expires_at) in instance._store.items():
            assert expires_at != float("inf")  # jamais permanent


class TestOtherLlmMethodsCache:
    """Autres méthodes LLM : mêmes garanties cache + comportement."""

    @pytest.mark.asyncio
    async def test_optimize_resources_uses_cache(self, service):
        """optimize_resources : 2e appel servi du cache (génération unique)."""
        first = await service.optimize_resources({"services": {}}, "docker")
        with patch.object(
            service,
            "_generate_llm_response",
            side_effect=AssertionError("should hit cache"),
        ):
            second = await service.optimize_resources({"services": {}}, "docker")
        assert second["content"] == first["content"]
        assert second["cached"] is True

    @pytest.mark.asyncio
    async def test_diagnose_error_uses_cache(self, service):
        """diagnose_error : cache hit au 2e appel."""
        await service.diagnose_error("Connection refused")
        with patch.object(
            service,
            "_generate_llm_response",
            side_effect=AssertionError("should hit cache"),
        ):
            result = await service.diagnose_error("Connection refused")
        assert result["cached"] is True

    @pytest.mark.asyncio
    async def test_suggest_improvements_parses_response(self, service):
        """suggest_improvements : réponse LLM parsée en liste de suggestions."""
        suggestions = await service.suggest_improvements({"services": {}})
        assert isinstance(suggestions, list)
        assert suggestions[0]["category"] == "simulated"
        assert suggestions[0]["implementation"]  # contenu de la réponse LLM

    @pytest.mark.asyncio
    async def test_disabled_raises_on_optimize_and_diagnose(self):
        """Service désactivé → RuntimeError sur chaque méthode générative."""
        service = LiteLLMService(enabled=False)
        with pytest.raises(RuntimeError, match="not enabled"):
            await service.optimize_resources({}, "docker")
        with pytest.raises(RuntimeError, match="not enabled"):
            await service.diagnose_error("err")
        with pytest.raises(RuntimeError, match="not enabled"):
            await service.suggest_improvements({})

    def test_model_name_mapping_per_provider(self, service):
        """_get_model_name : mapping par provider (ollama préfixé)."""
        from app.services.litellm_service import LLMProvider

        assert service._get_model_name(LLMProvider.OPENAI) == "gpt-4"
        assert service._get_model_name(LLMProvider.CLAUDE) == "claude-3-opus-20240229"
        assert service._get_model_name(LLMProvider.OLLAMA) == "ollama/llama2"

    def test_available_providers_with_api_keys(self):
        """Clés API fournies → providers openai/claude listés."""
        service = LiteLLMService(
            enabled=True,
            openai_api_key="sk-test",
            anthropic_api_key="sk-ant-test",
        )
        providers = service.get_available_providers()
        assert "openai" in providers
        assert "claude" in providers
        assert "ollama" in providers

    def test_validation_warns_when_api_key_missing(self, caplog):
        """Provider cloud sans clé API → warning de configuration."""
        with caplog.at_level(logging.WARNING):
            LiteLLMService(enabled=True, default_provider=LLMProvider.OPENAI)
        assert any("API key" in r.getMessage() for r in caplog.records)


class TestServiceBasics:
    """Comportements de base non-régressés du service."""

    @pytest.mark.asyncio
    async def test_disabled_service_raises_on_generate(self):
        """Service désactivé → RuntimeError explicite."""
        service = LiteLLMService(enabled=False)
        with pytest.raises(RuntimeError, match="not enabled"):
            await service.generate_docker_compose("x")

    def test_available_providers_always_include_ollama(self, service):
        """Ollama local toujours disponible (sans clés API)."""
        providers = service.get_available_providers()
        assert "ollama" in providers
