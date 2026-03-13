# Stack & contraintes techniques (WindFlow)

Backend :
- Python 3.12+
- FastAPI async (OpenAPI auto)
- SQLAlchemy 2.0 async + Alembic
- PostgreSQL
- Redis (cache + Streams pour event-driven)
- Celery (queue de tâches)

Frontend :
- Vue 3 (Composition API obligatoire)
- TypeScript strict
- Element Plus, UnoCSS, Pinia, Axios
- Vite

IA :
- LiteLLM multi-provider (fallback, rate limiting si nécessaire)

Dev tooling :
- Poetry uniquement côté Python (pas de requirements.txt édité à la main)
- pnpm côté frontend
- CI : lint + typecheck + tests + sécurité (bandit/semgrep, npm audit)
- Makefile: sur la racine pour toutes les actions de dev backend, frontend, deploiement, docker, tests, etc...

Règles :
- Respecter les conventions du projet cible si conflit avec legacy.
- Ne pas introduire de dépendance sans justification claire.
