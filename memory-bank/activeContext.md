# Active Context — WindFlow

## Travail actuel

### Tâche en cours : Terminal WebSocket Interactif (Priorité #5 roadmap)

**Décision clé (2026-03-05) :** Implémentation du terminal web interactif via WebSocket pour exécuter des commandes shell dans les conteneurs Docker.

**Architecture WindFlow vs Colibri :**

| Aspect | Colibri | WindFlow |
|--------|---------|----------|
| Serveur WS | Poetry.serve:5174 | FastAPI WebSocket natif |
| Auth | Query param | JWT dans premier message |
| Connexion exec | POST `/api/containers/{id}/exec` | Inline dans WebSocket |
| Streaming | Headers HTTP à supprimer | Docker API clean stream |

### Plan d'implémentation Terminal (6 phases)

#### Phase 1 — Backend Core (Jours 1-2) ✅ COMPLÉTÉ
1. **TerminalService** (`backend/app/services/terminal_service.py`)
   - Méthodes : create_exec, stream_output, send_input, resize_tty, cleanup_session
   - Utilisation subprocess docker exec -it (CLI-first WindFlow)
2. **Endpoint WebSocket** (`backend/app/api/v1/websockets.py`)
   - Route : `/ws/terminal/{container_id}`
   - Protocol: auth JWT → create exec → stream I/O → resize → cleanup

#### Phase 2 — Frontend Core (Jours 3-4) ✅ COMPLÉTÉ
1. **Dépendances NPM** (en attente d'installation)
   - `@xterm/xterm`, `@xterm/addon-fit`, `@xterm/addon-web-links`
2. **Composable** (`frontend/src/composables/useTerminal.ts`)
   - Gère connexion WS, intégration xterm.js, messages
3. **Composant** (`frontend/src/components/ContainerTerminal.vue`)
   - xterm.js rendering, toolbar (clear, copy, reconnect, font)

#### Phase 3 — Intégration UI & Sécurité (Jour 5) [À FAIRE]
1. **Intégration**
   - Onglet Terminal dans `DeploymentDetail.vue`
   - Vue standalone `/terminal`
2. **Sécurité**
   - Permission RBAC `container.exec`
   - Audit trail (via AuditLoggerPlugin existant)
   - Rate limiting (3 terminaux/user)

#### Phase 4 — Features Avancées (Jour 6) [À FAIRE]
- Détection shells disponibles (TerminalService.detect_shells())
- Reconnexion automatique (via composable)
- Copy output vers clipboard (implémenté)

#### Phase 5 — Tests (Jour 7) [À FAIRE]
- Unitaires TerminalService (85%+)
- Intégration WebSocket
- E2E Playwright

#### Phase 6 — Documentation (Jour 7)
- `doc/TERMINAL-WEBSOCKET.md`
- OpenAPI annotations
- Memory bank updates

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
