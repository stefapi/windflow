# Chapitre 18 — Plugins IA

> **Statut** : Spec cible · **Public** : Utilisateurs avancés, développeurs de plugins · **Lié à** : [11-plugins.md](11-plugins.md), [12-marketplace.md](12-marketplace.md), [15-securite.md](15-securite.md)

## Vue d'ensemble

Ce chapitre spécifie les capacités d'intelligence artificielle de WindFlow, fournies par les **plugins IA** — ce n'est pas une fonctionnalité du core. L'IA dans WindFlow est un assistant, pas un pilier : WindFlow fonctionne parfaitement sans aucun plugin IA. Elle est là pour ceux qui veulent aller plus vite — générer un docker-compose au lieu de l'écrire, diagnostiquer une erreur à partir de logs, obtenir des suggestions d'optimisation.

### Plugins IA disponibles

| Plugin | Description | Prérequis |
|--------|-------------|-----------|
| **Ollama** | LLM local — pas de clé API, tout tourne sur la machine | ≥ 8 Go RAM, GPU recommandé |
| **LiteLLM** | Proxy multi-provider — APIs cloud (OpenAI, Anthropic, etc.) | Clé API du provider choisi |

Les deux plugins peuvent être installés ensemble : Ollama pour le local/hors-ligne, LiteLLM pour les tâches complexes nécessitant un modèle plus puissant.

### Ce que l'IA peut faire

- **Générer un docker-compose** à partir d'une description en langage naturel ;
- **Diagnostiquer des erreurs** : analyser les logs d'un déploiement raté et suggérer un correctif ;
- **Suggérer des optimisations** : ajustements de ressources (CPU, RAM) basés sur l'usage ;
- **Chat assistant** intégré à l'UI pour poser des questions sur l'infrastructure ;
- **Suggestions de sécurité** : analyser une configuration et signaler les problèmes potentiels.

### Ce que l'IA ne fait pas

- l'IA ne prend pas de décisions automatiquement — elle suggère, l'utilisateur valide ;
- l'IA n'a pas accès aux secrets, mots de passe ou données sensibles ;
- l'IA ne modifie pas les configurations déployées sans action explicite de l'utilisateur.

## Prérequis et compatibilité

### Plugin Ollama (LLM local)

Ollama fait tourner un modèle de langage directement sur la machine — la solution la plus souveraine (pas de clé API, pas de dépendance cloud), mais gourmande en ressources.

| Ressource | Minimum | Recommandé |
|-----------|---------|------------|
| RAM | 8 Go (modèles 7B) | 16 Go (modèles 13B+) |
| CPU | 4 cores | 8 cores ou GPU |
| Stockage | 5 Go par modèle | 20 Go pour plusieurs modèles |

**Compatibilité ARM** : Ollama supporte ARM64 (Raspberry Pi 5 avec 8 Go, Orange Pi 5). Sur un RPi 4, c'est trop juste — préférer LiteLLM avec une API cloud.

**Modèles recommandés pour WindFlow :**

| Modèle | Taille | RAM nécessaire | Usage |
|--------|--------|----------------|-------|
| `llama3.2:3b` | 2 Go | 4 Go | Chat rapide, questions simples |
| `llama3.1:8b` | 4.7 Go | 8 Go | Génération de configs, diagnostic |
| `codellama:13b` | 7 Go | 16 Go | Génération de compose complexes |
| `mistral:7b` | 4.1 Go | 8 Go | Bon compromis général |

### Plugin LiteLLM (APIs cloud)

LiteLLM est un proxy qui connecte WindFlow à des APIs de LLM cloud. Il nécessite une clé API mais ne consomme quasiment pas de ressources locales (~50 Mo RAM) — c'est l'option pour les Raspberry Pi.

**Providers supportés** : OpenAI (GPT-4o, GPT-4o-mini), Anthropic (Claude 4 Sonnet/Haiku), Google (Gemini), Groq (Llama, Mixtral — rapide et économique), Mistral AI (Mistral Large/Small).

## Installation et configuration

```bash
# Installer Ollama (grammaire normalisée, chapitre 10)
windflow plugins install ollama
windflow plugins config ollama --set default_model=llama3.1:8b

# Installer LiteLLM
windflow plugins install litellm
windflow plugins config litellm --set provider=openai --set api_key=sk-...
# ou avec Anthropic
windflow plugins config litellm --set provider=anthropic --set api_key=sk-ant-...
```

