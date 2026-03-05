# System Patterns — WindFlow

## Architecture générale

**Modular Monolith** — FastAPI backend + Vue 3 frontend + PostgreSQL + Redis

```
frontend (Vue 3 + Pinia)
    ↕ REST API / WebSocket
backend (FastAPI async)
    ├── api/v1/           → routes HTTP
    ├── services/         → logique métier
    ├── models/           → SQLAlchemy 2.0
    ├── schemas/          → Pydantic v2
    ├── tasks/            → asyncio (fallback Celery)
    └── websocket/        → broadcasting temps réel
    ↕
PostgreSQL + Redis
```

## Patterns clés

### 1. Service Layer Pattern
Toute logique métier est dans `services/`, jamais directement dans les routes.
Les routes injectent les services via `Depends()`.

```python
# Route → Service → DB
@router.get("/{id}")
async def get_stack(id: str, session = Depends(get_db)):
    return await StackService.get_by_id(session, id)
```

### 2. Scoping Organisation
Toutes les ressources sont scopées par `organization_id`. Les routes vérifient systématiquement :
```python
if resource.organization_id != current_user.organization_id:
    raise HTTPException(403, "Accès refusé")
```

### 3. Déploiement Asynchrone
Pipeline de déploiement en 3 couches :
```
API route → DeploymentOrchestrator.start_deployment()
          → asyncio.create_task(_execute_deployment_with_retry())
          → deploy_stack_async()  [background_tasks.py]
          → DockerService ou DockerComposeService
```

Retry avec backoff exponentiel : 3 tentatives, délai initial 60s, max 600s.

### 4. WebSocket Broadcasting
Architecture pub/sub pour les mises à jour temps réel :
```
DeploymentService.update_status() → broadcasting.py → WebSocket clients
```
Infrastructure : `connection_managers.py` + `broadcasting.py`

### 5. Template Rendering (Jinja2)
Les stacks utilisent des templates Jinja2 avec des macros personnalisées :
```python
TemplateRenderer.render_dict(template, variables)
# Macros disponibles : generate_password(), get_valid_port(), random_string()
```

### 6. Rate Limiting
`conditional_rate_limiter(requests, seconds)` — conditionnel (désactivé si `DISABLE_RATE_LIMIT=true`)

### 7. Correlation IDs
Middleware `correlation.py` injecte un `correlation_id` dans chaque requête pour le tracing.

## Architecture Docker (locale uniquement)

### Connexion Docker
**Décision : Unix socket local uniquement** — `/var/run/docker.sock`

```
DockerClientService
    → httpx.AsyncClient(transport=AsyncHTTPTransport(uds="/var/run/docker.sock"))
    → Docker Engine API v1.41+
```

Pas de TCP distant, pas de TLS, pas de gestion de certificates pour l'instant.

### Méthode d'exécution (CLI vs Socket)

**Priorité : CLI** pour le débogage (meilleure visibility), **Socket** en fallback

```
DockerExecutor (Factory/Strategy)
    ├── CLIDockerExecutor     ← prioritaire (docker run, docker compose)
    │   └── subprocess.run() / asyncio.create_subprocess_shell()
    └── SocketDockerExecutor  ← fallback (API REST Docker)
        └── DockerClientService (httpx + UDS)
```

Pour les cibles distantes : SSHExecutor via `TargetScannerService`

### Hiérarchie des services Docker

```
DockerClientService          ← couche transport (API Docker Engine via socket)
    ↑ utilisé par
DockerService                ← containers simples (run/stop/rm/logs)
DockerComposeService         ← projets docker-compose (up/down/logs)
    ↑ utilisés par
background_tasks.deploy_stack_async()
    ↑ orchestré par
DeploymentOrchestrator
```

**Templates de stacks** : Les déploiements utilisent des templates stockés en BDD (table `stacks`)
- `stack.template` : configuration Docker Compose (JSON)
- `stack.variables` : variables configurables avec macros Jinja2
- `stack.target_type` : docker, docker_swarm, kubernetes, vm, physical

