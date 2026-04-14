# STORY-031 : Images Docker — Sélection, actions en lot, usage et détail

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Amélioration

## Description
En tant qu'utilisateur DevOps, je veux pouvoir sélectionner des images Docker via des cases à cocher (individuelle ou sélection globale), appliquer des actions en lot (remove, force_remove), importer/exporter des images, voir si une image est utilisée par des containers, filtrer sur ce critère, et cliquer sur une image pour afficher son détail.

## Contexte technique

### Comportement actuel
- La vue `views/Images.vue` affiche un tableau basique avec colonnes ID, Tags, Taille, Date de création et un champ de recherche
- `imagesApi` dans `services/api.ts` ne dispose que de `list()`
- Backend : `GET /docker/images`, `POST /docker/images/pull`, `DELETE /docker/images/{id}?force=false`
- Le service backend `docker_client_service.py` a une méthode `inspect_image()` mais aucun endpoint API ne l'expose
- Aucune indication d'utilisation (image utilisée par des containers ou non)
- Aucune route pour l'import/export d'images Docker (save/load)
- Pas de vue détail image

### Comportement attendu
- **Sélection** : colonne de checkboxes dans le tableau avec case globale dans le header (pattern `el-table` avec `@selection-change`)
- **Actions en lot** : barre d'actions contextuelle (pattern `BulkActionBar.vue` de STORY-023) avec boutons Remove et Force Remove, visibles uniquement quand des images sont sélectionnées
- **Import/Export** : boutons dans le header pour importer (upload tar) et exporter (download tar) des images
- **Utilisation** : colonne indiquant si l'image est utilisée par des containers (badge vert/rouge), avec filtre dédié
- **Détail** : clic sur une ligne → navigation vers `ImageDetail.vue` (écran vide/stub pour le moment, avec juste les infos de base de l'image)
- **Backend** : enrichir `ImageResponse` avec un champ `in_use` (booléen) et le nombre de containers; ajouter endpoint `GET /docker/images/{id}` pour l'inspect; ajouter endpoints save/load pour import/export

## Critères d'acceptation (AC)
- [ ] AC 1 : Le tableau des images dispose d'une colonne de sélection par checkbox avec sélection globale en-tête, et une barre d'actions apparaît quand des images sont sélectionnées (Remove, Force Remove)
- [ ] AC 2 : L'import d'image (upload fichier tar via `docker load`) et l'export d'image (download tar via `docker save`, pour les images sélectionnées ou une image individuelle) fonctionnent
- [ ] AC 3 : Chaque image affiche un indicateur d'utilisation (utilisée/non utilisée par des containers) et un filtre permet d'afficher uniquement les images utilisées ou non utilisées
- [ ] AC 4 : Cliquer sur une image navigue vers un écran de détail (vue `ImageDetail.vue` stub avec infos de base : ID, tags, size, created, labels, digests)
- [ ] AC 5 : L'amélioration ne casse pas les fonctionnalités existantes (liste, recherche, affichage)
- [ ] AC 6 : Build, lint et tests passent sans erreur

## Dépendances
- STORY-005 (Gestion des images Docker - Liste et visualisation — REVIEW)
- STORY-006 (Gestion des images Docker - Pull et suppression — TODO, partiellement couvert par cette story pour la suppression en lot)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story — inclura :
- Analyse du code existant
- Fichiers impactés et risques de régression
- Plan de non-régression
- Tâches d'implémentation ordonnées
-->

## Tests à écrire
<!-- Rempli par analyse-story -->
