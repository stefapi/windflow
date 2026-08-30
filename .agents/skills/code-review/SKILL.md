---
name: code-review
description: Revue de code en lecture seule d'un diff Git sur le projet **aetherteam** (système multi-agents IA — backend FastAPI/Python 3.13 + frontend Vue 3/TypeScript) : analyse par catégories, barème de sévérité, rapport structuré. Ne modifie aucun fichier. À utiliser dès que l'utilisateur demande une revue de code, une relecture de PR, un audit de branche, une analyse de diff, un "check avant merge", une vérification du respect des conventions, ou dès qu'il mentionne un SHA/une branche à comparer — même sans employer le mot "revue".
---

# Revue de code — aetherteam

> **Note** : Ce skill est générique. Les standards de référence du projet sont dans `.roo/rules/` — ils font foi en cas de contradiction avec cette skill. Voir en particulier [`30-code-standards.md`](.roo/rules/30-code-standards.md), [`20-architecture-and-api.md`](.roo/rules/20-architecture-and-api.md), [`21-realtime-websocket.md`](.roo/rules/21-realtime-websocket.md), [`40-security.md`](.roo/rules/40-security.md) et [`35-testing-quality-gates.md`](.roo/rules/35-testing-quality-gates.md).

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
- [ ] Accès en lecture au code source (`backend/src/**`, `backend/alembic/versions/**`, `backend/tests/**`, `frontend/src/**`, `frontend/tests/**`, `frontend/e2e/**`)
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
  - `backend/src/**` (Python) — routers FastAPI (`api/v1/`), services, modèles SQLAlchemy, schémas Pydantic, core, db
  - `backend/alembic/versions/**` (migrations Alembic)
  - `backend/tests/**` (tests pytest)
  - `frontend/src/**` (`.ts`, `.vue`) — vues, composants, composables, stores Pinia, `realtime/`, `api/queries/`, styles
  - `frontend/tests/**`, `frontend/e2e/**`
  - config/infra : `Makefile`, `docker-compose*.yml`, `frontend/vite.config.ts`, `frontend/eslint.config.ts`, `frontend/tsconfig*.json`, `backend/pyproject.toml`, `backend/alembic.ini`, CI Gitea Actions le cas échéant (`.gitea/`, actuellement déplacée dans `.gitea_old/`)
