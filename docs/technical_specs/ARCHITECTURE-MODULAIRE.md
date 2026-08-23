# Architecture modulaire — briques d'infrastructure optionnelles & profils compose

> **Statut** : Spécification technique · Partiellement implémenté (fichiers compose et cibles `make` livrés ; `scripts/enable-extension.sh` et `make enable-workers` divergents — voir § Activation)
> **Périmètre** : Mécanisme réel d'activation des briques d'infrastructure optionnelles de l'instance WindFlow (profils Docker Compose), inventaire des fichiers compose du dépôt, et distinction avec les Plugins.
> **Référence de fond** : [general_specs — ch. 04 architecture](../general_specs/04-architecture.md) · [ch. 05 stack technologique](../general_specs/05-stack-technologique.md) · [ch. 11 plugins](../general_specs/11-plugins.md) · [ch. 16 déploiement](../general_specs/16-deploiement.md)
> **Dernière mise à jour** : 2026-08-23 — **refondu vague 4** ([PLAN-REFONTE-TECHNICAL-SPECS.md](../../PLAN-REFONTE-TECHNICAL-SPECS.md))

> **Terminologie** : vocabulaire canonique du glossaire ([19-glossaire.md](../general_specs/19-glossaire.md)). Le mot « extension » est réservé au **type de plugin extension** (ch. 11) ; les services d'infrastructure activables via profils Compose sont appelés **briques d'infrastructure optionnelles** — voir l'encadré [Distinction briques compose ↔ Plugins](#distinction-briques-compose-et-plugins).

## Vue d'ensemble

Le déploiement de WindFlow suit le principe des profils de ressources du chapitre [04-architecture.md](../general_specs/04-architecture.md) (référence unique : léger / standard / complet) : un **core léger fixe** auquel l'opérateur ajoute des **briques d'infrastructure optionnelles** via des profils Docker Compose. Seuls les services activés consomment des ressources. Ce document décrit le mécanisme **réellement livré** dans le dépôt (fichiers compose, cibles `make`, script) ; les principes d'architecture et le rôle des services métier vivent dans general_specs (ch. 04 et 05) et ne sont pas répétés ici.

## Stack de base réelle (`docker-compose.minimal.yml`)

Le cœur livré correspond au **profil léger** : 3 conteneurs, < 512 Mo RAM, démarrage < 2 minutes — SQLite embarqué, cache local, secrets fichier, auth JWT, aucun service externe.

| Service | Image | Port | Routage Traefik |
|---|---|---|---|
| `traefik` | `traefik:v2.11` | 80, 443, 8080 (dashboard) | `traefik.localhost` |
| `windflow-api` | build `infrastructure/docker/Dockerfile.api` | 8000 (interne) | ``Host(`localhost`) && PathPrefix(`/api`)`` |
| `windflow-frontend` | build `infrastructure/docker/Dockerfile.frontend` | 80 (interne) | ``Host(`localhost`)`` (priorité 1) |

Extrait réel — [`docker-compose.minimal.yml`](../../docker-compose.minimal.yml) (service `windflow-api`) :

```yaml
    environment:
      # Configuration minimale - SQLite embedded
      DATABASE_TYPE: sqlite
      DATABASE_URL: sqlite:///./data/windflow.db
      CACHE_TYPE: local
      SECRETS_TYPE: file
      AUTH_TYPE: jwt

      # Configuration application
      SECRET_KEY: ${SECRET_KEY:-change-me-in-production-please}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      ENVIRONMENT: minimal
```

```yaml
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`localhost`) && PathPrefix(`/api`)"
      - "traefik.http.routers.api.entrypoints=web"
      - "traefik.http.services.api.loadbalancer.server.port=8000"
      - "traefik.http.middlewares.api-stripprefix.stripprefix.prefixes=/api"
```

Le socket Docker (`/var/run/docker.sock`) est monté dans l'API ; les données SQLite vivent dans le volume `windflow_data` (bind `./data/windflow`), les logs dans `windflow_logs`.

