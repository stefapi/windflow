# Guide utilisateur — Containers

## Vue d'ensemble

Ce guide couvre la gestion des containers Docker dans WindFlow, de leur création manuelle à leur cycle de vie complet (édition à chaud, recréation, promotion en stack).

### Accès

- Depuis la [vue Compute](../../docs/user-guide/compute.md) : bouton **Créer un container** dans la section Containers standalone.
- Depuis la vue **Containers** (liste) : bouton **+** en haut de la table.

---

## Table des matières

1. [Création manuelle de containers](#création-manuelle-de-containers)
2. [Édition à chaud des containers](#édition-à-chaud-des-containers)
3. [Cycle de vie d'un container](#cycle-de-vie-dun-container)
4. [Référence des endpoints](#référence-des-endpoints)
5. [Fichiers source](#fichiers-source)

---

## Création manuelle de containers

WindFlow permet de créer des containers Docker individuels sans passer par une stack ou un fichier `docker-compose.yml`. Cette fonctionnalité est utile pour des tests rapides, des containers utilitaires ou des services isolés.

### Ouverture du formulaire

Le formulaire de création s'ouvre dans une boîte de dialogue [`el-dialog`](https://element-plus.org/en-US/component/dialog.html) via le composant [`ContainerCreateDialog.vue`](../../frontend/src/components/ContainerCreateDialog.vue).

- Le dialogue est accessible depuis la vue Compute (bouton **Créer un container**) ou depuis la vue Containers (bouton **+**).
- Le titre du dialogue s'adapte selon le contexte d'appel.

### Champs obligatoires

Deux champs sont requis pour créer un container :

| Champ | Type | Validation | Description |
|-------|------|------------|-------------|
| **Nom** | `string` | Pattern `^[a-zA-Z0-9][a-zA-Z0-9_.-]*$` | Nom unique du container sur la target Docker |
| **Image** | `string` | Non vide | Image Docker à utiliser (ex : `nginx:latest`, `postgres:15`) |

> **Note** : Le nom du container doit être unique sur la machine cible. Si un container du même nom existe déjà, l'API retourne une erreur `409 Conflict`.

### Variables d'environnement

Le formulaire propose un tableau dynamique de variables d'environnement sous forme de paires clé/valeur.

| Colonne | Type | Description |
|---------|------|-------------|
| **Clé** | `string` | Nom de la variable (ex : `DATABASE_URL`) |
| **Valeur** | `string` | Valeur de la variable |

- Les lignes peuvent être ajoutées ou supprimées dynamiquement.
- Le masquage automatique des secrets est activé pour les clés contenant `PASSWORD`, `SECRET`, `TOKEN`, `KEY`, `API_KEY`, `CREDENTIAL` (via le composable [`useSecretMasker`](../../frontend/src/composables/useSecretMasker.ts)).
- Les valeurs masquées s'affichent sous forme de points (`••••`) dans l'interface.

### Mappings de ports

Les ports exposés par le container peuvent être mappés sur l'hôte via un tableau dynamique :

| Colonne | Type | Description |
|---------|------|-------------|
| **Hôte** | `string` | Port ou plage sur l'hôte (ex : `8080`, `8080-8085`) |
| **Container** | `string` | Port interne du container (ex : `80`) |
| **Protocole** | `string` | `tcp` (défaut) ou `udp` |

Le format affiché est `hôte:container` (ex : `8080:80/tcp`).

### Volumes

Les volumes permettent de monter des répertoires ou des volumes nommés dans le container :

| Colonne | Type | Description |
|---------|------|-------------|
| **Source** | `string` | Chemin sur l'hôte ou nom du volume |
| **Destination** | `string` | Chemin de montage dans le container |

Le format est `source:destination` (ex : `/data:/var/lib/postgresql/data`).

### Options avancées

Des options avancées sont disponibles dans un panneau repliable :

| Option | Type | Valeurs possibles | Défaut | Description |
|--------|------|-------------------|--------|-------------|
| **Restart policy** | `el-select` | `no`, `always`, `on-failure`, `unless-stopped` | `no` | Politique de redémarrage automatique du container |
| **Network mode** | `string` | `bridge`, `host`, `none`, etc. | `bridge` | Mode réseau du container |
| **Privileged** | `boolean` | `true` / `false` | `false` | Exécution en mode privilégié (accès complet au host) |

#### Détail des restart policies

| Valeur | Comportement |
|--------|--------------|
| `no` | Aucun redémarrage automatique (défaut) |
| `always` | Redémarrage systématique quel que soit le code de sortie |
| `on-failure` | Redémarrage uniquement si le code de sortie est non nul |
| `unless-stopped` | Redémarrage sauf si le container a été arrêté manuellement |

### Validation et création

Avant la création, le formulaire valide les champs obligatoires et le format du nom.

- **Bouton Créer** : Appelle `POST /docker/containers` avec le body [`ContainerCreateRequest`](../../backend/app/schemas/docker.py).
- **Erreur 409** : Si un container du même nom existe déjà sur la target, un message d'erreur contextuel s'affiche.
- **Succès** : Le container est créé et apparaît dans la liste des containers standalone.

> **Note** : Le container est créé mais **non démarré automatiquement**. Utilisez le bouton ▶ **Démarrer** depuis la liste pour le lancer.
>
> **Important** : La création manuelle diffère de la création via stack :
> - Pas de fichier `docker-compose.yml`
> - Pas de gestion de version ni de déploiements historisés
> - Pas d'orchestration groupée (start/stop de plusieurs services)
> - Le container reste **standalone** jusqu'à sa [promotion en stack](#promotion-en-stack)

---

## Édition à chaud des containers

L'édition à chaud permet de modifier certains paramètres d'un container en cours d'exécution **sans le recréer**, ainsi que d'autres paramètres nécessitant une recréation.

### Accès

Depuis le détail d'un container : onglet **Configuration** ([`ContainerConfigTab.vue`](../../frontend/src/components/ContainerConfigTab.vue)).

### Modifications sans recréation (à chaud)

Ces modifications sont appliquées immédiatement par l'API Docker sans interruption du service.

#### Restart Policy

La politique de redémarrage peut être modifiée à tout moment :

| Option | Comportement |
|--------|--------------|
| `no` | Aucun redémarrage automatique |
| `always` | Redémarrage systématique |
| `on-failure` | Redémarrage si échec. Un champ **Max retry count** apparaît pour limiter le nombre de tentatives |
| `unless-stopped` | Redémarrage sauf arrêt manuel |

- **Bouton Appliquer** → `PATCH /docker/containers/{id}/restart-policy`
- Schéma : [`ContainerUpdateRestartPolicyRequest`](../../backend/app/schemas/docker.py) (`name`, `maximum_retry_count` ≥ 0)

#### Resource Limits

Les limites de ressources peuvent être ajustées dynamiquement :

| Limite | Unité | Contrainte | Description |
|--------|-------|------------|-------------|
| **Memory limit** | MB / GB | ≥ 0 | Limite de mémoire allouée au container |
| **CPU shares** | entier | ≥ 0 | Poids relatif CPU (1024 = poids par défaut) |
| **PIDs limit** | entier | ≥ -1 | Nombre maximal de processus (`-1` = illimité) |

- **Bouton Appliquer** → `PATCH /docker/containers/{id}/resources`
- Schéma : [`ContainerUpdateResourcesRequest`](../../backend/app/schemas/docker.py) (`memory_limit` en bytes, `cpu_shares`, `pids_limit`)

> **Note** : Ces modifications sont appliquées immédiatement sans interruption du service.

### Modifications avec recréation

Ces modifications nécessitent l'arrêt et la recréation du container. Elles sont regroupées dans une section distincte avec un avertissement visible.

#### Variables d'environnement

- Tableau éditable de paires clé/valeur.
- ⚠️ **Alerte** : "Le layer writable sera perdu" — toute modification déclenche une recréation.

#### Labels

- Tableau éditable de paires clé/valeur.
- ⚠️ Même alerte sur la perte du layer writable.

#### Image

- Champ pour spécifier une nouvelle image Docker.
- Checkbox **Puller avant recréation** : force le `docker pull` de la nouvelle image.
- ⚠️ Alert sur la perte du layer writable.

#### Ports

- Tableau éditable avec les colonnes : Host IP, Host Port, Container Port, Protocole.
- Validation des doublons en temps réel.
- ⚠️ Alert sur la perte du layer writable.

> **Important** : Toute modification dans ces sections déclenche un arrêt + recréation du container. Les données non persistées dans un volume seront perdues. Assurez-vous que les données critiques sont sauvegardées dans des volumes ou bind mounts persistants.

### Différence entre à chaud et recréation

| Critère | Édition à chaud | Recréation requise |
|---------|-----------------|-------------------|
| **Disponibilité** | Immédiate, sans interruption | Temps d'arrêt pendant la recréation |
| **Données** | Aucune perte | Layer writable perdu |
| **Paramètres concernés** | Restart policy, resource limits | Env vars, labels, image, ports |
| **API Docker** | `Container.update()` | `Container.stop()` → `Container.remove()` → `Container.create()` → `Container.start()` |
| **Bouton d'action** | **Appliquer** ( PATCH ) | **Recréer** ( POST ) |

---

## Cycle de vie d'un container

Le cycle de vie complet d'un container dans WindFlow suit un flux séquentiel d'étapes, chacune avec ses actions disponibles.

### Diagramme de flux

```
Création (manuelle ou via stack)
    ↓
Démarrage (▶)
    ↓
Supervision (logs, stats, processes)
    ↓
Édition à chaud (restart, ressources)
    ↓
Recréation (image, ports, env)
    ↓
Adoption (standalone → stack managée)
    ↓
Arrêt (⏹)
    ↓
Suppression (🗑️)
```

### Table des actions par état

| État | Actions disponibles | Endpoints |
|------|---------------------|-----------|
| **running** | ⏹ Arrêter, 🔄 Redémarrer, ⏸ Pause, 📋 Logs, 🔧 Config | `POST /docker/containers/{id}/stop`, `restart`, `pause` ; `GET /docker/containers/{id}/logs` |
| **paused** | ▶ Reprendre, ⏹ Arrêter | `POST /docker/containers/{id}/unpause`, `stop` |
| **stopped** | ▶ Démarrer, 🗑️ Supprimer, ↗ Promouvoir en stack | `POST /docker/containers/{id}/start` ; `DELETE /docker/containers/{id}` ; `POST /docker/containers/{id}/promote` |
| **exited** | ▶ Démarrer, 🗑️ Supprimer | `POST /docker/containers/{id}/start` ; `DELETE /docker/containers/{id}` |

### Promotion en stack

Un container standalone peut être promu en stack WindFlow managée. Cette action :

- Crée une nouvelle stack mono-service à partir du container.
- Génère un template Docker Compose équivalent.
- Le container est alors géré comme un service de stack.

**API** : `POST /docker/containers/{id}/promote`

Pour plus de détails sur le processus d'adoption, consultez le [guide d'adoption](../../docs/user-guide/adoption.md).

### Actions batch

Les actions groupées permettent d'appliquer une opération à plusieurs containers simultanément :

| Action | Endpoint | Description |
|--------|----------|-------------|
| Démarrage multiple | `POST /docker/containers/batch/start` | Démarre tous les containers sélectionnés |
| Arrêt multiple | `POST /docker/containers/batch/stop` | Arrête tous les containers sélectionnés |

---

## Référence des endpoints

### Création

| Endpoint | Méthode | Description | Schéma |
|----------|---------|-------------|--------|
| `/docker/containers` | `POST` | Créer un container | [`ContainerCreateRequest`](../../backend/app/schemas/docker.py) → [`ContainerDetailResponse`](../../backend/app/schemas/docker.py) |

### Édition à chaud

| Endpoint | Méthode | Description | Schéma |
|----------|---------|-------------|--------|
| `/docker/containers/{id}/restart-policy` | `PATCH` | Modifier la restart policy | [`ContainerUpdateRestartPolicyRequest`](../../backend/app/schemas/docker.py) |
| `/docker/containers/{id}/resources` | `PATCH` | Modifier les limites de ressources | [`ContainerUpdateResourcesRequest`](../../backend/app/schemas/docker.py) |

### Recréation

| Endpoint | Méthode | Description | Schéma |
|----------|---------|-------------|--------|
| `/docker/containers/{id}/recreate` | `POST` | Recréer le container avec nouveaux paramètres | [`ContainerRecreateRequest`](../../backend/app/schemas/docker.py) → [`ContainerRecreateResponse`](../../backend/app/schemas/docker.py) |

### Cycle de vie

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/docker/containers/{id}/start` | `POST` | Démarrer le container |
| `/docker/containers/{id}/stop` | `POST` | Arrêter le container |
| `/docker/containers/{id}/restart` | `POST` | Redémarrer le container |
| `/docker/containers/{id}/pause` | `POST` | Mettre en pause le container |
| `/docker/containers/{id}/unpause` | `POST` | Reprendre un container en pause |
| `/docker/containers/{id}` | `DELETE` | Supprimer le container |
| `/docker/containers/{id}/promote` | `POST` | Promouvoir en stack |
| `/docker/containers/batch/start` | `POST` | Démarrer plusieurs containers |
| `/docker/containers/batch/stop` | `POST` | Arrêter plusieurs containers |

### Supervision

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/docker/containers/{id}/logs` | `GET` | Logs du container |
| `/docker/containers/{id}/stats` | `GET` | Statistiques instantanées |
| `/docker/containers/{id}/top` | `GET` | Processus du container |
| `/docker/containers/{id}/shells` | `GET` | Shells disponibles |

## Fichiers source

**Backend :**
- [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py) — Endpoints containers (création, édition, cycle de vie, batch)
- [`backend/app/services/container_builder.py`](../../backend/app/services/container_builder.py) — Logique de création de containers
- [`backend/app/schemas/docker.py`](../../backend/app/schemas/docker.py) — Schémas Pydantic (`ContainerCreateRequest`, `ContainerDetailResponse`, `ContainerUpdateRestartPolicyRequest`, `ContainerUpdateResourcesRequest`, `ContainerRecreateRequest`, `ContainerRecreateResponse`)

**Frontend :**
- [`frontend/src/components/ContainerCreateDialog.vue`](../../frontend/src/components/ContainerCreateDialog.vue) — Dialogue de création manuelle
- [`frontend/src/components/ContainerConfigTab.vue`](../../frontend/src/components/ContainerConfigTab.vue) — Onglet Configuration (édition à chaud et recréation)
- [`frontend/src/composables/useSecretMasker.ts`](../../frontend/src/composables/useSecretMasker.ts) — Masquage automatique des secrets
