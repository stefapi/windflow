# Règles Générales de Développement - WindFlow

## Vue d'Ensemble du Projet

WindFlow est un outil web intelligent de déploiement de containers Docker sur des machines cibles. Il combine une interface utilisateur moderne, un système d'échange de données flexible, et une intelligence artificielle pour automatiser et optimiser les déploiements.

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

### Front-end & mobile (selon contexte)

- Component-driven (Design Systems)
- gestion d’état
- accessibilité (WCAG)
- offline-first
- sync conflictuelle

## Conventions de Nommage

### Fichiers et Répertoires
- **snake_case** pour les fichiers Python : `deployment_service.py`
- **kebab-case** pour les fichiers frontend : `deployment-view.vue`
- **PascalCase** pour les classes et composants : `DeploymentService`, `DeploymentView`
- **camelCase** pour les variables et méthodes JavaScript/TypeScript

### Base de Données
- **snake_case** pour les tables et colonnes : `deployment_events`
- **UUID** pour tous les identifiants primaires
- **timestamps** obligatoires : `created_at`, `updated_at`

## Structure des Projets

### Backend (FastAPI)
```
windflow/
├── api/                 # Endpoints API REST
├── core/               # Configuration et utilitaires
├── models/             # Modèles SQLAlchemy
├── services/           # Logique métier
├── tasks/              # Tâches Celery
├── tests/              # Tests automatisés
└── main.py            # Point d'entrée FastAPI
```

### Frontend (Vue.js 3)
```
frontend/
├── src/
│   ├── components/     # Composants réutilisables
│   ├── views/          # Pages/vues
│   ├── stores/         # State management Pinia
│   ├── services/       # API services
│   ├── types/          # Types TypeScript
│   └── utils/          # Utilitaires
├── public/             # Assets statiques
└── package.json
```

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
