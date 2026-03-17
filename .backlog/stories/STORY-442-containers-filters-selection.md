# STORY-442 : Vue Containers — filtres, recherche et sélection multiple

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur avec de nombreux containers, je veux filtrer par statut/target, rechercher par nom, et sélectionner plusieurs containers pour des actions groupées afin de gérer efficacement mon infrastructure.

## Critères d'acceptation (AC)
- [x] AC 1 : Barre de filtres en haut de la liste : dropdown statut (Tous / Running / Stopped / Error), dropdown target
- [x] AC 2 : Champ de recherche textuel filtrant par nom de container (côté client, instantané)
- [x] AC 3 : Checkbox de sélection par ligne + checkbox « tout sélectionner » en tête de colonne
- [x] AC 4 : Barre d'actions groupées visible quand ≥1 container est sélectionné : Start, Stop, Restart, Supprimer
- [x] AC 5 : Suppression groupée demande confirmation avec le nombre de containers listés
- [x] AC 6 : Les filtres sont persistés dans l'URL (query params) pour le partage de liens
- [x] AC 7 : Le compteur de résultats reflète les filtres actifs (ex : « 4 containers (2 filtrés) »)

## État d'avancement technique
- [x] Composants filtres dropdown (Element Plus el-select)
- [x] Champ recherche avec debounce
- [x] Logique sélection multiple (checkbox + barre d'actions groupées)
- [x] Sync filtres ↔ URL query params (composable `useUrlFilters`)
- [x] Actions groupées avec appels API batch
- [x] Confirmation modale pour suppression groupée
- [x] Tests Vitest (filtrage, sélection, actions)

## Notes d'implémentation

### Fichiers créés
- `frontend/src/composables/useUrlFilters.ts` — Composable pour synchroniser les filtres avec les query params URL

### Fichiers modifiés
- `frontend/src/views/Containers.vue` — Ajout barre de filtres, sélection multiple, actions groupées
- `frontend/src/stores/containers.ts` — Ajout actions batch (startContainers, stopContainers, restartContainers, removeContainers)
- `frontend/tests/unit/views/Containers.spec.ts` — Tests pour nouvelles fonctionnalités

### Décisions techniques
1. **Filtrage côté client** : Le filtrage est fait côté client sur les containers déjà chargés pour une réactivité instantanée
2. **Debounce recherche** : 300ms de debounce sur le champ de recherche
3. **Actions batch** : Utilisation de `Promise.allSettled` pour exécuter les actions en parallèle et récupérer les succès/échecs
4. **Persistance URL** : Les filtres sont synchronisés avec les query params pour permettre le partage de liens

### Fonctionnalités implémentées
- Dropdown statut (Tous/Running/Stopped/Error)
- Recherche textuelle sur nom et image avec debounce
- Colonne checkbox avec sélection multiple
- Barre d'actions groupées (Start/Stop/Restart/Delete) visible quand ≥1 container sélectionné
- Modal de confirmation pour suppression groupée avec liste des containers
- Compteur de résultats avec indication des filtres actifs
- Bouton "Effacer les filtres" visible quand des filtres sont actifs
