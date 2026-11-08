# 05 — Stack technique (source de vérité)

> Source de vérité des versions et des bibliothèques. Toute bibliothèque absente de ce fichier suit la procédure du §5.

## 1. Environnements d'exécution

| Composant | Version | Épinglage |
| --- | --- | --- |
| Python | ≥ 3.11 | `python:3.11-slim` en Docker, `python-version: '3.11'` en CI |
| Node.js / pnpm | pnpm via `packageManager` | `frontend/package.json` |
| SQLite | par défaut (DB de dev) | `aiosqlite ^0.21.0` |
| PostgreSQL | optionnel | profil Docker `database` |
| Redis | cache + rate limiting | image officielle |

## 2. Backend

| Rôle | Bibliothèques |
| --- | --- |
| API | FastAPI async (OpenAPI auto), Uvicorn |
| Validation, configuration | Pydantic v2, pydantic-settings |
| Base de données | SQLAlchemy 2.0 async, aiosqlite, Alembic `^1.13.0` |
| Conteneurs | docker SDK `^7.0.0` |
| VM / SSH | asyncssh `^2.14.0`, libvirt-python `^11.8.0` (sdist sans wheel — install ciblée `make install-vm`, import défensif dans le code, STORY-255) |
| HTTP sortant | aiohttp `^3.11.0` |
| IA | litellm `^1.79.0` (multi-provider, cache LLM — `25`) |
| Auth | python-jose `^3.3.0` (JWT), passlib `[argon2]` / argon2-cffi `^23.0.0` (Argon2id), bcrypt `^4.0.0` (lecture seule des hashes legacy, retrait post-migration STORY-250), email-validator |
| Rate limiting | fastapi-limiter `^0.1.6` |
| Métriques | prometheus-client `^0.21` (`45` §4) |
| Docs API | scalar-fastapi `^1.0.3` |
| Scheduler | python-dateutil `^2.9.0` (croniter vendored) |
| UI terminal/CLI | rich `^14.2.0` ; CLI : **argparse** (pas click/typer) |
| YAML | pyyaml `^6.0.0` (`yaml.safe_load` uniquement) |
| Secrets | cryptography (Fernet AES-256, clé dérivée PBKDF2 — SecretManager, STORY-103) |

## 3. Frontend

| Rôle | Bibliothèques |
| --- | --- |
| Framework | Vue 3 (Composition API obligatoire), Vue Router |
| Langage, construction | TypeScript strict, Vite `^7.1.9` |
| Composants | Element Plus (+ `@element-plus/icons-vue`) |
| CSS | UnoCSS |
| État | Pinia |
| HTTP | Axios (via `frontend/src/services/` uniquement) |
| Formulaires dynamiques | @jsonforms/core `^3.6.0`, @jsonforms/vue, @jsonforms/vue-vanilla |
| Flux/édition de graphe | @vue-flow/core `^1.47.0` (+ background, controls, minimap) |
| Terminal | @xterm/xterm `^6.0.0` (+ addon-fit, addon-web-links) |
| Graphiques | echarts `^6.0.0` / vue-echarts `^8.0.1` |
| Validation | @vuelidate/core `^2.0.3` |
| Dates | dayjs |
| Auto-imports | unplugin-vue-router, unplugin-auto-import, unplugin-vue-components |

## 4. Outillage qualité

| Outil | Rôle | Configuration |
| --- | --- | --- |
| black | Formatage backend | — |
| isort | Tri des imports | `profile=black` |
| flake8 | Lint backend | `.flake8` |
| mypy | Types backend | `ignore_missing_imports=false`, `disallow_untyped_defs=false`, overrides tiers |
| bandit | Sécurité backend | niveau `low` minimum |
| pylint | Qualité backend | `.pylintrc` |
| ESLint v9 | Lint frontend | flat config |
| Prettier `^3.6.2` | Formatage frontend | — |
| Stylelint `^16.25.0` | Lint CSS | — |

Tests : voir `35-testing-quality-gates.md` §2.

## 5. Ajouter ou mettre à jour une dépendance

1. Vérifier qu'aucune bibliothèque déjà listée ne couvre le besoin (ex. VueUse avant un composable maison, `core/resilience.py` avant un mécanisme de retry).
2. Vérifier la licence et la maintenance : version publiée récemment, projet actif.
3. Ajouter par `uv add <paquet>` ou `pnpm add <paquet>`, dans une story ou un commit `chore(deps)` (`50` §5), avec justification claire.
4. Mettre à jour ce fichier dans le même changement.

**Interdit** : `pip install`, `npm install`, `yarn`, `poetry`, édition manuelle de `uv.lock` ou `pnpm-lock.yaml`, dépendance non justifiée (`02` §8).

Gestionnaires et commandes : `07-python-uv.md`, `50-dev-workflow.md` §3.