Ou depuis l'UI : **Marketplace → IA → Ollama / LiteLLM → Installer**. Le plugin Ollama déploie un container et télécharge le modèle par défaut (quelques minutes selon la connexion) ; le wizard LiteLLM demande le provider et la clé API.

**Les deux ensemble** : WindFlow utilise par défaut le modèle local (Ollama) pour les tâches simples et bascule sur LiteLLM (API cloud) pour les tâches complexes — comportement configurable :

```yaml
# windflow plugins config ai — routage combiné
routing:
  simple_tasks: "ollama"       # Questions simples → modèle local
  complex_tasks: "litellm"     # Génération complexe → API cloud
  fallback: "litellm"          # Si Ollama est surchargé → API cloud
```

## Fonctionnalités IA

### Génération de docker-compose

L'utilisateur décrit ce qu'il veut en langage naturel ; l'IA génère un docker-compose.yml complet. Depuis l'UI : bouton « Générer avec l'IA » dans l'éditeur de stacks. Depuis la CLI :

```bash
windflow ai generate "Un blog WordPress avec une base de données MySQL et phpMyAdmin"
```

Exemple illustratif — prompt interne (contextualisé, jamais envoyé brut) :

```python
COMPOSE_GENERATOR_PROMPT = """
Tu es un assistant spécialisé dans la création de fichiers docker-compose.yml.

Contexte WindFlow :
- Host cible : {host_arch} ({host_os})
- Ressources disponibles : {available_cpu} CPU, {available_ram} Mo RAM
- Plugins installés : {installed_plugins}

Règles :
- Images multi-arch (arm64 + amd64) quand possible
- Health checks sur chaque service ; volumes nommés pour la persistance
- Mots de passe générés aléatoirement
- Si le plugin Traefik est installé, ajouter les labels Traefik

Demande utilisateur : {user_description}
"""
```

**Résultat** : le compose est proposé dans l'éditeur ; l'utilisateur peut le modifier avant de déployer. **Rien n'est déployé automatiquement.**

### Diagnostic d'erreurs

Quand un déploiement échoue, l'IA analyse les logs et la configuration pour identifier la cause et proposer une solution. Depuis l'UI : bouton « Diagnostiquer avec l'IA » sur un déploiement en erreur. Le résultat s'affiche en encart avec la cause probable, les étapes de correction et la prévention — applicable ou ignorable par l'utilisateur.

### Chat assistant

Un chat intégré à l'UI (page « Assistant IA » ajoutée par les plugins) permet de poser des questions sur l'infrastructure gérée : « Combien de RAM utilise ma stack Nextcloud ? », « Pourquoi mon container redémarre en boucle ? ». Le chat a accès au contexte de l'instance (Hosts, Apps, stacks, plugins, logs récents) **mais pas aux secrets**. Contrat d'intégration UI de cette page : Écran 26 du chapitre [14-ui-maquettes.md](14-ui-maquettes.md).

### Suggestions de sécurité

L'IA peut auditer une stack et signaler les problèmes courants : containers en root sans nécessité, ports exposés inutilement sur `0.0.0.0`, secrets en clair dans les variables d'environnement, images sans tag fixe (`:latest`), absence de health checks, volumes montés en lecture-écriture quand la lecture seule suffit. Depuis l'UI : bouton « Audit sécurité » sur une stack → recommandations triées par sévérité.

### Suggestions d'optimisation

Pour les stacks en production, l'IA analyse l'utilisation des ressources et propose des ajustements (ex. réduire une limite RAM surestimée pour libérer de la mémoire). Cette fonctionnalité nécessite un historique de métriques — elle fonctionne mieux avec un plugin de monitoring installé (Netdata, Prometheus — chapitre [12-marketplace.md](12-marketplace.md)).

## Architecture technique

### Diagramme — Intégration des plugins IA au core

```mermaid
flowchart LR
    subgraph CoreWindFlow
        UI["UI chat, boutons IA"]
        API["API /plugins/ai/..."]
        Events["Bus d'événements"]
    end

    subgraph PluginOllama
        OllamaContainer["Container Ollama"]
        OllamaExt["Extension API"]
    end

    subgraph PluginLiteLLM
        LiteLLMContainer["Container LiteLLM"]
        LiteLLMExt["Extension API"]
    end

    UI --> API
    API --> OllamaExt
    API --> LiteLLMExt
    OllamaExt --> OllamaContainer
    LiteLLMExt --> LiteLLMContainer

    Events -. deployment.failed .-> OllamaExt
    Events -. deployment.failed .-> LiteLLMExt
```

