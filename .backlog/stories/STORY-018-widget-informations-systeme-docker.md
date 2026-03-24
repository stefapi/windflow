# STORY-018 : Widget informations système Docker

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux voir les informations système Docker (version, nombre de containers/images, ressources) dans un widget du dashboard afin d'avoir une vue d'ensemble rapide de l'état de l'hôte Docker.

## Contexte technique
- Nouveau composant `components/dashboard/DockerInfoWidget.vue`
- API : `GET /docker/system/info`
- Type TypeScript à ajouter : `SystemInfoResponse`
- Affichage : version Docker, nombre containers (running/stopped), images, CPU, mémoire
- Ajout de `dockerSystemApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [ ] AC 1 : Un nouveau widget DockerInfo est visible dans le dashboard et charge les données via `GET /docker/system/info`
- [ ] AC 2 : Le widget affiche : version Docker, nombre total de containers (running/paused/stopped), nombre d'images, OS et architecture
- [ ] AC 3 : Le type TypeScript `SystemInfoResponse` est défini et `dockerSystemApi.info` est disponible
- [ ] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
