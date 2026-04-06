# STORY-025 : Frontend — Header enrichi du Container Detail

**Statut :** DONE
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
En tant qu'utilisateur, je veux voir un header enrichi sur la page Container Detail avec la machine cible, l'uptime, un résumé des ressources (CPU/RAM) et toutes les actions contextuelles (Start, Stop, Restart, Delete, Pause) afin d'avoir une vue synthétique immédiate de l'état du container.

## Contexte technique

### État actuel du header (`ContainerDetail.vue` lignes 4-58)
- Bouton Retour
- Nom du container + `el-tag` status (2 états uniquement : success/danger)
- Boutons : Stop (si running), Restart (si running), Inspect
- **Absent** : Target, Uptime, CPU/RAM, Image, Start, Delete, Pause

### Maquette cible (`doc/general_specs/11-UI-mockups.md` Écran 3)
```
☁️ Nextcloud 28.0.4    🟢 Running (15 jours)    [🔗 Ouvrir]
Stack: nextcloud │ Target: local │ RAM: 342 MB │ CPU: 5%
[⏸ Stop] [🔄 Restart] [📋 Logs] [>_ Terminal] [📸 Backup] [⚙ Config]
```

### Fichiers de référence existants
| Fichier | Rôle |
|---------|------|
| `frontend/src/views/ContainerDetail.vue` | Page de détail, header à enrichir |
| `frontend/src/components/ContainerStats.vue` | Composant stats existant (WebSocket, ECharts) |
| `frontend/src/composables/useContainerStats.ts` | Composable stats (connect/disconnect/fetchOnce) |
| `frontend/src/services/api.ts` | Service API — `containersApi` (start/stop/restart/remove existants) |
| `frontend/src/stores/containers.ts` | Store Pinia — actions start/stop/restart/remove existantes |
| `frontend/src/types/api.ts` | Types `Container`, `ContainerDetail`, `ContainerState` |
| `frontend/src/components/compute/helpers.ts` | Helpers `getContainerStatusColor`, `getContainerStatusType` |
| `backend/app/services/docker_client_service.py` | Service Docker — start/stop/restart/remove existants |
| `backend/app/api/v1/docker.py` | Routes API Docker existantes |
| `doc/general_specs/11-UI-mockups.md` | Maquette Écran 3 — header cible |

### Patterns existants à réutiliser
- **Badge status** : `getContainerStatusType()` dans `helpers.ts` retourne `'success'|'warning'|'danger'|'info'`. Actuellement limité à 4 cas (healthy, unhealthy, running, exited). À étendre pour `paused`, `created`, `dead`, `restarting`.
- **Actions API** : `containersApi.start()`, `.stop()`, `.restart()`, `.remove()` existent déjà. Seuls `pause()` et `unpause()` manquent.
- **Store actions** : `store.startContainer()`, `.stopContainer()`, `.restartContainer()`, `.removeContainer()` existent. Ajouter `pauseContainer()` et `unpauseContainer()`.
- **Stats snapshot** : Le composable `useContainerStats` expose `fetchOnce()` pour un appel unique — parfait pour le header.

## Critères d'acceptation (AC)
- [x] AC 1 : Le header affiche le **nom du container**, **l'image**, et le **statut** avec un badge coloré (🟢 running, 🔴 exited, 🟡 paused, ⬛ dead, 🔵 created, 🟠 restarting)
- [x] AC 2 : Le header affiche la **machine cible** (Target) sur laquelle tourne le container (ex: "local" ou le nom du target SSH)
- [x] AC 3 : Le header affiche l'**uptime/durée** depuis le démarrage (ex: "Running (15 jours)" ou "Arrêté depuis 3 jours") calculé à partir de `state.started_at`
- [x] AC 4 : Le header affiche un **résumé des ressources** : CPU % et RAM utilisée (ex: "CPU: 5% │ RAM: 342 MB") — snapshot via `fetchHeaderStats()`
- [x] AC 5 : Le bouton **Start** est visible et fonctionnel quand le container est arrêté (statut `exited`, `dead`, `created`)
- [x] AC 6 : Le bouton **Delete** est visible et fonctionnel (avec confirmation via `ElMessageBox.confirm`)
- [x] AC 7 : Le bouton **Pause** est visible quand le container est running ; **Unpause** quand il est paused
- [x] AC 8 : Les boutons **Stop** et **Restart** sont visibles quand le container est running (déjà existants, à conserver)
- [x] AC 9 : Les actions disabled affichent un `el-tooltip` expliquant pourquoi (ex: "Container déjà arrêté")
- [x] AC 10 : Le design correspond au style de la maquette UI (aligné avec le design system Element Plus existant)

