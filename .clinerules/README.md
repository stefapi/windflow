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


## Application des Règles

### Processus de Développement
1. **Lecture obligatoire** des règles avant tout développement
2. **Respect strict** des conventions définies
3. **Validation automatique** via pre-commit hooks
4. **Review** systématique du respect des règles en code review

### Évolution des Règles
- **Mise à jour régulière** basée sur les retours d'expérience
- **Discussions d'équipe** pour les changements majeurs
- **Versioning** des règles avec changelog
- **Formation** continue sur les bonnes pratiques


### 📚 Ressources Complémentaires
- [Documentation Projet](../doc/general_specs/README.md) - Spécifications complètes
- [Architecture](../doc/general_specs/02-architecture.md) - Principes architecturaux
- [Stack Technologique](../doc/general_specs/03-technology-stack.md) - Technologies détaillées
- [Guide de Déploiement](../doc/general_specs/15-deployment-guide.md) - Installation
