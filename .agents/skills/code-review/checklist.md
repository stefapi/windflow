# Checklist de revue — WindFlow

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
- Endpoints ajoutés mais jamais appelés côté front ni documentés dans OpenAPI.
- Colonnes de modèle SQLAlchemy ajoutées mais jamais écrites ni lues.
- Fichiers ajoutés puis rendus orphelins par un renommage.

Commandes utiles :
```bash
rg -n "\bnom_du_symbole\b" backend/app frontend/src cli
rg -n "from ['\"].*<module>" backend/app
```

---

## B. Complexité et code inutile

- Fonction ou méthode dépassant ~30 lignes, ou avec plus de ~3 niveaux d'imbrication.
- Profondeur de nesting excessive (> 3 niveaux) — préférer early return ou extraction.
- Conditions imbriquées remplaçables par des early returns / clauses de garde.
- Duplication : même bloc logique répété dans plusieurs services/composants → extraire (DRY).
- Abstraction pour un seul usage (interface, classe de base, générique) sans bénéfice réel.
- Réimplémentation de ce qu'offrent déjà les libs du projet :
  - **Element Plus** — interdit de dupliquer un composant existant (`ElTable`, `ElDialog`, `ElMessage`/notifications, `ElMessageBox`/confirmations, `ElSelect`, `ElDatePicker`, `ElUpload`, `ElDropdown`, `ElPagination`).
  - **VueUse** — avant d'écrire un composable maison (si disponible dans les dépendances).
  - **Pinia** — pas d'état global maison redondant avec un store.
  - **Pydantic v2** — pas de validation manuelle redéclarant les règles d'un schéma.
  - **cache unifié** (`get_cache()`, `backend/app/core/cache.py`) — pas de cache maison en parallèle.
  - **`core/resilience.py`** — pas de circuit breaker/retry/bulkhead maison en parallèle.
  - **LiteLLM** — pas d'appel direct à un provider LLM contournant la gateway.
- Logique métier écrite dans un router FastAPI (interdit — doit être dans `services/`) ou dans un composant Vue (doit être dans un composable/store/service).
- SQL brut au lieu de `select()` ORM SQLAlchemy 2.0.
- `try/except` qui avale l'erreur sans la relancer ni la logger.
- Chaînes de `if/elif` sur un enum → `match` ou table de correspondance.
- État frontend dérivable d'un autre état (redondance qui produira des désynchronisations).

---

## C. Respect des règles de codage

Source de vérité : [`30-code-standards.md`](.roo/rules/30-code-standards.md), [`20-architecture-and-api.md`](.roo/rules/20-architecture-and-api.md), [`05-tech-stack.md`](.roo/rules/05-tech-stack.md), [`55-project-structure.md`](.roo/rules/55-project-structure.md), [`35-testing-quality-gates.md`](.roo/rules/35-testing-quality-gates.md), [`40-security.md`](.roo/rules/40-security.md).

### C1. Structure backend (FastAPI)

- Structure respectée : `backend/app/{api/v1, auth, core, models, schemas, services, tasks, websocket, middleware, helper, enums}`.
- Un router = un domaine dans `api/v1/`, monté dans `main.py`.
- Un service = une classe avec injection de dépendances (pas de singleton global sauf DB).
- Schémas Pydantic v2 séparés en `*Request` / `*Response` / `*Update` selon usage.
- Migrations Alembic dans `backend/alembic/versions/` (jamais modifier les tables manuellement).
- **Toujours** lever des exceptions de `core/exceptions.py` (`WindFlowException` et sous-classes), jamais d'exceptions Python brutes dans les endpoints.
- Tests dans `backend/tests/unit/` et `backend/tests/integration/` (pas de `e2e/` backend).

### C2. Schémas Pydantic v2 (backend)

- Tout payload entrant est validé par un schéma Pydantic v2 avec `Field`, `field_validator`, `model_validator`.
- Schémas séparés `*Request` / `*Response` / `*Update` selon usage.
- Type hints sur tous les champs ; tout élément couvert par Pydantic (API-first).
- Champs sensibles exclus explicitement des schémas `*Response` (`exclude={"password", "token", ...}`).
- Pas de `Any` non justifié sur les payloads d'entrée.
- Pagination obligatoire pour les listes > 20 éléments.

### C3. Modèles SQLAlchemy 2.0 (backend)