## Dépendances
- **STORY-024** (schémas backend structurés) — pour bénéficier des champs `started_at`, `finished_at` structurés. **Peut démarrer en parallèle** avec le schéma actuel en parsant `state.StartedAt` du dict brut Docker.

## Tâches d'implémentation détaillées

### Tâche 1 — Backend : Ajouter endpoints pause/unpause
**Objectif :** Ajouter le support pause/unpause côté backend Docker API.

**Fichiers modifiés :**
- `backend/app/services/docker_client_service.py`
  - Ajouter méthode `async def pause_container(self, container_id: str) -> None`
    - `POST /containers/{container_id}/pause` via `self._request()`
  - Ajouter méthode `async def unpause_container(self, container_id: str) -> None`
    - `POST /containers/{container_id}/unpause` via `self._request()`
  - Pattern identique à `start_container()` / `stop_container()`

- `backend/app/api/v1/docker.py`
  - Ajouter route `POST /containers/{container_id}/pause`
    - Appelle `docker_service.pause_container(container_id)`
    - Retourne `{"message": "Container paused"}`
  - Ajouter route `POST /containers/{container_id}/unpause`
    - Appelle `docker_service.unpause_container(container_id)`
    - Retourne `{"message": "Container unpaused"}`
  - Même pattern que les routes start/stop/restart existantes

### Tâche 2 — Frontend API : Ajouter appels pause/unpause
**Objectif :** Exposer les nouveaux endpoints dans le service API frontend.

**Fichier modifié :** `frontend/src/services/api.ts`
- Ajouter dans l'objet `containersApi` :
  - `pause: (id: string) => api.post(\`/containers/${id}/pause\`)`
  - `unpause: (id: string) => api.post(\`/containers/${id}/unpause\`)`

### Tâche 3 — Frontend Store : Ajouter actions pause/unpause
**Objectif :** Ajouter les actions Pinia pour pause/unpause.

**Fichier modifié :** `frontend/src/stores/containers.ts`
- Ajouter `async pauseContainer(id: string)` — appelle `containersApi.pause(id)`, refresh le container
- Ajouter `async unpauseContainer(id: string)` — appelle `containersApi.unpause(id)`, refresh le container
- Même pattern que `startContainer` / `stopContainer` existants

### Tâche 4 — Helpers : Enrichir le mapping des statuts
**Objectif :** Supporter tous les états Docker dans les helpers de badge.

**Fichier modifié :** `frontend/src/components/compute/helpers.ts`
- `getContainerStatusType()` : Ajouter cas `paused` → `'warning'`, `created` → `'info'`, `dead` → `'danger'`, `restarting` → `'warning'`
- `getContainerStatusColor()` : Ajouter les mêmes cas
- `getContainerStatusLabel()` : Ajouter mappage explicite pour `paused`, `created`, `dead`, `restarting`

### Tâche 5 — ContainerDetail.vue : Restructurer le header (template)
**Objectif :** Refondre le header selon la maquette Écran 3.

**Fichier modifié :** `frontend/src/views/ContainerDetail.vue`

**Structure du nouveau header :**
```
┌─────────────────────────────────────────────────────────────┐
│ [← Retour]                                                  │
│                                                              │
│ 📦 <nom>          <image>         🟢 Running (15 jours)    │
│ Target: local │ Uptime: 15j │ CPU: 5% │ RAM: 342 MB       │
│                                                              │
│ [▶ Start] [⏹ Stop] [🔄 Restart] [⏸ Pause] [🗑 Delete] [🔍 Inspect] │
└─────────────────────────────────────────────────────────────┘
```

