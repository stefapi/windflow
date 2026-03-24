# STORY-006 : Gestion des images Docker - Pull et suppression

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux pouvoir télécharger (pull) de nouvelles images Docker et supprimer des images existantes depuis l'interface afin de gérer le registre local d'images sur mes targets.

## Contexte technique
- Vue existante `views/Images.vue`
- APIs : `POST /docker/images/pull`, `DELETE /docker/images/{id}`
- Types TypeScript : `ImagePullRequest`, `ImagePullResponse`
- Dialog pull avec champ de saisie `nom:tag`
- Dialogue de confirmation avant suppression

## Critères d'acceptation (AC)
- [ ] AC 1 : Un bouton "Pull image" ouvre un dialog avec un champ de saisie pour le nom de l'image (format `nom:tag`) et déclenche `POST /docker/images/pull`
- [ ] AC 2 : La progression du pull est indiquée (loading state) et la liste se rafraîchit après succès
- [ ] AC 3 : Chaque ligne de la table dispose d'une action "Supprimer" qui demande confirmation avant d'appeler `DELETE /docker/images/{id}`
- [ ] AC 4 : Les erreurs (image introuvable, image en cours d'utilisation) sont affichées via une notification toast
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-005 (Liste des images — même vue, mêmes APIs)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
