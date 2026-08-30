# Organisation des répertoires du projet

## Structure racine

```
windflow/
├── backend/          # API FastAPI + services métier
├── frontend/         # SPA Vue 3
├── cli/              # CLI client Python
├── infrastructure/   # Docker, Nginx, Prometheus, Grafana
├── scripts/          # Scripts d'installation et utilitaires
├── dev/              # Scripts de développement et templates
├── stacks_definitions/ # Définitions YAML de stacks Docker
├── doc/              # Documentation et spécifications
├── .backlog/         # Gestion de projet (epics, stories, kanban)
├── .clinerules/      # Règles de développement
├── Makefile          # Toutes les commandes de dev (source de vérité)
└── pyproject.toml    # Config Poetry + dépendances Python
```

---

## Backend (`backend/`)

### Structure des modules

```
backend/
├── app/
│   ├── main.py               # Point d'entrée FastAPI, montage des routers
│   ├── config.py             # Settings Pydantic-settings (env vars)
│   ├── database.py           # Session async SQLAlchemy
│   ├── celery_app.py         # Config Celery
│   │
│   ├── api/v1/               # Endpoints REST (routers FastAPI)
│   │   └── *.py              # Un fichier par domaine (containers.py, stacks.py, auth.py…)
│   │
│   ├── auth/                 # AuthN/AuthZ
│   │   ├── jwt.py            # Génération/vérification JWT
│   │   └── dependencies.py   # Dépendances FastAPI (get_current_user, require_role…)
│   │
│   ├── core/                 # Transversal (ne pas mettre de logique métier ici)
│   │   ├── exceptions.py     # Exceptions personnalisées (WindFlowException et sous-classes)
│   │   ├── abstractions.py   # Classes de base abstraites
│   │   ├── events.py         # Événements système (Redis Streams)
│   │   ├── rate_limit.py     # Rate limiting
│   │   └── resilience.py     # Circuit breaker, retry, bulkhead
│   │
│   ├── models/               # Modèles SQLAlchemy (ORM)
│   │   └── *.py              # Un fichier par entité (user.py, stack.py, deployment.py…)
│   │
│   ├── schemas/              # Schémas Pydantic (validation I/O)
│   │   └── *.py              # Un fichier par domaine (stack.py, docker.py, auth.py…)
│   │
│   ├── services/             # Logique métier (pas de dépendance HTTP directe)
│   │   └── *.py              # Un fichier par domaine (docker_client_service.py…)
│   │
│   ├── tasks/                # Tâches Celery (async background)
│   │   └── *.py
│   │
│   ├── websocket/            # Handlers WebSocket (temps réel)
│   │   └── *.py
│   │
│   ├── middleware/           # Middlewares FastAPI (logging, correlation ID…)
│   │   └── *.py
│   │
│   ├── helper/               # Fonctions utilitaires pures (pas de dépendances métier)
│   │   └── *.py
│   │
│   └── enums/                # Énumérations partagées
│       └── *.py
│
└── tests/
    ├── conftest.py           # Fixtures partagées (DB de test, clients HTTP…)
    ├── unit/                 # Tests unitaires (mocks des dépendances externes)
    │   ├── test_services/
    │   ├── test_schemas/
    │   └── test_*.py
    └── integration/          # Tests d'intégration (DB réelle, Redis…)
        └── test_api_*.py
```

### Conventions backend

- **Un router = un domaine** dans `api/v1/` (monté dans `main.py`)
- **Un service = une classe** avec injection de dépendances (pas de singleton global sauf DB)
- **Schémas Pydantic** séparés en `*Request`, `*Response`, `*Update` selon usage
- **Migrations Alembic** dans `alembic/versions/` (jamais modifier les tables manuellement)
- **Toujours** lever des exceptions de `core/exceptions.py`, jamais des exceptions Python brutes dans les endpoints

---

## Frontend (`frontend/`)

### Structure des modules

```
frontend/
├── src/
│   ├── main.ts               # Point d'entrée Vue 3
│   ├── App.vue               # Composant racine
│   │
│   ├── views/                # Pages (une vue = une route)
│   │   └── *.vue             # ContainerDetail.vue, Stacks.vue…
│   │
│   ├── components/           # Composants réutilisables
│   │   ├── ui/               # Composants UI génériques (boutons, badges…)
│   │   └── [domaine]/        # Composants spécifiques à un domaine
│   │
│   ├── composables/          # Logique réutilisable (Composition API)
│   │   └── use*.ts           # useContainerStats.ts, useDeployments.ts…
│   │
│   ├── stores/               # État global Pinia
│   │   └── *.ts              # containers.ts, deployments.ts, auth.ts…
│   │
│   ├── services/             # Appels API HTTP (axios)
│   │   └── *.ts              # Un fichier par domaine
│   │
│   ├── types/                # Types TypeScript partagés
│   │   └── *.ts              # api.ts, models.ts…
│   │
│   ├── router/               # Vue Router
│   │   └── index.ts
│   │
│   ├── utils/                # Fonctions utilitaires pures
│   │   └── *.ts
│   │
│   ├── assets/               # Images, icônes statiques
│   ├── styles/               # CSS/UnoCSS global
│   └── layouts/              # Layouts de pages (DefaultLayout.vue…)
│
└── tests/
    ├── unit/                 # Tests unitaires Vitest
    │   ├── views/            # Tests des vues (*.spec.ts)
    │   ├── components/       # Tests des composants
    │   └── composables/      # Tests des composables
    ├── integration/          # Tests d'intégration
    └── e2e/                  # Tests E2E Playwright (workflows critiques uniquement)
```

### Conventions frontend

- **Composition API obligatoire** (`<script setup lang="ts">`)
- **Fichiers kebab-case** : `container-detail.vue` (mais le composant s'appelle `ContainerDetail`)
- **Un store Pinia = un domaine** (état + actions + getters)
- **Composables `use*`** pour toute logique réutilisable ou avec état local
- **Services** pour les appels HTTP (jamais d'axios directement dans les views/composants)
- **Types** centralisés dans `src/types/` — importer depuis là, ne pas redéfinir localement

---

## Tests — localisation des fichiers

| Type de test | Backend | Frontend |
|---|---|---|
| Unitaire service | `backend/tests/unit/test_services/test_xxx_service.py` | — |
| Unitaire schéma | `backend/tests/unit/test_schemas/test_xxx.py` | — |
| Unitaire endpoint | `backend/tests/unit/test_api/test_xxx.py` | — |
| Unitaire composant | — | `frontend/tests/unit/components/Xxx.spec.ts` |
| Unitaire composable | — | `frontend/tests/unit/composables/useXxx.spec.ts` |
| Unitaire vue | — | `frontend/tests/unit/views/XxxView.spec.ts` |
| Intégration API | `backend/tests/integration/test_api_xxx.py` | — |
| E2E workflow | — | `frontend/tests/e2e/xxx.spec.ts` |

---

## Makefile — commandes disponibles

Le `Makefile` à la racine est la **source de vérité** pour toutes les commandes de développement.
Consulter `make help` pour la liste complète. Les principales :

```bash
make test-backend          # Tous les tests backend
make test-frontend         # Tous les tests frontend
make lint                  # Lint backend + frontend
make typecheck             # mypy + tsc
make build                 # Build production
make dev                   # Démarrer les services de dev
```
