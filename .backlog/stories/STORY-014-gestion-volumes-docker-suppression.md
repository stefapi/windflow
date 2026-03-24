# STORY-014 : Gestion des volumes Docker - Suppression

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux supprimer des volumes Docker inutilisés depuis l'interface afin de libérer de l'espace disque sur mes machines cibles.

## Contexte technique
- Vue existante `views/Volumes.vue`
- API : `DELETE /docker/volumes/{name}`
- Confirmation avant suppression (volumes potentiellement en cours d'utilisation)
- Extension de `volumesApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [ ] AC 1 : Chaque volume dans la liste dispose d'une action "Supprimer" qui demande confirmation
- [ ] AC 2 : La suppression appelle `DELETE /docker/volumes/{name}` et la liste se rafraîchit
- [ ] AC 3 : Si le volume est en cours d'utilisation, l'erreur retournée par l'API est affichée via notification toast
- [ ] AC 4 : `volumesApi.remove` est disponible dans `services/api.ts`
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-013 (Liste volumes — même vue)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
