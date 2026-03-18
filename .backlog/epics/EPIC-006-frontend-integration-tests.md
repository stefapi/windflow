# EPIC-006 : Tests d'Intégration Frontend

**Statut :** TODO
**Priorité :** Haute

## Vision
Étendre la couverture de tests d'intégration du frontend Vue.js 3 pour atteindre 80%+ sur les flux critiques. Actuellement, le dossier `frontend/tests/integration/` est vide (`.gitkeep` uniquement). Les tests unitaires existent, mais les tests d'intégration (API mockée, stores, composants connectés) manquent.

## Contexte
- Tests unitaires existants dans `frontend/tests/unit/`
- Stack de test : Vitest + @vue/test-utils + @pinia/testing
- Couverture actuelle : ~70% (unitaires uniquement)
- Objectif : 80%+ avec tests d'intégration

## Périmètre

### Domaines à tester (priorité décroissante)
| Domaine | Priorité | Description |
|---------|----------|-------------|
| Authentification | P0 | Login/logout, refresh token, gestion erreurs 401/403 |
| Client API | P0 | Interceptors axios, retry, timeout, cancellation |
| Stores Pinia | P1 | Auth store, Containers store, Deployments store |
| Composables | P1 | useUrlFilters, useRelativeTime, useSecretMasker |
| Composants connectés | P2 | Dashboard, Containers, ContainerDetail |

## Liste des Stories liées
*À créer ultérieurement*

- [ ] STORY-XXX : Tests Auth Flow (login, logout, token refresh)
- [ ] STORY-XXX : Tests API Client (interceptors, error handling)
- [ ] STORY-XXX : Tests Auth Store (Pinia + API mockée)
- [ ] STORY-XXX : Tests Containers Store (CRUD + WebSocket mock)
- [ ] STORY-XXX : Tests Composables (useUrlFilters, useRelativeTime, useSecretMasker)
- [ ] STORY-XXX : Tests Dashboard Integration (widgets connectés)

## Critères de succès (Definition of Done)
- [ ] Couverture tests frontend ≥ 80%
- [ ] Tests d'intégration avec API mockée (MSW ou mocks manuels)
- [ ] Tests stores Pinia avec API mockée
- [ ] CI/CD intégré (vitest --run en CI)
- [ ] Documentation des patterns de test

## Notes de conception
### Stack de test
- **Vitest** : Runner de test (déjà configuré)
- **@vue/test-utils** : Montage de composants (déjà installé)
- **@pinia/testing** : Testing stores (déjà installé)
- **MSW** (Mock Service Worker) : Mock API REST (à ajouter si nécessaire)

### Patterns de test
- Isolation des tests : chaque test est indépendant
- Mock de l'API REST pour les tests d'intégration
- Utilisation de `createTestingPinia` pour les stores
- Fixtures pour les données de test

### Structure proposée
```
frontend/tests/integration/
├── auth/
│   ├── login.integration.spec.ts
│   ├── logout.integration.spec.ts
│   └── token-refresh.integration.spec.ts
├── api/
│   ├── client.integration.spec.ts
│   └── interceptors.integration.spec.ts
├── stores/
│   ├── auth-store.integration.spec.ts
│   ├── containers-store.integration.spec.ts
│   └── deployments-store.integration.spec.ts
├── composables/
│   ├── useUrlFilters.integration.spec.ts
│   └── useRelativeTime.integration.spec.ts
└── views/
    ├── Dashboard.integration.spec.ts
    └── Containers.integration.spec.ts
```

## Risques et mitigation
| Risque | Mitigation |
|--------|------------|
| MSW trop complexe à configurer | Utiliser des mocks manuels simples si nécessaire |
| Tests flaky avec timers | Utiliser `vi.useFakeTimers()` de Vitest |
| Couverture difficile à mesurer | Configurer vitest coverage avec istanbul |
| WebSocket mocking | Utiliser des mocks manuels pour WebSocket |

## Dépendances
- Aucune dépendance bloquante
- Peut être développé en parallèle de EPIC-005 (Backend Integration Tests)
