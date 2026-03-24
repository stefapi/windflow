# STORY-011 : Archivage de stack

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux archiver une stack qui n'est plus en service afin de la conserver pour référence sans qu'elle encombre la vue principale.

## Contexte technique
- Vue existante `views/Stacks.vue`
- API : `POST /stacks/{id}/archive`
- Confirmation avant archivage
- Stack archivée déplacée dans une section "Archivées" (masquée par défaut)
- Extension de `stacksApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [ ] AC 1 : Chaque stack active dispose d'une action "Archiver" qui demande confirmation avant d'appeler `POST /stacks/{id}/archive`
- [ ] AC 2 : La stack archivée est retirée de la liste principale et apparaît dans une section "Archivées" (accessible via un filtre ou toggle)
- [ ] AC 3 : `stacksApi.archive` est disponible dans `services/api.ts`
- [ ] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
