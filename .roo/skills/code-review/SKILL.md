---
name: code-review
description: Revue de code en lecture seule d'un diff Git sur le projet **WindFlow** (outil web de déploiement de conteneurs Docker — backend FastAPI/Python 3.11 + frontend Vue 3/TypeScript) : analyse par catégories, barème de sévérité, rapport structuré. Ne modifie aucun fichier. À utiliser dès que l'utilisateur demande une revue de code, une relecture de PR, un audit de branche, une analyse de diff, un "check avant merge", une vérification du respect des conventions, ou dès qu'il mentionne un SHA/une branche à comparer — même sans employer le mot "revue".
---

# Revue de code — WindFlow

> **Note** : Ce skill est générique. Les standards de référence du projet sont dans `.roo/rules/` — ils font foi en cas de contradiction avec cette skill. Voir en particulier [`30-code-standards.md`](.roo/rules/30-code-standards.md), [`20-architecture-and-api.md`](.roo/rules/20-architecture-and-api.md), [`40-security.md`](.roo/rules/40-security.md) et [`35-testing-quality-gates.md`](.roo/rules/35-testing-quality-gates.md).

Analyse d'un diff Git et production d'un rapport de revue. **Aucune modification de code.**

## Usage

Utilise cette skill quand :
- L'utilisateur demande une revue de code, une relecture de PR, un "check avant merge"
- L'utilisateur demande un audit de branche, une analyse de diff, une comparaison de SHA/branche
- L'utilisateur veut vérifier le respect des conventions du projet sur un ensemble de changements
- L'utilisateur mentionne un SHA ou une branche à comparer — même sans employer le mot "revue"

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le dépôt est dans un état propre (pas de modifications non commitées inattendues, sauf si l'utilisateur veut les inclure)
- [ ] La base de comparaison est identifiable (branche `main`, SHA, tag fourni)
- [ ] Accès en lecture au code source (`backend/app/**`, `backend/alembic/versions/**`, `backend/tests/**`, `frontend/src/**`, `frontend/tests/**`, `cli/**`)
- [ ] La story/PR concernée est idéalement en `REVIEW` (mais la revue peut porter sur tout diff)

## Règle absolue : lecture seule

Pendant toute l'exécution de cette skill :

- Ne jamais écrire, modifier, créer ou supprimer un fichier du dépôt.
- Ne jamais exécuter `git add`, `git commit`, `git checkout`, `git stash`, `git restore`, `git rebase`, `git reset`, `git push`, `poetry install`, `pnpm install`, ni aucune commande qui modifie l'état du dépôt ou du working tree.
- Seules les commandes de lecture sont autorisées : `git diff`, `git log`, `git show`, `git merge-base`, `git ls-files`, `grep`/`rg`, lecture de fichiers.
- Le livrable est un **rapport**, pas un patch. Si des corrections sont souhaitées, les proposer sous forme de recommandations et attendre une demande explicite de l'utilisateur dans un second temps.

## Étape 0 — Déterminer la base de comparaison

1. Si l'utilisateur fournit un SHA, un tag ou une branche, l'utiliser tel quel : `<BASE>..HEAD`.
2. Sinon, calculer la base :
   ```bash
   git merge-base origin/main HEAD
   ```
3. Vérifier que la base existe (`git cat-file -e <BASE>^{commit}`). Si elle est introuvable ou si le résultat est ambigu (base non ancêtre de HEAD, plusieurs candidats), **demander à l'utilisateur** avant de continuer.
4. Annoncer explicitement la plage retenue dans le rapport (`<BASE>..HEAD`).

Note : `git diff A..HEAD` compare les deux commits. Si l'utilisateur veut inclure le travail non commité, utiliser aussi `git diff` (working tree) et `git diff --cached`, et le signaler dans le rapport.

## Étape 1 — Cadrage

```bash
git log <BASE>..HEAD --oneline
git diff <BASE>..HEAD --stat
git diff <BASE>..HEAD --name-status
```

Classer les fichiers en trois lots :

- **À analyser en profondeur** :
  - `backend/app/**` (Python) — routers FastAPI (`api/v1/`), services, modèles SQLAlchemy, schémas Pydantic, auth, core, websocket, middleware, tasks
  - `backend/alembic/versions/**` (migrations Alembic)
  - `backend/tests/**` (tests pytest `unit/` + `integration/`)
  - `frontend/src/**` (`.ts`, `.vue`) — vues, composants, composables, stores Pinia, services, types, utils, styles UnoCSS
  - `frontend/tests/**` (`unit/`, `integration/`, `e2e/` Playwright)
  - `cli/**` (CLI Python argparse)
  - config/infra : `Makefile`, `infrastructure/docker/**`, `infrastructure/nginx/**`, `frontend/vite.config.ts`, `frontend/eslint.config.ts`, `frontend/tsconfig*.json`, `pyproject.toml`, `backend/alembic.ini`, CI Gitea Actions (`.gitea/`)
- **À survoler** : fichiers de traduction, fixtures de test (`backend/tests/fixtures/**`), snapshots/golden files.
- **À ignorer** (mentionner seulement le volume) : `frontend/pnpm-lock.yaml`, `poetry.lock`, client API généré (vérifier seulement qu'il a été régénéré via `make generate-api`, pas le détail), `frontend/dist/`, `frontend/node_modules/`, `.ruff_cache/`, `data/`, fichiers open-source (`README.md`, `LICENSE`, etc. sauf changement significatif).

**Identifier le périmètre des changements** — c'est déterminant pour la suite :

- **Backend uniquement** : diff limité à `backend/**` (routers FastAPI, services, modèles SQLAlchemy, schémas Pydantic, migrations Alembic, tests pytest).
- **Frontend uniquement** : diff limité à `frontend/**` (vues, composants, composables, stores Pinia, services, types, styles UnoCSS).
- **Full-stack** : diff touchant à la fois `backend/` et `frontend/` — appliquer alors les deux volets de la checklist et vérifier la cohérence des contrats : schémas Pydantic ↔ types TypeScript (le client API doit être régénéré via `make generate-api` dans la même PR si le contrat change), endpoints REST ↔ services frontend (`frontend/src/services/`), cohérence des canaux WebSocket.

Annoncer le périmètre retenu dans le rapport (section « Périmètre »). Adapter la profondeur d'analyse en fonction : un diff full-stack nécessite de croiser les contrats API (schémas Pydantic ↔ types générés, endpoints ↔ services frontend, canaux WebSocket).

Si le diff dépasse ~40 fichiers ou ~3000 lignes, annoncer un traitement par lots (priorité : sécurité/contrat API/migrations d'abord, puis backend, puis frontend, puis config) et prévenir l'utilisateur que la revue sera synthétique sur les fichiers à faible risque.

## Étape 2 — Charger le contexte projet

Lire les règles avant d'analyser (elles font foi ; en cas de contradiction avec cette skill, **`.roo/rules/` gagne**) :

```bash
ls .roo/rules/
```

Lire les fichiers de règles pertinents pour le périmètre identifié à l'étape 1 :

- [`00-project-context.md`](.roo/rules/00-project-context.md) — contexte projet, priorités (API-first, sécurité, observabilité)
- [`01-Project-management.md`](.roo/rules/01-Project-management.md) — gestion backlog (epics, stories, bugs, kanban), cycle de vie, DoD
- [`05-tech-stack.md`](.roo/rules/05-tech-stack.md) — stack technique détaillée (backend + frontend + IA + tooling)
- [`20-architecture-and-api.md`](.roo/rules/20-architecture-and-api.md) — architecture API-first, modular monolith, bus d'événements `Bus`, WebSocket, middlewares
- [`30-code-standards.md`](.roo/rules/30-code-standards.md) — standards de code (type safety, clean code, nommage, erreurs)
- [`35-testing-quality-gates.md`](.roo/rules/35-testing-quality-gates.md) — tests, couverture, quality gates
- [`40-security.md`](.roo/rules/40-security.md) — sécurité, auth JWT, RBAC, secrets, scans
- [`45-observability.md`](.roo/rules/45-observability.md) — logging standard format JSON, corrélation, métriques Prometheus
- [`50-dev-workflow.md`](.roo/rules/50-dev-workflow.md) — workflow, Makefile, commits
- [`55-project-structure.md`](.roo/rules/55-project-structure.md) — structure des répertoires backend + frontend
- [`60-output-format.md`](.roo/rules/60-output-format.md) — format de sortie attendu (plan/act)

Repères principaux (à vérifier contre les fichiers réels, ils peuvent avoir évolué) :

- **Backend** : Python 3.11 + FastAPI async + SQLAlchemy 2.0 async + Alembic + SQLite (aiosqlite) par défaut / PostgreSQL optionnel + Redis (cache + rate limiting) + Pydantic v2 + Poetry. Outils : black, isort, flake8, mypy, bandit, pylint. Structure `backend/app/{api/v1, auth, core, models, schemas, services, tasks, websocket, middleware, helper, enums}`.
- **Frontend** : Vue 3 Composition API (`<script setup lang="ts">`, TS strict) + Element Plus + UnoCSS + Pinia + Axios + Vite 7 + pnpm. Tests : Vitest + `@vue/test-utils` + Playwright (chromium/firefox/webkit). Outils : ESLint 9 flat config, Prettier, Stylelint.
- **CLI** : Python + argparse (pas click/typer).
- **IA** : LiteLLM multi-provider (fallback).
- **Auth** : JWT python-jose + refresh tokens opaques révocables `wf_rt_` (rotation) + clés API `wf_ak_` via `X-API-Key` + hash Argon2id (passlib/argon2-cffi, double lecture bcrypt legacy) + RBAC 4 rôles (`viewer < operator < admin < super_admin`) via `require_role(...)` sur REST et `ensure_role_ws` sur WebSocket (`backend/app/auth/rbac.py`).
- **Temps réel** : module WebSocket dédié `backend/app/websocket/` (terminal, logs/stats conteneurs, logs déploiements, event bridge, plugins) — pas de SSE.
- **Événements** : bus canonique `Bus` (`backend/app/core/events.py`) — `InMemoryEventBus` par défaut, `RedisPubSubEventBus` optionnel sur le canal `windflow:events`. Redis Streams hors périmètre.
- **Observabilité** : `logging` standard format JSON configurable (PAS structlog), middleware correlation ID (`X-Correlation-ID`), métriques Prometheus préfixe `windflow_` exposées sur `GET /api/v1/metrics`.
- **Docs API** : Scalar sur `/docs`, Swagger UI sur `/swagger`, ReDoc sur `/redoc`.

## Étape 3 — Analyse fichier par fichier

Pour chaque fichier retenu :

```bash
git diff <BASE>..HEAD -- <fichier>
```

Le diff seul ne suffit pas : lire le fichier complet (ou les fonctions concernées) dès que le contexte manque — un `-` de trois lignes peut supprimer une garde de sécurité invisible dans le hunk.

Parcourir les catégories **A** à **F** décrites dans [`checklist.md`](checklist.md). Lire ce fichier au début de l'étape 3.

| Cat. | Objet |
|---|---|
| A | Code mort (variables, imports, blocs commentés, props, schémas, fixtures) |
| B | Complexité inutile, duplication, abstractions superflues |
| C | Non-respect des règles `.roo/rules/` (structure, TS/Python, nommage, schémas, imports, lint, frontend) |
| D | Nettoyage (debug, `print`/`console.log`, TODO/FIXME, commentaires obsolètes) |
| E | Sécurité (auth JWT, RBAC, secrets, exposition, WebSocket, injection) |
| F | Fiabilité (migrations Alembic, tests, performances/N+1, erreurs/observabilité, cohérence contrats) |

Adapter le focus selon le périmètre :
- **Backend** : insister sur C1 (structure FastAPI `backend/app/`), C2 (schémas Pydantic), C3 (modèles SQLAlchemy), E (sécurité JWT/RBAC), F1 (migrations Alembic), F2 (tests pytest `unit/` + `integration/`).
- **Frontend** : insister sur C7 (conventions Vue 3/Element Plus/UnoCSS), C6 (ESLint 9 + Prettier + Stylelint), D (nettoyage), services (`frontend/src/services/`).
- **Full-stack** : couvrir les deux volets et vérifier la cohérence des contrats (schémas Pydantic ↔ types générés, endpoints ↔ services frontend, canaux WebSocket).

## Étape 4 — Vérifier avant d'affirmer (anti faux positifs)

**Cette étape n'est pas optionnelle.** Un rapport qui signale du code vivant comme mort perd toute crédibilité.

Avant de classer quoi que ce soit en « inutilisé », chercher les usages dans tout le dépôt :

```bash
rg -n "<symbole>" backend/app frontend/src cli
```

Pièges connus sur ce projet — ne **pas** déclarer morts sans preuve :

- Modèles SQLAlchemy : métaprogrammation ORM (`__tablename__`, `mapped_column`, relations `lazy`, hybrid properties) — « jamais appelé » ≠ inutilisé.
- Barrels `__init__.py` qui réexportent les modèles/schémas : consommés ailleurs via l'import du package.
- Décorateurs Pydantic (`@field_validator`, `@model_validator`) : invoqués par la validation runtime.
- Fixtures `conftest.py` (`client`, `auth_headers`, `viewer_headers`, `db_session`, etc.) : injectées par pytest, jamais importées explicitement.
- Injection de dépendances FastAPI (`Depends`, `get_current_user`, `require_role(...)`) : fonctions « jamais appelées » mais résolues par le framework.
- **Auto-imports unplugin** (`unplugin-auto-import`) : composables et APIs Vue (`ref`, `computed`, `watch`, `useRouter`…) utilisés dans `<script setup>` sans import explicite.
- **Résolveurs de composants** (`unplugin-vue-components`) : composants Vue et Element Plus résolus automatiquement dans les templates — pas d'import explicite ni de registration globale nécessaire.
- Composants Element Plus référencés par nom PascalCase/kebab-case dans les templates : auto-résolus.
- Stores Pinia `defineStore` : consommés via `useXxxStore()` dans les composants/composables.
- Handlers WebSocket / plugins enregistrés dynamiquement : pas d'import statique.
- Code généré : client API généré (`make generate-api`), migrations Alembic autogénérées, scripts vendored (ex: croniter) — ne pas revue ligne à ligne, vérifier seulement la régénération.
- Code de services IA avec fallback multi-provider (LiteLLM) : branches « mortes » en test mais vivantes en prod selon le provider disponible.
- Décorateurs de métriques/enregistrements `prometheus-client` (Histogram/Counter/Gauge) : effets de bord à l'import.

Si le doute persiste après recherche, ne pas trancher : classer en **Info** avec la mention « à confirmer » et lister la question dans la section dédiée du rapport.

Règle de preuve : chaque finding doit citer `chemin/fichier.ext:ligne` et l'élément concerné. Pas de finding sans localisation.

## Étape 5 — Rédiger le rapport

Utiliser le gabarit [`rapport-template.md`](rapport-template.md).

Barème de sévérité :

| Sévérité | Critère |
|---|---|
| **Critique** | Contournement auth (JWT, `ensure_role_ws`), secret exposé (clés API, `JWT_SECRET`, credentials SSH), perte de données en migration Alembic, régression cassant le contrat API (client généré), injection SQL/commande non paramétrée. À corriger avant merge, sans discussion. |
| **Majeur** | Endpoint de liste >20 éléments sans pagination (règle API-first), N+1 SQLAlchemy sur chemin chaud, schéma Pydantic sans validation, logique métier dans un router au lieu d'un service, endpoint modifiant des données sans les tests sécurité 401/403/422 obligatoires, exception Python brute levée dans un endpoint (au lieu de `WindFlowException`), violation des interdits frontend structurants (données API hors stores Pinia, axios direct hors `services/`, nouvelle socket hors du module WebSocket backend), données sensibles dans les logs ou les métriques. À corriger avant merge. |
| **Mineur** | Code mort, `print()`/`console.log` oublié, écart de convention (nommage, import), test manquant sur un chemin secondaire, label de métrique non normalisé (préfixe `windflow_`, chemins UUID → `{id}`). À corriger idéalement dans la PR. |
| **Info** | Observation, suggestion d'amélioration, point à confirmer avec l'auteur. Aucune action requise. |

Contraintes de rédaction :

- Trier les findings par sévérité décroissante, puis par fichier.
- Un finding = un problème = une recommandation actionnable. Pas de conseil générique du type « pensez à tester ».
- Ne pas gonfler le rapport : s'il n'y a rien à signaler dans une catégorie, écrire « RAS ».
- Ne jamais inventer de ligne ni de contenu de fichier. Si la ligne est approximative, écrire `~123`.
- Signaler aussi ce qui est bien fait quand c'est notable (section « Points positifs ») — cela aide l'auteur à savoir quoi garder.
- Terminer par les questions ouvertes à l'utilisateur.

Le rapport est rendu dans la conversation. Ne l'écrire dans un fichier que si l'utilisateur le demande explicitement (dans ce cas seulement, la règle de lecture seule est levée pour ce fichier de rapport).

## Fichiers concernés

Cette skill s'appuie sur trois fichiers, tous dans `.roo/skills/code-review/` :

- [`SKILL.md`](SKILL.md) — ce fichier : procédure de revue (étapes 0 à 5).
- [`checklist.md`](checklist.md) — checklist détaillée des catégories A à F. À lire au début de l'étape 3.
- [`rapport-template.md`](rapport-template.md) — gabarit de sortie. À lire au début de l'étape 5.

## Checklist de fin

Avant de rendre le rapport, vérifier :

- [ ] La base de comparaison est annoncée dans le rapport
- [ ] Le périmètre (backend / frontend / full-stack) est identifié
- [ ] Chaque finding cite un `chemin/fichier.ext:ligne` (pas de finding sans localisation)
- [ ] Aucun symbole n'a été déclaré « mort » sans recherche préalable dans le dépôt
- [ ] Les catégories A à F sont toutes présentes (RAS si vide)
- [ ] Les findings sont triés par sévérité décroissante
- [ ] Les points positifs et les questions pour l'utilisateur sont présents
- [ ] Le verdict (Bloquant / Corrections demandées / Mergeable) est justifié
- [ ] Aucun fichier du dépôt n'a été modifié, aucun commit créé
