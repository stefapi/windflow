# 00 — Contexte du projet

> Fichier lu en premier. Il fixe le cadre ; les règles détaillées suivent. L'ordre de lecture n'est pas un ordre de priorité : voir `02-gouvernance-regles.md` §2.

## 1. Le produit en une phrase

WindFlow est un outil web de déploiement de conteneurs Docker vers des machines cibles multiples (Docker, Kubernetes, VMs, machines physiques), avec UI moderne, CLI/TUI, et intégration IA (LiteLLM) : il construit un logiciel neuf en réutilisant intelligemment le code existant, sans copier-coller aveugle, avec un niveau de qualité élevé (tests, sécurité, observabilité).

## 2. Utilisateurs et rôles

| Acteur | Accès |
| --- | --- |
| `super_admin` | Administration de la plateforme, tout pouvoir |
| `admin` | Gestion complète des ressources de son périmètre |
| `operator` | Déploiements et opérations, sans administration |
| `viewer` | Lecture seule |
| Agents de code (Roo Code, Claude Code, Codex, OpenCode) | Développent le produit selon ce corpus ; jamais d'accès aux données de production |

Matrice RBAC détaillée : `40-security.md` §3, `docs/general_specs/08-rbac-permissions.md`.

## 3. Architecture d'ensemble

Monolithe modulaire : `backend/` (API FastAPI async + services métier + WebSocket temps réel), `frontend/` (SPA Vue 3), `cli/` (client Python argparse), `infrastructure/` (Docker, Nginx, Prometheus, Grafana). API-first : toute fonctionnalité est exposée via l'API REST avant d'être consommée par l'UI ou la CLI. Communication asynchrone par le bus canonique `Bus` (`backend/app/core/events.py`) ; temps réel par WebSocket (`21-realtime-websocket.md`).

Détails : `20-architecture-and-api.md`, `21-realtime-websocket.md`, `25-ai-llm-mcp.md`. Référence fonctionnelle : `docs/general_specs/` (index `00-index.md`).

## 4. Stack résumée

Python ≥ 3.11, FastAPI async, SQLAlchemy 2.0 async + Alembic, SQLite par défaut (configurable PostgreSQL), Redis (cache + rate limiting) ; Vue 3 Composition API, TypeScript strict, Element Plus, UnoCSS, Pinia, Axios, Vite ; CLI argparse ; LiteLLM multi-provider ; Docker Compose.

Source de vérité détaillée : `05-tech-stack.md`. Frontend : `06-frontend-vue3.md`.

## 5. Gestionnaires de dépendances

- Python : **uv** uniquement (`uv add`, `uv remove`, `uv sync`, `uv run`) — migration UV terminée (EPIC-016).
- Frontend : **pnpm** uniquement (`pnpm add`, `pnpm remove`, `pnpm install`, `pnpm dlx`).
- **Interdit** : `pip install`, `python -m pip`, `uv pip install`, `poetry`, `pipenv`, `conda`, `npm install`, `npm i`, `yarn`, `npx` (utiliser `pnpm dlx`), toute installation globale, toute édition manuelle de `uv.lock` ou de `pnpm-lock.yaml`.

Détails : `07-python-uv.md`, `50-dev-workflow.md` §3.

## 6. Priorité des règles

Une règle du projet prime toujours sur une habitude générale d'un modèle, d'un framework ou d'un tutoriel. Entre deux règles du projet : ordre de `02-gouvernance-regles.md` §2. En cas de doute : `02-gouvernance-regles.md` §10.

## 7. Priorités produit (ordre)

1. **API-first** : toute fonctionnalité est disponible via API REST avant UI/CLI.
2. **Sécurité by design** (OWASP, least privilege, secrets, RBAC).
3. **Observabilité native** (logs structurés, métriques, corrélation).
4. **Réutilisation intelligente** du code legacy (pas de copier-coller aveugle).
5. **Maintenabilité** : modular monolith d'abord ; hexagonale si la complexité augmente.

## 8. Premières commandes

| Commande | Effet |
| --- | --- |
| `make help` | Liste des cibles disponibles |
| `make setup` | Dépendances (uv, pnpm) et environnement |
| `make dev` | Démarrer backend + frontend |
| `make test` | Lancer tous les tests |
| `make ci-fast` | Retour intermédiaire local (lint, types, corpus, backlog, tests sans couverture) |
| `make check` | Portes locales complètes avant acceptation |
| `make backlog` / `make backlog-check` | Régénérer / contrôler le kanban depuis les contrats |

Toute commande récurrente passe par le `Makefile` (`50-dev-workflow.md` §1).

## 9. Documents de référence

- Spécification fonctionnelle (le « quoi ») : `docs/general_specs/` (index `00-index.md`), spécifications techniques : `docs/technical_specs/`. Ne lire que les sections citées par l'élément de backlog en cours.
- Feuille de route : `docs/Roadmap.md` (jamais recopiée ailleurs).
- Backlog : `.backlog/` (`01-Project-management.md`).
- Noms de code des termes métier : `03-glossary.md`.
- [Protocole commun d'exécution](../../docs/dev/protocole-execution.md) et [matrice de validation](../../docs/dev/controles-validation.md) : `docs/dev/`.
