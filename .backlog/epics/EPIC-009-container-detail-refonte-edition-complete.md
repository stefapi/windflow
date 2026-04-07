# EPIC-009 : Refonte de la page ContainerDetail — Homogénéisation et édition complète

**Statut :** IN_PROGRESS
**Priorité :** Haute

## Vision

La page de détail d'un container (`/containers/:id`) est le point central de gestion des containers standalone dans WindFlow. Elle souffre actuellement de **trois déficiences majeures** :

1. **Incohérence visuelle** : l'onglet *Infos* utilise un design plat (simples `div` sur fond secondaire) alors que l'onglet *Aperçu* utilise un système de cards colorées avec bordures thématiques — deux langages visuels contradictoires dans la même page.

2. **Duplication des données** : les sections Volumes et Réseau sont affichées à la fois dans *Aperçu* (vue synthétique) et dans *Infos* (vue détaillée), sans séparation claire des responsabilités.

3. **Édition incomplète** : l'onglet *Config* permet d'éditer les variables d'environnement (stub non-fonctionnel), les labels (stub non-fonctionnel), la restart policy et les limites de ressources. Il **ne permet pas** d'éditer les ports, les réseaux, les volumes, le mode privilégié, les capabilities, ni de mettre à jour l'image du container.

Cette epic vise à résoudre ces trois problèmes en une refonte complète, axée sur l'expérience opérateur : **voir clairement, agir directement**.

---

## Description

### 1. Homogénéisation visuelle des onglets

#### État actuel

| Onglet | Composant | Design |
|--------|-----------|--------|
| Aperçu | `ContainerOverviewTab.vue` | `el-card` avec `#header` coloré (border-bottom 3px thématique) |
| Infos | `ContainerInfoTab.vue` | `div.bg-[var(--color-bg-secondary)]` + `el-descriptions` — design plat |
| Config | `ContainerConfigTab.vue` | `div.config-section` — design plat |

#### Cible

Tous les onglets adoptent le **pattern visuel de l'Aperçu** :
- `el-card` avec slot `#header` coloré
- Iconographie cohérente (icône + titre en couleur thématique)
- Bordure colorée en bas du header (`border-bottom: 3px solid <couleur>`)
- Shadow `hover` au survol

**Palette de couleurs thématiques** (à respecter) :
- 🔵 Bleu (`--el-color-primary`) : Identité, Services
- 🟢 Vert (`--el-color-success`) : Volumes, Réseau
- 🟣 Violet (`#9b59b6`) : Configuration, Ports
- 🟠 Orange (`--el-color-warning`) : Santé, Sécurité
- 🔴 Rouge (`--el-color-danger`) : Ressources, Mode privilégié
- ⚫ Gris (`--el-color-info`) : Labels, Infos générales

### 2. Clarification de la séparation Aperçu / Infos

#### Responsabilités cibles

| Onglet | Responsabilité | Données affichées |
|--------|---------------|-------------------|
| **Aperçu** | Vue synthétique **live** | Services du projet Compose, Volumes résumés, Réseau résumé, Santé, Métriques temps réel |
| **Infos** | Vue exhaustive **read-only** | Toutes les propriétés du container (sans doublons avec Aperçu), labels, host config, disk, env vars masquées |

**Suppressions de doublons** :
- La section **Volumes** de l'onglet Infos reste (liste complète avec tous les champs), mais l'Aperçu garde uniquement sa vue synthétique (3 colonnes max) — pas de suppression mais de différenciation.
- La section **Réseau** de l'onglet Infos reste (détails IP/MAC/Passerelle/ID endpoint), l'Aperçu garde sa vue synthétique.
- **Différenciateur clé** : l'Aperçu a le live streaming (métriques WebSocket), Infos est statique.

### 3. Extension de l'onglet Config — Édition complète

L'onglet Config est étendu avec **6 nouvelles sections** (ou améliorées) :

#### 3.1 Variables d'environnement (amélioration)
- **Actuel** : UI fonctionnelle, bouton "Appliquer" → message "Fonctionnalité à venir"
- **Cible** : Appel réel à `POST /docker/containers/{id}/recreate` avec les nouvelles env vars
- Avertissement explicite : arrêt + recréation + redémarrage du container
- Confirmation requise avant action