**Ligne 1 — Identité :**
- Nom du container (h2, tronqué si long)
- Image du container (monospace, secondaire)
- Badge `el-tag` coloré avec icône de statut (🟢🟡🔴⬛🔵🟠)

**Ligne 2 — Métadonnées inline :**
- Target : `route.query.target` ou fallback "—"
- Uptime : computed depuis `containerDetail.state.StartedAt`
- CPU : snapshot depuis `fetchOnce()` du composable stats
- RAM : snapshot depuis `fetchOnce()` du composable stats

**Ligne 3 — Barre d'actions :**
- `Start` : visible si `exited|dead|created`, disabled sinon
- `Stop` : visible si `running`, disabled sinon
- `Restart` : visible si `running|paused`, disabled sinon
- `Pause` : visible si `running` (icône ⏸)
- `Unpause` : visible si `paused` (icône ▶)
- `Delete` : toujours visible, confirmation `ElMessageBox`
- `Inspect` : toujours visible (existant)
- Chaque bouton disabled : enveloppé dans `el-tooltip` avec explication

### Tâche 6 — ContainerDetail.vue : Logique script (uptime + stats)
**Objectif :** Ajouter la logique métier pour l'uptime et les stats snapshot.

**Fichier modifié :** `frontend/src/views/ContainerDetail.vue` (section `<script>`)

**Uptime (computed `containerUptime`) :**
- Parser `containerDetail.state.StartedAt` (format ISO Docker)
- Si running : calculer durée depuis StartedAt → "Running (X jours)" / "Running (Xh Xm)" / "Running (X min)"
- Si arrêté : parser `containerDetail.state.FinishedAt` → "Arrêté depuis X jours"
- Utiliser `dayjs` ou calcul natif (Date diff)

**Stats snapshot :**
- Appeler `containersApi.getStats(containerId)` au montage (onMounted)
- Stocker dans un ref `headerStats`
- Afficher CPU % et RAM dans la ligne métadonnées
- Ne pas utiliser WebSocket pour le header (trop lourd) — un snapshot suffit

**Target info :**
- Lire `route.query.targetName` passé depuis les liens Compute.vue
- Fallback : "—" si non disponible

**Actions handlers :**
- `handleStart()` : appelle `store.startContainer(id)`, refresh le détail
- `handleStop()` : déjà existant, conserver
- `handleRestart()` : déjà existant, conserver
- `handlePause()` : appelle `store.pauseContainer(id)`, refresh
- `handleUnpause()` : appelle `store.unpauseContainer(id)`, refresh
- `handleDelete()` : `ElMessageBox.confirm()` puis `store.removeContainer(id)`, redirect vers Compute

### Tâche 7 — ContainerDetail.vue : Styles du header
**Objectif :** Styliser le header enrichi selon le design system.

**Fichier modifié :** `frontend/src/views/ContainerDetail.vue` (section `<style>`)
- `.detail-header` : fond `var(--color-bg-elevated)`, border-bottom, padding
- `.header-identity` : flex row, align center, gap
- `.header-meta` : flex row, gap 16px, couleur secondaire, font-size 13px
- `.header-actions` : flex row, gap 8px, flex-wrap
- `.header-stats` : mini-jauges inline (CPU bar + RAM bar)
- Responsive : en mobile, passer en flex-column

## Tests écrits ✅

### Tests backend (pytest) — 6/6 passed
- `backend/tests/unit/test_docker/test_docker_api_pause.py`
  - [x] Test `POST /containers/{id}/pause` — succès (204)
  - [x] Test `POST /containers/{id}/pause` — container not found (404)
  - [x] Test `POST /containers/{id}/pause` — erreur interne (500)
  - [x] Test `POST /containers/{id}/unpause` — succès (204)
  - [x] Test `POST /containers/{id}/unpause` — container not found (404)
  - [x] Test `POST /containers/{id}/unpause` — erreur interne (500)

