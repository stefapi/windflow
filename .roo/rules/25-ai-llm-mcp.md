# 25 — IA, LLM et outils d'agent

## 1. Place de l'IA dans le produit

- L'IA dans WindFlow est un assistant, pas un pilier : le produit fonctionne parfaitement sans plugin IA (spécification `docs/general_specs/18-plugins-ia.md`). Les plugins IA (Ollama local, LiteLLM multi-provider) sont optionnels et installables ensemble.
- **Ce que l'IA fait** : générer un docker-compose depuis une description en langage naturel, diagnostiquer des erreurs de déploiement à partir des logs, suggérer des optimisations de ressources, chat assistant sur l'infrastructure, suggestions de sécurité.
- **Ce que l'IA ne fait jamais** : prendre des décisions automatiquement (elle suggère, l'utilisateur valide) ; accéder aux secrets, mots de passe ou données sensibles ; modifier une configuration déployée sans action explicite de l'utilisateur.

## 2. Accès aux modèles

- Abstraction unique : `backend/app/services/litellm_service.py` sur LiteLLM `^1.79.0` (multi-provider, fallback provider, cache LLM STORY-168).
- **Interdit** : appeler directement un provider LLM (SDK OpenAI/Anthropic/…) en contournant la gateway LiteLLM ; mettre une clé de provider dans le code, les tests, les logs ou une URL (`40` §5) ; les clés passent par la configuration (`07` §5).
- Le cache LLM suit le cache unifié (`get_cache()`, STORY-168) : Redis si configuré, sinon mémoire locale bornée.
- Fournisseur indisponible : relances puis bascule selon la configuration ; jamais d'abandon silencieux présenté comme un résultat.

## 3. Prompts, données et journalisation

- Minimisation : n'envoyer que le contexte utile (logs pertinents, description de stack), jamais de secrets ni d'identifiants d'infrastructure (`40` §6).
- Chaque appel IA est journalisé (utilisateur, provider, modèle, durée, résultat) sans données sensibles ; la consommation peut être mesurée via les métriques `windflow_*` (`45` §4).
- Les sorties de modèle sont des **suggestions** : affichées comme telles dans l'UI, jamais appliquées sans validation explicite de l'utilisateur.

## 4. Agents de développement

- Leur comportement est fixé par ce corpus (`.roo/rules/`, `.roo/rules-<mode>/`) et les skills de `.agents/skills/`.
- Ils n'accèdent qu'au dépôt et à l'environnement de développement, avec des données fictives. **Interdit** : se connecter à la production ; lire un chemin exclu par `.rooignore` ; configurer un serveur MCP (`.roo/mcp.json`) qui donne accès à des données réelles ou sensibles.
- `.rooignore` limite ce que l'agent lit, mais ce n'est pas une frontière de sécurité : les données réelles ne sont jamais placées dans l'espace de travail.
- Les serveurs MCP déclarés dans `.roo/mcp.json` restent limités aux outils de développement (base de dev, documentation) et ne servent jamais de canal vers des données de production.
