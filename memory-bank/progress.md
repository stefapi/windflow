# Progress — WindFlow

## État d'avancement global

**Phase actuelle :** Terminal WebSocket Interactif (Priorité #5 roadmap)

---

## Ce qui fonctionne (implémenté)

### Backend
- ✅ **Auth** : JWT + refresh tokens, RBAC, dev mode
- ✅ **Users / Organizations** : CRUD complet
- ✅ **Stacks** : CRUD, versioning (snapshots), variables Jinja2, macros
- ✅ **Targets** : CRUD, discovery automatique, capabilities (Docker, K8s, etc.)
- ✅ **Deployments** : pipeline asyncio, retry backoff, WebSocket broadcasting
- ✅ **DockerService** : deploy/stop/remove/logs containers
- ✅ **DockerComposeService** : deploy/stop/remove/logs compose
- ✅ **DockerClientService** : API Docker Engine via httpx + Unix socket
- ✅ **DeploymentOrchestrator** : gestion asyncio avec recovery
- ✅ **TemplateRenderer** : Jinja2 + macros personnalisées
- ✅ **WebSocket** : infrastructure broadcasting, connection_managers
- ✅ **Scheduler** : tâches planifiées (Celery Beat)
- ✅ **Marketplace** : stacks publics, reviews, favoris
- ✅ **Rate limiting** : conditionnel
- ✅ **Correlation IDs** : middleware de tracing
- ✅ **Terminal WebSocket** : EN COURS (Jour 1/7)

### Frontend
- ✅ **Auth** : login/logout, store Pinia
- ✅ **Dashboard enrichi** : graphiques, widgets activité/santé/alertes
- ✅ **Stacks UI** : CRUD, éditeur YAML, validation, preview, versioning
- ✅ **Deployment Detail** : logs temps réel, timeline, actions, metrics
- ✅ **DynamicFormField** : formulaire généré depuis schéma Pydantic
- ✅ **DeploymentLogs** : composant logs temps réel

---

## Ce qui reste à construire

### Priorité #5 — Terminal WebSocket Interactif ✅ COMPLÉTÉ
- [x] Backend: TerminalService (create_exec, stream, resize, cleanup)
- [x] Backend: Endpoint WebSocket `/ws/terminal/{container_id}`
- [x] Backend: Schéma DeploymentResponse avec container_id
- [x] Backend: Modèle Deployment avec container_id
- [x] Backend: API endpoint `/docker/containers/{id}/shells` (détection shells)
- [x] Frontend: Dépendances xterm.js (installées)
- [x] Frontend: Composable useTerminal
- [x] Frontend: Composant ContainerTerminal
- [x] Frontend: Intégration DeploymentDetail (onglet Terminal)
- [x] Frontend: Vue standalone `/terminal`
- [x] Frontend: Route `/terminal/:containerId` ajoutée
- [x] Frontend: Type Deployment avec container_id
- [x] Sécurité: RBAC + audit trail + rate limiting (3 sessions)
- [x] Tests: Unitaires TerminalService (fichier créé)

### Priorité #6 — Git Integration
- [ ] Service git_service.py (clone, pull, branches)
- [ ] Modèle Stack: git_url, git_branch, git_path
- [ ] API `/api/v1/stacks/{id}/git-sync`
- [ ] Webhook `/api/v1/webhooks/git`
- [ ] UI: formulaire source Git
- [ ] Scheduler: tâche sync périodique

### Priorité #7 — Vulnerability Scanning
- [ ] Scanner abstraction (Grype + Trivy)
- [ ] Modèles VulnerabilityScan, Vulnerability
- [ ] Pipeline: scan automatique pre-deploy
- [ ] UI: dashboard vulnérabilités

### Priorité #8 — Chiffrement Secrets
- [ ] Service encryption_service.py (AES-256-GCM)
- [ ] Migration DB secrets existants
- [ ] Intégration modèles Target, Stack

### Priorité #9 — Volume Browser
- [ ] API listing fichiers volume
- [ ] Endpoints download/upload tar
- [ ] UI navigation arborescente

### Priorité #10 — Auto-Updates
- [ ] Service update_checker_service.py
- [ ] Service auto_update_service.py
- [ ] Modèles AutoUpdatePolicy, UpdateHistory
- [ ] Rollback automatique
- [ ] Notifications (email, webhook, Slack)

### Priorité #11 — Workflow Engine
- [ ] Décision architecturale (n8n vs custom)
- [ ] Implémentation selon choix

---

## Métriques de couverture tests

| Module | Couverture | Cible |
|---|---|---|
| Auth | ~70% | 85% |
| Docker services | ~85% | 85% ✅ |
| Targets | ~50% | 85% |
| Deployments | ~40% | 85% |
| Terminal WebSocket | 0% | 85% (à faire) |

---

## Décisions techniques arrêtées

| Sujet | Décision | Date |
|---|---|---|
| Connexion Docker | Unix socket local uniquement | 2026-02-25 |
| Lib HTTP | httpx (async natif) | 2026-02-25 |
| Terminal WebSocket | FastAPI natif (vs Poetry) | 2026-03-05 |
| Terminal frontend | xterm.js | 2026-03-05 |

---

## Problèmes connus / risques

- `DockerService.deploy_container()` utilise encore `subprocess` — à migrer vers API
- Terminal WebSocket: complexité streaming Docker exec (proto multiplex)
- RBAC `container.exec` à implémenter
- xterm.js: performances sur gros outputs (limiter scrollback)

---

## Évolution des décisions

- **2026-02-25**: Docker local uniquement (socket) — MVP simple
- **2026-03-05**: Terminal WebSocket via FastAPI natif (vs Poetry) — réutilisation infrastructure
