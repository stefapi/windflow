# Active Context — WindFlow

## Travail actuel

### Type de target déprécié au profit de `target_capabilities` ✅ COMPLÉTÉ (2026-03-05)

**Décision clé (2026-03-05) :** le champ `targets.type` ne doit plus être utilisé comme source de vérité fonctionnelle pour décrire les capacités d’une machine découverte. Le typage fonctionnel doit désormais être déduit exclusivement des entrées persistées dans `target_capabilities`.

**Contexte du bug :**
- La target `localhost` créée au bootstrap apparaissait avec `type=DOCKER`.
- Pourtant le scan persistait bien plusieurs capacités (`docker`, `docker_compose`, `libvirt`, `virtualbox`, `vagrant`, etc.) dans `target_capabilities`.
- La logique de déduction exclusive du type (`docker` prioritaire sur `vm`) masquait donc les capacités VM visibles via l’API/UI quand certaines vues ou raisonnements s’appuyaient sur `targets.type`.

**Changements réalisés :**
1. **Seed DB** (`backend/app/database_seed.py`)
   - Suppression de la déduction exclusive `_infer_target_type_from_scan()`
   - Remplacement par `_default_seed_target_type()` qui force un type technique neutre (`physical`)
   - Les capacités réelles restent persistées par `TargetService.apply_scan_result()`

2. **Découverte API** (`backend/app/api/v1/targets.py`)
   - L’endpoint `POST /targets/discover` n’infère plus automatiquement un type depuis le scan
   - Si `preferred_type` n’est pas fourni, la target est créée avec `TargetType.PHYSICAL`
   - Le `preferred_type` reste supporté pour les cas explicites côté client

3. **Tests**
   - Suppression des tests unitaires qui validaient l’ancienne logique `_infer_target_type`
   - Conservation des tests sur `build_capabilities_payload()`, qui reste la vraie source des capacités disponibles

**Conséquence architecturale :**
- `targets.type` devient un champ technique/legacy compatible API, mais ne doit plus piloter la logique métier de découverte de capacités
- Toute décision de support Docker / Docker Compose / VM / Kubernetes doit se baser sur `target_capabilities`

### Terminal WebSocket Interactif ✅ COMPLÉTÉ (2026-03-05)

**Décision clé (2026-03-05) :** Implémentation du terminal web interactif via WebSocket pour exécuter des commandes shell dans les conteneurs Docker.

**Architecture WindFlow vs Colibri :**

| Aspect | Colibri | WindFlow |
|--------|---------|----------|
| Serveur WS | Poetry.serve:5174 | FastAPI WebSocket natif |
| Auth | Query param | JWT dans premier message |
| Connexion exec | POST `/api/containers/{id}/exec` | Inline dans WebSocket |
| Streaming | Headers HTTP à supprimer | Docker API clean stream |

### Implémentation Terminal (6 phases)

#### Phase 1 — Backend Core ✅ COMPLÉTÉ
1. **TerminalService** (`backend/app/services/terminal_service.py`)
   - Méthodes : create_session, stream_output, send_input, resize_tty, cleanup_session, detect_shells
   - Utilisation subprocess docker exec -it (CLI-first WindFlow)
2. **Endpoint WebSocket** (`backend/app/api/v1/websockets.py`)
   - Route : `/ws/terminal/{container_id}`
   - Protocol: auth JWT → create exec → stream I/O → resize → cleanup

#### Phase 2 — Frontend Core ✅ COMPLÉTÉ
1. **Dépendances NPM** ✅ Installées
   - `@xterm/xterm`, `@xterm/addon-fit`, `@xterm/addon-web-links`
2. **Composable** (`frontend/src/composables/useTerminal.ts`)
   - Gère connexion WS, intégration xterm.js, messages
3. **Composant** (`frontend/src/components/ContainerTerminal.vue`)
   - xterm.js rendering, toolbar (clear, copy, reconnect, font)

#### Phase 3 — Intégration UI & Sécurité ✅ COMPLÉTÉ
1. **Intégration**
   - ✅ Onglet Terminal dans `DeploymentDetail.vue`
   - ✅ Vue standalone `/terminal` (`frontend/src/views/Terminal.vue`)
   - ✅ Route ajoutée dans `router/index.ts`
2. **Modèle & Types**
   - ✅ Ajout `container_id` dans `Deployment` model (backend)
   - ✅ Ajout `container_id` dans `DeploymentResponse` schema (backend)
   - ✅ Mise à jour type `Deployment` (frontend)
3. **Sécurité** ✅ COMPLÉTÉ
   - ✅ RBAC: Vérification organisation sur déploiement contenant le container
   - ✅ Audit trail: Logging des sessions terminal (`log_terminal_audit`)
   - ✅ Rate limiting: Max 3 sessions simultanées par utilisateur

#### Phase 4 — Features Avancées ✅ COMPLÉTÉ
- Détection shells disponibles (TerminalService.detect_shells())
- API endpoint `/api/v1/docker/containers/{id}/shells`
- Copy output vers clipboard (implémenté)

#### Phase 5 — Tests ✅ COMPLÉTÉ
- **16 tests unitaires** passent (100%)
- Fichier : `backend/tests/unit/test_docker/test_terminal_service.py`

#### Phase 6 — Documentation ✅ COMPLÉTÉ
- Memory bank mis à jour
- Tests documentés avec fixtures et cas de test

---

## Contexte Précédent (2026-02)

### Implémentation Docker complétée ✅

**Décision (2026-02-25) :** Les targets Docker sont **locales uniquement** — connexion via Unix socket `/var/run/docker.sock` exclusivement.

**Points clés :**
- `DockerClientService` : couche accès API Docker Engine via httpx + UDS
- API REST Docker : containers, images, volumes, networks, system
- `DockerExecutor` : CLI (prioritaire) + Socket (fallback)
- `DockerService` et `DockerComposeService` refactorés
- WebSocket streaming logs : `WS /ws/docker/containers/{container_id}/logs`
- Tests : 91 unitaires + 55 intégration

---

## Décisions Actives

| Décision | Raison |
|---|---|
| Docker local uniquement (socket) | Simplicité, MVP, pas de gestion TLS/certs |
| httpx + UDS | Async natif, pas de dépendance dockerode |
| FastAPI WebSocket (vs Poetry) | Simplicité, réutilisation infrastructure existante |
| xterm.js frontend | Solution standard, bien maintenue |
| `target_capabilities` = source de vérité | Une machine peut exposer plusieurs capacités simultanées |