- **À survoler** : fichiers de traduction, fixtures de test, snapshots.
- **À ignorer** (mentionner seulement le volume) : `frontend/pnpm-lock.yaml`, `frontend/src/api/generated/**` (client généré — vérifier seulement qu'il a été régénéré, pas le détail), `frontend/dist/`, `frontend/node_modules/`, `.ruff_cache/`, `backend/data/`, fichiers open-source (`README.md`, `LICENSE`, etc. sauf changement significatif).

**Identifier le périmètre des changements** — c'est déterminant pour la suite :

- **Backend uniquement** : diff limité à `backend/**` (routers FastAPI, services, modèles SQLAlchemy, schémas Pydantic, migrations Alembic, tests pytest).
- **Frontend uniquement** : diff limité à `frontend/**` (vues, composants, composables, stores Pinia, `realtime/`, `api/queries/`, styles).
- **Full-stack** : diff touchant à la fois `backend/` et `frontend/` — appliquer alors les deux volets de la checklist et vérifier la cohérence des contrats : schémas Pydantic ↔ types générés `frontend/src/api/generated/` (toute modif du contrat backend doit régénérer le client dans la même PR), endpoints ↔ TanStack Query (`api/queries/`), cohérence des enveloppes WS.

Annoncer le périmètre retenu dans le rapport (section « Périmètre »). Adapter la profondeur d'analyse en fonction : un diff full-stack nécessite de croiser les contrats API (schémas Pydantic ↔ types générés, endpoints ↔ TanStack Query, enveloppes WS).

Si le diff dépasse ~40 fichiers ou ~3000 lignes, annoncer un traitement par lots (priorité : sécurité/contrat API/migrations d'abord, puis backend, puis frontend, puis config) et prévenir l'utilisateur que la revue sera synthétique sur les fichiers à faible risque.

## Étape 2 — Charger le contexte projet

Lire les règles avant d'analyser (elles font foi ; en cas de contradiction avec cette skill, **`.roo/rules/` gagne**) :

```bash
ls .roo/rules/
```

Lire les 15 fichiers de règles pertinents pour le périmètre identifié à l'étape 1 :

- [`00-project-context.md`](.roo/rules/00-project-context.md) — contexte projet, architecture 6 couches, Poetry obligatoire
- [`01-Project-management.md`](.roo/rules/01-Project-management.md) — gestion backlog (epics, stories, bugs, kanban), cycle de vie, DoD
- [`05-tech-stack.md`](.roo/rules/05-tech-stack.md) — stack technique détaillée (backend + frontend + IA + Docker)
- [`06-frontend-vue3.md`](.roo/rules/06-frontend-vue3.md) — conventions Vue 3/PrimeVue 4 unstyled/Tailwind 4
- [`07-poetry-python.md`](.roo/rules/07-poetry-python.md) — Poetry obligatoire (jamais pip/python directs)
- [`10-project-requirements.md`](.roo/rules/10-project-requirements.md) — exigences fonctionnelles et non-fonctionnelles
- [`20-architecture-and-api.md`](.roo/rules/20-architecture-and-api.md) — architecture API-first, routes, services, migrations Alembic (00NN)
- [`21-realtime-websocket.md`](.roo/rules/21-realtime-websocket.md) — source de vérité temps réel (4 couches, ticket éphémère)
- [`30-code-standards.md`](.roo/rules/30-code-standards.md) — standards de code (type safety, clean code, nommage, erreurs)
- [`35-testing-quality-gates.md`](.roo/rules/35-testing-quality-gates.md) — tests, couverture, quality gates
- [`40-security.md`](.roo/rules/40-security.md) — sécurité, auth JWT, RBAC, secrets, scans
- [`45-observability.md`](.roo/rules/45-observability.md) — structlog JSON, métriques, monitoring
- [`50-dev-workflow.md`](.roo/rules/50-dev-workflow.md) — workflow, Makefile, commits, `.env.sample`
- [`55-project-structure.md`](.roo/rules/55-project-structure.md) — structure des répertoires backend + frontend
- [`60-output-format.md`](.roo/rules/60-output-format.md) — format de sortie attendu (plan/act)

Repères principaux (à vérifier contre les fichiers réels, ils peuvent avoir évolué) :

- **Backend** : FastAPI + SQLAlchemy 2.0 async (SQLite dev / PostgreSQL prod) + Pydantic v2 + Poetry (Python 3.13+) + Alembic + structlog + LiteLLM. Structure `backend/src/{api/v1, core, db, models, schemas, services}`.
- **Frontend** : Vue 3.5+ (`<script setup>`, TS strict) + PrimeVue 4 `unstyled: true` + pass-through `primevue-pt.ts` + Tailwind CSS 4 CSS-first (`@theme`) + Pinia 3 (setup stores) + TanStack Query + Vite 7 + pnpm + client généré `@hey-api/openapi-ts`. Structure `frontend/src/{api/generated, api/queries, realtime/, components, composables, features, layouts, router, stores, types, utils, assets/styles}`.
- **Auth** : JWT PyJWT HS256 (access 30min + refresh 7j) + bcrypt direct (`bcrypt.hashpw`/`checkpw`) + RBAC `require_role(*roles)` dans `core/dependencies.py`.
- **Temps réel** : `src/realtime/` 4 couches (transport/protocol/core/session), ticket éphémère `?ticket=` (codes 4001/4003/4009), JWT longue durée en query string interdit pour tout nouveau code.

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
- **Backend** : insister sur C1 (structure FastAPI), C2 (schémas Pydantic), C3 (modèles SQLAlchemy), E (sécurité JWT/RBAC), F1 (migrations Alembic 00NN), F2 (tests pytest).
- **Frontend** : insister sur C7 (conventions Vue 3/PrimeVue/Tailwind), C6 (ESLint 9 + `vue/no-restricted-block`), D (nettoyage), temps réel (`realtime/`).
- **Full-stack** : couvrir les deux volets et vérifier la cohérence des contrats (schémas Pydantic ↔ types générés, endpoints ↔ TanStack Query, enveloppes WS).

## Étape 4 — Vérifier avant d'affirmer (anti faux positifs)

**Cette étape n'est pas optionnelle.** Un rapport qui signale du code vivant comme mort perd toute crédibilité.

Avant de classer quoi que ce soit en « inutilisé », chercher les usages dans tout le dépôt :

```bash
rg -n "<symbole>" backend/src frontend/src
```

Pièges connus sur ce projet — ne **pas** déclarer morts sans preuve :

- Modèles SQLAlchemy : métaprogrammation ORM (`__tablename__`, `mapped_column`, relations `() => Model`) — « jamais appelé » ≠ inutilisé.
- `__init__.py` barrels qui réexportent les modèles/schémas : consommés ailleurs via l'import du package.
- Décorateurs Pydantic (`@field_validator`, `@model_validator`) : invoqués par la validation runtime.
- Fixtures `conftest.py` (`client`, `db_session`, `client_with_db`, `auth_headers`, `event_bus`, `task_queue`, `runner`, `auth_service`, `test_user`, `admin_user`, `seed_universal_archetypes`) : injectées par pytest, jamais importées explicitement.
- Injection de dépendances FastAPI (`Depends`) : fonctions « jamais appelées » mais résolues par le framework.
- Composants Vue référencés par nom PascalCase dans les templates : pas d'import explicite si auto-resolver ou registration globale.
- Stores Pinia `defineStore` : consommés via `useXxxStore()` dans les composants/composables.
- Composables `use*` : utilisés dans `<script setup>` sans import visible si auto-import configuré.
- Types générés `src/api/generated/` : parfois consommés sans import explicite (types globaux).
- Handlers realtime enregistrés dynamiquement via le dispatcher (`on('type', handler)`) : pas d'import statique.
- Code de services LLM avec fallback multi-provider (LiteLLM) : branches « mortes » en test mais vivantes en prod selon le provider disponible.

Si le doute persiste après recherche, ne pas trancher : classer en **Info** avec la mention « à confirmer » et lister la question dans la section dédiée du rapport.

Règle de preuve : chaque finding doit citer `chemin/fichier.ext:ligne` et l'élément concerné. Pas de finding sans localisation.

## Étape 5 — Rédiger le rapport

Utiliser le gabarit [`rapport-template.md`](rapport-template.md).

Barème de sévérité :

| Sévérité | Critère |
|---|---|
| **Critique** | Contournement auth (JWT, ticket WS), secret exposé (clés API LLM, `JWT_SECRET`), perte de données en migration Alembic, régression cassant le contrat API (client généré), JWT longue durée en query string WS. À corriger avant merge, sans discussion. |
| **Majeur** | Endpoint de liste >20 éléments sans pagination (règle API-first), N+1 SQLAlchemy sur chemin chaud, schéma Pydantic sans validation, logique métier dans un router au lieu d'un service, violation des interdits frontend structurants (données API dans Pinia, fetch/axios direct, `<style>` dans SFC, nouvelle socket hors `realtime/`), tâche background publiant directement sur une socket. À corriger avant merge. |
| **Mineur** | Code mort, `print()`/`console.log` oublié, écart de convention (nommage, import), test manquant sur un chemin secondaire. À corriger idéalement dans la PR. |
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

Cette skill s'appuie sur trois fichiers, tous dans `.agents/skills/code-review/` :

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