Les plugins IA sont des **hybrid plugins** (chapitre [11-plugins.md](11-plugins.md)) : ils déploient un container (Ollama ou LiteLLM) **et** ajoutent endpoints API + composants UI au core.

### Endpoints API ajoutés

```
POST   /api/v1/plugins/ai/generate     # Générer un docker-compose
POST   /api/v1/plugins/ai/diagnose     # Diagnostiquer une erreur
POST   /api/v1/plugins/ai/chat         # Chat assistant
POST   /api/v1/plugins/ai/audit        # Audit sécurité
POST   /api/v1/plugins/ai/optimize     # Suggestions d'optimisation
GET    /api/v1/plugins/ai/models       # Lister les modèles disponibles
PUT    /api/v1/plugins/ai/config       # Configurer provider/modèle par défaut
```

Ces routes héritent de l'authentification JWT et du RBAC du core (chapitre [08-rbac-permissions.md](08-rbac-permissions.md)).

### Service LLM et cache des réponses

Les réponses de génération et de diagnostic sont mises en cache (hash du prompt, TTL 24 h) via le cache du core — Redis en mode standard, mémoire en mode léger — pour éviter de re-solliciter le LLM à l'identique.

Exemple illustratif — appel au modèle configuré :

```python
class LLMService:
    """Service LLM utilisé par les plugins IA."""

    async def complete(self, system_prompt: str, user_message: str) -> str:
        """Envoie une requête au LLM configuré (Ollama ou provider cloud)."""
        response = await acompletion(
            model=f"ollama/{self.model}" if self.provider == "ollama" else self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        return response.choices[0].message.content
```

## Configuration

```yaml
# Plugin Ollama — UI : Plugins > Ollama > Configuration
default_model: "llama3.1:8b"
gpu_enabled: false
max_concurrent_requests: 2
pull_models_on_install:
  - "llama3.1:8b"

# Plugin LiteLLM — UI : Plugins > LiteLLM > Configuration
provider: "openai"              # openai, anthropic, groq, mistral, google
api_key: "sk-..."              # Stockée chiffrée (chapitre 15)
default_model: "gpt-4o-mini"
fallback_model: "gpt-4o"
max_tokens: 2000
monthly_budget_usd: 10.0        # 0 = illimité
```

## Limites et considérations

### Qualité des réponses

Les LLM peuvent générer des configurations incorrectes ou des diagnostics erronés. WindFlow affiche toujours les suggestions dans un éditeur modifiable — l'utilisateur doit vérifier avant d'appliquer. Pour la génération de compose, WindFlow valide la syntaxe YAML et l'existence des images référencées ; la logique de la configuration (bons ports, bonnes variables) reste de la responsabilité de l'utilisateur.

### Vie privée

- **Ollama** : tout tourne en local, aucune donnée ne quitte la machine.
- **LiteLLM** : les prompts sont envoyés au provider cloud choisi ; les logs et configurations de l'infrastructure sont inclus dans les prompts de diagnostic. Si c'est un problème, utiliser Ollama uniquement.

Les secrets (mots de passe, clés API, tokens) ne sont **jamais** inclus dans les prompts envoyés au LLM — WindFlow les masque automatiquement (chapitre [15-securite.md](15-securite.md)).

### Performance sur ARM

- Ollama sur Raspberry Pi 5 (8 Go) : fonctionne avec des modèles 3B-7B, temps de réponse de 10-30 secondes ;
- Ollama sur Raspberry Pi 4 : non recommandé (trop lent, risque de OOM) ;
- LiteLLM fonctionne sur n'importe quelle machine (simple proxy HTTP).

## Voir aussi

- [11-plugins.md](11-plugins.md) — système de plugins dont les plugins IA sont des instances
- [12-marketplace.md](12-marketplace.md) — fiches marketplace des plugins IA
- [17-automatisation-workflows.md](17-automatisation-workflows.md) — automatisation, où le diagnostic IA peut s'insérer via n8n
- [15-securite.md](15-securite.md) — masquage des secrets et chiffrement des clés API
- [../Roadmap.md](../Roadmap.md) — feuille de route (plugins IA en phase finale)
