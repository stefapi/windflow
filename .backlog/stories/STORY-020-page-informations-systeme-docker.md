# STORY-020 : Page informations système Docker

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'administrateur, je veux accéder à une page dédiée aux informations système Docker (version de l'API, Go version, température système, ping) afin de diagnostiquer les problèmes de connectivité et connaître les capacités exactes de l'hôte Docker.

## Contexte technique
- Nouvelle vue `views/SystemInfo.vue`
- APIs : `GET /docker/system/version`, `GET /docker/system/ping`
- Types TypeScript à ajouter : `SystemVersionResponse`, `PingResponse`
- Extension de `dockerSystemApi` dans `services/api.ts`
- Page accessible depuis la navigation admin/système

## Critères d'acceptation (AC)
- [ ] AC 1 : Une page SystemInfo affiche les informations de version Docker via `GET /docker/system/version` (version, API version, Go version, OS, architecture)
- [ ] AC 2 : Un indicateur de connectivité est affiché en utilisant `GET /docker/system/ping` (disponible/non disponible)
- [ ] AC 3 : Les types TypeScript `SystemVersionResponse` et `PingResponse` sont définis, les méthodes `dockerSystemApi.version` et `dockerSystemApi.ping` sont disponibles
- [ ] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-018 (Widget Docker Info — partage les types et l'API `dockerSystemApi`)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
