# WindFlow - Règles de Développement

Le répertoire `.clinerules` contient **uniquement les règles de développement concrètes** pour le projet WindFlow.

## Séparation des Responsabilités

### 📚 Memory Bank (`memory-bank/`)
Contient le **contexte du projet et l'état actuel** :
- `projectbrief.md` : Vue d'ensemble et objectifs du projet
- `productContext.md` : Problèmes résolus et utilisateurs cibles
- `activeContext.md` : État actuel et prochaines étapes
- `systemPatterns.md` : Patterns architecturaux et décisions techniques
- `techContext.md` : Technologies utilisées et environnement de développement
- `progress.md` : État d'avancement et métriques

### 📋 Règles de Développement (`.clinerules/`)
Contient **les conventions de code et bonnes pratiques** :
- Règles de développement spécifiques par technologie
- Conventions de nommage et formatage
- Patterns de code et structures
- Outils et workflows de développement

## Organisation des Fichiers

### 🐍 [backend.md](backend.md) - Règles Backend
Règles spécifiques au développement backend FastAPI :
- **Stack Technologique** : FastAPI, SQLAlchemy 2.0, Pydantic V2, Celery
- **Architecture des Services** : Structure des répertoires, patterns
- **Conventions Python** : Type hints obligatoires, docstrings Google Style
- **Gestion des Erreurs** : Exceptions personnalisées, middleware
- **Modèles de Données** : SQLAlchemy 2.0, Pydantic V2 schemas
- **Services** : Pattern Repository, Dependency Injection
- **Tâches Asynchrones** : Configuration Celery, retry policies
- **Configuration** : Variables d'environnement, settings centralisés
- **Logging** : Structuré JSON, contexte métier
- **Tests** : pytest, fixtures, couverture
- **Performance** : Métriques Prometheus, monitoring

### 🖥️ [frontend.md](frontend.md) - Règles Frontend
Règles spécifiques au développement frontend Vue.js 3 :
- **Stack Technologique** : Vue.js 3, TypeScript strict, Element Plus, UnoCSS
- **Architecture des Composants** : Structure des répertoires, composables
- **Conventions TypeScript** : Types stricts, configuration stricte
- **Composition API** : Structure des composables, conventions composants
- **Gestion d'État** : Pinia stores, persistence, réactivité
- **Services API** : HTTP client, interceptors, gestion erreurs
- **Routing** : Vue Router, guards, navigation
- **Styling** : UnoCSS, conventions CSS, responsive
- **Tests** : Vitest unitaires, Playwright E2E
- **Performance** : Lazy loading, optimisations, code splitting

### ⌨️ [cli.md](cli.md) - Règles CLI/TUI
Règles spécifiques au développement de l'interface CLI/TUI :
- **Stack Technologique** : Rich, Typer, Textual, argparse, python-dotenv
- **Architecture des Services** : Services modulaires, parsers hiérarchiques
- **Conventions CLI** : Commandes type-safe, gestion d'erreurs standardisée
- **Interface TUI** : Textual, écrans structurés, widgets personnalisés
- **Configuration** : Hiérarchique, variables d'environnement, fichiers config
- **Gestion de Session** : Authentification, état persistant, tokens
- **Tests** : Tests CLI avec Typer testing, tests TUI avec Textual
- **Auto-complétion** : Scripts bash/zsh/fish, complétion dynamique
- **Plugins** : Système extensible, découverte automatique, enregistrement

### 🧪 [testing.md](testing.md) - Règles de Test
Règles spécifiques aux tests et à la qualité du code :
- **Stratégie de Tests** : Pyramide des tests, couverture minimale, niveaux de validation
- **Outils Backend** : pytest, fixtures, mocks, tests async, SQLAlchemy test
- **Outils Frontend** : Vitest, Vue Test Utils, mocks MSW, composants
- **Tests E2E** : Playwright, workflows complets, scénarios utilisateur
- **Tests API** : FastAPI TestClient, mocks services externes, intégration
- **Structure Répertoires** : Organisation unit/integration/e2e, fixtures
- **Performance** : Tests de charge, métriques, benchmarks
- **CI/CD** : GitHub Actions, rapports coverage, validation automatique

