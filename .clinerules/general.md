# Règles Générales de Développement - WindFlow

**Note** : Ce fichier contient uniquement les conventions de nommage et règles transversales concrètes.
Pour le contexte architectural, les principes de développement et l'état du projet, voir `memory-bank/`.

## Standards de Code Transversaux

### Type Safety Obligatoire
- **Python** : Type hints complets sur toutes les fonctions et méthodes publiques
- **TypeScript** : Mode strict activé, pas de `any` sauf cas exceptionnels justifiés
- **Validation** : mypy et tsc strict en CI/CD

### Clean Code Essentials
- **Noms explicites** : Variables, fonctions et classes avec intention claire
- **Fonctions courtes** : Maximum 20 lignes, responsabilité unique
- **DRY** : Éliminer la duplication, extraire les abstractions communes
- **SOLID** : Principes orientés objet respectés

### Tests Obligatoires
- **Couverture minimale** : 80% pour nouveaux composants
- **Pyramide des tests** : Unitaires > Intégration > E2E
- **TDD encouragé** : Tests d'abord pour les nouvelles fonctionnalités

## Conventions de Nommage

### Fichiers et Répertoires
- **Classes/Composants** : PascalCase (ex: `LLMClient`, `GraphExecutor`)
- **Fonctions/Méthodes Python** : snake_case (ex: `generate_response()`, `process_node()`)
- **Variables** : snake_case (ex: `config`, `result_data`)
- **Constantes** : UPPER_SNAKE_CASE (ex: `DEFAULT_MODEL`)
- **Modules/Fichiers Python** : snake_case (ex: `llm_client.py`, `graph_executor.py`)
- **Fichiers Frontend** : kebab-case (ex: `deployment-view.vue`)
- **Variables/Méthodes/Fonctions Javascript/Typescript** : camelCase (ex: `viewGraph`, `callBackend`)

### Base de Données
- **snake_case** pour les tables et colonnes : `deployment_events`
- **UUID** pour tous les identifiants primaires
- **timestamps** obligatoires : `created_at`, `updated_at`

## Gestion des Erreurs

### Backend
- Utiliser les exceptions personnalisées héritant de `WindFlowException`
- Logging structuré avec contexte approprié
- Codes de statut HTTP appropriés
- Messages d'erreur internationalisés

### Frontend
- Gestion centralisée des erreurs avec Pinia store
- Notifications utilisateur via Element Plus
- Fallback gracieux en cas d'échec API
- Retry automatique pour les erreurs temporaires

## Sécurité

#### Principes de base

- Principe OWASP Top 10
- Least privilege
- zero trust
- chiffrement en transit et au repos

### Authentification/Autorisation
- JWT tokens avec refresh automatique
- RBAC granulaire avec vérification côté API
- Validation des inputs côté client ET serveur
- Protection CSRF pour les opérations critiques

### Secrets
- Utilisation obligatoire de HashiCorp Vault
- Jamais de secrets en dur dans le code
- Rotation automatique des credentials
- Audit trail pour tous les accès secrets

## Performance

### Backend
- Pagination obligatoire pour les listes > 20 éléments
- Cache Redis pour les requêtes coûteuses
- Requêtes SQL optimisées avec indexes appropriés
- Profiling des endpoints critiques

### Frontend
- Lazy loading des composants non-critiques
- Optimisation des bundles avec tree-shaking
- Cache des requêtes API répétitives
- Progressive Web App pour performance mobile

## Déploiement et CI/CD

### Tests Requis
- Tests unitaires avec pytest/vitest
- Tests d'intégration avec base de données test
- Tests E2E pour les workflows critiques
- Tests de sécurité avec bandit/semgrep

### Validation Pre-commit
- Formatage automatique : black, prettier
- Linting : flake8, eslint
- Type checking : mypy, typescript
- Sécurité : bandit, npm audit

### Environnements
- **dev** : Base de données locale, hot reload
- **staging** : Réplique exacte de production, tests automatisés
- **production** : Haute disponibilité, monitoring complet

## Monitoring et Observabilité

### Métriques Obligatoires
- Latence des endpoints API
- Taux d'erreur par service
- Utilisation des ressources (CPU/RAM)
- Métriques business (déploiements réussis/échoués)

### Logging
- Format JSON structuré
- Correlation IDs pour le tracing distribué
- Niveaux appropriés : DEBUG, INFO, WARNING, ERROR, CRITICAL
- Pas de données sensibles dans les logs

## Documentation

### Code
- Docstrings Python selon standard Google
- JSDoc pour les fonctions TypeScript importantes
- README.md pour chaque module/service
- Exemples d'usage dans la documentation

### API
- Documentation OpenAPI/Swagger automatique
- Exemples de requêtes/réponses
- Codes d'erreur documentés
- Changelog des versions API

Ces règles guident tous les développements futurs et doivent être respectées pour maintenir la cohérence et la qualité du projet WindFlow.
