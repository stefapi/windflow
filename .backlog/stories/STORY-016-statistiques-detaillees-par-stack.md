# STORY-016 : Statistiques détaillées par stack

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux consulter les statistiques détaillées d'une stack (déploiements par statut, activité sur les 30 derniers jours) afin de suivre son historique et son taux de succès.

## Contexte technique
- Vue existante `views/Stacks.vue` (section détails à enrichir)
- API : `GET /stats/stacks/{id}`
- Type TypeScript à ajouter : `StackStatsResponse`
- Extension de `dashboardApi` dans `services/api.ts`
- Affichage : distribution des déploiements par statut + compteur 30 derniers jours

## Critères d'acceptation (AC)
- [ ] AC 1 : La vue de détail d'une stack affiche les statistiques de déploiements via `GET /stats/stacks/{id}`
- [ ] AC 2 : Les statistiques incluent le nombre de déploiements par statut (succès/échec/en cours) et le total sur 30 jours
- [ ] AC 3 : Le type TypeScript `StackStatsResponse` est défini et `dashboardApi.getStackStats` est disponible
- [ ] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
