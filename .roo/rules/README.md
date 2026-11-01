# WindFlow - Règles de Développement

Le répertoire `.roo/rules` contient **uniquement les règles de développement concrètes** pour le projet WindFlow.

## Organisation du projet

### 📋 Règles de Développement (`.roo/rules/`)
Contient **les conventions de code et bonnes pratiques** :
- Règles de développement spécifiques par technologie
- Conventions de nommage et formatage
- Patterns de code et structures
- Outils et workflows de développement

### 📚 Contexte projet et suivi
Le contexte du projet et son état d'avancement se trouvent :
- dans `docs/` (documentation et spécifications, dont `docs/general_specs/` et `docs/Roadmap.md`)
- dans `.backlog/` (gestion de projet : epics, stories, bugs, kanban)
- dans `.backlog/_models/` (gabarits de contrats : epic, story, sous-story, bug)


## Application des Règles

### Processus de Développement
1. **Lecture obligatoire** des règles avant tout développement
2. **Respect strict** des conventions définies
3. **Validation automatique** via pre-commit hooks
4. **Review** systématique du respect des règles en code review

### Évolution des Règles
- Toute modification du corpus passe par la skill `update-rules` ; l'ordre de priorité en cas de conflit, le plan de numérotation et les interdits sont définis dans `02-gouvernance-regles.md`
- **Mise à jour régulière** basée sur les retours d'expérience
- **Discussions d'équipe** pour les changements majeurs
- **Versioning** des règles avec changelog
- **Formation** continue sur les bonnes pratiques


### 📚 Ressources Complémentaires
- [Documentation Projet](../../docs/general_specs/README.md) - Spécifications complètes
- [Architecture](../../docs/general_specs/04-architecture.md) - Principes architecturaux
- [Stack Technologique](../../docs/general_specs/05-stack-technologique.md) - Technologies détaillées
- [Guide de Déploiement](../../docs/general_specs/16-deploiement.md) - Installation
