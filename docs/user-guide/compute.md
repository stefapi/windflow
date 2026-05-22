# Guide utilisateur — Vue Compute

## Vue d'ensemble

La **vue Compute** (titre UI : *Containers — vue globale*) est le centre de gestion des ressources compute dans WindFlow. Elle offre une vision unifiée de l'ensemble des containers, stacks et objets découverts sur vos machines cibles, quelle que soit leur origine.

### Accès

Depuis la barre latérale principale : **Containers — vue globale**.

### Les trois niveaux de contrôle

La vue repose sur le [modèle Compute](../general_specs/12-compute-model.md) qui distingue trois catégories de ressources, identifiables visuellement par une légende de couleur en bas de page :

| Couleur | Catégorie | Description |
|---------|-----------|-------------|
| 🔵 Bleu | **Stacks WindFlow** | Stacks managées par WindFlow (source of truth dans l'application) |
| 🟠 Orange | **Discovered** | Objets découverts sur les machines (observés, non managés) |
| ⚪ Gris | **Standalone** | Containers individuels créés directement, sans composition |

---

## Table des matières

1. [Bandeau de statistiques](#bandeau-de-statistiques)
2. [Stacks WindFlow (managées)](#stacks-windflow-managées)
3. [Objets découverts (Discovered)](#objets-découverts-discovered)
4. [Containers standalone](#containers-standalone)
5. [Filtres et vues](#filtres-et-vues)

---

## Bandeau de statistiques

En haut de la vue, le composant [`ComputeStatsBanner`](../../frontend/src/components/ComputeStatsBanner.vue) affiche cinq métriques synthétiques agrégées sur l'ensemble de votre infrastructure. Ces données sont récupérées via l'endpoint `GET /compute/stats` (voir [`backend/app/api/v1/compute.py`](../../backend/app/api/v1/compute.py)).

| Métrique | Source API | Description |
|----------|------------|-------------|
| **Containers Total** | `stats.total_containers` | Nombre total de containers sur toutes les machines |
| **Running** | `stats.running_containers` | Containers en cours d'exécution. La valeur s'affiche en vert si au moins un container tourne, en rouge si zéro |
| **Stacks WindFlow** | `stats.stacks_running_count` / `stats.stacks_targets_count` | Stacks managées actives, avec le nombre de machines concernées |
| **Discovered** | `stats.discovered_count` / `stats.discovered_targets_count` | Objets découverts non managés, avec le nombre de machines concernées. La valeur s'affiche en orange si au moins un objet existe |
| **Standalone** | `stats.standalone_count` | Containers standalone (individuels sans composition), avec le nombre de machines concernées |

### Comportement de chargement

Pendant le chargement initial des données (`computeStore.statsLoading`), chaque carte affiche un skeleton animé ([`el-skeleton`](https://element-plus.org/en-US/component/skeleton.html)) à la place des valeurs.

---

## Stacks WindFlow (managées)

Cette section affiche les stacks que vous avez créées ou importées dans WindFlow. Chaque stack est présentée dans une carte pliable ([`el-collapse-item`](https://element-plus.org/en-US/component/collapse.html)).

### Identification d'une stack

Dans l'en-tête de chaque carte :
- **Nom de la stack**
- Badge bleu **`stack WindFlow`**
- Badge de **technologie** (ex : `compose`, `helm`)
- Badge de **target** (ex : `● localhost`)
- Compteur **`services_running/services_total running`** — indique l'état global (ex : `3/3 running`)

### Actions globales de stack

Chaque stack dépliée affiche une barre d'actions [`StackActionsBar`](../../frontend/src/components/compute/StackActionsBar.vue) avec trois boutons :

| Action | Comportement |
|--------|--------------|
| **Démarrer** | Démarre tous les services de la stack (désactivé si tous les services tournent déjà). Demande une confirmation préalable |
| **Arrêter** | Arrête tous les services de la stack (désactivé si tous les services sont arrêtés). Demande une confirmation préalable |
| **Redéployer** | Ouvre un dialogue de choix de stratégie :<br>• **Arrêt puis démarrage** — arrête tous les services puis les redémarre (temps d'arrêt court garanti)<br>• **Rolling (séquentiel)** — redémarre les services un par un pour maintenir la disponibilité |

### Expansion d'une stack — services

En dépliant une stack, vous accédez à ses services affichés dans une table [`ContainerTable`](../../frontend/src/components/compute/ContainerTable.vue) avec les colonnes suivantes :

- **Nom** du service
- **Image** Docker utilisée
- **Statut** (running, exited, etc.)
- **CPU %** — consommation processeur
- **Mémoire** — usage et limite
- **Uptime** — temps depuis le démarrage
- **Ports** — mappings exposés
- **Actions** — boutons par ligne

### Actions individuelles par service

Chaque ligne de service dispose de boutons d'action rapide :
- ▶ **Démarrer** — démarre le container
- ⏹ **Arrêter** — arrête le container
- 🔄 **Redémarrer** — redémarre le container
- 🗑️ **Supprimer** — supprime le container (avec confirmation)
- 📋 **Logs** — redirige vers la page de détail du container

### Actions en masse (bulk)

La sélection multiple de services via les cases à cocher de la table déclenche l'affichage de la barre [`BulkActionBar`](../../frontend/src/components/compute/BulkActionBar.vue). Elle permet d'appliquer une action groupée :

- **Démarrer** les services sélectionnés
- **Arrêter** les services sélectionnés
- **Redémarrer** les services sélectionnés
- **Supprimer** les services sélectionnés (avec confirmation)

### Boutons utilitaires

Dans l'en-tête de chaque stack :
- 📄 **Copier ID** — copie l'identifiant de la stack dans le presse-papiers
- 🔄 **Rafraîchir** — recharge les données de la vue
- **Éditer stack** — accède à l'édition de la stack (bouton de navigation)

---

## Objets découverts (Discovered)

Cette section liste les objets détectés sur vos machines mais qui ne sont pas encore managés par WindFlow (projets Compose externes, releases Helm, containers orphelins).

### Identification d'un objet découvert

Dans l'en-tête de chaque carte :
- **Nom de l'objet**
- Badge orange **`discovered`**
- Badge de **technologie**
- Badge de **target**
- Compteur **`services_running/services_total running`**

### Alert `source_path`

Si l'objet a été détecté via un fichier de définition (ex : `docker-compose.yml`), une alerte [`el-alert`](https://element-plus.org/en-US/component/alert.html) de type warning s'affiche :

> ⚠ Détecté via `/home/user/monitoring/docker-compose.yml` — lecture seule. Adoptez pour gérer depuis WindFlow.

### Badge « adoptable »

Un objet découvert peut être **adoptable** ou non. Si `adoptable=true`, des actions supplémentaires sont disponibles. Si `adoptable=false`, la section est en lecture seule.

### Bouton « Adopter »

Pour les objets adoptables, le bouton **↗ Adopter** ouvre le wizard d'adoption ([`AdoptionWizard`](../../frontend/src/components/compute/AdoptionWizard.vue)) qui vous guide en trois étapes pour importer l'objet dans WindFlow. Consultez le [guide d'adoption](STORY-039.4-docs-user-guide-adoption-containers.md) pour plus de détails.

### Actions start/stop conditionnelles

Pour les objets adoptables uniquement :
- **▶ Démarrer** — disponible uniquement si au moins un service est arrêté (`services_running < services_total`)
- **⏹ Arrêter** — disponible uniquement si au moins un service tourne (`services_running > 0`)

> **Note** : ces actions agissent sur l'ensemble des services de l'objet découvert, pas individuellement.

### Actions en masse

Comme pour les stacks managées, la sélection multiple de services dans un objet découvert affiche la [`BulkActionBar`](../../frontend/src/components/compute/BulkActionBar.vue) avec les actions groupées Démarrer, Arrêter, Redémarrer et Supprimer.

---

## Containers standalone

Cette section affiche les containers créés individuellement, sans appartenance à une composition ou une stack WindFlow.

### Identification

- En-tête de section avec badge gris
- Chaque container est affiché dans une table [`ContainerTable`](../../frontend/src/components/compute/ContainerTable.vue)
- Colonnes identiques aux services de stacks : nom, image, statut, CPU, mémoire, uptime, ports, actions

### Actions individuelles

Par container :
- ▶ Démarrer / ⏹ Arrêter / 🔄 Redémarrer / 🗑️ Supprimer / 📋 Logs

### Sélection multiple et actions en masse

La table supporte la sélection multiple. La [`BulkActionBar`](../../frontend/src/components/compute/BulkActionBar.vue) apparaît avec les actions Démarrer, Arrêter, Redémarrer et Supprimer.

### Suppression groupée

Le bouton **Supprimer** de la barre bulk ouvre un dialogue de confirmation affichant :
- La liste des containers concernés (limitée à 5, avec un indicateur `... et N autres`)
- Une case à cocher **Forcer la suppression** pour passer l'option `force=true` à l'API
- Un bouton **Supprimer N containers** pour confirmer

### Bouton « Promouvoir en stack »

Chaque container standalone dispose d'un bouton pour le transformer en stack WindFlow. Cette action ouvre un dialogue demandant le nom de la nouvelle stack. Consultez le [guide des stacks](STORY-039.3-docs-user-guide-stacks.md) pour plus de détails.

---

## Filtres et vues

### Filtres combinables

La barre de filtres en haut de la vue permet de combiner plusieurs critères. Toute modification déclenche automatiquement un appel à `GET /compute/global` avec les paramètres correspondants.

#### Filtre par type

Un groupe de radio buttons permet de filtrer par catégorie :
- **Tout** (défaut) — affiche les trois sections
- **Stacks WindFlow** — filtre `filterType='managed'`
- **Discovered** — filtre `filterType='discovered'`
- **Standalone** — filtre `filterType='standalone'`

#### Recherche textuelle

Un champ libre avec **debounce de 300 ms** permet de rechercher par nom de stack, de service ou de container. Le paramètre API est `search`.

#### Filtre par technologie

Des pills cliquables affichent les technologies détectées (Docker, Compose, Helm…). Le clic permet de sélectionner ou désélectionner une technologie.

#### Filtre par target

Des pills cliquables affichent les machines cibles enregistrées (localhost, vps-ovh…). Le clic permet de filtrer par machine.

> **Comportement** : les filtres se combinent entre eux. Par exemple, vous pouvez afficher uniquement les stacks WindFlow en technologie Compose sur la machine localhost, avec une recherche textuelle sur "monitoring".

### Toggle « Tout / Par machine »

Deux boutons en haut à droite de la vue permettent de changer le mode d'affichage :

#### Mode « Tout » (défaut)

Les trois sections sont affichées séparément : Stacks WindFlow → Discovered → Standalone. Chaque section utilise ses composants dédiés avec actions complètes.

#### Mode « Par machine »

Les ressources sont regroupées par target via le composant [`TargetGroupView`](../../frontend/src/components/compute/TargetGroupView.vue). L'appel API utilise `GET /compute/global?group_by=target`.

Pour chaque machine, un panneau pliable affiche :
- **Nom de la target**
- **Technologie** déployée (ex : Docker Engine 26.1)
- **Métriques agrégées** : CPU total (%) et RAM utilisée / totale

Sous-sections internes :
- **Stacks** (bleu) — services des stacks managées sur cette machine
- **Discovered** (orange) — services des objets découverts sur cette machine
- **Standalone** (gris) — containers standalone sur cette machine

> **Important** : en mode « Par machine », les tables sont en mode `size="small"` et **n'offrent pas d'actions individuelles** (lecture seule). Pour agir sur une ressource, basculez en mode « Tout ».

---

## Glossaire des types API

| Type | Description | Fichier source |
|------|-------------|----------------|
| `ComputeStatsResponse` | 10 compteurs synthétiques pour le bandeau | [`frontend/src/types/api.ts`](../../frontend/src/types/api.ts) |
| `ComputeGlobalView` | Vue unifiée avec les 3 sections (mode « Tout ») | [`frontend/src/types/api.ts`](../../frontend/src/types/api.ts) |
| `TargetGroup` | Groupe de ressources par machine (mode « Par machine ») | [`frontend/src/types/api.ts`](../../frontend/src/types/api.ts) |
| `StackWithServices` | Stack managée avec ses services et métriques | [`frontend/src/types/api.ts`](../../frontend/src/types/api.ts) |
| `DiscoveredItem` | Objet découvert avec propriétés `adoptable` et `source_path` | [`frontend/src/types/api.ts`](../../frontend/src/types/api.ts) |
| `StandaloneContainer` | Container individuel avec métriques inline | [`frontend/src/types/api.ts`](../../frontend/src/types/api.ts) |
| `ServiceWithMetrics` | Service individuel avec CPU%, mémoire, uptime, ports | [`frontend/src/types/api.ts`](../../frontend/src/types/api.ts) |

## Référence des endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/compute/stats` | `GET` | Statistiques synthétiques pour le bandeau |
| `/compute/global` | `GET` | Vue unifiée avec filtres. `group_by=stack` (défaut) ou `group_by=target` |

Voir l'implémentation complète dans [`backend/app/api/v1/compute.py`](../../backend/app/api/v1/compute.py).
