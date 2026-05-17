# STORY-037 : Couverture frontend — Installation et vérification

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Amélioration technique
**Priorité :** Moyenne

## Description
Installer `@vitest/coverage-v8`, mesurer la couverture frontend et compléter les tests des composants sans tests dédiés.

## Contexte technique

### Comportement actuel
- Aucun outil de couverture de code frontend n'est configuré
- Plusieurs composants de l'EPIC-008 n'ont pas de tests dédiés
- Impossible de mesurer la qualité des tests frontend

### Composants sans tests dédiés
- `ManagedStacksSection.vue`
- `DiscoveredSection.vue`
- `StandaloneSection.vue`
- `TargetGroupView.vue`
- `BulkActionBar.vue`

### Fichiers impactés
| Fichier | Modification |
|---------|-------------|
| `frontend/package.json` | Ajout dépendance `@vitest/coverage-v8` |
| `frontend/vitest.config.ts` | Configuration couverture |
| `frontend/tests/unit/components/compute/*.spec.ts` | Nouveaux fichiers de test |

## Critères d'acceptation (AC)
- [ ] AC 1 : `@vitest/coverage-v8` installé et configuré
- [ ] AC 2 : Couverture frontend mesurable via `pnpm test:coverage`
- [ ] AC 3 : Couverture globale ≥ 80% pour les composants de l'EPIC-008
- [ ] AC 4 : Tests dédiés créés pour les composants sans tests :
  - `ManagedStacksSection.vue`
  - `DiscoveredSection.vue`
  - `StandaloneSection.vue`
  - `TargetGroupView.vue`
  - `BulkActionBar.vue`

## Tâches d'implémentation
- [ ] Installer `@vitest/coverage-v8` : `cd frontend && pnpm add -D @vitest/coverage-v8`
- [ ] Configurer vitest pour la couverture dans `vitest.config.ts`
- [ ] Créer les fichiers de test manquants :
  - `frontend/tests/unit/components/compute/ManagedStacksSection.spec.ts`
  - `frontend/tests/unit/components/compute/DiscoveredSection.spec.ts`
  - `frontend/tests/unit/components/compute/StandaloneSection.spec.ts`
  - `frontend/tests/unit/components/compute/TargetGroupView.spec.ts`
  - `frontend/tests/unit/components/compute/BulkActionBar.spec.ts`
- [ ] Exécuter `pnpm test:coverage` et vérifier ≥ 80%
- [ ] Compléter les tests si nécessaire pour atteindre le seuil
