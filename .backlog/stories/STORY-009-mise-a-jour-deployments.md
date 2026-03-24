# STORY-009 : Mise à jour des déploiements existants

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux modifier la configuration d'un déploiement existant depuis l'interface afin de mettre à jour ses paramètres sans avoir à le recréer.

## Contexte technique
- Vue existante `views/DeploymentDetail.vue`
- API : `PUT /deployments/{id}`
- Type TypeScript à ajouter : `DeploymentUpdate`
- Extension de `deploymentsApi` dans `services/api.ts`
- Formulaire d'édition inline dans la page de détail du déploiement

## Critères d'acceptation (AC)
- [ ] AC 1 : La page de détail d'un déploiement dispose d'un bouton "Modifier" qui active un formulaire d'édition
- [ ] AC 2 : Le formulaire permet de modifier le nom, la configuration et l'environnement via `PUT /deployments/{id}`
- [ ] AC 3 : Les modifications sont sauvegardées avec confirmation toast et la page se rafraîchit
- [ ] AC 4 : Le type TypeScript `DeploymentUpdate` est défini et `deploymentsApi.update` est disponible
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
