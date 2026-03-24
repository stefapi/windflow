# STORY-010 : Duplication de stack

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux dupliquer une stack existante afin de créer rapidement une stack similaire sans tout reconfigurer depuis zéro.

## Contexte technique
- Vue existante `views/Stacks.vue`
- API : `POST /stacks/{id}/duplicate`
- Type TypeScript à ajouter : `StackDuplicateRequest`
- Dialog de duplication : champ nom de la nouvelle stack + option de target différente
- Extension de `stacksApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [ ] AC 1 : Chaque stack dispose d'une action "Dupliquer" qui ouvre un dialog de configuration
- [ ] AC 2 : Le dialog permet de saisir le nom de la nouvelle stack et optionnellement de choisir une target différente
- [ ] AC 3 : La duplication appelle `POST /stacks/{id}/duplicate` et la liste se rafraîchit avec la nouvelle stack
- [ ] AC 4 : Le type TypeScript `StackDuplicateRequest` est défini et `stacksApi.duplicate` est disponible
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