#### 3.2 Labels (amélioration)
- **Actuel** : UI fonctionnelle, bouton "Appliquer" → message "Fonctionnalité à venir"
- **Cible** : Appel réel à `POST /docker/containers/{id}/recreate` avec les nouveaux labels
- Avertissement identique à env vars

#### 3.3 Image (nouvelle section)
- **Actuel** : Affichée dans le header, non modifiable
- **Cible** : Champ d'édition de l'image Docker dans l'onglet Config
  - Input text pour saisir la nouvelle image (ex: `nginx:1.26`, `ghcr.io/org/app:latest`)
  - Bouton "Mettre à jour l'image" → appel à `POST /docker/containers/{id}/recreate` avec nouvelle image
  - Affichage de l'image actuelle en hint
  - Avertissement : recréation du container avec la nouvelle image
  - Option optionnelle : pull de la nouvelle image avant recréation

#### 3.4 Ports (nouvelle section)
- **Actuel** : Ports affichés dans Infos en lecture seule
- **Cible** : Section éditables dans Config

Interface :
```
┌─────────────────────────────────────────────────────────┐
│ 🟣 Ports                                                │
├─────────────────────────────────────────────────────────┤
│ ⚠️ Modifier les ports nécessite de recréer le container │
├──────────┬──────────┬──────────────┬──────────┬────────┤
│ Host IP  │ Host Port│ Container Port│ Protocole│ Action│
├──────────┼──────────┼──────────────┼──────────┼────────┤
│ 0.0.0.0  │ 8080     │ 80           │ TCP      │ [🗑️]  │
│ [input]  │ [input]  │ [input]      │ [select] │ [🗑️]  │
└──────────┴──────────┴──────────────┴──────────┴────────┘
[+ Ajouter un port]                          [Appliquer]
```

Validation :
- Port host : entier 1-65535
- Port container : entier 1-65535
- Pas de doublon sur le port host
- Protocole : tcp / udp

#### 3.5 Réseaux (nouvelle section)
- **Actuel** : Réseaux affichés dans Infos en lecture seule
- **Cible** : Section éditables dans Config — **opérations à chaud** (sans recréation)

Interface :
```
┌─────────────────────────────────────────────────────────┐
│ 🟢 Réseaux                                              │
├─────────────────────────────────────────────────────────┤
│ ℹ️ Connexion/déconnexion possible sans redémarrage      │
├────────────────────────────────────────┬────────────────┤
│ Réseau                                 │ Actions        │
├────────────────────────────────────────┼────────────────┤
│ bridge (172.17.0.0/16)                 │ [Déconnecter]  │
│ my-network                             │ [Déconnecter]  │
└────────────────────────────────────────┴────────────────┘
[Sélectionner un réseau... ▼]           [Connecter]
```

Comportement :
- Liste des réseaux disponibles sur le daemon Docker (via `GET /docker/networks`)
- Connexion à chaud → `POST /docker/containers/{id}/networks/connect`
- Déconnexion à chaud → `POST /docker/containers/{id}/networks/disconnect`
- Feedback immédiat (pas de recréation)

#### 3.6 Volumes (nouvelle section)
- **Actuel** : Volumes affichés dans Infos en lecture seule
- **Cible** : Section éditables dans Config (recréation requise)

Interface :
```
┌─────────────────────────────────────────────────────────┐
│ 🟢 Volumes & Montages                                   │
├─────────────────────────────────────────────────────────┤
│ ⚠️ Modifier les volumes nécessite de recréer le container│
├──────────┬──────────────────────┬──────────────┬───────┤
│ Type     │ Source / Nom de volume│ Destination  │ Action│
├──────────┼──────────────────────┼──────────────┼───────┤
│ volume   │ open-webui           │ /app/backend │ [🗑️]  │
│ bind     │ /host/path           │ /container   │ [🗑️]  │
└──────────┴──────────────────────┴──────────────┴───────┘
[+ Ajouter un volume]                          [Appliquer]
```

Types supportés : `volume`, `bind`, `tmpfs`

#### 3.7 Sécurité & Capabilities (nouvelle section)
- **Actuel** : Affiché dans Infos en lecture seule (section "Sécurité & Capabilities")
- **Cible** : Section éditables dans Config (recréation requise)

