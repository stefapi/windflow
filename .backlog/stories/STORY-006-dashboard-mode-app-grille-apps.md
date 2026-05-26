# STORY-006 : Dashboard Mode App — Grille Apps

**Statut :** TODO
**Epic Parent :** EPIC-010 — Mode App — Navigation & UX Simplifiée

## Description
En tant qu'Utilisateur, je veux accéder rapidement à mes applications depuis le dashboard via une grille d'icônes cliquables de type Umbrel afin d'avoir une vue d'ensemble visuelle et intuitive de mes apps.

## Contexte technique
La vue [`Dashboard.vue`](frontend/src/views/Dashboard.vue) est enrichie avec une section "Mes Apps" contenant une grille d'icônes cliquables (type Umbrel). Chaque icône affiche : icône de l'app, nom, statut (dot coloré), domaine. Le clic sur une app navigue vers le Détail App.

Les widgets existants (métriques, activité, alertes) sont conservés mais repositionnés sous la grille Apps. Une salutation personnalisée ("Bonjour, {username}") est ajoutée en haut du dashboard.

Spécification de référence : [`docs/general_specs/11-UI-mockups.md`](docs/general_specs/11-UI-mockups.md) — Écran 1

## Critères d'acceptation (AC)
- [ ] AC 1 : Une section "Mes Apps" avec grille d'icônes cliquables est affichée sur le dashboard, chaque icône montrant le nom de l'app et un indicateur de statut (dot coloré)
- [ ] AC 2 : Le clic sur une icône app navigue vers le Détail App correspondant
- [ ] AC 3 : Les widgets existants (métriques, activité, alertes) sont conservés et repositionnés sous la grille Apps
- [ ] AC 4 : Une salutation personnalisée ("Bonjour, {username}") est affichée en haut du dashboard
- [ ] AC 5 : Build, lint et tests passent

## Dépendances
- STORY-001 (Composable de Vocabulaire Mode App)

## État d'avancement techniques
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
