# STORY-012 : Promotion container standalone en stack

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux promouvoir un container standalone en stack WindFlow managée afin de le placer sous contrôle complet de WindFlow avec toutes les fonctionnalités associées (déploiements, monitoring, actions globales).

## Contexte technique
- Vue existante `views/ContainerDetail.vue`
- API : `POST /containers/{id}/promote`
- Type TypeScript à ajouter : `ContainerPromoteRequest`
- Dialog de confirmation avec saisie du nom de la nouvelle stack
- Extension de `containersApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [ ] AC 1 : La page de détail d'un container standalone dispose d'une action "Promouvoir en stack"
- [ ] AC 2 : Un dialog demande le nom de la stack à créer avant d'appeler `POST /containers/{id}/promote`
- [ ] AC 3 : Après promotion, l'utilisateur est redirigé vers la nouvelle stack créée
- [ ] AC 4 : Le type TypeScript `ContainerPromoteRequest` est défini et `containersApi.promote` est disponible
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-001 (Vue globale Compute — la section Standalone est le contexte de cette action)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
