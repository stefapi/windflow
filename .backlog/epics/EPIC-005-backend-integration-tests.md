# EPIC-005 : Tests d'Intégration Backend

**Statut :** TODO
**Priorité :** Haute

## Vision
Étendre la couverture de tests d'intégration du backend pour atteindre 85%+ sur les APIs REST critiques. Les tests actuels couvrent l'authentification et les déploiements de base, mais de nombreuses APIs core (stacks, targets, users, organizations, docker) manquent de tests d'intégration.

## Contexte
- Tests existants : `test_auth_api.py`, `test_deployments_api.py`, `test_rate_limiting.py`, `test_correlation_id.py`, `test_security_headers.py`, `test_timing.py`, `test_openapi.py`
- Couverture actuelle : ~70%
- Objectif : 85%+

## Périmètre

### APIs à tester (priorité décroissante)
| API | Priorité | Complexité |
|-----|----------|------------|
| Stacks | P0 | Haute (macros, versioning) |
| Targets | P0 | Moyenne |
| Users | P1 | Moyenne |
| Organizations | P1 | Moyenne |
| Docker | P1 | Haute (mock daemon) |
| RBAC | P1 | Moyenne |
| Deployment Workflow | P2 | Haute |
| WebSocket Terminal | P3 | Haute |
| Résilience/Cache | P3 | Moyenne |

## Liste des Stories liées
- [ ] STORY-482 : Tests API Stacks (CRUD, macros, versioning)
- [ ] STORY-483 : Tests API Targets (CRUD, discovery, connectivité)
- [ ] STORY-484 : Tests API Users (CRUD, profil, permissions)
- [ ] STORY-485 : Tests API Organizations (multi-tenant)
- [ ] STORY-486 : Tests API Docker (conteneurs, logs, actions)
- [ ] STORY-487 : Tests RBAC (contrôle d'accès)
- [ ] STORY-488 : Tests Workflow Déploiement (bout-en-bout)
- [ ] STORY-489 : Tests WebSocket Terminal
- [ ] STORY-490 : Tests Résilience (circuit breaker, cache)

## Critères de succès (Definition of Done)
- [ ] Couverture tests backend ≥ 85%
- [ ] Tous les endpoints API v1 testés
- [ ] Tests multi-tenant (isolation organisations)
- [ ] Tests RBAC complets
- [ ] CI/CD intégré (tests passent en CI)
- [ ] Documentation des patterns de test

## Notes de conception
- Utiliser les fixtures existantes dans `conftest.py`
- Mock des services externes (Docker daemon, Redis)
- Focus sur les APIs critiques en priorité
- Tests de non-régression pour bugs corrigés
- Pattern AAA (Arrange-Act-Assert) systématique
- Nommage clair : `test_<endpoint>_<action>_<condition>`

## Risques et mitigation
| Risque | Mitigation |
|--------|------------|
| Docker daemon non disponible en CI | Mock complet avec `unittest.mock` |
| Tests lents | Parallelisation avec pytest-xdist |
| Flaky tests | Timeouts explicites, retry logic |
