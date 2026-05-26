# STORY-003 : Menu Contextuel `[⋯ Plus]` Canonique

**Statut :** TODO
**Epic Parent :** EPIC-010 — Mode App — Navigation & UX Simplifiée

## Description
En tant qu'Utilisateur, je veux un menu contextuel standardisé `[⋯ Plus]` pour chaque app afin d'avoir une expérience cohérente et intuitive pour accéder aux actions disponibles sur mes applications.

## Contexte technique
Le composant réutilisable `AppContextMenu` remplace les boutons d'action dispersés. Il affiche un menu déroulant avec 3 sections : Actions principales (Ouvrir, Start/Stop, Redémarrer), Outils (Logs, Console, Config), Avancé (Détails techniques, Supprimer). La section Avancé est la seule zone où le vocabulaire technique peut apparaître en Mode App.

Ce composant est utilisé depuis la liste Apps, le dashboard et le détail App.

Spécification de référence : [`docs/general_specs/11b-workload-families-and-adapters.md`](docs/general_specs/11b-workload-families-and-adapters.md)

## Critères d'acceptation (AC)
- [ ] AC 1 : Le composant `AppContextMenu` affiche les 3 sections (Actions principales, Outils, Avancé) avec un séparateur entre Outils et Avancé
- [ ] AC 2 : Le menu est utilisable et cohérent depuis la liste Apps, le dashboard et le détail App
- [ ] AC 3 : Le vocabulaire technique n'apparaît que dans la section Avancé du menu en Mode App
- [ ] AC 4 : Build, lint et tests passent

## Dépendances
- STORY-001 (Composable de Vocabulaire Mode App)

## État d'avancement techniques
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
