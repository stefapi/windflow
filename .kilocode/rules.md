## Principes de Développement

### Architecture
- **API-First** : Toute fonctionnalité doit d'abord être disponible via l'API REST
- **Microservices** : Services découplés et interchangeables
- **Event-Driven** : Communication asynchrone via messages Redis Streams
- **Security by Design** : Sécurité intégrée à tous les niveaux
- **Observabilité** : Monitoring et logging natifs obligatoires
- **Style**: Modular Monolith d'abord puis Hexagonale si complexité augmente

### Standards de Code
- **Type Safety** : Usage obligatoire des type hints en Python et TypeScript strict
- **Documentation** : Code auto-documenté avec docstrings et commentaires explicatifs
- **Tests** : Couverture de tests minimale de 80% pour les nouveaux composants
- **Clean Code** : Noms explicites, fonctions courtes, responsabilités uniques
- **Principes de conception**: SOLID, DRY, KISS, YAGNI, SoC

### Performances et résilience
- Caching (client, edge, app, DB), circuit breaker, retry/backoff, bulkhead, rate limiting.
- Scalabilité horizontale d’abord ; services stateless autant que possible.

### Qualité, tests & observabilité

- Test Pyramid : beaucoup d’unitaires, moins d’intégration, peu d’end-to-end.
- Tests exhaustifs pour les API

## Conventions de nommage

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

## Règles de développement

### Commits
Suivre les conventions définies dans `COMMIT_CONVENTION.md` :
```
<type>(<scope>): <description>

Types: feat, fix, docs, style, refactor, test, chore
```

### Tests
- **Couverture minimale** : 80% des lignes de code
- **Tests async** : Utiliser `pytest-asyncio`
- **Isolation** : Mock des dépendances externes
- **Convention de nommage** : `test_<fonctionnalité>`

### Documentation
- **Docstrings** : Format Google ou NumPy pour toutes les fonctions publiques
- **Memory Bank** : Mettre à jour les fichiers appropriés lors de changements significatifs
- **README** : Maintenir à jour pour les nouvelles fonctionnalités

### Dépendances
- **Poetry uniquement** : Pas de modification manuelle des requirements.txt
- **Versions épinglées** : Utiliser des contraintes précises dans pyproject.toml
- **Révision régulière** : Vérifier les vulnérabilités de sécurité

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

## Sécurité

### Principes de base

- Principe OWASP Top 10
- Least privilege
- zero trust
- chiffrement en transit et au repos
- Auditer régulièrement les vulnérabilités
- 
## Authentification/Autorisation
- JWT tokens avec refresh automatique
- RBAC granulaire avec vérification côté API
- Validation des inputs côté client ET serveur (pydantic)
- Protection CSRF pour les opérations critiques

## Secrets
- Utilisation obligatoire de HashiCorp Vault
- Jamais de secrets en dur dans le code
- Rotation automatique des credentials
- Audit trail pour tous les accès secrets
- Ne pas logger d'informations privées

## Maintenabilité
- **Séparation des responsabilités** : Un module/fonction = une responsabilité
- **Interfaces claires** : Classes abstraites pour les contrats
- **Configuration centralisée** : Pydantic models pour tous les paramètres

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

## Déploiement et Qualité

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
