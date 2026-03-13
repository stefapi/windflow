# STORY-442 : Vue Containers — filtres, recherche et sélection multiple

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur avec de nombreux containers, je veux filtrer par statut/target, rechercher par nom, et sélectionner plusieurs containers pour des actions groupées afin de gérer efficacement mon infrastructure.

## Critères d'acceptation (AC)
- [ ] AC 1 : Barre de filtres en haut de la liste : dropdown statut (Tous / Running / Stopped / Error), dropdown target
- [ ] AC 2 : Champ de recherche textuel filtrant par nom de container (côté client, instantané)
- [ ] AC 3 : Checkbox de sélection par ligne + checkbox « tout sélectionner » en tête de colonne
- [ ] AC 4 : Barre d'actions groupées visible quand ≥1 container est sélectionné : Start, Stop, Restart, Supprimer
- [ ] AC 5 : Suppression groupée demande confirmation avec le nombre de containers listés
- [ ] AC 6 : Les filtres sont persistés dans l'URL (query params) pour le partage de liens
- [ ] AC 7 : Le compteur de résultats reflète les filtres actifs (ex : « 4 containers (2 filtrés) »)

## État d'avancement technique
- [ ] Composants filtres dropdown (Element Plus el-select)
- [ ] Champ recherche avec debounce
- [ ] Logique sélection multiple (checkbox + barre d'actions groupées)
- [ ] Sync filtres ↔ URL query params (composable `useUrlFilters`)
- [ ] Actions groupées avec appels API batch
- [ ] Confirmation modale pour suppression groupée
- [ ] Tests Vitest (filtrage, sélection, actions)
