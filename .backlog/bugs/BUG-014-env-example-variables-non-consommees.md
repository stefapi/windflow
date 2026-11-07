# BUG-014 : `env.example` — variables d'environnement non consommées par les settings

**Statut :** DONE
**Gravité :** Mineur

> Constaté lors de la revue finale de conformité (STORY-254.3, 2026-11-07) ; signalement n°4 de STORY-252, jamais traité.

## Reproduction
1. Comparer les noms de variables de [`env.example`](../../env.example) aux champs de [`backend/app/config.py`](../../backend/app/config.py) (Pydantic-settings)
2. Identifier les variables sans setting correspondant : `ACCESS_TOKEN*`, `SECRET_KEY`… (noms ne correspondant à aucun champ réel)

## Comportement attendu
Chaque variable documentée dans `env.example` doit correspondre à un setting consommé (ou être retirée) — le fichier est la documentation de référence de la configuration pour les opérateurs.

## Comportement actuel
Plusieurs noms (`ACCESS_TOKEN`/`SECRET_KEY`…) ne correspondent à aucun setting réel : un opérateur qui les définit s'attend à un effet qui n'a pas lieu (silencieusement ignorés).

## Résolution

Corrigé le 2026-11-07 (cycle NEW → CONFIRMED → IN_PROGRESS → REVIEW → DONE parcouru lors de la session de correction).

### Inventaire exhaustif (croisement `env.example` ↔ `config.py` ↔ interpolation compose `${...}` ↔ Makefile/vite)

Variables orphelines identifiées et traitées :

| Variable orpheline | Traitement |
|---|---|
| `SECRET_KEY` (env + `.env.prod` + compose dev/minimal/prod) | **Remplacée par `JWT_SECRET_KEY`** (setting réel — critique : compose prod passait `SECRET_KEY` ignoré → le conteneur tournait sur le JWT par défaut du code) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` (env + `.env.prod` + compose prod) | **Remplacé par `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15`** (setting réel, arbitrage F5) |
| `REDIS_ENABLED` | Retirée (aucun setting ; le mode Redis est activé par `CACHE_URL` définie) |
| `REDIS_URL` (compose dev/prod passé au conteneur API) | **Remplacé par `CACHE_URL`** (setting réellement consommé — cache unifié STORY-168 + bus STORY-162) ; `REDIS_MAX_CONNECTIONS` retiré |
| `SMTP_HOST` (env.example, section backend) | Remplacé par `SMTP_SERVER` (consommé par [`backend/app/helper/email.py`](../../backend/app/helper/email.py)) ; `SMTP_HOST` conservé dans `.env.prod.example` **uniquement** pour Grafana (`GF_SMTP_HOST`) avec commentaire distinguant les deux consommateurs |
| `RATE_LIMIT_PER_MINUTE`, `REQUEST_TIMEOUT` | Retirées (aucun setting, aucun compose) |
| `WINDFLOW_EXTENSIONS`, bloc `ENABLE_PROMETHEUS/GRAFANA/ELK…/KEYCLOAK/AI/KUBERNETES/SWARM` | Retirés (les extensions se pilotent par **profils compose / cibles Makefile** `make enable-*`, pas par env) ; remplacés par un bloc documentaire + les vraies variables compose (`KEYCLOAK_ADMIN`/`KEYCLOAK_PASSWORD` de `docker-compose.extensions.yml`, `GRAFANA_USER`/`GRAFANA_PASSWORD` du dev) |
| `ENABLE_VAULT` | **Remplacé par `VAULT_ENABLED`** (setting réel `vault_enabled`) |
| `LLM_PROVIDER`/`LLM_MODEL`/`LLM_TEMPERATURE`/`LLM_MAX_TOKENS`/`LLM_BASE_URL` | Retirés (aucun setting ne les consomme — [`litellm_service.py`](../../backend/app/services/litellm_service.py) reçoit ses paramètres par injection) ; remplacés par les settings réels `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`OLLAMA_BASE_URL` |
| `OLLAMA_URL` | **Remplacé par `OLLAMA_BASE_URL`** (setting réel `ollama_base_url`) |
| `KEYCLOAK_ADMIN_USER`/`KEYCLOAK_ADMIN_PASSWORD` | Corrigés en `KEYCLOAK_ADMIN`/`KEYCLOAK_PASSWORD` (noms réellement interpolés par `docker-compose.extensions.yml`) |
| `PROMETHEUS_RETENTION` | Retirée de env.example (config `infrastructure/docker/prometheus.yml`, pas une env) ; remplacée par `PROMETHEUS_ENABLED` (setting réel de `/api/v1/metrics`) |
| `BACKUP_ENABLED`/`BACKUP_RETENTION_DAYS`/`BACKUP_SCHEDULE`/`BACKUP_STORAGE` + bloc `ENABLE_LLM_OPTIMIZATION/AUTO_SCALING/BACKUP_AUTOMATION/SLACK/DISCORD` | Retirés (aucun consommateur — fonctionnalités non implémentées) ; le S3 backup compose (`BACKUP_S3_BUCKET`/`AWS_*`) reste documenté en commentaire (interpolé par compose prod) |
| `RELOAD`, `PROFILING` | Retirés (aucun setting ; `DEBUG` setting réel conservé) |
| `DOMAIN` (env.example dev) | Retiré (interpolation compose prod uniquement, déjà documenté dans `.env.prod.example`) |
| `DOCKER_TAG` | Retiré (le Makefile dérive le tag de `git describe`, ne le lit pas depuis l'env) ; `DOCKER_REGISTRY` conservé (lu par le Makefile) |
| `VITE_WS_URL` | Retiré (le frontend lit `VITE_API_BASE_URL` ; WS servi par le même proxy `/api`) |
| compose prod service api : `APP_ENV`, `API_WORKERS`, `LLM_*` (résidus non consommés) | Retirés ; `ENVIRONMENT=production` conservé (setting réel) |
| compose minimal : `DATABASE_TYPE`/`CACHE_TYPE`/`SECRETS_TYPE`/`AUTH_TYPE`/`API_V1_PREFIX`/`API_TITLE`/`API_VERSION`/`ENVIRONMENT: minimal` | Retirés (aucun setting ; `ENVIRONMENT: minimal` → `development`, valeur cohérente avec l'enum du code) |
| `.env.prod.example` : section Worker (`WORKER_*`) | Retirée (résidu purge Celery STORY-130.2) ; checklist finale mise à jour |

### Vérification

- Écran final : `grep` croisé variables `env.example`/`.env.prod.example` ↔ `config.py`/compose/Makefile → **0 variable orpheline** (les hits restants sont les settings réels ou des variables légitimement interpolées par compose : `SMTP_HOST`→Grafana, `GRAFANA_SECRET_KEY`…) ;
- Les 5 fichiers compose revalidés en YAML (`yaml.safe_load` OK) ;
- `env.example` documente désormais pour chaque section le consommateur réel (`config.py`, `helper/email.py`, compose, vite.config.ts, Makefile).

### Note

La correction compose prod (`SECRET_KEY` → `JWT_SECRET_KEY`) a été validée par yaml.safe_load ; un `docker compose config` sur machine de déploiement reste recommandé au prochain déploiement (zone « revue humaine déploiement Docker production », rules 02 §7).