*État actuel (implémenté)* vs *Cible (general_specs ch. 04)* : le mode léger canonique prévoit un worker Celery (1 process) à côté de l'API — le compose minimal actuel n'en définit pas (le worker n'existe que dans `docker-compose.prod.yml`) ; et la frontière cible place le reverse proxy côté Plugins (ch. 04), alors que Traefik est ici inclus au core compose. Écarts d'état, sans incidence sur le mécanisme décrit ici.

## Briques d'infrastructure optionnelles (`docker-compose.extensions.yml`)

Cinq profils Compose sont réellement définis, à combiner avec le compose minimal :

| Profil | Services ajoutés | Images | Accès |
|---|---|---|---|
| `database` | `windflow-postgres` | `postgres:15-alpine` | `localhost:${POSTGRES_PORT:-5432}` (non routé Traefik) |
| `cache` | `windflow-redis` | `redis:7-alpine` | `localhost:${REDIS_PORT:-6379}` (mot de passe, maxmemory 256 Mo) |
| `secrets` | `windflow-vault` | `hashicorp/vault:1.15` (mode dev) | `http://vault.localhost` |
| `sso` | `windflow-keycloak` + `windflow-keycloak-db` | `quay.io/keycloak/keycloak:23.0` + `postgres:15-alpine` | `http://keycloak.localhost` (admin/${KEYCLOAK_PASSWORD:-admin123}) |
| `monitoring` | `windflow-prometheus` + `windflow-grafana` | `prom/prometheus:v2.48.0` + `grafana/grafana:10.2.2` | `http://prometheus.localhost` · `http://grafana.localhost` (admin/${GRAFANA_PASSWORD:-admin123}) |

Extrait réel — [`docker-compose.extensions.yml`](../../docker-compose.extensions.yml) (brique `database`) :

```yaml
  windflow-postgres:
    image: postgres:15-alpine
    container_name: windflow-postgres
    restart: unless-stopped
    profiles: ["database"]
    environment:
      POSTGRES_DB: windflow
      POSTGRES_USER: windflow
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-windflow123}
      POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=C"
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infrastructure/docker/init-scripts:/docker-entrypoint-initdb.d:ro
    networks:
      - windflow-network
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
```

Chaque brique a son volume dédié (`postgres_data`, `redis_data`, `vault_data`, `keycloak_db_data`, `prometheus_data`, `grafana_data`) ; les briques ne dépendent pas les unes des autres, sauf `sso` qui embarque sa propre base (`windflow-keycloak-db`, indépendante du profil `database`). Les configurations montées vivent sous `infrastructure/docker/` (`prometheus.yml`, `prometheus-rules/`, `grafana/dashboards/`, `grafana/provisioning/`, `vault-config/`, `init-scripts/`).

⚠️ **Non implémenté / divergent** : il n'existe **aucun** profil compose `logging` (ELK), `ai`, `kubernetes` ni `swarm` dans le dépôt — ces briques citées par d'anciens documents n'ont jamais été livrées (arbitrage general_specs : pas de self-hosting K8s de WindFlow, ch. 04 ; IA = plugins `ollama`/`litellm`, ch. 18).

## Activation & désactivation

Le mécanisme fiable et livré est le **Makefile** :

```bash
make minimal            # core léger (docker-compose.minimal.yml)
make enable-database    # + PostgreSQL   (idem: enable-cache, enable-secrets,
make enable-monitoring  # + Prometheus+Grafana   enable-sso)
make disable-monitoring # compose down du profil (volume conservé)
make dev-full           # core + database + cache + monitoring
make prod               # docker-compose.prod.yml
make status | logs | stop | restart
```

Chaque cible `enable-*` lance `docker compose -f docker-compose.minimal.yml -f docker-compose.extensions.yml --profile <profil> up -d` ; le réseau `windflow-network` est créé au besoin.

⚠️ **Écarts connus (vérifiés dans le dépôt)** :
- `make enable-workers` active les profils `cache` + `workers`, mais **aucun service `profiles: ["workers"]` n'est défini** dans `docker-compose.extensions.yml` — la cible ne démarre aucun worker. Les workers Celery ne sont définis que dans `docker-compose.prod.yml` (service `windflow-worker`, image `Dockerfile.worker`).
- [`scripts/enable-extension.sh`](../../scripts/enable-extension.sh) est livré mais **désynchronisé** : il pilote des extensions `monitoring`/`logging`/`vault`/`sso`/`ai`/`kubernetes`/`swarm` via des variables `ENABLE_*` dans `.env` et appelle `--profile vault` (le profil réel s'appelle `secrets`), sur base `docker-compose.yml` (simple redirecteur d'aide) ; les profils `logging`, `ai`, `kubernetes`, `swarm` n'existent pas. Les variables `ENABLE_*` ne sont lues par aucun fichier compose. **Voie recommandée : les cibles `make`.**

## Variables d'environnement

Les variables réellement lues par les compose (avec défauts) : `SECRET_KEY`, `LOG_LEVEL` (core) ; `POSTGRES_PASSWORD`, `POSTGRES_PORT` ; `REDIS_PASSWORD`, `REDIS_PORT` ; `VAULT_TOKEN`, `VAULT_PORT` ; `KEYCLOAK_ADMIN`, `KEYCLOAK_PASSWORD`, `KEYCLOAK_DB_PASSWORD` ; `GRAFANA_USER`, `GRAFANA_PASSWORD`. Modèles fournis : [`env.example`](../../env.example) et [`.env.prod.example`](../../.env.prod.example) (production : `DOMAIN`, `ACME_EMAIL`, `LLM_*`, S3 de backup…).

## Fichiers compose du dépôt

| Fichier (racine) | Rôle réel |
|---|---|
| [`docker-compose.yml`](../../docker-compose.yml) | Redirecteur d'aide (service factice `windflow-help`) — ne déploie rien |
| [`docker-compose.minimal.yml`](../../docker-compose.minimal.yml) | Core léger réel : traefik + api (SQLite) + frontend |
| [`docker-compose.extensions.yml`](../../docker-compose.extensions.yml) | Briques optionnelles — 5 profils compose |
| [`docker-compose-dev.yml`](../../docker-compose-dev.yml) | Développement : postgres, redis, vault, api :8000, frontend :3000, **nginx** :80/443, prometheus :9090, grafana :3001 |
| [`docker-compose.prod.yml`](../../docker-compose.prod.yml) | Production : traefik v3 + Let's Encrypt, postgres, redis, vault (mode fichier), api ×2, worker ×2, frontend ×2, prometheus, grafana, node-exporter, cAdvisor, backup, loki, promtail |
| [`redis-compose.yaml`](../../redis-compose.yaml) | Utilitaire Redis isolé (hors mécanisme des profils) |

⚠️ **Écart de nommage connu** : le chapitre [16-déploiement.md](../general_specs/16-deploiement.md) référence `docker-compose.light.yml` (profil léger) et `docker-compose.yml` (profil standard) — le dépôt livre `docker-compose.minimal.yml` (même fonction) et un `docker-compose.yml` redirecteur ; la stack « standard » complète vit en pratique dans `docker-compose.prod.yml`. Convergence à planifier (tracée dans le plan de refonte).

## Distinction briques compose et Plugins

| | Briques d'infrastructure (profils compose) | Plugins (ch. 11-12) |
|---|---|---|
| **Nature** | Services d'infrastructure pour l'**instance WindFlow elle-même** (BD, cache, secrets, SSO, monitoring) | Packages applicatifs installables **dans** WindFlow |
| **Activation** | Par l'opérateur, au niveau Docker (`make enable-*`) | Par l'utilisateur, via le Plugin Manager / marketplace |
| **Définition** | Entrées `services:` + `profiles:` dans un fichier compose | Manifest, types service/extension/hybride, hooks lifecycle |
| **Référence** | Ce document | [11-plugins.md](../general_specs/11-plugins.md) · [12-marketplace.md](../general_specs/12-marketplace.md) |

*État actuel (implémenté)* vs *Cible (general_specs ch. 04)* : la frontière cible classe plusieurs de ces fonctions côté Plugins (reverse proxy Traefik, monitoring, SSO, bases de données, IA — ch. 04) ; les compose actuels les traitent en briques d'infrastructure d'instance. Les deux mécanismes coexistent : compose = déployer l'instance, plugins = étendre l'application. En particulier, **l'IA n'est pas une brique compose** : elle passe par les plugins `ollama` et `litellm` du catalogue (ch. 12 ; [18-plugins-ia.md](../general_specs/18-plugins-ia.md)), le backend consommant `LLM_PROVIDER`/`LLM_MODEL`/`LLM_BASE_URL` (définis dans `docker-compose.prod.yml`).

## Arborescence réelle du dépôt

```
windflow/
├── docker-compose*.yml             # Compose (voir tableau ci-dessus) + redis-compose.yaml
├── Makefile                        # minimal / dev-full / prod, enable-*, disable-*
├── env.example / .env.prod.example # Modèles de configuration
├── backend/app/                    # API FastAPI : models/, schemas/, services/, tasks/, middleware/, core/
├── cli/                            # CLI Python (commands/, services/)
├── frontend/                       # Web UI Vue 3 + TypeScript
├── infrastructure/docker/          # Dockerfile.{api,frontend,worker}, traefik/, grafana/,
│                                   #   prometheus.yml, prometheus-alerts.yml, nginx.conf
├── scripts/                        # install.sh, enable-extension.sh
├── stacks_definitions/             # Catalogue interne de stacks (YAML — voir STACK-DEFINITIONS.md)
└── docs/
    ├── general_specs/              # Référence de fond (le QUOI)
    └── technical_specs/            # Ce corpus (le COMMENT)
```

Il n'existe ni `backend/app/extensions/`, ni `infrastructure/{kubernetes,helm,terraform}/`, ni répertoire `doc/` (les anciennes sections qui les décrivaient étaient fictives ; les specs vivent dans `docs/technical_specs/`).

## Migration entre configurations

- **Activer à chaud** : `make enable-<brique>` — le core continue de tourner, la brique rejoint le réseau `windflow-network`.
- **Désactiver** : `make disable-<brique>` (`compose down` du profil ; le volume dédié est conservé — une réactivation retrouve les données).
- **Retour au core** : `make stop && make minimal` (ou `make restart`).
- ⚠️ **SQLite → PostgreSQL** : aucun chemin de migration de données n'est livré (`scripts/` ne contient que `install.sh` et `enable-extension.sh`) ; les deux modes utilisent des stockages disjoints (`windflow_data` vs `postgres_data`).

## Voir aussi

- [04-architecture.md](../general_specs/04-architecture.md) — profils de déploiement (référence unique), frontière core/plugins
- [16-deploiement.md](../general_specs/16-deploiement.md) — procédures d'installation et profils
- [11-plugins.md](../general_specs/11-plugins.md) · [12-marketplace.md](../general_specs/12-marketplace.md) — système de plugins et catalogue
- [05-stack-technologique.md](../general_specs/05-stack-technologique.md) — SQLite/PostgreSQL, Traefik
- [README.md](../../README.md) du dépôt (démarrage) · [DOCKER-ENVIRONMENTS.md](../../DOCKER-ENVIRONMENTS.md) (environnements Docker)
- [STACK-DEFINITIONS.md](STACK-DEFINITIONS.md) · [CI-CD-GUIDE.md](CI-CD-GUIDE.md) — fichiers techniques liés