- UUID pour les PK, champs de timestamp `created_at` / `updated_at`, nommage snake_case.
- Relations déclarées proprement (`relationship()`, `mapped_column`).
- Un fichier par modèle dans `models/`.
- Jamais de modification manuelle des tables — migrations Alembic uniquement.

### C4. TypeScript strict (frontend)

- `strict: true` avec `noUnusedLocals`, `noUnusedParameters`, `noUncheckedIndexedAccess`, `noImplicitOverride`, `noPropertyAccessFromIndexSignature`.
- Alias `@/` → `src/`.
- `any`, `@ts-ignore`, `as unknown as` interdits (sauf exception justifiée).
- Types centralisés dans `src/types/` — importer depuis là, ne pas redéfinir localement.

### C5. Imports

- Backend : triés par isort (`profile=black`) — ordre builtin → external → internal.
- Frontend : ESLint 9 flat config.
- Pas d'imports circulaires.
- Attention aux auto-imports unplugin : un symbole utilisé sans import n'est pas forcément une erreur.

### C6. Formatage / lint

- Backend : black (formatage) + isort (`profile=black`) + flake8 + mypy + bandit + pylint (qualité).
- Frontend : ESLint 9 (flat config) + Prettier + Stylelint pour le CSS.
- `.editorconfig` unifié.

### C7. Frontend (Vue 3 / Element Plus / UnoCSS)

