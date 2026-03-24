# STORY-013 : Gestion des volumes Docker - Liste et création

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux consulter la liste des volumes Docker et en créer de nouveaux afin de gérer le stockage persistant de mes containers depuis l'interface WindFlow.

## Contexte technique
- Vue existante `views/Volumes.vue` (actuellement StubPage — à implémenter)
- APIs : `GET /docker/volumes`, `POST /docker/volumes`
- Types TypeScript à ajouter : `VolumeResponse`, `VolumeCreateRequest` dans `types/api.ts`
- Table avec colonnes : Nom, Driver, Mountpoint, Date de création, Labels, Actions
- Dialog de création : nom, driver (local par défaut), labels optionnels

## Critères d'acceptation (AC)
- [ ] AC 1 : La vue Volumes affiche la liste des volumes via `GET /docker/volumes` dans un tableau avec colonnes (Nom, Driver, Mountpoint, Date)
- [ ] AC 2 : Un bouton "Créer un volume" ouvre un dialog avec les champs nom et driver, et appelle `POST /docker/volumes`
- [ ] AC 3 : Les types TypeScript `VolumeResponse` et `VolumeCreateRequest` sont définis, et `volumesApi.list`/`volumesApi.create` sont disponibles
- [ ] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