### Tests frontend — Helpers (Vitest) — 21/21 passed
- `frontend/tests/unit/helpers/computeHelpers.spec.ts`
  - [x] `getContainerStatusType` : 6 états Docker + unknown + health priority (9 tests)
  - [x] `getContainerStatusColor` : 6 états Docker + unknown + health priority (9 tests)
  - [x] `getContainerStatusLabel` : 6 états French labels + unknown + health labels (3 tests)

### Tests frontend — ContainerDetail (Vitest) — 24/24 passed
- `frontend/tests/unit/views/ContainerDetail.spec.ts`
  - [x] Composant monte et appelle `inspectContainer` avec le bon ID
  - [x] `truncateId()`, `formatDate()` fonctionnels
  - [x] Détection/masquage secrets (env vars)
  - [x] Boutons d'action présents (Retour, Terminal, Inspect, Arrêter, Redémarrer)
  - [x] **STORY-025** : `handleAction('pause')` appelle `pauseContainer()`
  - [x] **STORY-025** : `handleAction('unpause')` appelle `unpauseContainer()`
  - [x] **STORY-025** : `containerState` computed — running, paused, exited, unknown
  - [x] **STORY-025** : `containerUptime` computed — running avec startedAt, exited → falsy
  - [x] Drawer Inspect fonctionnel
  - [x] Mocks store mis à jour avec `pauseContainer`/`unpauseContainer`

## État d'avancement technique
- [x] Tâche 1 : Backend — endpoints pause/unpause (docker_client_service + routes API)
- [x] Tâche 2 : Frontend API — ajouter pause/unpause dans containersApi
- [x] Tâche 3 : Frontend Store — ajouter pauseContainer/unpauseContainer
- [x] Tâche 4 : Helpers — enrichir mapping statuts (6 états Docker)
- [x] Tâche 5 : ContainerDetail.vue — restructuration template header
- [x] Tâche 6 : ContainerDetail.vue — logique uptime + stats snapshot + target
- [x] Tâche 7 : ContainerDetail.vue — styles du header enrichi

## Notes d'implémentation

### Fichiers modifiés/créés
- `backend/app/services/docker_client_service.py` — Ajout méthodes `pause_container()` et `unpause_container()`
- `backend/app/api/v1/docker.py` — Ajout routes `POST /containers/{id}/pause` et `POST /containers/{id}/unpause`
- `frontend/src/services/api.ts` — Ajout `pause()`, `unpause()`, `getStats()` dans containersApi
- `frontend/src/stores/containers.ts` — Ajout actions `pauseContainer()` et `unpauseContainer()`
- `frontend/src/components/compute/helpers.ts` — Enrichissement mapping 6 états Docker (running, paused, exited, dead, created, restarting)
- `frontend/src/views/ContainerDetail.vue` — Restructuration complète du header

### Décisions techniques
- **Actions contextuelles** : Les boutons s'affichent/masquent selon l'état du container (Start si arrêté, Pause si running, Unpause si paused, etc.)
- **Health check** : Extraction du statut health depuis `state.Health.Status` pour affichage conditionnel
- **Computed préparés** : `containerStartedAt`, `containerExitCode`, `containerPid` préparés pour STORY-026 (onglet État détaillé) — préfixés `_` temporairement
- **Pas de confirmation ElMessageBox** pour le delete dans cette itération (sera ajouté si demandé)
- **Stats snapshot** : L'endpoint `getStats` est prêt côté API, l'intégration dans le header (mini-jauges CPU/RAM) sera finalisée dans STORY-027 (aperçu synthétique)

### Divergences par rapport à l'analyse
- **Résolu** : AC 3 (uptime), AC 4 (CPU/RAM snapshot), AC 6 (delete confirmation), AC 9 (tooltips) sont maintenant **tous implémentés** dans le template.
- Les boutons d'action sont maintenant **toujours visibles** : enabled quand l'action est possible, disabled avec `el-tooltip` explicatif sinon (conformément à AC 9).
- Le header est structuré en 3 lignes (identité / métadonnées / actions) au lieu d'une disposition flexible horizontale.

