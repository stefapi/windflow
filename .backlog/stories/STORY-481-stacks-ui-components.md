# STORY-481 : Intégration composants UI harmonisés dans Stacks

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace
**Type :** Amélioration

## Description
En tant que développeur frontend, je veux intégrer les composants UI harmonisés (STORY-423) dans la vue Stacks afin d'unifier le design system et améliorer l'expérience utilisateur.

### Contexte
Cette story améliore une fonctionnalité existante : la vue Stacks Management (`frontend/src/views/Stacks.vue`).

### Comportement actuel
- Les boutons d'actions utilisent `el-button` standard (Edit, Deploy, Delete)
- Pas de badge de statut sur les stacks
- Les compteurs de services ne sont pas visuels

### Comportement attendu
- Les boutons d'actions utilisent `ActionButtons.vue` avec icônes et tooltips
- Les statuts des stacks sont affichés avec `StatusBadge.vue`
- Les services parsés peuvent afficher leur statut avec `StatusBadge.vue`

## Critères d'acceptation (AC)
- [x] AC 1 : Les boutons Edit/Deploy/Delete sont remplacés par `ActionButtons.vue`
- [x] AC 2 : Chaque stack affiche un `StatusBadge` (draft/deployed/error)
- [x] AC 3 : L'amélioration ne casse pas les fonctionnalités existantes (navigation, dialogs)
- [x] AC 4 : Les tests existants passent toujours
- [x] AC 5 : Les tooltips sont informatifs et accessibles

## État d'avancement technique
- [x] Analyse du code existant dans `Stacks.vue`
- [x] Intégration de `ActionButtons.vue` dans la colonne Actions
- [x] Ajout de `StatusBadge.vue` pour les statuts de stack
- [x] Mise à jour des tests unitaires
- [x] Vérification de non-régression

## Risques de régression

### Fichiers impactés
| Fichier | Impact | Action requise |
|---------|--------|----------------|
| `frontend/src/views/Stacks.vue` | Remplacement boutons par ActionButtons | Vérifier événements @click |
| `frontend/src/stores/stacks.ts` | Ajout champ status si nécessaire | Maintenir compatibilité |

### Fonctionnalités annexes à vérifier
- [ ] Dialog de création de stack : Vérifier que le bouton "Create Stack" fonctionne
- [ ] Dialog de déploiement : Vérifier que le bouton "Deploy" ouvre le dialog
- [ ] Suppression de stack : Vérifier que le bouton "Delete" déclenche la confirmation

### Tests existants à maintenir
- [ ] `frontend/tests/unit/views/Stacks.spec.ts` si existant

## Plan de non-régression

### Tests à exécuter avant modification
```bash
cd frontend && pnpm test -- tests/unit/views/Stacks
```

### Tests à exécuter après modification
```bash
cd frontend && pnpm test -- tests/unit/views/Stacks
cd frontend && pnpm test -- tests/unit/components/ui
cd frontend && pnpm build
cd frontend && pnpm lint
```

### Vérifications manuelles
- [x] Cliquer sur "Edit" ouvre le panneau de détail
- [x] Cliquer sur "Deploy" ouvre le dialog de déploiement
- [x] Cliquer sur "Delete" affiche la confirmation
- [x] Les tooltips s'affichent au survol

## Notes d'implémentation

### Fichiers modifiés/créés
| Fichier | Action |
|---------|--------|
| `frontend/src/components/ui/ActionButtons.vue` | Extension (ajout actions 'edit', 'deploy') |
| `frontend/src/components/ui/StatusBadge.vue` | Extension (ajout statuts 'draft', 'deployed', 'pending', 'failed') |
| `frontend/src/components/ui/CounterCard.vue` | Extension (ajout props badge/badgeType) |
| `frontend/src/views/Stacks.vue` | Intégration des composants ActionButtons et StatusBadge |
| `frontend/src/views/Dashboard.vue` | Intégration CounterCard pour les statistiques |
| `frontend/src/components/dashboard/TargetHealthWidget.vue` | Intégration StatusBadge |
| `frontend/src/components/dashboard/ActivityFeedWidget.vue` | Intégration StatusBadge |
| `frontend/tests/unit/views/Stacks.spec.ts` | Création tests unitaires |

### Décisions techniques
1. **Extension des composants UI** : Ajout des actions `edit` et `deploy` dans ActionButtons.vue et des statuts `draft` et `deployed` dans StatusBadge.vue pour répondre aux besoins spécifiques de la vue Stacks.

2. **Calcul du statut** : Le statut des stacks est déterminé via le champ `metadata.status` de chaque stack. Si absent, le statut par défaut est `draft`.

3. **Pattern de dispatch** : Utilisation d'une fonction `handleStackAction` centralisée pour dispatcher les actions vers les méthodes existantes (`selectStack`, `openDeployDialog`, `confirmDelete`).

4. **Largeur de colonne** : La colonne Actions a été réduite de 300px à 150px grâce à l'utilisation de boutons icônes compacts.

### Tests
- Tests unitaires créés pour `getStackStatus` (4 cas)
- Test d'intégration pour les types d'actions
- Build frontend validé
