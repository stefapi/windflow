# Guide utilisateur — Stacks

## Vue d'ensemble

La **vue Stacks** est le centre de gestion des stacks WindFlow. Elle permet de créer, importer, exporter et gérer le cycle de vie complet de vos stacks Docker Compose, ainsi que d'effectuer des actions globales (démarrage, arrêt, redéploiement, duplication, archivage).

### Accès

Depuis la barre latérale principale : **Stacks**.

---

## Table des matières

1. [Export de stacks](#export-de-stacks)
2. [Import de stacks](#import-de-stacks)
3. [Actions de stack](#actions-de-stack)
4. [Cycle de vie d'une stack](#cycle-de-vie-dune-stack)
5. [Référence des endpoints](#référence-des-endpoints)

---

## Export de stacks

L'export permet de sauvegarder une stack sous forme de fichier JSON, utile pour la sauvegarde, le partage entre environnements ou la migration vers une autre organisation.

### Accès

Depuis [`Stacks.vue`](../../frontend/src/views/Stacks.vue) : bouton **Export** dans la liste des stacks ou dans le panneau de détail d'une stack.

### Format du fichier exporté

L'endpoint retourne un fichier JSON au format **v1.0** avec un header `Content-Disposition` provoquant le téléchargement automatique du fichier `{stack_name}.json`.

```json
{
  "version": "1.0",
  "stack": {
    "name": "...",
    "description": "...",
    "version": "...",
    "category": "...",
    "tags": ["..."],
    "template": { ... },
    "variables": { ... },
    "icon_url": "...",
    "screenshots": ["..."],
    "documentation_url": "...",
    "author": "...",
    "license": "..."
  }
}
```

### Champs exportés

| Champ | Type | Description |
|-------|------|-------------|
| `name` | `string` | Nom de la stack |
| `description` | `string \| null` | Description textuelle |
| `version` | `string` | Version sémantique (ex : `1.0.0`) |
| `category` | `string \| null` | Catégorie (ex : `database`, `web`) |
| `tags` | `string[]` | Liste de tags |
| `template` | `object` | Template Docker Compose complet |
| `variables` | `object` | Variables configurables et leurs valeurs |
| `icon_url` | `string \| null` | URL de l'icône de la stack |
| `screenshots` | `string[]` | Liste des URLs de captures d'écran |
| `documentation_url` | `string \| null` | Lien vers la documentation |
| `author` | `string \| null` | Auteur de la stack |
| `license` | `string` | Licence (défaut : `MIT`) |

### Cas d'usage

- **Sauvegarde** avant une modification majeure du template ou des variables
- **Partage** de configurations entre équipes ou environnements
- **Migration** vers une autre organisation ou instance WindFlow

Appel API : `GET /stacks/{stack_id}/export` (voir [`backend/app/api/v1/import_export.py`](../../backend/app/api/v1/import_export.py)).

> **Note** : l'export est limité aux stacks appartenant à votre organisation. Les super-utilisateurs peuvent exporter toute stack.

---

## Import de stacks

L'import permet de créer une nouvelle stack à partir d'un fichier JSON exporté précédemment.

### Accès

Depuis [`Stacks.vue`](../../frontend/src/views/Stacks.vue) : bouton **Import Stack** en haut de la liste des stacks.

### Procédure

1. Cliquez sur **Import Stack** pour ouvrir le dialogue de sélection de fichier
2. Sélectionnez un fichier `.json` au format d'export v1.0
3. L'application valide le format et crée la stack

### Validation du format

Le fichier doit respecter les critères suivants :

| Critère | Détail |
|---------|--------|
| **Version** | Le champ `version` doit être `"1.0"` |
| **Racine** | Le champ `stack` doit être présent et contenir les données |
| **Template** | Le champ `stack.template` est obligatoire |
| **Nom** | Le champ `stack.name` est obligatoire |

En cas de format invalide, l'API retourne une erreur `400 Bad Request` avec un message descriptif.

### Résultat

La stack importée est créée avec les propriétés suivantes :

- **Visibilité** : `is_public: false` (privée par défaut)
- **Organisation** : rattachée à l'organisation de l'utilisateur courant
- **Variables** : importées telles quelles depuis le fichier
- **Tags** : conservés depuis le fichier source

### Cas d'usage

- **Restauration** d'une stack depuis une sauvegarde
- **Migration** depuis un autre environnement WindFlow
- **Partage** de stacks entre équipes via des fichiers JSON

Appel API : `POST /stacks/import` (voir [`backend/app/api/v1/import_export.py`](../../backend/app/api/v1/import_export.py)).

---

## Actions de stack

Chaque stack dispose d'un ensemble d'actions globales accessibles depuis la barre d'actions [`StackActionsBar`](../../frontend/src/components/compute/StackActionsBar.vue) dans la vue Compute, ou depuis les boutons d'action dans [`Stacks.vue`](../../frontend/src/views/Stacks.vue).

### Démarrer une stack (Start)

Démarre tous les services de la stack en parallèle. Les containers déjà en cours d'exécution sont ignorés.

- **Comportement** : parcourt tous les containers de la stack et démarre ceux dont l'état n'est pas `running`
- **Résultat** : retourne le nombre de services affectés dans `affected_services`
- **Désactivé si** : tous les services tournent déjà

Appel API : `POST /stacks/{stack_id}/start`. Réponse : [`StackActionResponse`](../../backend/app/schemas/stack.py).

### Arrêter une stack (Stop)

Arrête tous les services de la stack. Les containers déjà arrêtés sont ignorés.

- **Paramètre optionnel** : `timeout` (défaut : `10` secondes) — délai avant arrêt forcé
- **Comportement** : parcourt tous les containers et arrête ceux en état `running`
- **Désactivé si** : tous les services sont déjà arrêtés

Appel API : `POST /stacks/{stack_id}/stop`. Réponse : [`StackActionResponse`](../../backend/app/schemas/stack.py).

### Redéployer une stack (Redeploy)

Redéploie tous les services de la stack selon la stratégie choisie. Un dialogue de confirmation s'affiche dans [`StackActionsBar.vue`](../../frontend/src/components/compute/StackActionsBar.vue) permettant de sélectionner la stratégie.

#### Stratégies de redéploiement

| Stratégie | Identifiant | Comportement |
|-----------|-------------|--------------|
| **Arrêt puis démarrage** | `stop_start` (défaut) | Arrête tous les containers, puis les redémarre. Temps d'arrêt court garanti |
| **Rolling (séquentiel)** | `rolling` | Redémarre les services un par un : stop → start → vérification → suivant. Maintient la disponibilité |

#### Options

| Option | Type | Description |
|--------|------|-------------|
| `pull_images` | `boolean` | Force le pull des dernières versions d'images avant redéploiement |

Appel API : `POST /stacks/{stack_id}/redeploy` avec le body [`StackRedeployRequest`](../../backend/app/schemas/stack.py). Réponse : [`StackRedeployResponse`](../../backend/app/schemas/stack.py).

### Dupliquer une stack (Duplicate)

Crée une copie intégrale de la stack avec un nouveau nom. Un dialogue demande les informations suivantes :

| Champ | Type | Description |
|-------|------|-------------|
| **New Stack Name** | `string` (obligatoire) | Nom de la nouvelle stack |
| **Organization** | `string` (optionnel) | Organisation cible (défaut : organisation courante) |

La stack dupliquée hérite de :
- Le template Docker Compose complet
- Les variables et leurs valeurs
- La catégorie et la version
- Un tag `"duplicate"` est ajouté automatiquement
- La visibilité est toujours `is_public: false`

Appel API : `POST /stacks/{stack_id}/duplicate` avec le body [`StackDuplicateRequest`](../../backend/app/schemas/stack.py).

### Archiver une stack (Archive)

Marque la stack comme archivée (**soft delete**, réversible). La stack disparaît de la liste principale mais reste accessible via le filtre **Show Archived**.

- **Comportement** : positionne `is_archived=True` et `archived_at=now`
- **Idempotent** : archiver une stack déjà archivée est sans effet
- **Prérequis** : la stack doit appartenir à votre organisation

Appel API : `POST /stacks/{stack_id}/archive`. Réponse : [`StackActionResponse`](../../backend/app/schemas/stack.py).

### Désarchiver une stack (Unarchive)

Restaure une stack archivée dans la liste principale.

- **Comportement** : positionne `is_archived=False` et `archived_at=None`
- **Idempotent** : désarchiver une stack non archivée est sans effet

Appel API : `POST /stacks/{stack_id}/unarchive`. Réponse : [`StackActionResponse`](../../backend/app/schemas/stack.py).

### Table récapitulative des actions

| Action | Endpoint | Description |
|--------|----------|-------------|
| **Start** | `POST /stacks/{stack_id}/start` | Démarre tous les services |
| **Stop** | `POST /stacks/{stack_id}/stop` | Arrête tous les services |
| **Redeploy** | `POST /stacks/{stack_id}/redeploy` | Redéploie avec stratégie `stop_start` ou `rolling` |
| **Duplicate** | `POST /stacks/{stack_id}/duplicate` | Crée une copie avec un nouveau nom |
| **Archive** | `POST /stacks/{stack_id}/archive` | Archive la stack (soft delete) |
| **Unarchive** | `POST /stacks/{stack_id}/unarchive` | Restaure une stack archivée |

---

## Cycle de vie d'une stack

Le cycle de vie complet d'une stack WindFlow suit les étapes suivantes :

```
Création → Déploiement → Actions (Start/Stop/Redeploy) → Export (sauvegarde) → Duplication → Archivage → Suppression
```

### Étapes détaillées

| Étape | Action | Prérequis | Impact |
|-------|--------|-----------|--------|
| **Création** | Définition du template et des variables | Template Docker Compose valide | Stack en mode brouillon |
| **Déploiement** | Déploiement sur une target | Stack existante, target connectée | Containers créés sur la machine cible |
| **Start / Stop** | Gestion de l'état des services | Stack déployée | Containers démarrés ou arrêtés |
| **Redeploy** | Mise à jour des containers | Stack déployée | Containers recréés selon la stratégie choisie |
| **Export** | Sauvegarde JSON | Stack existante | Fichier téléchargé localement |
| **Import** | Restauration depuis JSON | Fichier v1.0 valide | Nouvelle stack créée en mode privé |
| **Duplication** | Copie de la stack | Stack existante | Nouvelle stack avec tag `duplicate` |
| **Archivage** | Retrait de la liste principale | Stack appartenant à l'utilisateur | Stack masquée, données préservées |
| **Désarchivage** | Restauration dans la liste | Stack archivée | Stack de nouveau visible |
| **Suppression** | Suppression définitive | Stack existante | **Irréversible** — toutes les données perdues |

### Bonnes pratiques

- **Exporter avant un redéploiement majeur** : en cas de problème, l'export permet de restaurer la configuration d'origine
- **Archiver plutôt que supprimer** : l'archivage est réversible et préserve les données ; la suppression est définitive
- **Utiliser la stratégie `rolling`** pour les stacks de production afin de maintenir la disponibilité pendant les mises à jour
- **Vérifier les variables importées** après un import, notamment les mots de passe et les domaines qui peuvent différer entre environnements

---

## Référence des endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/stacks/{stack_id}/export` | `GET` | Export d'une stack au format JSON v1.0 |
| `/stacks/import` | `POST` | Import d'une stack depuis un fichier JSON |
| `/stacks/{stack_id}/start` | `POST` | Démarrer tous les services d'une stack |
| `/stacks/{stack_id}/stop` | `POST` | Arrêter tous les services d'une stack |
| `/stacks/{stack_id}/redeploy` | `POST` | Redéployer une stack (stratégie `stop_start` ou `rolling`) |
| `/stacks/{stack_id}/duplicate` | `POST` | Dupliquer une stack avec un nouveau nom |
| `/stacks/{stack_id}/archive` | `POST` | Archiver une stack (soft delete) |
| `/stacks/{stack_id}/unarchive` | `POST` | Désarchiver une stack |

### Fichiers source

**Backend :**
- [`backend/app/api/v1/import_export.py`](../../backend/app/api/v1/import_export.py) — Endpoints import/export
- [`backend/app/api/v1/stacks.py`](../../backend/app/api/v1/stacks.py) — Endpoints actions de stack
- [`backend/app/schemas/stack.py`](../../backend/app/schemas/stack.py) — Schemas Pydantic (`StackActionResponse`, `StackRedeployRequest`, `StackRedeployResponse`, `StackDuplicateRequest`, `RedeployStrategy`)

**Frontend :**
- [`frontend/src/views/Stacks.vue`](../../frontend/src/views/Stacks.vue) — Vue principale des stacks
- [`frontend/src/components/compute/StackActionsBar.vue`](../../frontend/src/components/compute/StackActionsBar.vue) — Barre d'actions globales
- [`frontend/src/services/api.ts`](../../frontend/src/services/api.ts) — Service API stacks (`stacksApi.export`, `stacksApi.import`, etc.)
- [`frontend/src/types/api.ts`](../../frontend/src/types/api.ts) — Types TypeScript (`StackExportData`, `StackActionResponse`, etc.)