### Démultiplexage stream Docker
Le protocole Docker multiplexe stdout/stderr avec un header 8 bytes :
- Byte 0 : type (0=stdin, 1=stdout, 2=stderr)
- Bytes 4-7 : taille du frame (big endian)
- Bytes 8+ : payload

```python
def demux_docker_stream(buffer: bytes) -> tuple[str, str]:
    """Sépare stdout et stderr du stream Docker multiplexé"""
    ...
```

## Modèles de données clés

### Stack
- `name`, `description`, `target_type` (docker/docker-compose/kubernetes)
- `template` (JSONB) : configuration du service/compose
- `variables` (JSONB) : définitions de variables avec defaults/macros
- `deployment_name` : template Jinja pour le nom de déploiement

### Deployment
- `status` : PENDING → DEPLOYING → RUNNING | FAILED | STOPPED
- `variables` : configuration appliquée lors du déploiement
- `logs` : logs accumulés (mis à jour en temps réel)
- `task_retry_count`, `task_started_at` : tracking asyncio

### Target
- `type` : docker, ssh, kubernetes, docker_swarm, vm, physical
- `host`, `port`, `credentials` (JSONB)
- `scan_date`, `scan_success` : résultats du dernier scan
- `capabilities` : relation vers `TargetCapability`

## Conventions de code

- **Async partout** : toutes les fonctions de service sont `async def`
- **Logging structuré** : `extra={"correlation_id": ..., "user_id": ...}`
- **Exceptions** : `HTTPException` dans les routes, exceptions Python dans les services
- **Schémas** : séparation `Create` / `Update` / `Response` pour chaque modèle
- **UUIDs** : toutes les PKs sont des UUIDs

### Pattern: Terminal WebSocket Interactif

**Problème:** Exécution de commandes shell dans les conteneurs Docker via interface web

**Solution:** WebSocket bidirectionnel + xterm.js frontend

**Architecture WindFlow (vs Colibri):**

| Aspect | Colibri | WindFlow |
|--------|---------|----------|
| Serveur WS | Poetry.serve:5174 | FastAPI WebSocket natif |
| Auth | Query param | JWT dans premier message |
| Connexion exec | POST + HTTP upgrade tcp | Inline dans WebSocket |

**Implémentation WindFlow (COMPLÉTÉE):**
1. **Backend**: `TerminalService` → subprocess `docker exec -it` (CLI-first)
2. **WebSocket**: `/ws/terminal/{container_id}` → auth JWT → stream I/O
3. **Frontend**: xterm.js + composable `useTerminal` + composant `ContainerTerminal`
4. **TTY resize**: séquence escape xterm `\x1b[8;rows;cols t`

**Fichiers créés:**
- `backend/app/services/terminal_service.py`
- `backend/app/api/v1/websockets.py` (endpoint ajouté)
- `frontend/src/composables/useTerminal.ts`
- `frontend/src/components/ContainerTerminal.vue`

**Protocole messages:**

Client → Serveur:
```json
{"type": "auth", "token": "JWT"}
{"type": "input", "data": "ls\n"}
{"type": "resize", "cols": 120, "rows": 30}
```

Serveur → Client:
```json
{"type": "ready", "exec_id": "xxx", "shell": "/bin/sh", "user": "root", "cols": 80, "rows": 24}
{"type": "output", "data": "root@container:/# "}
{"type": "error", "message": "..."}
{"type": "exit", "code": 0}
```

**Avantages WindFlow:**
- Pas de serveur WebSocket séparé
- Auth cohérente avec le reste de l'API (JWT)
- Réutilisation infrastructure WebSocket existante
- Simplicité de déploiement

**Prochaines étapes:**
- Installation dépendances xterm.js (`pnpm add @xterm/xterm @xterm/addon-fit @xterm/addon-web-links`)
- Intégration dans DeploymentDetail.vue (onglet Terminal)
- Tests unitaires et intégration
