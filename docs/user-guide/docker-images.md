# Guide utilisateur — Docker Images

## Vue d'ensemble

La **vue Docker Images** est le centre de gestion des images Docker sur vos machines cibles. Elle offre une vision unifiée de l'ensemble des images présentes sur vos targets, avec des outils de filtrage, de recherche et d'actions (pull, suppression, prune, inspection détaillée).

### Accès

Depuis la barre latérale principale : **Docker → Images**.

---

## Table des matières

1. [Liste des images](#liste-des-images)
2. [Filtres](#filtres)
3. [Actions sur les images](#actions-sur-les-images)
4. [Détail d'une image](#détail-dune-image)

---

## Liste des images

La vue affiche une table paginée ([`el-table`](https://element-plus.org/en-US/component/table.html)) listant l'ensemble des images Docker présentes sur les targets sélectionnées. Les données sont récupérées via l'endpoint `GET /docker/images` (voir [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py)).

### Colonnes affichées

| Colonne | Source API | Description |
|---------|------------|-------------|
| **ID** | `image.id` | Identifiant court de l'image (12 premiers caractères du hash) |
| **Repository** | `image.repo_tags[0]` (avant `:`) | Nom du repository Docker |
| **Tag** | `image.repo_tags[0]` (après `:`) | Tag de l'image (ex : `latest`, `1.0`) |
| **Size** | `image.size` | Taille de l'image formatée (ex : `245 MB`) |
| **Created** | `image.created` | Date de création de l'image |
| **In Use** | `image.in_use` | Badge indiquant si l'image est utilisée par au moins un container |

### Tri et recherche

- **Tri** : chaque colonne de la table est triable en cliquant sur son en-tête.
- **Recherche textuelle** : un champ libre avec **debounce de 300 ms** permet de rechercher par repository, tag ou ID d'image. Le paramètre API est `search`.

### Pagination

La table utilise une pagination côté serveur via [`el-pagination`](https://element-plus.org/en-US/component/pagination.html). Les paramètres API sont `page` et `per_page`.

![Liste des images](../assets/screenshots/docker-images-list.png)

---

## Filtres

La barre de filtres en haut de la vue permet de combiner plusieurs critères. Toute modification déclenche automatiquement un appel à `GET /docker/images` avec les paramètres correspondants.

### Filtre par target

Un sélecteur de dropdown permet de choisir une machine cible spécifique. Par défaut, toutes les targets sont affichées.

### Filtre « In Use Only »

Un toggle switch permet d'afficher uniquement les images actuellement utilisées par au moins un container. Le paramètre API est `in_use=true`.

### Filtre « Dangling Only »

Un toggle switch permet d'afficher uniquement les images dangling (images sans tag, `<none>:<none>`). Le paramètre API est `dangling=true`.

> **Comportement** : les filtres se combinent entre eux. Par exemple, vous pouvez afficher uniquement les images dangling sur la machine `localhost`.

---

## Actions sur les images

Plusieurs boutons d'action sont disponibles dans l'en-tête de la vue et sur chaque ligne de la table.

### Inspecter une image

Un clic sur une ligne de la table ouvre la vue détaillée de l'image ([`ImageDetail.vue`](../../frontend/src/views/ImageDetail.vue)). Cette vue présente trois onglets :

- **Info** — métadonnées complètes de l'image (ID, tags, taille, date de création, architecture, OS, etc.)
- **History** — historique des couches de l'image avec les commandes de création
- **Layers** — analyse détaillée des couches avec leur taille respective

Les données sont récupérées via `GET /docker/images/{id}/inspect` et `GET /docker/images/{id}/history`.

### Pull une image

Le bouton **Pull** ouvre un dialogue de saisie permettant de spécifier le repository et le tag de l'image à télécharger.

- **Champ repository:tag** : saisie libre au format `repository:tag` (ex : `nginx:latest`)
- **Target** : sélection de la machine cible où puller l'image
- **Confirmation** : le dialogue affiche un récapitulatif avant lancement

Appel API : `POST /docker/images/pull` avec le body `{ "repository": "nginx", "tag": "latest", "target_id": "..." }`.

> **Note** : l'opération de pull peut être longue. Un indicateur de chargement s'affiche pendant le téléchargement.

### Supprimer une image

Le bouton **Delete** sur chaque ligne permet de supprimer l'image sélectionnée.

- **Confirmation** : un dialogue de confirmation s'affiche avec le nom/ID de l'image
- **Forcer** : une case à cocher permet de forcer la suppression (`force=true`) même si l'image est utilisée

Appel API : `DELETE /docker/images/{id}` avec le paramètre optionnel `force`.

### Prune les images

Le bouton **Prune** permet de supprimer en masse les images dangling (sans tag et non utilisées).

- **Confirmation** : un dialogue affiche le nombre d'images qui seront supprimées
- **Résultat** : un récapitulatif de l'espace libéré est affiché après l'opération

Appel API : `POST /docker/images/prune`.

---

## Détail d'une image

La vue détaillée ([`ImageDetail.vue`](../../frontend/src/views/ImageDetail.vue)) s'ouvre après un clic sur une image de la liste. Elle présente les informations complètes sous forme d'onglets.

### Onglet Info

Affiche les métadonnées principales de l'image :
- ID complet du hash
- Liste des tags (`repo_tags`)
- Taille brute et formatée
- Date de création
- Architecture et OS
- Docker version utilisée pour la création
- Commande par défaut (`Cmd`) et point d'entrée (`Entrypoint`)
- Variables d'environnement (`Env`)
- Labels
- Exposed ports

### Onglet History

Affiche l'historique des couches de l'image dans une table avec les colonnes :
- **Layer** — index de la couche
- **Created By** — commande qui a généré la couche
- **Size** — taille de la couche
- **Comment** — éventuel commentaire

### Onglet Layers

Affiche une analyse détaillée des couches avec visualisation de leur taille relative. Permet d'identifier les couches les plus volumineuses.

![Détail image](../assets/screenshots/docker-images-detail.png)

---

## Référence des endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/docker/images` | `GET` | Liste paginée des images avec filtres |
| `/docker/images/{id}` | `DELETE` | Suppression d'une image |
| `/docker/images/{id}/inspect` | `GET` | Inspection détaillée d'une image |
| `/docker/images/{id}/history` | `GET` | Historique des couches d'une image |
| `/docker/images/pull` | `POST` | Pull d'une image depuis un registry |
| `/docker/images/prune` | `POST` | Suppression des images dangling |

Voir l'implémentation complète dans [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py).
