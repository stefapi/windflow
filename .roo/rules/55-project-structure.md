# 55 — Structure du dépôt

## 1. Racine

```
windflow/
├── .agents/               skills du pipeline backlog (création, analyse, traitement, revue)
├── .backlog/              contrats : epics, stories, bugs, registre, kanban (généré), gabarits
├── .gitea/                CI (workflows Gitea Actions)
├── .husky/                hooks Git (commit-msg)
├── .roo/                  règles (.roo/rules/, .roo/rules-<mode>/), mcp.json
├── backend/               API FastAPI + services métier
├── frontend/              SPA Vue 3
├── cli/                   CLI client Python (argparse)
├── infrastructure/        Docker, Nginx, Prometheus, Grafana
├── scripts/               garde-fous (backlog.py, check_harness.py) et utilitaires
├── dev/                   scripts de développement
├── stacks_definitions/    définitions YAML de stacks
├── docs/                  spécifications (general_specs, technical_specs), docs dev
├── Makefile               source de vérité des commandes
├── pyproject.toml         config uv (PEP 621) + dépendances Python + uv.lock
└── .env.example  .env.prod.example  .rooignore  .gitignore  .editorconfig
```

Aucun autre dossier de premier niveau sans mise à jour de ce fichier.

## 2. Backend (`backend/`)

```
backend/
├── app/
│   ├── main.py               # Point d'entrée FastAPI, montage des routers
│   ├── config.py             # Settings pydantic-settings (seul lieu lisant l'environnement)
│   ├── database.py           # Session async SQLAlchemy
│   ├── api/v1/               # Endpoints REST (un fichier par domaine)
│   ├── auth/                 # AuthN/AuthZ (jwt.py, dependencies.py, rbac.py)
│   ├── core/                 # Transversal, sans logique métier (exceptions, abstractions,
│   │                         # events.py — bus Bus, cache, rate_limit, resilience, metrics)
│   ├── models/               # Modèles SQLAlchemy (un fichier par entité)
│   ├── schemas/              # Schémas Pydantic (*Request/*Response/*Update)
│   ├── services/             # Logique métier (une classe, injection de dépendances)
│   ├── tasks/                # Tâches async
│   ├── websocket/            # Handlers temps réel (21)
│   ├── middleware/           # Middlewares FastAPI (ordre critique, voir middleware/README.md)
│   ├── helper/               # Utilitaires purs
│   └── enums/                # Énumérations partagées
├── alembic/versions/         # Migrations (jamais de DDL manuel)
└── tests/                    # conftest.py, unit/, integration/
```

Conventions : un router = un domaine ; validation Pydantic systématique ; exceptions de `core/exceptions.py` uniquement ; migrations Alembic.

## 3. Frontend (`frontend/`)

```
frontend/
├── src/
│   ├── main.ts  App.vue
│   ├── views/                # Pages (une vue = une route)
│   ├── components/           # ui/ (génériques) + [domaine]/ (spécifiques)
│   ├── composables/          # use*.ts (Composition API)
│   ├── stores/               # Pinia (un store = un domaine)
│   ├── services/             # Appels HTTP Axios (seul point d'accès à l'API)
│   ├── types/                # Types TypeScript partagés (importer depuis là)
│   ├── router/  layouts/  utils/  assets/  styles/
└── tests/                    # unit/ (views, components, composables), integration/, e2e/
```

Conventions : `<script setup lang="ts">` obligatoire ; fichiers kebab-case ; composables `use*` pour la logique réutilisable ; jamais d'axios hors `services/` (`06`).

## 4. Localisation des tests

| Type | Backend | Frontend |
| --- | --- | --- |
| Unitaire service | `backend/tests/unit/test_services/test_xxx_service.py` | — |
| Unitaire schéma/endpoint | `backend/tests/unit/test_schemas/`, `test_api/` | — |
| Unitaire composant/composable/vue | — | `frontend/tests/unit/{components,composables,views}/Xxx.spec.ts` |
| Intégration API | `backend/tests/integration/test_api_xxx.py` | `frontend/tests/integration/` |
| E2E | — | `frontend/tests/e2e/xxx.spec.ts` |

## 5. Dossiers générés ou techniques

| Chemin | Règle |
| --- | --- |
| Client API généré | Généré par `make generate-api`, commité, jamais édité à la main |
| `.backlog/kanban.md` | Généré par `make backlog` ; édition manuelle interdite |
| `.venv/`, `venv/`, `node_modules/`, `dist/`, caches, `htmlcov/`, `coverage.xml` | Jamais commités ; exclus par `.gitignore` et `.rooignore` |
| `data/`, logs, dumps | Jamais commités ; jamais lus par un agent (`.rooignore`) |
| `backend/alembic/versions/` | Modifiés seulement selon `20` §6 |

## 6. Documentation

```
docs/
├── general_specs/    # spécification fonctionnelle canonique (00-index.md, 01…19)
├── technical_specs/  # spécifications techniques (WEBSOCKET-REAL-TIME, DESIGN-SYSTEM, …)
├── dev/              # protocole d'exécution, matrice de validation
├── Roadmap.md
└── rapports et plans de remédiation
```
