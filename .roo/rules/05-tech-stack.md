# Stack & contraintes techniques

Backend :
- Python >=3.11 (`python:3.11-slim` en Docker, `python-version: '3.11'` en CI)
- FastAPI async (OpenAPI auto)
- SQLAlchemy 2.0 async + Alembic
- SQLite (aiosqlite `^0.21.0`) — DB par défaut, configurable vers PostgreSQL
- PostgreSQL — optionnel via profil Docker `database`
- Redis (cache + rate limiting)
- CLI : argparse (pas click/typer)

Dépendances backend notables :
- docker SDK `^7.0.0`
- asyncssh `^2.14.0`
- libvirt-python `^11.8.0`
- aiohttp `^3.11.0`
- pyyaml `^6.0.0`
- rich `^14.2.0`
- scalar-fastapi `^1.0.3`
- fastapi-limiter `^0.1.6`
- email-validator
- python-jose `^3.3.0` (JWT) + passlib `[argon2]` / argon2-cffi `^23.0.0` (hash Argon2id, STORY-130.1)
- bcrypt `^4.0.0` — transition lecture seule des hashes legacy, retrait post-migration (cf. STORY-250)
- alembic `^1.13.0` (migrations, STORY-120)
- prometheus-client `^0.21` (observabilité réelle, STORY-172)
- python-dateutil `^2.9.0` (croniter vendored / scheduler, STORY-160.1)
- litellm `^1.79.0` (IA multi-provider — dépendance réelle, consommée par le cache LLM STORY-168)

Frontend :
- Vue 3 (Composition API obligatoire)
- TypeScript strict
- Element Plus, UnoCSS, Pinia, Axios
- Vite `^7.1.9`

Dépendances frontend notables :
- echarts `^6.0.0` / vue-echarts `^8.0.1`
- @xterm/xterm `^6.0.0`
- @jsonforms/core `^3.6.0`
- @vue-flow/core `^1.47.0`
- @vuelidate/core `^2.0.3`
- dayjs
- unplugin-vue-router, unplugin-auto-import, unplugin-vue-components

IA :
- LiteLLM multi-provider (fallback, rate limiting si nécessaire)

Dev tooling :
- Poetry uniquement côté Python (pas de requirements.txt édité à la main)
- pnpm côté frontend
- CI : lint + typecheck + tests + sécurité (bandit/semgrep, npm audit)
- Makefile : sur la racine pour toutes les actions de dev backend, frontend, déploiement, docker, tests, etc.

Outils format/lint backend :
- black (formatage)
- isort (imports, profile=black)
- flake8 (lint)
- mypy (vérification de types)
- bandit (sécurité)
- pylint (qualité)

Outils format/lint frontend :
- ESLint v9 flat config
- Prettier `^3.6.2`
- Stylelint `^16.25.0`

Règles :
- Respecter les conventions du projet cible si conflit avec legacy.
- Ne pas introduire de dépendance sans justification claire.
