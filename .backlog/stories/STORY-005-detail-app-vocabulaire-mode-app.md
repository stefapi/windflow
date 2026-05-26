# STORY-005 : Détail App — Vocabulaire Mode App

**Statut :** TODO
**Epic Parent :** EPIC-010 — Mode App — Navigation & UX Simplifiée

## Description
En tant qu'Utilisateur, je veux consulter le détail d'une application avec un vocabulaire simplifié et des onglets adaptés au Mode App afin de gérer mon application sans être exposé aux termes techniques Docker.

## Contexte technique
La vue [`ContainerDetail.vue`](frontend/src/views/ContainerDetail.vue) est adaptée pour le Mode App. Le header affiche le nom de l'app (pas le nom du container), version, statut, domaine et métriques inline (CPU, RAM). L'action bar est simplifiée : Ouvrir, Stop/Start, Redémarrer, Logs, Console, Config.

Onglets Mode App : Aperçu, Logs, Console, Métriques, Config. Les onglets techniques (Info/inspect Docker, Processes, Stats détaillées) sont masqués. Le menu `[⋯ Plus]` contient les actions avancées (Supprimer, Renommer, Voir les détails techniques — désactivé).

[`ContainerOverviewTab`](frontend/src/components/ContainerOverviewTab.vue) utilise le vocabulaire "App" au lieu de "Container".

Spécification de référence : [`docs/general_specs/11-UI-mockups.md`](docs/general_specs/11-UI-mockups.md) — Écran 3

## Critères d'acceptation (AC)
- [ ] AC 1 : Le header affiche le nom de l'app, version, statut, domaine et métriques inline (CPU, RAM) au lieu du nom du container
- [ ] AC 2 : Les onglets Mode App (Aperçu, Logs, Console, Métriques, Config) sont affichés ; les onglets techniques (Info, Processes, Stats détaillées) sont masqués
- [ ] AC 3 : L'action bar simplifiée (Ouvrir, Stop/Start, Redémarrer, Logs, Console, Config) fonctionne correctement
- [ ] AC 4 : Le menu `[⋯ Plus]` contient les actions avancées (Supprimer, Renommer, Voir les détails techniques — désactivé)
- [ ] AC 5 : Build, lint et tests passent

## Dépendances
- STORY-001 (Composable de Vocabulaire Mode App)
- STORY-003 (Menu Contextuel Canonique)

## État d'avancement techniques
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
