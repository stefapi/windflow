# Guide utilisateur — Docker Networks

## Vue d'ensemble

La **vue Docker Networks** est le centre de gestion des réseaux Docker sur vos machines cibles. Elle offre une vision unifiée de l'ensemble des réseaux, avec des outils de filtrage, de recherche et d'actions (création, suppression, inspection, prune).

### Accès

Depuis la barre latérale principale : **Docker → Networks**.

---

## Table des matières

1. [Liste des réseaux](#liste-des-réseaux)
2. [Filtres](#filtres)
3. [Créer un réseau](#créer-un-réseau)
4. [Actions sur les réseaux](#actions-sur-les-réseaux)

---

## Liste des réseaux

La vue affiche une table paginée ([`el-table`](https://element-plus.org/en-US/component/table.html)) listant l'ensemble des réseaux Docker présents sur les targets sélectionnées. Les données sont récupérées via l'endpoint `GET /docker/networks` (voir [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py)).

### Colonnes affichées

| Colonne | Source API | Description |
|---------|------------|-------------|
| **ID** | `network.id` | Identifiant court du réseau (12 premiers caractères) |
| **Name** | `network.name` | Nom du réseau |
| **Driver** | `network.driver` | Driver réseau (ex : `bridge`, `host`, `overlay`) |
| **Scope** | `network.scope` | Portée du réseau (`local` ou `global`) |
| **Subnet** | `network.ipam.config[0].subnet` | Sous-réseau CIDR (ex : `172.18.0.0/16`) |
| **Gateway** | `network.ipam.config[0].gateway` | Passerelle par défaut du réseau |

### Tri et recherche

- **Tri** : chaque colonne de la table est triable en cliquant sur son en-tête.
- **Recherche textuelle** : un champ libre avec **debounce de 300 ms** permet de rechercher par nom ou ID de réseau. Le paramètre API est `search`.

### Pagination

La table utilise une pagination côté serveur via [`el-pagination`](https://element-plus.org/en-US/component/pagination.html). Les paramètres API sont `page` et `per_page`.

![Liste des réseaux](../assets/screenshots/docker-networks-list.png)

---

## Filtres

La barre de filtres en haut de la vue permet de combiner plusieurs critères. Toute modification déclenche automatiquement un appel à `GET /docker/networks` avec les paramètres correspondants.

### Filtre par target

Un sélecteur de dropdown permet de choisir une machine cible spécifique. Par défaut, toutes les targets sont affichées.

### Filtre par driver

Un groupe de pills cliquables permet de filtrer par type de driver :
- **bridge** — réseau pont par défaut des containers
- **host** — utilisation directe de l'interface réseau du host
- **overlay** — réseau multi-host pour Docker Swarm
- **macvlan** — attribution d'une adresse MAC propre au container
- **none** — pas de connectivité réseau

> **Comportement** : les filtres se combinent entre eux. Par exemple, vous pouvez afficher uniquement les réseaux de type `bridge` sur la machine `localhost`.

---

## Créer un réseau

Le bouton **Create** dans l'en-tête de la vue ouvre un dialogue de création de réseau.

### Champs du dialogue

| Champ | Type | Description |
|-------|------|-------------|
| **Name** | Texte | Nom du réseau (obligatoire) |
| **Driver** | Dropdown | Driver réseau (`bridge` par défaut) |
| **Subnet** | Texte | Sous-réseau CIDR (ex : `172.20.0.0/16`) |
| **Gateway** | Texte | Passerelle par défaut (ex : `172.20.0.1`) |

### Validation

- Le nom du réseau est obligatoire et doit être unique sur la target.
- Le subnet et la gateway sont optionnels mais doivent être cohérents si renseignés.

Appel API : `POST /docker/networks` avec le body `{ "name": "...", "driver": "bridge", "subnet": "...", "gateway": "...", "target_id": "..." }`.

> **Note** : après création, le dialogue se ferme et la liste des réseaux est rafraîchie automatiquement.

---

## Actions sur les réseaux

Plusieurs boutons d'action sont disponibles sur chaque ligne de la table.

### Inspecter un réseau

Un clic sur une ligne de la table ouvre un modal/panneau affichant les détails JSON complets du réseau.

Les informations affichées incluent :
- **Métadonnées** — ID, nom, driver, scope, date de création
- **Configuration IPAM** — subnet, gateway, plage d'IP
- **Containers attachés** — liste des containers connectés à ce réseau avec leur IP interne
- **Options** — options spécifiques au driver
- **Labels** — labels associés au réseau
- **JSON brut** — affichage formaté de la réponse complète de l'API Docker

Les données sont récupérées via `GET /docker/networks/{id}`.

![Inspect réseau](../assets/screenshots/docker-networks-inspect.png)

### Supprimer un réseau

Le bouton **Delete** sur chaque ligne permet de supprimer le réseau sélectionné.

- **Confirmation** : un dialogue de confirmation s'affiche avec le nom du réseau
- **Blocage** : la suppression est refusée si des containers sont encore attachés au réseau

Appel API : `DELETE /docker/networks/{id}`.

### Prune les réseaux

Le bouton **Prune** permet de supprimer en masse les réseaux non utilisés (sans container attaché).

- **Confirmation** : un dialogue affiche le nombre de réseaux qui seront supprimés
- **Exclusions** : les réseaux système (comme `bridge`, `host`, `none`) ne sont jamais supprimés

Appel API : `POST /docker/networks/prune`.

---

## Référence des endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/docker/networks` | `GET` | Liste paginée des réseaux avec filtres |
| `/docker/networks` | `POST` | Création d'un réseau |
| `/docker/networks/{id}` | `GET` | Inspection détaillée d'un réseau |
| `/docker/networks/{id}` | `DELETE` | Suppression d'un réseau |
| `/docker/networks/prune` | `POST` | Suppression des réseaux non utilisés |

Voir l'implémentation complète dans [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py).
