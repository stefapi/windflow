# STORY-008 : Import de stacks depuis fichier JSON

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux importer une stack depuis un fichier JSON afin de restaurer une configuration sauvegardée ou déployer une stack partagée par un collègue.

## Contexte technique
- Vue existante `views/Stacks.vue`
- API : `POST /stacks/import` (multipart/form-data)
- Upload fichier + validation format avant envoi
- Extension de `stacksApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [ ] AC 1 : Un bouton "Importer" ouvre un dialog permettant de sélectionner un fichier JSON
- [ ] AC 2 : Le fichier est validé côté client (format JSON valide, structure attendue) avant envoi
- [ ] AC 3 : L'import appelle `POST /stacks/import` et redirige vers la stack créée en cas de succès
- [ ] AC 4 : Les erreurs de validation (format invalide, stack existante) sont affichées clairement
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-007 (Export — format JSON de référence)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