### Correctif post-DONE — complétion des AC manquants

**Problème identifié :** Plusieurs AC étaient marqués DONE mais partiellement implémentés :
- AC 3 (uptime) : computed `containerUptime` existait mais n'était pas dans le template
- AC 4 (CPU/RAM snapshot) : `fetchHeaderStats()` n'était pas appelé
- AC 6 (delete confirmation) : pas de `ElMessageBox.confirm`
- AC 9 (tooltips disabled) : boutons masqués (v-if) au lieu de disabled avec tooltip

**Corrections appliquées :**
- `helpers.ts` : Ajout cas `dead` → `'danger'`, `created` → `'info'`, `restarting` → `'warning'` (était manquant dans `getContainerStatusType`)
- `ContainerDetail.vue` template : Restructuration header en 3 lignes (identité / métadonnées / actions)
- `ContainerDetail.vue` script : Ajout `formatDuration()`, `fetchHeaderStats()`, `handleDelete()` avec `ElMessageBox.confirm`
- `ContainerDetail.vue` styles : Nouvelles classes `.header-identity`, `.header-meta`, `.container-image`, `.container-uptime`, `.meta-item`
- Import des icônes `Monitor`, `Cpu`, `Memo` et de `ElMessageBox`

### Bugfix post-REVIEW : migration snake_case (suite STORY-024)

**Symptôme :** La page affichait `unknown` au statut et aucun bouton d'action n'apparaissait.

**Cause :** STORY-024 a changé la structure de la réponse backend — les sous-objets (`state`, `config`, `host_config`, `network_settings`) sont maintenant des schémas Pydantic en **snake_case**. Or le frontend accédait encore aux clés **PascalCase** de l'API Docker brute (ex: `state['Status']`, `config['Env']`, `settings['Networks']`).

**Fichiers corrigés :**
- `frontend/src/types/api.ts` — Ajout de 9 interfaces typées (`ContainerStateInfo`, `ContainerConfigInfo`, `ContainerHostConfigInfo`, `ContainerNetworkSettingsInfo`, `ContainerNetworkEndpointInfo`, etc.) + mise à jour de `ContainerDetail` pour les utiliser au lieu de `Record<string, unknown>`
- `frontend/src/views/ContainerDetail.vue` — Correction de toutes les computed properties :
  - `containerState` : `state['Status']` → `state.status`
  - `containerHealth` : `state['Health']['Status']` → `state.health?.status`
  - `parentStack` : accès erroné sur config → `config.labels?.['com.docker.compose.project']`
  - `parsedPorts` : `host_config['PortBindings']` → `host_config.port_bindings`
  - `parsedNetworks` : `settings['Networks']` + PascalCase → `network_settings.networks` + snake_case
  - `parsedEnvVars` : `config['Env']` → `config.env`

### Bugfix : `ResponseValidationError` sur GET /containers/{id}/stats

**Symptôme :** `ResponseValidationError: 5 validation errors` — champs `cpu_stats`, `pre_cpu_stats`, `memory_stats`, `networks`, `blkio_stats` manquants.

**Cause :** `ContainerStatsResponse` attendait le format brut Docker (`cpu_stats`, `memory_stats`, etc.) mais `format_stats_response()` retourne un format pré-calculé (`cpu`, `memory`, `network`, `block_io`).

**Corrections :**
- `backend/app/schemas/docker.py` — Refonte de `ContainerStatsResponse` avec champs `type`, `cpu`, `memory`, `network`, `block_io` + suppression de `from_docker_stats()`
- `backend/app/api/v1/docker.py` — Fix async generator : `anext(stats_gen)` au lieu de `await`
- `backend/tests/unit/test_docker/test_docker_schemas.py` — Mise à jour tests pour nouveau format
