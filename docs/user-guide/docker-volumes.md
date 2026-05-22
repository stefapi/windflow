# Guide utilisateur — Docker Volumes

## Vue d'ensemble

La **vue Docker Volumes** est le centre de gestion des volumes persistants Docker sur vos machines cibles. Elle offre une vision unifiée de l'ensemble des volumes, avec des outils de filtrage, de recherche et d'actions (création, suppression, prune).

### Accès

Depuis la barre latérale principale : **Docker → Volumes**.

---

## Table des matières

1. [Liste des volumes](#liste-des-volumes)
2. [Filtres](#filtres)
3. [Créer un volume](#créer-un-volume)
4. [Actions sur les volumes](#actions-sur-les-volumes)

---

## Liste des volumes

La vue affiche une table paginée ([`el-table`](https://element-plus.org/en-US/component/table.html)) listant l'ensemble des volumes Docker présents sur les targets sélectionnées. Les données sont récupérées via l'endpoint `GET /docker/volumes` (voir [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py)).

### Colonnes affichées

| Colonne | Source API | Description |
|---------|------------|-------------|
| **Name** | `volume.name` | Nom du volume Docker |
| **Driver** | `volume.driver` | Driver utilisé (ex : `local`, `nfs`) |
| **Mountpoint** | `volume.mountpoint` | Chemin de montage sur le host |
| **Size** | `volume.size` | Taille occupée par le volume (si disponible) |
| **Created** | `volume.created_at` | Date de création du volume |

### Tri et recherche

- **Tri** : chaque colonne de la table est triable en cliquant sur son en-tête.
- **Recherche textuelle** : un champ libre avec **debounce de 300 ms** permet de rechercher par nom de volume ou par driver. Le paramètre API est `search`.

### Pagination

La table utilise une pagination côté serveur via [`el-pagination`](https://element-plus.org/en-US/component/pagination.html). Les paramètres API sont `page` et `per_page`.

![Liste des volumes](../assets/screenshots/docker-volumes-list.png)

---

## Filtres

La barre de filtres en haut de la vue permet de combiner plusieurs critères. Toute modification déclenche automatiquement un appel à `GET /docker/volumes` avec les paramètres correspondants.

### Filtre par target

Un sélecteur de dropdown permet de choisir une machine cible spécifique. Par défaut, toutes les targets sont affichées.

### Filtre « Dangling Only »

Un toggle switch permet d'afficher uniquement les volumes dangling (volumes non référencés par aucun container). Le paramètre API est `dangling=true`.

> **Comportement** : les filtres se combinent entre eux. Par exemple, vous pouvez afficher uniquement les volumes dangling sur la machine `localhost`.

---

## Créer un volume

Le bouton **Create** dans l'en-tête de la vue ouvre un dialogue de création de volume.

### Champs du dialogue

| Champ | Type | Description |
|-------|------|-------------|
| **Name** | Texte | Nom du volume (obligatoire) |
| **Driver** | Dropdown | Driver de stockage (`local` par défaut) |
| **Driver Options** | Key/Value pairs | Options spécifiques au driver (ex : `type=nfs`, `o=addr=...`) |

### Validation

- Le nom du volume est obligatoire et doit être unique sur la target.
- Les options du driver sont optionnelles et dépendent du driver sélectionné.

Appel API : `POST /docker/volumes` avec le body `{ "name": "...", "driver": "local", "driver_opts": {...}, "target_id": "..." }`.

> **Note** : après création, le dialogue se ferme et la liste des volumes est rafraîchie automatiquement.

![Création volume](../assets/screenshots/docker-volumes-create.png)

---

## Actions sur les volumes

Plusieurs boutons d'action sont disponibles sur chaque ligne de la table.

### Supprimer un volume

Le bouton **Delete** sur chaque ligne permet de supprimer le volume sélectionné.

- **Confirmation** : un dialogue de confirmation s'affiche avec le nom du volume
- **Forcer** : une case à cocher permet de forcer la suppression (`force=true`) même si le volume est utilisé

Appel API : `DELETE /docker/volumes/{name}` avec le paramètre optionnel `force`.

> **Attention** : la suppression d'un volume est irréversible et entraîne la perte définitive des données qu'il contient.

### Prune les volumes

Le bouton **Prune** permet de supprimer en masse les volumes non utilisés (non référencés par aucun container).

- **Confirmation** : un dialogue affiche le nombre de volumes qui seront supprimés
- **Résultat** : un récapitulatif de l'espace libéré est affiché après l'opération

Appel API : `POST /docker/volumes/prune`.

---

## Référence des endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/docker/volumes` | `GET` | Liste paginée des volumes avec filtres |
| `/docker/volumes` | `POST` | Création d'un volume |
| `/docker/volumes/{name}` | `DELETE` | Suppression d'un volume |
| `/docker/volumes/prune` | `POST` | Suppression des volumes non utilisés |

Voir l'implémentation complète dans [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py).
