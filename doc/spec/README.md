# WindFlow - Spécifications Techniques

Documentation technique complète du projet WindFlow, un outil web intelligent de déploiement de containers Docker sur des machines cibles.

## Structure de la Documentation

### 📋 Documents de Vue d'Ensemble
- **[01-overview.md](01-overview.md)** - Vue générale du projet, objectifs, proposition de valeur
- **[02-architecture.md](02-architecture.md)** - Architecture générale et principes de conception  
- **[03-technology-stack.md](03-technology-stack.md)** - Stack technologique détaillé par composant

### 🔧 Documents de Conception Technique
- **[04-data-model.md](04-data-model.md)** - Modèle de données, entités, relations (avec diagrammes Mermaid)
- **[05-authentication.md](05-authentication.md)** - Architecture d'authentification complète (SSO, 2FA, CLI, etc.)
- **[06-deployment-architecture.md](06-deployment-architecture.md)** - Architectures de déploiement (dev/prod/multi-cible)

### 🖥️ Documents d'Interfaces
- **[07-api-design.md](07-api-design.md)** - Conception des APIs REST et architecture backend
- **[08-cli-interface.md](08-cli-interface.md)** - Interface CLI/TUI complète avec tous les services
- **[09-web-interface.md](09-web-interface.md)** - Interface web Vue.js et composants

### ⚡ Documents de Fonctionnalités
- **[10-core-features.md](10-core-features.md)** - Fonctionnalités principales (DNS, orchestration, stacks)
- **[11-advanced-features.md](11-advanced-features.md)** - Fonctionnalités avancées (marketplace, backup, multi-tenant)
- **[12-integrations.md](12-integrations.md)** - Intégrations externes (CI/CD, monitoring, compliance)

### 🔒 Documents Opérationnels
- **[13-security.md](13-security.md)** - Sécurité, RBAC, audit, conformité
- **[14-testing-strategy.md](14-testing-strategy.md)** - Stratégies de tests et assurance qualité
- **[15-deployment-guide.md](15-deployment-guide.md)** - Guide de déploiement et configuration

### 📚 Documents de Référence
- **[16-workflows.md](16-workflows.md)** - Système de workflows et échange de données
- **[17-llm-integration.md](17-llm-integration.md)** - Intégration LiteLLM et intelligence artificielle
- **[18-roadmap.md](18-roadmap.md)** - Roadmap de développement et phases

## Navigation Rapide

### Par Public Cible

**👨‍💻 Développeurs**
- [Stack Technologique](03-technology-stack.md)
- [API Design](07-api-design.md)
- [Modèle de Données](04-data-model.md)
- [Stratégie de Tests](14-testing-strategy.md)

**🏗️ Architectes**  
- [Architecture Générale](02-architecture.md)
- [Architecture de Déploiement](06-deployment-architecture.md)
- [Sécurité](13-security.md)
- [Intégrations](12-integrations.md)

**⚙️ Ops/DevOps**
- [Guide de Déploiement](15-deployment-guide.md)
- [Interface CLI](08-cli-interface.md)
- [Fonctionnalités Principales](10-core-features.md)
- [Authentification](05-authentication.md)

**📊 Product Managers**
- [Vue d'Ensemble](01-overview.md)
- [Fonctionnalités Avancées](11-advanced-features.md)
- [Roadmap](18-roadmap.md)
- [Workflows](16-workflows.md)

### Par Cas d'Usage

**🚀 Démarrage Rapide**
1. [Vue d'Ensemble](01-overview.md) - Comprendre WindFlow
2. [Guide de Déploiement](15-deployment-guide.md) - Installation et configuration
3. [Interface Web](09-web-interface.md) - Utilisation de l'interface
4. [Fonctionnalités Principales](10-core-features.md) - Fonctionnalités essentielles

**🔧 Configuration Avancée**
1. [Architecture](02-architecture.md) - Principes de conception
2. [Stack Technologique](03-technology-stack.md) - Composants techniques
3. [Authentification](05-authentication.md) - Configuration SSO/2FA
4. [Sécurité](13-security.md) - Bonnes pratiques sécuritaires

**🏢 Déploiement Enterprise**
1. [Architecture de Déploiement](06-deployment-architecture.md) - Environnements de production
2. [Fonctionnalités Avancées](11-advanced-features.md) - Multi-tenant, backup, etc.
3. [Intégrations](12-integrations.md) - CI/CD, monitoring, compliance
4. [Interface CLI](08-cli-interface.md) - Automatisation avancée

## Conventions de Documentation

### Structure Standard
Chaque document suit une structure cohérente :
- **Vue d'ensemble** - Introduction et contexte
- **Architecture/Conception** - Design technique détaillé  
- **Spécifications** - Détails d'implémentation
- **Exemples pratiques** - Code et configurations
- **Références** - Liens vers documents connexes

### Diagrammes
- Diagrammes d'architecture en Mermaid
- Schémas de base de données
- Flux de données et séquences
- Diagrammes de déploiement

### Code et Configuration
- Exemples de code commentés
- Fichiers de configuration type
- Scripts d'installation
- Commandes CLI fréquentes

## Maintenance

Cette documentation est maintenue de façon modulaire :
- Chaque document peut être mis à jour indépendamment
- Les liens croisés permettent une navigation cohérente
- La structure facilite l'ajout de nouvelles sections
- Les exemples sont maintenus à jour avec les versions

---

**Version de la documentation :** 1.0  
**Dernière mise à jour :** 29/09/2025  
**Auteur :** Équipe WindFlow