### 🏗️ [infrastructure.md](infrastructure.md) - Règles d'Infrastructure
Règles spécifiques à l'infrastructure et aux fichiers annexes :
- **Organisation Hiérarchique** : Structure des répertoires racine et dev/
- **Makefile** : Orchestrateur principal avec sections organisées et commandes standardisées
- **Docker** : Images multi-stage, compose modulaire, configurations environnement
- **Scripts** : Automatisation setup/génération/validation/déploiement
- **Templates** : Génération automatique backend/frontend/infrastructure/documentation
- **Configuration** : Variables d'environnement, monitoring, validation qualité
- **Conventions** : Nommage fichiers, structure package.json, pre-commit hooks

### 🤖 [ai-guidelines.md](ai-guidelines.md) - Règles d'Utilisation de l'IA
Règles spécifiques à l'utilisation de l'intelligence artificielle dans WindFlow :
- **Philosophie IA** : IA collaborative, validation humaine, transparence
- **Intégration LLM** : LiteLLM multi-provider, configuration Ollama/OpenAI
- **Patterns de Code** : Génération assistée backend/frontend/CLI
- **Optimisation Déploiements** : IA pour Kubernetes, Docker Compose intelligent
- **Code Review** : Assistant IA pour review automatisé, suggestions d'amélioration
- **Sécurité** : Validation des sorties IA, filtrage de contenu
- **Monitoring** : Métriques IA, performance LLM, audit trail
- **Bonnes Pratiques** : Guidelines, limitations, configuration CI/CD

## Application des Règles

### Processus de Développement
1. **Lecture obligatoire** des règles avant tout développement
2. **Respect strict** des conventions définies
3. **Validation automatique** via pre-commit hooks
4. **Review** systématique du respect des règles en code review

### Outils de Validation
- **Pre-commit hooks** : Formatage, linting, type checking
- **CI/CD Pipeline** : Tests, sécurité, qualité de code
- **Monitoring** : Respect des patterns de performance
- **Documentation** : Génération automatique depuis le code

### Évolution des Règles
- **Mise à jour régulière** basée sur les retours d'expérience
- **Discussions d'équipe** pour les changements majeurs
- **Versioning** des règles avec changelog
- **Formation** continue sur les bonnes pratiques

## Guides de Référence Rapide

### 🚀 Démarrage Rapide - Nouveau Développeur
1. Lire [general.md](general.md) pour comprendre la philosophie du projet
2. Configurer l'environnement selon le stack choisi (backend/frontend)
3. Installer les pre-commit hooks et outils de validation
4. Créer un premier commit respectant les conventions

### 🔧 Configuration IDE
#### PyCharm (Backend)
- Plugin Python Type Checker (mypy)
- Plugin pre-commit
- Configuration Black formatter
- Configuration pytest runner

#### VS Code (Frontend)
- Extension Vue Language Features (Volar)
- Extension TypeScript strict mode
- Extension UnoCSS IntelliSense
- Extension Vitest runner

### 📚 Ressources Complémentaires
- [Documentation Projet](../doc/general_specs/README.md) - Spécifications complètes
- [Architecture](../doc/general_specs/02-architecture.md) - Principes architecturaux
- [Stack Technologique](../doc/general_specs/03-technology-stack.md) - Technologies détaillées
- [Guide de Déploiement](../doc/general_specs/15-deployment-guide.md) - Installation

## Exemples Pratiques

### Création d'un Nouveau Service Backend
```python
# 1. Structure de fichier respectant les conventions
# windflow/services/deployment_service.py

from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

class DeploymentService:
    """Service de gestion des déploiements.
    
    Respecte les patterns Repository et Dependency Injection
    définis dans backend.md.
    """
    
    async def create_deployment(
        self,
        deployment_data: DeploymentCreate,
        user_id: UUID,
        db: AsyncSession
    ) -> DeploymentResponse:
        """Crée un nouveau déploiement avec validation métier."""
        # Implémentation suivant les règles backend
```

### Création d'un Nouveau Composant Frontend
```vue
<!-- Composant respectant les conventions frontend -->
<template>
  <div class="deployment-card card">
    <!-- Structure Element Plus + UnoCSS -->
  </div>
</template>

<script setup lang="ts">
// Types stricts obligatoires
interface Props {
  deployment: Deployment
}

interface Emits {
  'action': [id: string]
}

// Composition API avec readonly exports
const props = defineProps<Props>()
const emit = defineEmits<Emits>()
</script>
```

---

**Version des règles :** 1.0  
**Dernière mise à jour :** 29/09/2025  
**Auteur :** Équipe WindFlow

Ces règles évoluent avec le projet et sont mises à jour régulièrement pour refléter les meilleures pratiques et les retours d'expérience de l'équipe.
