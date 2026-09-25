# Checklist de revue — aetherteam

Sommaire :
- [A. Code mort](#a-code-mort)
- [B. Complexité et code inutile](#b-complexité-et-code-inutile)
- [C. Respect des règles de codage](#c-respect-des-règles-de-codage)
- [D. Nettoyage](#d-nettoyage)
- [E. Sécurité](#e-sécurité)
- [F. Fiabilité : migrations, tests, performances, erreurs, contrats](#f-fiabilité--migrations-tests-performances-erreurs-contrats)

Rappel : toute affirmation d'inutilisation doit être vérifiée par recherche dans le dépôt (étape 4 de la skill). Adapter le focus selon le périmètre (backend / frontend / full-stack) identifié à l'étape 1.

---

## A. Code mort

- Variables, constantes, fonctions, méthodes privées déclarées et jamais lues.
- Imports inutilisés (le diff en introduit souvent lors d'un refactor partiel).
- Blocs de code commentés laissés en place.
- Paramètres de fonction ou de méthode jamais utilisés.
- Props de composant/composable déclarées dans l'interface mais jamais passées, ou passées mais jamais consommées.
- `ref` / `computed` / `shallowRef` dont la valeur n'est jamais lue.
- Stores Pinia (`defineStore`) non utilisés dans aucun composant/composable.
- Schémas Pydantic (`*Request` / `*Response` / `*Update`) non consommés par un router ou un service.
- Fixtures `conftest.py` mortes (déclarées mais jamais injectées par un test).
- Endpoints ajoutés mais jamais appelés côté front ni documentés.
- Colonnes de modèle SQLAlchemy ajoutées mais jamais écrites ni lues.
- Fichiers ajoutés puis rendus orphelins par un renommage.

Commandes utiles :
```bash
rg -n "\bnom_du_symbole\b" backend/src frontend/src
rg -n "from ['\"].*<module>" backend/src
```

---

## B. Complexité et code inutile

- Fonction ou méthode dépassant ~30 lignes, ou avec plus de ~3 niveaux d'imbrication.
- Profondeur de nesting excessive (> 3 niveaux) — préférer early return ou extraction.
- Conditions imbriquées remplaçables par des early returns / clauses de garde.
- Duplication : même bloc logique répété dans plusieurs services/composants → extraire (DRY).
- Abstraction pour un seul usage (interface, classe de base, générique) sans bénéfice réel.
- Réimplémentation de ce qu'offrent déjà les libs du projet :
  - **PrimeVue** — interdit de dupliquer un composant existant (`DataTable`, `Dialog`, `Toast`, `ConfirmDialog`, `Select`, `DatePicker`, `FileUpload`, `Menu`, `Paginator`).
  - **VueUse** — avant d'écrire un composable maison.
  - **TanStack Query** — pas de cache/fetch maison pour les données serveur.
  - **Pydantic v2** — pas de validation manuelle redéclarant les règles d'un schéma.
  - **LiteLLM** — pas d'appel direct à un provider LLM contournant la gateway.
- Logique métier écrite dans un router FastAPI (interdit — doit être dans `services/`) ou dans un composant Vue (doit être dans un composable/store).
- SQL brut au lieu de `select()` ORM SQLAlchemy 2.0.
- `try/except` qui avale l'erreur sans la relancer ni la logger.
- Chaînes de `if/elif` sur un enum → `match` ou table de correspondance.
- État frontend dérivable d'un autre état (redondance qui produira des désynchronisations).

---

## C. Respect des règles de codage

Source de vérité : [`30-code-standards.md`](.roo/rules/30-code-standards.md), [`20-architecture-and-api.md`](.roo/rules/20-architecture-and-api.md), [`05-tech-stack.md`](.roo/rules/05-tech-stack.md), [`55-project-structure.md`](.roo/rules/55-project-structure.md), [`06-frontend-vue3.md`](.roo/rules/06-frontend-vue3.md), [`21-realtime-websocket.md`](.roo/rules/21-realtime-websocket.md), [`07-poetry-python.md`](.roo/rules/07-poetry-python.md), [`35-testing-quality-gates.md`](.roo/rules/35-testing-quality-gates.md), [`40-security.md`](.roo/rules/40-security.md).

### C1. Structure backend (FastAPI)

- Structure respectée : `backend/src/{api/v1, core, db, models, schemas, services}`.
- Un router = un domaine dans `api/v1/`, monté via `router.py`.
- Un service = une classe avec injection de dépendances (pas de singleton global sauf DB).
- Schémas Pydantic v2 séparés en `*Request` / `*Response` / `*Update` selon usage.
- Migrations Alembic dans `alembic/versions/` (jamais modifier les tables manuellement).
- **Toujours** lever des exceptions de `core/exceptions.py` (`AppException` et sous-classes), jamais d'exceptions Python brutes dans les endpoints.
- Tests à plat dans `backend/tests/` (pas de sous-répertoires `unit/` / `integration/`), distinction par marqueur `@pytest.mark.integration`.

### C2. Schémas Pydantic v2 (backend)

- Tout payload entrant est validé par un schéma Pydantic v2 avec `Field`, `field_validator`, `model_validator`.
- Schémas séparés `*Request` / `*Response` / `*Update` selon usage.
- Type hints sur tous les champs.
- Pas de `Any` non justifié sur les payloads d'entrée.

### C3. Modèles SQLAlchemy 2.0 (backend)

- UUID pour les PK, champs de timestamp `created_at` / `updated_at`.
- Base déclarative commune (`models/base.py`).
- Jamais de modification manuelle des tables — migrations Alembic uniquement.
- Relations déclarées proprement (`relationship()`, `mapped_column`, `() => Model`).
- Un fichier par modèle dans `models/`.

### C4. TypeScript strict (frontend)

- `strict: true` avec `noUnusedLocals`, `noUnusedParameters`, `noUncheckedIndexedAccess`.
- Alias `@/` → `src/`.
- `any`, `@ts-ignore`, `as unknown as` interdits.
- Types d'API exclusivement depuis `src/api/generated/` — jamais écrits à la main.

### C5. Imports

- Backend : triés par Ruff isort (rule I) — ordre builtin → external → internal.
- Frontend : ESLint 9 flat config.
- Pas d'imports circulaires.

### C6. Formatage / lint

- Backend : Ruff (`line-length=120`, `target-version=py313`, rules E, W, F, I, UP, B, SIM, TCH, RUF, `quote-style="double"`, `indent-style="space"`).
- Frontend : ESLint 9 (flat config) + Prettier + règle `vue/no-restricted-block` (interdiction des blocs `<style>` dans un SFC).
- `.editorconfig` unifié : Python 4 espaces, TS/Vue 2 espaces, LF.

### C7. Frontend (Vue 3 / PrimeVue / Tailwind)

- Vue 3.5+ `<script setup lang="ts">` (Options API interdite).
- Ordre des blocs : `<script setup>` → `<template>`, pas de 3ᵉ bloc (`<style>`).
- Composant >~200 lignes ou 3 responsabilités → découper.
- PrimeVue 4 `unstyled: true` + pass-through global `primevue-pt.ts` (pas de CSS local, pas de `:deep()`, pas de `!important`, pas de sélecteurs `.p-*`).
- Tailwind CSS 4 CSS-first (`@theme` dans `main.css`) + variantes `dark:` (classe `.app-dark`).
- Pinia 3 setup stores (état client uniquement — **jamais** de données API dans Pinia).
- TanStack Query : `useQuery` / `useMutation`, clés centralisées dans `api/queries/`, invalidation explicite, `staleTime` explicite.
- Client généré `@hey-api/openapi-ts` — `fetch` / `axios` directs interdits vers l'API applicative.
- VueUse avant un composable maison.
- WebSocket uniquement dans `src/realtime/` (jamais `new WebSocket()` ailleurs).
- `useToast` / `useConfirm` (pas d'`alert()` / `confirm()` natifs).
- `DataTable` >100 lignes : mode `lazy` avec pagination serveur.
- Composants en PascalCase, un composant par fichier.

### C8. Conventions de commits

- Format Conventional Commits : `<type>(<scope>): <description>`.
- Types : `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `ci`, `chore`, `revert`.
- Scopes usuels : `backend`, `frontend`, `infra`, `docs`, etc. (indicatif — la règle 50 ne fixe que les types, pas les scopes).
- Signaler les messages hors format dans `git log`, ainsi que les commits fourre-tout.

### C9. Cohérence backlog

Source : [`01-Project-management.md`](.roo/rules/01-Project-management.md).

- Référence STORY/EPIC dans les `// TODO STORY-XXX` (pas de `TODO`/`FIXME` orphelin).
- Synchronisation `.backlog/` : statut story/bug à jour, présence dans le kanban, case cochée dans l'epic parent quand une story passe `DONE`.
- Numérotation cohérente : `EPIC-XXX`, `STORY-XXX`, `BUG-XXX` (séquentielle globale).
- Ne jamais supprimer un fichier de backlog (statut `ABANDONED` + note explicative).
- Section « Notes d'implémentation » présente dans le fichier story si son statut est `REVIEW` ou `DONE` (DoD règle 01).
- Statut de l'epic cohérent avec le statut dérivé de ses stories (règle 01 §3.1 : TODO/IN_PROGRESS/DONE dérivés).

La correction des écarts détectés relève de `treat-story` / `finalise-story` — la revue ne fait que les signaler dans le rapport.

---

## D. Nettoyage

- Backend : `print(`, `breakpoint(`, `import pdb`, `# TODO` / `# FIXME` sans référence STORY.
- Frontend : `console.log`, `console.debug`, `debugger`.
- Tests : `@pytest.mark.skip`, `-k` laissé dans une commande, `.only` / `.skip` Vitest.
- Code commenté en bloc laissé en place.
- Fichiers temporaires : `*.bak`, `*.orig`, `*.rej`, scripts de debug, dumps.
- `.env` ou fichiers de configuration locale commités.
- Commentaires devenus faux après modification du code voisin ; docstring décrivant des paramètres disparus.
- Marqueurs de conflit de merge (`<<<<<<<`, `=======`, `>>>>>>>`).
- Fichiers en double ou quasi identiques.
- Dépendances ajoutées dans `pyproject.toml` / `package.json` mais jamais importées, ou l'inverse.
- Variables intermédiaires inutiles.

Commandes utiles :
```bash
git diff <BASE>..HEAD | rg -n "^\+.*(print\(|breakpoint\(|import pdb|console\.(log|debug)|debugger|TODO|FIXME|HACK|XXX)"
git diff <BASE>..HEAD | rg -n "^\+.*(<<<<<<<|>>>>>>>)"
```

---

## E. Sécurité

Source : [`40-security.md`](.roo/rules/40-security.md), [`21-realtime-websocket.md`](.roo/rules/21-realtime-websocket.md). Ces points sont prioritaires.

### E1. Authentification

- JWT PyJWT HS256 (access 30min + refresh 7j).
- bcrypt direct (`bcrypt.hashpw` / `bcrypt.checkpw`) — pas de passlib.
- Refresh token stocké en Redis avec expiration (révocable).
- Token d'accès conservé **en mémoire** (Pinia auth store) — **jamais** en `localStorage` ni `sessionStorage`.
- Manipulation du JWT : changement d'algorithme, `ignoreExpiration`, allongement du TTL → à signaler.

### E2. Autorisation

- RBAC via `require_role(*roles)` (factory dependency dans `core/dependencies.py`).
- Vérifier chaque endpoint protégé : un endpoint sensible sans `require_role` alors que les endpoints équivalents en ont un est une escalade.
- Cohérence des rôles : un endpoint d'administration accessible à `user` est une escalade de privilèges.

### E3. Secrets

- `JWT_SECRET`, `DATABASE_URL`, `REDIS_URL`, clés API LLM (Anthropic / OpenAI / Mistral) — **jamais** en dur, **jamais** dans les logs.
- `.env.sample` mis à jour si une nouvelle variable d'environnement est ajoutée.
- Vault en production.

### E4. Exposition

- Docs FastAPI servies sur `/api/docs` uniquement si `APP_DEBUG` (voir `backend/src/main.py`) — signaler toute réactivation inconditionnelle des docs en production.
- CORS : `CORS_ORIGINS` configuré — signaler tout élargissement (`"*"`).
- Pas de données sensibles dans les logs (structlog JSON).
- Rate limiting `slowapi` sur les endpoints sensibles.

### E5. Injection et WebSocket

- Validation Pydantic sur toutes les entrées.
- SQLAlchemy paramétré — pas de SQL brut concaténé.
- **WebSocket** : validation du ticket éphémère **AVANT** `websocket.accept()` (codes `4001` / `4003` / `4009`).
- **JWT longue durée ou clé d'API en query string interdits** pour tout nouveau code (mécanisme hérité `?token=` à signaler s'il est étendu).
- Enveloppes WS validées à la réception côté front (zod / valibot dans `protocol/`).

---

## F. Fiabilité : migrations, tests, performances, erreurs, contrats

> **Rappel lecture seule** : les quality gates (couverture pytest-cov, `make lint`, `make check-style`, `make test`, `make security`) ne sont **PAS** exécutés pendant la revue. On vérifie statiquement la présence et la qualité des tests dans le diff ; leur exécution relève de `finalise-story`, de la CI ou de l'auteur de la PR.

### F1. Migrations Alembic

- Fichiers dans `backend/alembic/versions/` numérotés `00NN_description.py` (**JAMAIS** de hash Alembic).
- `revision` = `"00NN"`, `down_revision` = `"00NN-1"` corrects.
- `downgrade` supporté.
- Pas de changements parasites sur d'autres tables (nettoyer la migration autogénérée).
- Migration destructive (`DROP COLUMN`, `ALTER TYPE`) sans stratégie de compatibilité : **Critique**.
- Colonne `NOT NULL` ajoutée sans valeur par défaut sur une table existante.
- Chaîne `revision` / `down_revision` et `downgrade` vérifiés statiquement ; l'exécution d'`alembic upgrade head` relève de l'auteur de la PR ou de `finalise-story`, pas de la revue.

### F2. Tests

- Backend : pytest + pytest-asyncio (`asyncio_mode="auto"`), marqueurs `@pytest.mark.unit` / `@pytest.mark.integration`.
- Tests à plat dans `backend/tests/`, fixtures `conftest.py` (`client`, `db_session`, `client_with_db`, `auth_headers`, `event_bus`, `task_queue`, `runner`, `auth_service`, `test_user`, `admin_user`, `seed_universal_archetypes`).
- httpx `AsyncClient` avec `ASGITransport`.
- Couverture ≥ 85% (`--cov-fail-under=85`).
- Frontend : Vitest + `@vue/test-utils` dans `frontend/tests/unit/`, E2E Playwright dans `frontend/e2e/`, couverture ≥ 80%.
- Tout nouveau type de message WS doit avoir : un test de validation d'enveloppe + un test de handler.
- Tests existants supprimés, désactivés ou skippés (`@pytest.mark.skip`, `describe.skip`, `it.skip`, `test.skip`) dans le diff → exiger une justification ; la non-régression d'exécution relève de `finalise-story` / `make test`.

### F3. Quality gates

- `make lint`, `make check-style`, `make test`, `make security` (bandit).
- Commandes Poetry (`cd backend && poetry run ...`) et pnpm (`cd frontend && pnpm ...`) — **jamais** `python` / `pip` / `pytest` ni `npm` / `yarn` directs.

### F4. Performances

- N+1 SQLAlchemy : accès à une relation lazy dans une boucle.
- Pagination serveur obligatoire > 20 éléments (règle API-first) ; `DataTable` lazy > 100 lignes.
- Cache Redis pour les requêtes coûteuses (résultats LLM).
- Retries `tenacity` / circuit breaker `pybreaker` sur les appels LLM.
- Front : `shallowRef` pour les flux WS haute fréquence, buffer circulaire borné pour les logs (5000 lignes), pas de rendu par message WS (agrégation / throttle), listes virtualisées au-delà de quelques centaines de lignes.

### F5. Erreurs et observabilité

- Exceptions `AppException` (`NotFoundException`, `ValidationException`, `UnauthorizedException`, `ForbiddenException`, `BusinessException`) mappées HTTP par le handler global.
- structlog JSON (processors standard : `merge_contextvars`, `add_log_level`, `TimeStamper`, `StackInfoRenderer`, `format_exc_info`, `UnicodeDecoder`, `JSONRenderer`).
- Messages d'erreur API en anglais avec `error_code` typé.
- Adaptateur unique `api/client.ts` côté front (422 → champs, 4xx → toast, 5xx → générique).
- Pas de Sentry (cible Prometheus / Grafana / OpenTelemetry).

### F6. Cohérence des contrats

- Toute modif de contrat backend → `openapi.json` exporté + client régénéré (`npx @hey-api/openapi-ts -i openapi.json -o src/api/generated`) dans la **même PR**.
- Types WS générés depuis Pydantic (jamais écrits à la main) — pour toute modification de l'enveloppe `Envelope` / des modèles Pydantic WS, régénérer via `make generate-ws-schema` (cible Makefile réelle) ; les types TS doivent être régénérés, jamais écrits à la main.
- Enveloppe versionnée : `v`, `id` (uuid), `type` (namespace pointé), `ts`, `seq`, `correlationId`.
- Interface en anglais par défaut.