Interface :
```
┌─────────────────────────────────────────────────────────┐
│ 🔴 Sécurité                                             │
├─────────────────────────────────────────────────────────┤
│ ⚠️ Ces modifications nécessitent de recréer le container│
├─────────────────────────────────────────────────────────┤
│ Mode privilégié       [  Désactivé ●○ ]  ← toggle      │
│ Read-only rootfs      [  Désactivé ●○ ]                 │
├─────────────────────────────────────────────────────────┤
│ Capabilities ajoutées (cap_add):                        │
│ [NET_ADMIN ×] [SYS_PTRACE ×]  [+ Ajouter]              │
│                                                         │
│ Capabilities retirées (cap_drop):                       │
│ [SETUID ×] [SETGID ×]         [+ Ajouter]              │
└─────────────────────────────────────────────────────────┘
[Appliquer]
```

### 4. Endpoint Backend : `POST /docker/containers/{id}/recreate`

#### Description
Permet de recréer un container existant avec une nouvelle configuration. L'opération :
1. Inspecte le container source (pour récupérer sa config complète)
2. Arrête le container (si en cours d'exécution) avec timeout configurable
3. Supprime le container (`force=True`)
4. Récrée un nouveau container avec la config fusionnée (config existante + overrides)
5. Redémarre le nouveau container
6. Retourne le détail du nouveau container

#### Schéma de requête (`ContainerRecreateRequest`)
```python
class ContainerRecreateRequest(BaseModel):
    # Image (optionnel — si absent, utilise l'image actuelle)
    image: Optional[str] = None          # ex: "nginx:1.26", "postgres:16"
    pull_image: bool = False             # pull la nouvelle image avant recréation

    # Config container (optionnel — si absent, conserve la valeur actuelle)
    env: Optional[list[str]] = None      # format ["KEY=VALUE", ...]
    labels: Optional[dict[str, str]] = None

    # Host config (optionnel — si absent, conserve la valeur actuelle)
    port_bindings: Optional[dict[str, Any]] = None
    # Ex: {"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]}

    mounts: Optional[list[dict[str, Any]]] = None
    # Ex: [{"Type": "volume", "Source": "my-vol", "Target": "/app/data"}]

    privileged: Optional[bool] = None
    readonly_rootfs: Optional[bool] = None
    cap_add: Optional[list[str]] = None
    cap_drop: Optional[list[str]] = None

    # Timeout d'arrêt avant suppression (secondes)
    stop_timeout: int = 10
```

#### Schéma de réponse (`ContainerRecreateResponse`)
```python
class ContainerRecreateResponse(BaseModel):
    success: bool
    message: str
    old_container_id: str          # ID original (maintenant supprimé)
    new_container_id: str          # ID du nouveau container
    container: ContainerDetailResponse  # Détails du nouveau container
    warnings: list[str] = []
```

#### Route API
```
POST /api/v1/docker/containers/{container_id}/recreate
```
- **Rate limit** : 10/min
- **Auth** : Requise
- **Idempotence** : Non (crée toujours un nouveau container)

### 5. Endpoint Backend : `POST /docker/containers/{id}/networks/connect`

#### Description
Connecte un container à un réseau Docker existant **à chaud** (sans recréation).

#### Schéma de requête (`ContainerNetworkConnectRequest`)
```python
class ContainerNetworkConnectRequest(BaseModel):
    network_id: str  # ID ou nom du réseau
    aliases: Optional[list[str]] = None  # Alias réseau optionnels
    ipv4_address: Optional[str] = None  # IP fixe optionnelle
```

#### Route API
```
POST /api/v1/docker/containers/{container_id}/networks/connect
```

### 6. Endpoint Backend : `POST /docker/containers/{id}/networks/disconnect`

#### Description
Déconnecte un container d'un réseau Docker **à chaud**.

#### Schéma de requête (`ContainerNetworkDisconnectRequest`)
```python
class ContainerNetworkDisconnectRequest(BaseModel):
    network_id: str  # ID ou nom du réseau
    force: bool = False
```

#### Route API
```
POST /api/v1/docker/containers/{container_id}/networks/disconnect
```

---

## Analyse de l'état actuel du code

### Backend

| Endpoint existant | Statut | Lien avec cette epic |
|---|---|---|
| `PATCH /containers/{id}/restart-policy` | ✅ Fonctionnel | Déjà dans Config |
| `PATCH /containers/{id}/resources` | ✅ Fonctionnel | Déjà dans Config |
| `POST /containers/{id}/rename` | ✅ Fonctionnel | Header page |
| `POST /containers` | ✅ Fonctionnel | Base pour `recreate` |
| `POST /containers/{id}/networks/connect` | ❌ Absent | À créer |
| `POST /containers/{id}/networks/disconnect` | ❌ Absent | À créer |
| `POST /containers/{id}/recreate` | ❌ Absent | À créer |

### Frontend

| Composant | Statut | Problème |
|---|---|---|
| `ContainerOverviewTab.vue` | ✅ Design référence | Cards colorées OK |
| `ContainerInfoTab.vue` | ⚠️ Design incohérent | Design plat, pas de cards |
| `ContainerConfigTab.vue` | ⚠️ Fonctions stub | Env vars / Labels non implémentés, sections manquantes |
| `ContainerDetail.vue` | ✅ Fonctionnel | Orchestre les onglets |

### Client Docker (`docker_client_service.py`)

Méthodes existantes à vérifier :
- `create_container()` — base pour recreate
- `stop_container()` — utilisé dans recreate
- `remove_container()` — utilisé dans recreate
- `list_processes()`, `container_stats()` — non impactés

Méthodes à ajouter :
- `connect_container_to_network()` — appel Docker API `POST /networks/{id}/connect`
- `disconnect_container_from_network()` — appel Docker API `POST /networks/{id}/disconnect`
- `pull_image()` — si pas déjà présent (pour l'option pull avant recreate)

---

## Stories liées

- [x] STORY-024 : Homogénéisation visuelle — onglet Infos au design d'Aperçu
- [ ] STORY-025 : Backend — Endpoint de recréation de container (`/recreate`)
- [ ] STORY-026 : Backend — Endpoints connect/disconnect réseau
- [ ] STORY-027 : Frontend Config — Édition des ports et image (recréation)
- [ ] STORY-028 : Frontend Config — Gestion des réseaux à chaud
- [ ] STORY-029 : Frontend Config — Édition volumes et sécurité (recréation)
- [ ] STORY-030 : Frontend Config — Implémentation réelle env vars et labels (recréation)

---

## Critères de succès (Definition of Done)

- [ ] L'onglet Infos utilise le même système de cards colorées que l'Aperçu
- [ ] Aucune duplication fonctionnelle entre Aperçu et Infos
- [ ] L'opérateur peut modifier l'image du container (avec recréation)
- [ ] L'opérateur peut modifier les ports exposés (avec recréation)
- [ ] L'opérateur peut connecter/déconnecter des réseaux **sans redémarrage**
- [ ] L'opérateur peut modifier les montages de volumes (avec recréation)
- [ ] L'opérateur peut basculer le mode privilégié et les capabilities (avec recréation)
- [ ] L'action "Appliquer" sur env vars et labels déclenche réellement la recréation
- [ ] Toutes les opérations de recréation affichent un avertissement clair avec confirmation
- [ ] La recréation préserve la config non-modifiée du container original
- [ ] L'endpoint `POST /recreate` est couvert par des tests unitaires (≥ 80%)
- [ ] Les endpoints connect/disconnect réseau sont couverts par des tests unitaires (≥ 80%)
- [ ] Les nouveaux composants frontend ont une couverture de tests ≥ 80%
- [ ] Pas de régression sur les fonctionnalités existantes (restart policy, resources, rename)
- [ ] OpenAPI/Swagger à jour avec documentation complète des nouveaux endpoints

---

## Notes de conception

### Stratégie de recréation

La recréation d'un container est une opération **destructive avec perte de données** dans le layer writable. L'implémentation doit :

1. **Inspecter d'abord** : appel `GET /containers/{id}` pour récupérer la config complète
2. **Merger la config** : config existante + overrides de la requête (les champs `None` conservent la valeur existante)
3. **Avertir l'utilisateur** : l'UI affiche un dialog de confirmation avec la liste des changements
4. **Arrêter proprement** : `stop_container(timeout=stop_timeout)` avant suppression
5. **Supprimer** : `remove_container(force=True)` pour forcer si stop a échoué
6. **Pull optionnel** : si `pull_image=True` et nouvelle image demandée, pull avant création
7. **Recréer** : `create_container()` avec la config mergée
8. **Redémarrer** : `start_container()` sur le nouveau container
9. **Retourner le détail complet** du nouveau container

**Gestion d'erreurs** : si la suppression réussit mais la création échoue, logguer l'incident et retourner une erreur 500 avec le détail (le container original est perdu).

### Gestion des volumes lors de la recréation

- Les **named volumes** (`type: volume`) sont préservés automatiquement (le volume Docker existe indépendamment du container)
- Les **bind mounts** (`type: bind`) sont préservés (le répertoire hôte persiste)
- Les **tmpfs** sont perdus (temporaires par nature)
- L'UI doit l'indiquer clairement dans le dialog de confirmation

### Connexion réseau à chaud

Docker supporte nativement `POST /v1.xx/networks/{id}/connect` sur un container en cours d'exécution. Cette opération :
- N'arrête pas le container
- Ajoute une interface réseau virtuelle
- Permet de spécifier une IP fixe optionnelle
- Peut échouer si le réseau est en mode `host` ou `none`

### Permissions Docker

Le daemon Docker doit être accessible depuis le backend WindFlow. Si le daemon est distant (via TCP), les opérations réseau peuvent nécessiter des capabilities supplémentaires côté daemon.

### Contraintes connues de Docker API

| Opération | Faisable à chaud | Méthode |
|---|---|---|
| Modifier env vars | ❌ Non | Recréation |
| Modifier labels | ❌ Non | Recréation |
| Modifier ports | ❌ Non | Recréation |
| Modifier volumes | ❌ Non | Recréation |
| Modifier mode privilégié | ❌ Non | Recréation |
| Modifier capabilities | ❌ Non | Recréation |
| Modifier image | ❌ Non | Recréation |
| Connecter/déconnecter réseau | ✅ Oui | `network connect/disconnect` |
| Modifier restart policy | ✅ Oui | `PATCH /containers/{id}/update` |
| Modifier limites resources | ✅ Oui | `PATCH /containers/{id}/update` |
| Renommer | ✅ Oui | `POST /containers/{id}/rename` |

### Patterns UI à respecter

- Boutons d'"Appliquer" : toujours `type="primary"` avec `loading` pendant l'opération
- Avertissements : `el-alert type="warning"` avant les sections nécessitant une recréation
- Confirmations : `ElMessageBox.confirm()` avec description des impacts
- Feedback : `ElMessage.success()` / `ElMessage.error()` en fin d'opération
- Reload : après une recréation, appeler `loadContainerDetail()` pour rafraîchir

### Références de code existant

- **Pattern cards colorées** : `ContainerOverviewTab.vue` lignes 4-81 (card-services)
- **Pattern recréation (conf)** : `ContainerConfigTab.vue` lignes 407-422 (`applyEnvVars`)
- **Pattern update API** : `ContainerConfigTab.vue` lignes 451-471 (`applyRestartPolicy`)
- **Schema HostConfig** : `backend/app/schemas/docker.py` lignes 277-366
- **Schema CreateRequest** : `backend/app/schemas/docker.py` lignes 448-465
- **Client Docker create** : `backend/app/api/v1/docker.py` lignes 178-239

---

## Risques et dépendances

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| Perte de données lors de la recréation (layer writable) | Haut | Inévitable | Avertissement clair + confirmation + documentation |
| Échec de recréation après suppression | Haut | Faible | Logging détaillé, retour d'erreur explicite avec OldContainerId |
| Container avec dépendances réseau inter-containers pendant recréation | Moyen | Moyen | Avertissement sur les liens détectés |
| Pull d'image lent (timeout frontend) | Moyen | Moyen | Opération async, progress feedback via polling ou WebSocket |
| Désynchronisation entre ID ancien et nouveau container dans l'URL | Moyen | Inévitable | Redirect vers nouvelle URL après recréation |

### Dépendances inter-stories

```
STORY-025 (Backend recreate)
    └── STORY-027 (Frontend ports + image)
    └── STORY-029 (Frontend volumes + sécurité)
    └── STORY-030 (Frontend env vars + labels)

STORY-026 (Backend networks)
    └── STORY-028 (Frontend réseaux)

STORY-024 (Frontend Infos design) — indépendante
```

---

## Historique

| Date | Modification | Auteur |
|------|--------------|--------|
| 2026-04-07 | Création de l'epic | Claude |
