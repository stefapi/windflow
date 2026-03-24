# STORY-005 : Gestion des images Docker - Liste et visualisation

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux consulter la liste des images Docker disponibles sur mes targets afin de visualiser les images présentes, leur taille et leurs tags.

## Contexte technique
- Vue existante `views/Images.vue` (actuellement StubPage — à implémenter)
- API : `GET /docker/images`
- Type TypeScript à ajouter : `ImageResponse` dans `types/api.ts`
- Table avec colonnes : ID, Repo Tags, Size, Created, Actions
- Pagination pour les listes longues

## Critères d'acceptation (AC)
- [ ] AC 1 : La vue Images affiche la liste des images via `GET /docker/images` dans un tableau avec colonnes (ID, Tags, Taille, Date de création)
- [ ] AC 2 : La taille des images est affichée dans un format lisible (MB/GB)
- [ ] AC 3 : Un champ de recherche permet de filtrer les images par tag ou ID
- [ ] AC 4 : Le type TypeScript `ImageResponse` est défini dans `types/api.ts` et l'API `imagesApi.list` est disponible dans `services/api.ts`
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
