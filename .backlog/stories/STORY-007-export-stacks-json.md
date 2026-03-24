# STORY-007 : Export de stacks au format JSON

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux exporter une stack au format JSON depuis l'interface afin de sauvegarder ou partager la configuration d'une stack avec d'autres utilisateurs.

## Contexte technique
- Vue existante `views/Stacks.vue`
- API : `GET /stacks/{id}/export`
- Type TypeScript à ajouter : `StackExportData`
- Bouton "Exporter" sur chaque stack → déclenche téléchargement du fichier JSON
- Extension de `stacksApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [ ] AC 1 : Chaque stack dispose d'un bouton/action "Exporter" qui appelle `GET /stacks/{id}/export`
- [ ] AC 2 : L'export déclenche automatiquement le téléchargement d'un fichier `{nom-stack}.json` dans le navigateur
- [ ] AC 3 : Le type TypeScript `StackExportData` est défini et `stacksApi.export` est disponible
- [ ] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