- Vue 3 Composition API obligatoire : `<script setup lang="ts">` (Options API interdite).
- Fichiers kebab-case ; composants en PascalCase, un composant par fichier.
- Composant >~200 lignes ou 3 responsabilités → découper.
- Element Plus pour tous les composants UI génériques (pas de duplication maison).
- UnoCSS pour le styling (pas de Tailwind, pas de CSS ad hoc non justifié).
- Un store Pinia = un domaine (état + actions + getters) ; gestion centralisée des erreurs via store + notifications Element Plus.
- Appels HTTP exclusivement via `frontend/src/services/` (jamais d'axios directement dans les vues/composants).
- Composables `use*` pour toute logique réutilisable ou avec état local.
- Notifications via Element Plus (`ElMessage`, `ElNotification`), pas d'`alert()` / `confirm()` natifs.
- Tables > 100 lignes : pagination serveur (l'API est paginée au-delà de 20 éléments).

### C8. Conventions de commits

- Signaler les messages hors format dans `git log`, ainsi que les commits fourre-tout.

### C9. Cohérence backlog

Source : [`01-Project-management.md`](.roo/rules/01-Project-management.md).

- Référence STORY/EPIC dans les `// TODO STORY-XXX` (pas de `TODO`/`FIXME` orphelin).
- Synchronisation `.backlog/` : statut story/bug à jour, présence dans le kanban, case cochée dans l'epic parent quand une story passe `DONE`.
- Numérotation cohérente : `EPIC-XXX`, `STORY-XXX` (sous-stories `STORY-XXX.N`), `BUG-XXX` (séquentielle globale).
- Ne jamais supprimer un fichier de backlog (statut `ABANDONED` + note explicative — règle d'or §10).
- Section « Notes d'implémentation » présente dans le fichier story si son statut est `REVIEW` ou `DONE` (DoD `01` §7).
- Statut de l'epic cohérent avec le statut dérivé de ses stories (règle 01 §6 : statuts et dérivation des epics).

La correction des écarts détectés relève de `treat-story` / `finalise-story` — la revue ne fait que les signaler dans le rapport.

---

## D. Nettoyage

- Backend : `print(`, `breakpoint(`, `import pdb`, `# TODO` / `# FIXME` sans référence STORY.
- Frontend : `console.log`, `console.debug`, `debugger`.
- Tests : `@pytest.mark.skip`, `-k` laissé dans une commande, `.only` / `.skip` Vitest/Playwright.
- Code commenté en bloc laissé en place.
- Fichiers temporaires : `*.bak`, `*.orig`, `*.rej`, scripts de debug, dumps.
- `.env` ou fichiers de configuration locale commités (le projet documente `env.example` et `.env.prod.example`).
- Commentaires devenus faux après modification du code voisin ; docstring décrivant des paramètres disparus.
- Marqueurs de conflit de merge (`<<<<<<<`, `=======`, `>>>>>>>`).
- Fichiers en double ou quasi identiques.
- Dépendances ajoutées dans `pyproject.toml` / `package.json` mais jamais importées, ou l'inverse (règle 05 : pas de dépendance sans justification claire).
- Variables intermédiaires inutiles.

Commandes utiles :
```bash
git diff <BASE>..HEAD | rg -n "^\+.*(print\(|breakpoint\(|import pdb|console\.(log|debug)|debugger|TODO|FIXME|HACK|XXX)"
git diff <BASE>..HEAD | rg -n "^\+.*(<<<<<<<|>>>>>>>)"
```

---

## E. Sécurité

Source : [`40-security.md`](.roo/rules/40-security.md). Ces points sont prioritaires.

### E1. Authentification

- JWT (python-jose) : access + refresh tokens opaques révocables `wf_rt_` avec rotation.
- Hash Argon2id (passlib/argon2-cffi) ; double lecture bcrypt legacy avec re-hash automatique au login uniquement.
- Clés API `wf_ak_` via header `X-API-Key`.
- Protection brute-force login : 5 échecs par username / fenêtre 10 min → lockout 5 min.
- Token d'accès conservé **en mémoire** (store Pinia auth) — **jamais** en `localStorage` ni `sessionStorage`.
- Manipulation du JWT : changement d'algorithme, `ignoreExpiration`, allongement du TTL → à signaler.
- Mode dev `disable_auth` : signaler toute activation hors environnement de développement.

### E2. Autorisation

- RBAC 4 rôles `viewer < operator < admin < super_admin` via `require_role(...)` (et aliases `require_viewer`, `require_operator`, `require_admin`, `require_super_admin`) sur les endpoints REST — `backend/app/auth/rbac.py`.
- `ensure_role_ws` / `require_role_ws` sur les canaux WebSocket.
- Vérifier chaque endpoint protégé : un endpoint sensible sans `require_role` alors que les endpoints équivalents en ont un est une escalade.
- Cohérence des rôles : un endpoint d'administration accessible à `viewer` est une escalade de privilèges.
- Isolation des ressources par organisation/utilisateur (un user ne peut pas accéder aux ressources d'un autre).

### E3. Secrets

- `JWT_SECRET`, `DATABASE_URL`, `REDIS_URL`, clés API LLM (via LiteLLM), credentials SSH/hosts — **jamais** en dur, **jamais** dans les logs.
- SecretManager Fernet (AES-256, clé dérivée PBKDF2) pour les credentials en base.
- HashiCorp Vault optionnel (`vault_enabled: false` par défaut).
- `env.example` / `.env.prod.example` mis à jour si une nouvelle variable d'environnement est ajoutée.

### E4. Exposition

- Documentation API : Scalar `/docs`, Swagger `/swagger`, ReDoc `/redoc` — signaler toute exposition inconditionnelle de docs internes en production.
- CORS : origines configurées — signaler tout élargissement (`"*"`).
- Security headers middleware (CSP configurable, HSTS, X-Frame-Options).
- Pas de données sensibles dans les logs (`logging` standard JSON) ni dans les labels de métriques (jamais de query string).
- Rate limiting fastapi-limiter (Redis, fallback mémoire) sur les endpoints sensibles.
- Schémas `*Response` : vérifier l'exclusion des champs sensibles.

### E5. Injection et WebSocket

- Validation Pydantic sur toutes les entrées (path/query typés et bornés, min/max, regex).
- SQLAlchemy paramétré — pas de SQL brut concaténé ; sanitisation des entrées YAML/JSON/commandes shell.
- Uploads de fichiers validés (type MIME, taille max) le cas échéant.
- **WebSocket** : authentification et contrôle de rôle (`ensure_role_ws`) **AVANT** `websocket.accept()` ; validation des payloads entrants.
- CSRF pour les opérations critiques.
- Pas de stack trace ni de détail interne dans les messages d'erreur API (messages génériques).

---

## F. Fiabilité : migrations, tests, performances, erreurs, contrats

> **Rappel lecture seule** : les quality gates (`make backend-test`, `make frontend-test`, `make lint`, `make typecheck`, sécurité bandit/npm audit) ne sont **PAS** exécutés pendant la revue. On vérifie statiquement la présence et la qualité des tests dans le diff ; leur exécution relève de `finalise-story`, de la CI ou de l'auteur de la PR.

### F1. Migrations Alembic

- Fichiers dans `backend/alembic/versions/`, chaîne `revision` / `down_revision` correcte.
- `downgrade` supporté (des tests d'intégration round-trip upgrade/downgrade existent).
- Pas de changements parasites sur d'autres tables (nettoyer la migration autogénérée).
- Migration destructive (`DROP COLUMN`, `ALTER TYPE`) sans stratégie de compatibilité : **Critique**.
- Colonne `NOT NULL` ajoutée sans valeur par défaut sur une table existante.
- L'exécution d'`alembic upgrade head` relève de l'auteur de la PR ou de `finalise-story`, pas de la revue.

### F2. Tests

- Backend : pytest + pytest-asyncio dans `backend/tests/unit/` et `backend/tests/integration/` (pas de `e2e/` backend).
- Fixtures `conftest.py` (`client`, `auth_headers`, `viewer_headers`, `db_session`, etc.).
- Client HTTP de test : httpx `AsyncClient` avec `ASGITransport`.
- Couverture ≥ 80% (`--cov-fail-under=80`), chemins critiques (auth, déploiement, RBAC) : viser 95%.
- **Tout nouvel endpoint ou feature modifiant des données DOIT avoir les tests sécurité obligatoires** : 401 sans token, 403 rôle insuffisant, 422 body invalide, 404 ressource introuvable (+ 403 ressource d'un autre user si applicable, absence de champs sensibles dans la réponse).
- Frontend : Vitest + `@vue/test-utils` dans `frontend/tests/unit/`, intégration dans `tests/integration/`, E2E Playwright (chromium/firefox/webkit) dans `tests/e2e/`.
- Tests existants supprimés, désactivés ou skippés (`@pytest.mark.skip`, `describe.skip`, `it.skip`, `test.skip`) dans le diff → exiger une justification ; la non-régression d'exécution relève de `finalise-story` / `make test`.

### F3. Quality gates

- Commandes Makefile (source de vérité) : `make lint`, `make typecheck`, `make backend-test`, `make frontend-test`, `make ci-security-backend`, `make ci-security-frontend`.
- uv côté Python et pnpm côté frontend — **jamais** `pip` / `npm` / `yarn` / `poetry` directs (`00` §5).

### F4. Performances

- N+1 SQLAlchemy : accès à une relation lazy dans une boucle.
- Pagination serveur obligatoire > 20 éléments (règle API-first).
- Cache unifié `get_cache()` (Redis si configuré, sinon mémoire locale bornée) pour les requêtes coûteuses (dont cache LLM).
- Circuit breaker câblé sur Docker, SSH et le registre de plugins ; retries/backoff sur les appels externes.
- Front : flux WebSocket haute fréquence (logs/stats) — throttling/agrégation du rendu, pas de rendu par message.

### F5. Erreurs et observabilité

- Exceptions `WindFlowException` (`backend/app/core/exceptions.py`) et sous-classes mappées HTTP par le handler global — jamais d'exception Python brute dans un endpoint.
- `logging` standard avec format JSON configurable (PAS structlog) ; niveaux cohérents ; pas de données sensibles.
- Correlation ID : middleware dédié, header `X-Correlation-ID` propagé, inclus dans les logs.
- Timing middleware : log des requêtes lentes (`slow_request_threshold`).
- Métriques Prometheus : préfixe unique `windflow_` (`backend/app/core/metrics.py` + `backend/app/websocket/metrics.py`), endpoint `GET /api/v1/metrics` sans auth, jamais enveloppé, labels sans données sensibles (chemins normalisés UUID → `{id}`, numérique → `{n}`).
- Événements via le bus canonique `Bus` (`backend/app/core/events.py`) — `InMemoryEventBus` par défaut, `RedisPubSubEventBus` optionnel sur `windflow:events` ; retry/backoff, idempotence ; Redis Streams hors périmètre.
- Gestion d'erreurs frontend centralisée (store Pinia) + notifications Element Plus + fallback gracieux.

### F6. Cohérence des contrats

- API-first : toute fonctionnalité exposée via API REST avant UI/CLI ; OpenAPI exhaustif et à jour (descripteurs, exemples) sur les nouveaux endpoints.
- Toute modif de contrat backend → client TypeScript régénéré via `make generate-api` dans la **même PR** ; vérifier seulement que la régénération a eu lieu, pas le détail du code généré.
- Types WS/métier générés via `make generate-types` — jamais écrits à la main.
- Enveloppes de réponse et pagination cohérentes d'un router à l'autre (contrats testés).
- Full-stack : vérifier la cohérence schémas Pydantic ↔ types TS ↔ services frontend.
