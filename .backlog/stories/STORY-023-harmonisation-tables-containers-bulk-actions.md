# STORY-023 : Frontend — Harmonisation tables containers et actions en masse

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur, je veux que l'affichage des containers soit homogène entre les sections Managed, Discovered et Standalone (mêmes colonnes, même rendu statut/mémoire/CPU, ports, uptime), afin de pouvoir comparer et agir sur tous les containers de manière cohérente, avec la possibilité de faire des actions en masse dans chaque section.

## Contexte technique
Après le refactoring de STORY-022, les 3 sections utilisent `ContainerTable.vue` mais avec des colonnes et un rendu différents :

**Divergences actuelles :**

| Élément | Managed/Discovered | Standalone |
|---------|-------------------|------------|
| CPU | barre de progression (`cpu`) | texte compact (`cpuMemory`) |
| Mémoire | colonne séparée (`memory`) | intégré dans `cpuMemory` |
| Uptime | absent | présent |
| Ports | absent | présent |
| Health status | non affiché | non affiché |
| Sélection/bulk | absent | présent |
| Colonnes cible | absent | `target` |

**Types API en cause :**
- `ServiceWithMetrics` : id, name, image, status, cpu_percent, memory_usage, memory_limit? — PAS de uptime, ports, health_status
- `StandaloneContainer` : id, name, image, target_id, target_name, status, cpu_percent, memory_usage, uptime, ports, health_status

**Composants impactés :**
- `frontend/src/components/compute/ContainerTable.vue` — colonnes et rendu
- `frontend/src/components/compute/ManagedStacksSection.vue` — colonnes + bulk actions
- `frontend/src/components/compute/DiscoveredSection.vue` — colonnes + bulk actions
- `frontend/src/components/compute/StandaloneSection.vue` — harmonisation colonnes
- `frontend/src/components/compute/helpers.ts` — normalisation
- `frontend/src/composables/useBulkActions.ts` — **nouveau** composable partagé

## Critères d'acceptation (AC)
- [ ] AC 1 : Les 3 sections (Managed, Discovered, Standalone) affichent les mêmes colonnes dans le même ordre : `name`, `image`, `status`, `cpu` (barre), `memory`, `uptime`, `ports`, `actions`
- [ ] AC 2 : Les colonnes `uptime` et `ports` affichent "—" pour les services managed/discovered (données non disponibles côté backend)
- [ ] AC 3 : Le rendu du statut est identique partout : dot coloré + ElTag avec type cohérent (success/warning/danger/info)
- [ ] AC 4 : Le rendu CPU est harmonisé : barre de progression + pourcentage dans toutes les sections
- [ ] AC 5 : Le rendu mémoire est harmonisé : texte dans toutes les sections
- [ ] AC 6 : La colonne `cpuMemory` compacte est supprimée au profit de `cpu` + `memory` séparés
- [ ] AC 7 : Les sections Managed et Discovered supportent la sélection multiple de services dans les tables
- [ ] AC 8 : Les sections Managed et Discovered ont une barre d'actions en masse (Démarrer, Arrêter, Redémarrer, Supprimer)
- [ ] AC 9 : Un composable `useBulkActions()` mutualise la logique de sélection, barre d'actions et dialog de suppression
- [ ] AC 10 : La section Standalone refactorée utilise le même composable `useBulkActions()`
- [ ] AC 11 : Le dialogue de suppression groupée est identique visuellement dans les 3 sections
- [ ] AC 12 : Pas de régression visuelle ou fonctionnelle par rapport à STORY-022
- [ ] AC 13 : Build, lint et tous les tests passent sans erreur

## Dépendances
- STORY-022 : Frontend — Refactoring de Compute.vue en sous-composants (DONE)

## État d'avancement technique
- [ ] Tâche 1 : Créer le composable `useBulkActions.ts`
- [ ] Tâche 2 : Harmoniser les colonnes dans `ContainerTable.vue` (supprimer `cpuMemory`, uniformiser rendu)
- [ ] Tâche 3 : Mettre à jour `helpers.ts` — ajuster `serviceToRow` pour les champs manquants
- [ ] Tâche 4 : Mettre à jour `StandaloneSection.vue` — colonnes harmonisées + composable
- [ ] Tâche 5 : Mettre à jour `ManagedStacksSection.vue` — colonnes harmonisées + bulk actions
- [ ] Tâche 6 : Mettre à jour `DiscoveredSection.vue` — colonnes harmonisées + bulk actions
- [ ] Tâche 7 : Mettre à jour `TargetGroupView.vue` — colonnes harmonisées
- [ ] Tâche 8 : Mettre à jour les tests
- [ ] Tâche 9 : Build, lint et vérification non-régression

## Tâches d'implémentation détaillées
<!-- Sera rempli par la skill analyse-story -->

## Tests à écrire
<!-- Sera rempli par la skill analyse-story -->
