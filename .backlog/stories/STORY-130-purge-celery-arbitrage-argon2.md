# STORY-130 : [ABANDONED] Purge Celery + arbitrage Argon2 — suppression du double runtime fantôme et migration Argon2id (P1-11 + P1-10)

**Statut :** ABANDONED
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-11 (axes F1 + E10, rapports §6/§9.1) + P1-10 (arbitrage F2, rapport §2) — ampleur **S+S**

> **Note de clôture (split-story, mode proactif — 2026-10-02)** : cette story a été **découpée en deux sous-stories autonomes** à l'issue de son analyse (`analyse-story`, 13 tâches, 9 arbitrages), la complexité étant multi-domaines — sécurité/auth et infrastructure/purge, deux volets hétérogènes **sans interaction technique** :
>
> - **[STORY-130.1 — Migration Argon2id](STORY-130.1-argon2id-migration-hash.md)** : tâches 1-2 + 11 (partie service hash/upgrade + login API) + 12 + 13 (partie Argon2) — reprend les AC 2 et 3 de la mère ;
> - **[STORY-130.2 — Purge des références Celery](STORY-130.2-purge-references-celery.md)** : tâches 3-10 + 11 (partie garde-fou `test_no_celery_residue.py`) + 13 (partie Celery) — reprend l'AC 1 de la mère ; l'AC 4 est réparti entre les deux (périmètre auth → 130.1, périmètre purge → 130.2).
>
> L'intégralité de l'analyse (état des lieux, arbitrages n°1-9, tâches détaillées, tests) est **conservée ci-dessous pour historique** et a été reprise/redistribuée intégralement dans les sous-stories. Ne pas implémenter cette story — se référer aux sous-stories.

## Description

En tant que mainteneur de WindFlow, je veux (1) **purger le double runtime Celery fantôme** (`celery_app.py`, `Dockerfile.worker`, cibles Makefile associées) pour assumer un runtime asyncio unique (arbitrage F1 validé), et (2) **documenter l'upgrade path Argon2id** en migrant le hachage des mots de passe de bcrypt vers Argon2id via l'upgrade automatique au login (arbitrage F2 : le code est correct, c'est la spec 07 qui doit être corrigée), afin d'éliminer la surface de test/déploiement morte et d'aligner le hashage sur les rules sécurité.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §2, §6, §9.1, §14) : [`celery_app.py`](../../backend/app/celery_app.py:19) est complet mais **jamais importé** — le runtime réel est asyncio ([`DeploymentOrchestrator`](../../backend/app/services/deployment_orchestrator.py:21), boucle de santé lifespan, [`background_tasks.py`](../../backend/app/tasks/background_tasks.py)) ; la dépendance Celery n'est même pas installable via Poetry. Côté hash : le code utilise passlib/bcrypt alors que les rules 40 imposent argon2-cffi — l'arbitrage F2 tranche : **migrer le code** vers Argon2id et corriger la spec 07.

## Contexte technique

> Analyse remplie par `analyse-story` (2026-10-02). Constats vérifiés dans le code au moment de l'analyse. Les deux volets sont **indépendants** : Argon2 (tâches 1-2, 11-12) et purge Celery (tâches 3-10) peuvent être traités dans un ordre quelconque, y compris en deux lots de commit/merge séparés.

### État des lieux — volet Argon2 (P1-10, F2) : la migration est plus avancée que l'ébauche ne le laissait croire

- **`pwd_context` est déjà Argon2** : [`user_service.py`](../../backend/app/services/user_service.py:20) définit `CryptContext(schemes=["argon2"])` — `hash_password` (:31), `verify_password` (:48), `create` (hash à la création, :324) et `update` (re-hash, :374) produisent donc déjà de l'Argon2id. STORY-129 a confirmé et étendu ce socle : `PUT /auth/password` hash en Argon2 ([`auth.py:1126-1128`](../../backend/app/api/v1/auth.py:1126)), le seed admin passe par `UserService.create` ([`database_seed.py:82`](../../backend/app/database_seed.py:82)) → Argon2id dès la création.
- **`argon2-cffi` est déjà une dépendance Poetry** : [`pyproject.toml:24-25`](../../pyproject.toml:24) déclare `passlib = "^1.7.4"` (extra `argon2`) **et** `argon2-cffi = "^23.0.0"` (présent dans `poetry.lock`). L'AC 2 « dépendance argon2-cffi ajoutée » est donc **satisfaite de facto** — divergence consignée.
- **Le mécanisme d'upgrade au login existe et est déjà branché** : [`UserService.verify_and_update_user()`](../../backend/app/services/user_service.py:98) (passlib `verify_and_update` + écriture DB + refresh) est consommé par le login ([`auth.py:290-292`](../../backend/app/api/v1/auth.py:290)).
- **⚠️ Trou réel — la double lecture bcrypt est impossible en l'état** : un contexte `schemes=["argon2"]` **ne sait pas vérifier** un hash bcrypt legacy (`$2b$...`) — passlib ne reconnaît pas le schème → vérification échouée → **un éventuel compte bcrypt ne peut pas se connecter aujourd'hui**, donc pas non plus être re-haché. Pour honorer l'AC 2 (« login bcrypt → re-hash Argon2id, aucun reset requis »), il faut :
  1. déclarer `schemes=["argon2", "bcrypt"]` avec `deprecated="auto"` — bcrypt devient un schème **déprécié en lecture seule** : `verify_and_update` retourne alors un hash Argon2id à ré-écrire ; l'ordre des schèmes fait d'argon2 le schème par défaut en **écriture** (`hash_password` inchangé) ;
  2. ajouter la dépendance **`bcrypt`** — la seule réellement manquante (absente de [`poetry.lock`] ; passlib exige le package `bcrypt` pour activer son handler bcrypt). C'est une dépendance de **transition (lecture)** : rules 40 (écriture Argon2) restent respectées ; sa retraite post-migration est à consigner pour STORY-250.
- **Bcrypt legacy résiduel** : [`helper/security.py`](../../backend/app/helper/security.py:1) (bcrypt nu) n'est **importé nulle part** (vérifié par grep sur `backend/`, `cli/`, `frontend/`) — code mort, sa suppression reste réservée à STORY-250 ; cette story s'assure uniquement qu'aucun chemin d'auth ne l'utilise (déjà le cas — à proscrire, arbitrage n°1 de STORY-129 toujours valable).
- **Docstrings/OpenAPI mensongères** : [`auth.py:96-98`](../../backend/app/api/v1/auth.py:96) (login : « Password hashing with bcrypt »), [`auth.py:674-676`](../../backend/app/api/v1/auth.py:674) (register), [`users.py:427-429`](../../backend/app/api/v1/users.py:427) (« Passwords are hashed with bcrypt ») — descriptions OpenAPI publiques à corriger en Argon2id. Les **specs** `docs/general_specs/07|15` restent réservées à STORY-252 (répartition du plan).
- **Paramètres Argon2id** : passlib/argon2-cffi appliquent leurs défauts (variant id, recommandations RFC 9106). Décision : **ne pas surcharger** les paramètres (arbitrage n°2 ci-dessous).

### État des lieux — volet purge Celery (P1-11, F1/E10) : inventaire exhaustif des références

Runtime réel confirmé asyncio : [`DeploymentOrchestrator`](../../backend/app/services/deployment_orchestrator.py:21), boucle de santé lifespan ([`main.py:150`](../../backend/app/main.py:150)), purge refresh tokens ([`main.py:172`](../../backend/app/main.py:172), STORY-123.4), [`background_tasks.py`](../../backend/app/tasks/background_tasks.py). [`celery_app.py`](../../backend/app/celery_app.py:19) n'est importé **nulle part** (grep sur `backend/`, `cli/`, `frontend/`) ; la dépendance `celery` est absente de [`pyproject.toml`](../../pyproject.toml:8) — le worker n'a d'ailleurs jamais pu démarrer via Poetry, et le [`Dockerfile.worker:81`](../../infrastructure/docker/Dockerfile.worker:81) référence `backend.celery_app` (chemin inexistant : le module réel est `backend.app.celery_app`) — double preuve du caractère fantôme.

| # | Fichier | Références à retirer |
|---|---|---|
| 1 | [`backend/app/celery_app.py`](../../backend/app/celery_app.py:19) | **Supprimer le fichier entier** (app Celery + Beat schedule + 3 tâches — comportements déjà portés par asyncio : health-check targets = boucle lifespan ; retry pending = `DeploymentOrchestrator.recover_pending_deployments()` ; cleanup logs 2h/jour = jamais exécuté, voir arbitrage n°6) |
| 2 | [`infrastructure/docker/Dockerfile.worker`](../../infrastructure/docker/Dockerfile.worker:1) | **Supprimer le fichier entier** |
| 3 | [`Makefile`](../../Makefile:34) | `WORKER_IMAGE` (:34), cible `docker-build-worker` (:364-365), dépendance dans `docker-build` (:367), `enable-workers` (:471-479), `disable-workers` (:506-510), raccourci `enable-work` (:534), ligne d'aide (:405-406), build local worker (:628) |
| 4 | [`docker-compose.prod.yml`](../../docker-compose.prod.yml:303) | service `windflow-worker` (:303-345), volume `worker_data` (:690-691) — **ne pas toucher** `API_WORKERS: 4` (:262 = workers uvicorn, piège d'homonymie) ; vérifier l'absence de `depends_on` vers le worker |
| 5 | [`.gitea/workflows/build.yml`](../../.gitea/workflows/build.yml:63) | job `build-worker` (:63-103) + références dans le job summary (`needs` :159-168) |
| 6 | [`.gitea/workflows/ci.yml`](../../.gitea/workflows/ci.yml:326) | step « Build Worker image » (:326-333) |
| 7 | [`infrastructure/docker/prometheus.yml`](../../infrastructure/docker/prometheus.yml:33) | scrape job `windflow-worker` (:33-35) |
| 8 | [`infrastructure/docker/prometheus-alerts.yml`](../../infrastructure/docker/prometheus-alerts.yml:216) | règles `CeleryWorkerDown` / `CeleryQueueBacklog` / `CeleryHighTaskFailureRate` (:216-246, retirer le groupe entier s'il devient vide) |
| 9 | [`env.example`](../../env.example:202) | section CELERY (:202-221) + Flower (:232-234) — **conserver** la section Redis (rate limiting) |
| 10 | [`.env.prod.example`](../../.env.prod.example:216) | section CELERY (:216-231) + Flower (:258-260) + commentaire Redis « requis pour Celery » (:83-84 → reformuler : rate limiting/cache) |
| 11 | [`scripts/install.sh`](../../scripts/install.sh:463) | ligne « • Celery Worker » de l'affichage des services |
| 12 | [`.gitignore`](../../.gitignore:118) | entrées `celerybeat-schedule` / `celerybeat.pid` (:118-121) |
| 13 | [`pyproject.toml`](../../pyproject.toml:111) | override mypy `celery.*` (:111) — **conserver** l'override `bcrypt` (:110, bcrypt devient une vraie dépendance, sans stubs) |
| 14 | Commentaires/docstrings backend | [`main.py:150`](../../backend/app/main.py:150) « fallback when Celery is unavailable », [`main.py:172-174`](../../backend/app/main.py:172) « F1 reporté à STORY-130 » (arbitrage consommé — dater), [`config.py:51-53`](../../backend/app/config.py:51) même mention, [`background_tasks.py`](../../backend/app/tasks/background_tasks.py:1) docstrings « fallback quand Celery… » (:1-12, :31-35, :476-479, :534-536), [`models/scheduled_task.py:2,35`](../../backend/app/models/scheduled_task.py:2) « Celery Beat », [`scheduler_service.py:4,165`](../../backend/app/services/scheduler_service.py:4), [`deployment_orchestrator.py:4`](../../backend/app/services/deployment_orchestrator.py:4) « Remplace Celery » |
| 15 | Rules `.roo` | [`05-tech-stack.md:10`](../../.roo/rules/05-tech-stack.md:10) « Celery — prévu mais pas encore intégré », [`50-dev-workflow.md:108-109`](../../.roo/rules/50-dev-workflow.md:108) ligne enable/disable-workers, [`55-project-structure.md:32-33,57-59`](../../.roo/rules/55-project-structure.md:32) `celery_app.py` + `tasks/` « Tâches Celery » |
| 16 | Docs générales hors specs | [`docs/Roadmap.md:100`](../../docs/Roadmap.md:100) « Celery pour tâches asynchrones », [`docs/technical_specs/ARCHITECTURE-MODULAIRE.md:109-111`](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md:109) écart enable-workers, [`docs/technical_specs/WEBSOCKET-REAL-TIME.md:274-283`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md:274) note explicative |

**Exclusions du périmètre** (répartition du plan, arbitrage n°5) : `docs/general_specs/*` (04/05/16/17/02/03 mentionnent Celery — consolidées par STORY-252/P3-4), `docs/backend_status.md` + `docs/backend_remediation_plan.md` (snapshots d'audit/plan, régénérés par STORY-253/P3-5), `CHANGELOG.md` (trace historique — la nouvelle entrée nomme ce qu'elle supprime), `.backlog/` (planification), artefacts de build (`coverage.xml`, `backend/htmlcov/`, `.mypy_cache/`, `.idea/` — régénérés par `make clean-tests`).

**Compose sains vérifiés** : `docker-compose.minimal.yml`, `docker-compose-dev.yml`, `docker-compose.extensions.yml` et `docker-compose.yml` racine (redirecteur d'aide) **ne référencent aucun worker** — le profil `workers` ciblé par `make enable-workers` n'est défini dans aucun fichier (cible déjà morte, documentée dans [`ARCHITECTURE-MODULAIRE.md:110`](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md:110)) : retrait sans risque fonctionnel.

### Patterns existants à réutiliser (réutilisation directe)

| Besoin | Élément réutilisable | Fichier |
|---|---|---|
| Upgrade hash au login | `UserService.verify_and_update_user(db, user, plain)` — déjà branché au login | [`user_service.py:98`](../../backend/app/services/user_service.py:98), consommé [`auth.py:291`](../../backend/app/api/v1/auth.py:291) |
| Hash Argon2id (écriture) | `UserService.hash_password` — inchangé par l'extension de schèmes | [`user_service.py:31`](../../backend/app/services/user_service.py:31) |
| Hash Argon2 déterministe (clés API) | pattern `pwd_context.handler().using(salt=...)` — **non impacté** (argileux : déjà argon2-only, aucune donnée bcrypt) | [`api_key_service.py:72`](../../backend/app/services/api_key_service.py:72) |
| Comptes seedés Argon2 | `UserService.create` consommé par le seed | [`database_seed.py:82`](../../backend/app/database_seed.py:82) |
| Génération d'un hash bcrypt de fixture | passlib `CryptContext(schemes=["bcrypt"])` local au test (après ajout de la dépendance) | — |
| Tests login/password sur DB réelle | fixtures du conftest + patterns de [`test_auth_password_flow.py`](../../backend/tests/integration/test_auth_password_flow.py) | [`conftest.py`](../../backend/tests/conftest.py) |
| Validation syntaxique des compose modifiés | `docker compose -f <file> config -q` | — |

### Arbitrages d'analyse (décisions proposées, à appliquer telles quelles)

| # | Question | Décision | Justification |
|---|---|---|---|
| 1 | Dépendance à ajouter | **`bcrypt = "^4.0.0"`** (transition, lecture seule) — **pas** argon2-cffi (déjà présent, divergence AC 2) | passlib exige le package bcrypt pour vérifier les hashes legacy ; l'avertissement passlib 1.7.4 / bcrypt ≥ 4.1 (« error reading bcrypt version ») est cosmétique — l'ignorer, ou pinner `4.0.1` s'il bruite la CI |
| 2 | Paramètres Argon2id | **Défauts passlib/argon2-cffi, sans surcharge** (pas de `argon2__*`) | Les hashes existants utilisent ces défauts ; surcharger déclencherait un re-hash de **tous** les comptes au login via `deprecated="auto"` (coût ~100 ms/compte, gain nul) ; tout durcissement futur sera auto-porté par `verify_and_update` |
| 3 | Stratégie de migration | **Upgrade paresseux au login uniquement** — pas de script de masse en migration Alembic | Conforme à l'arbitrage F2 et au critère de done P1-10 (« aucun reset requis ») ; un re-hash de masse coûterait cher pour un gain nul ; les comptes inactifs gardent un hash bcrypt vérifiable indéfiniment (double lecture permanente) |
| 4 | `helper/security.py` (bcrypt nu) | **Ne pas toucher** — purge réservée à STORY-250 | Code mort non importé (vérifié) ; périmètre minimal ; cette story garantit seulement qu'aucun chemin d'auth ne l'importe |
| 5 | Rules `.roo` et écran grep | Rules 05/50/55 **nettoyées dans cette story** ; écran `grep -ri celery` avec **exclusions documentées** (général_specs → STORY-252, backend_status/plan/CHANGELOG → traces historiques, `.backlog/`, artefacts de build) | L'écran AC 1 couvre le dépôt hors exclusions ; les rules ne sont pas des `general_specs` ; STORY-253 gardera la refonte complète des rules. Un littéral « zéro occurrence sur tout le dépôt » est impossible (la trace du changement nomme Celery) |
| 6 | Beat schedule « cleanup-logs-daily » | **Disparaît sans remplacement immédiat** | Jamais exécuté (worker fantôme) — aucun comportement réel perdu ; la rétention structurée des logs relève du scheduler P2 (STORY-160) ; à consigner en note d'implémentation |
| 7 | Dépendance `redis` | **Conservée** | Sert au rate limiting (fastapi-limiter) et au cache — indépendant de Celery |
| 8 | Garde-fou automatisé anti-régression | Nouveau test léger `test_no_celery_residue.py` : `importlib.util.find_spec("app.celery_app") is None` + `pyproject.toml` sans dépendance celery (parse `tomllib`) | L'écran grep AC 1 reste manuel/CI ; ce test protège la régression la plus probable (réintroduction du module ou de la dépendance) |
| 9 | Blindage des hashes illisibles | `verify_password` / `verify_and_update` interceptent `ValueError`/`TypeError` (schème inconnu, hash corrompu) → `(False, None)` sans lever | Un hash imprévisible en base ne doit jamais provoquer de 500 au login ; échec silencieux = même 401 générique anti-énumération (rules 40) |

### Points d'attention sécurité (checklist rules 40 appliquée à cette story)

- **Aucun nouvel endpoint** → pas de surface HTTP nouvelle ; le login existant change de comportement uniquement pour les hashes bcrypt (vérification + re-hash transparent). Tests 401/403/422/404 existants non impactés (non-régression à jouer).
- **Jamais de mot de passe ni de hash dans les logs/réponses** : l'upgrade au login logge uniquement `user_id` (pattern existant) ; les tests assertent l'absence de hash dans les réponses login/password.
- **Messages génériques** : échec bcrypt ou argon2 → même 401 générique (aucune fuite d'information sur l'algorithme du hash stocké — anti-énumération).
- **Audit** : aucun événement d'audit nouveau requis (le re-hash est une opération technique transparente, pas une action utilisateur) — décision à consigner dans les notes d'implémentation.
- **Exposition de données sensibles** : aucune réponse API ne change de forme ; `users.hashed_password` n'est jamais sérialisé (schémas Pydantic existants).

## Critères d'acceptation (AC)

- [ ] AC 1 : [`celery_app.py`](../../backend/app/celery_app.py:19) et [`Dockerfile.worker`](../../infrastructure/docker/Dockerfile.worker) sont supprimés ; les cibles Makefile et services compose liés au worker sont retirés ; `make docker-build` ne build plus d'image worker ; `grep -ri celery` (code, CI, scripts, env, docs hors backlog/specs P3) ne retourne **aucune référence** ; CI et tests verts.
- [ ] AC 2 : La dépendance `argon2-cffi` est ajoutée (Poetry) ; le login d'un utilisateur bcrypt → **hash re-haché Argon2id en base après login** (test) ; **aucun reset de mot de passe requis** (tous les comptes existants continuent de se connecter) ; comptes nouvellement créés hashés Argon2id.
- [ ] AC 3 : L'upgrade path est **documenté** (notes d'implémentation + mention dans la story) : paramètres Argon2id, transition double lecture, renvoi de la correction consolidée des specs 07/15 à STORY-252 (P3-4) avec les arbitrages F5 (JWT 15 min) et F1 (specs 04/05) ;
- [ ] AC 4 : `make lint` + `make backend-test` verts ; non-régression complète des flux auth (login username/email, register, refresh, disable_auth).

## Références spécification

- [`docs/general_specs/04-architecture.md`](../../docs/general_specs/04-architecture.md) + [`docs/general_specs/05-stack-technologique.md`](../../docs/general_specs/05-stack-technologique.md) — runtime de tâches (specs à corriger en P3-4, référencées ici pour traçabilité F1) ;
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § hashage (bcrypt cost 12 — à corriger en Argon2id via STORY-252 conformément à l'arbitrage F2), § flow de login (upgrade au login) ;
- `.roo/rules/40-security.md` — bibliothèques d'authentification : passlib + **argon2-cffi** (hash des mots de passe) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §9.1 (Celery jamais importé), §2 (bcrypt vs rules), §14 (deux lignes « Celery non intégré ») ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §3 F1 (asyncio assumé) et F2 (Argon2, corriger le code), §4 P1-10/P1-11, §7.4 arbitrages 1-2 (validés).

## Dépendances

- **Arbitrages F1 et F2 validés par l'utilisateur** (plan §7.4 — validation acquise lors de la création des epics).
- **STORY-129 — DONE ✔** : `pwd_context` déjà Argon2 ; `PUT /auth/password`, register et seed hashsent déjà en Argon2id — cette story n'a **aucun changement** à y apporter ; l'extension `schemes=["argon2","bcrypt"]` est rétro-compatible avec tous les hashes Argon2 déjà écrits (aucun re-hash superflu — arbitrage n°2).
- **STORY-123.4 — DONE ✔** : purge refresh tokens en boucle asyncio au lifespan — la disparition du Beat schedule Celery ne crée **aucun trou fonctionnel** (vérifié : les 3 tâches Celery étaient soit déjà couvertes par asyncio, soit jamais exécutées).
- **STORY-125.3 — DONE ✔** : rétention audit en asyncio (lifespan) — idem, indépendant de Celery.
- **Aucune migration DB** : `users.hashed_password` (colonne String existante) accueille indifféremment `$argon2id$...` et `$2b$...` — l'upgrade est purement applicatif, au fil des logins (arbitrage n°3).
- **Aucun service externe nouveau** ; `redis` conservé (rate limiting/cache — arbitrage n°7).
- **Interaction STORY-252 (P3-4, EPIC-014)** : corrections consolidées des specs 04/05/07/15/16 réservées — cette story **ne modifie aucun fichier `docs/general_specs/`** (divergence contrôlée documentée dans l'epic).
- **Interaction STORY-250/253 (EPIC-014)** : retraite de la dépendance `bcrypt` post-migration + suppression de `helper/security.py` (STORY-250) ; refonte complète des rules et régénération de `backend_status.md` (STORY-253).
- **Conditionne** : STORY-160 (scheduler asyncio — son texte cite déjà « F1 ayant purgé Celery »), STORY-250/254 (écrans de contrôle grep sur dépôt nettoyé).

## Sous-stories

*(analyse-story, 2026-10-02 : la story cumule ~13 tâches sur **deux domaines hétérogènes** (sécurité/auth vs infrastructure/purge). Les deux volets étant strictement indépendants — aucune interaction technique — une découpe `split-story` en **STORY-130.1 (Argon2id, tâches 1-2 + 11-12)** et **STORY-130.2 (purge Celery, tâches 3-10 + 13)** avait été **recommandée** pour isoler les risques et permettre deux revues/merges séparés.)*

*(split-story, mode proactif, 2026-10-02 : découpe **exécutée** — la story est fermée (`ABANDONED`, Règle d'Or : contenu conservé pour historique) et remplacée par :)*

- [ ] STORY-130.1 : [Migration Argon2id](STORY-130.1-argon2id-migration-hash.md) — double lecture bcrypt + re-hash au login (tâches 1-2 + 11 partie Argon2 + 12 + 13 partie Argon2) — couvre les AC 2 et 3 de la mère
- [ ] STORY-130.2 : [Purge des références Celery](STORY-130.2-purge-references-celery.md) — runtime asyncio unique assumé (tâches 3-10 + 11 partie garde-fou + 13 partie Celery) — couvre l'AC 1 de la mère (AC 4 réparti entre les deux)

## État d'avancement technique

*(cochage progressif pendant treat-story — rien n'est coché à ce stade)*

- [ ] Tâche 1 — Double lecture Argon2/bcrypt : `pwd_context` + dépendance `bcrypt` + blindage
- [ ] Tâche 2 — Correction docstrings/OpenAPI « bcrypt » → Argon2id (auth.py, users.py)
- [ ] Tâche 3 — Suppression `celery_app.py` + `Dockerfile.worker` + override mypy `celery.*`
- [ ] Tâche 4 — Purge Makefile (WORKER_IMAGE, docker-build-worker, enable/disable-workers)
- [ ] Tâche 5 — Purge `docker-compose.prod.yml` (service worker + volume + depends_on)
- [ ] Tâche 6 — Purge CI `.gitea/` (build.yml job + needs, ci.yml step)
- [ ] Tâche 7 — Purge monitoring (prometheus.yml job + alertes Celery)
- [ ] Tâche 8 — Purge env/scripts/.gitignore (env.example, .env.prod.example, install.sh)
- [ ] Tâche 9 — Nettoyage commentaires/docstrings backend (runtime asyncio assumé)
- [ ] Tâche 10 — Rules `.roo` + docs générales hors specs + écran grep
- [ ] Tâche 11 — Tests unitaires (service hash/upgrade + login API + garde-fou no-celery)
- [ ] Tâche 12 — Tests d'intégration (migration bcrypt→Argon2id de bout en bout)
- [ ] Tâche 13 — CHANGELOG + validation finale (lint, tests, compose config, grep screen)

## Tâches d'implémentation détaillées

> Séquencement : volet Argon2 (tâches 1-2) → volet Celery (tâches 3-10) → tests (11-12) → clôture (13). Les deux volets sont indépendants (voir Sous-stories). Les exigences sécurité (rules 40) sont intégrées inline dans les tâches concernées.

### Tâche 1 : Double lecture Argon2/bcrypt — `pwd_context` + dépendance `bcrypt`

**Objectif :** permettre la vérification (et le re-hash automatique au login) des mots de passe bcrypt legacy, l'écriture restant Argon2id — cœur de l'AC 2.

**Fichiers :**
- [`pyproject.toml`](../../pyproject.toml:24) — **Modifier** : ajouter `bcrypt = "^4.0.0"` dans `[tool.poetry.dependencies]` (à côté de `passlib`/`argon2-cffi`, avec un commentaire « transition : vérification des hashes bcrypt legacy (lecture seule) — retrait post-migration, cf. STORY-250 ») ; régénérer le lock (`poetry lock && poetry install` — Poetry uniquement, rules 05) ; **conserver** l'override mypy `bcrypt` (:110, pas de stubs) ;
- [`backend/app/services/user_service.py`](../../backend/app/services/user_service.py:20) — **Modifier** :
  - `pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")` avec commentaire : argon2 = schème par défaut en **écriture** (premier non-déprécié) ; bcrypt = **lecture seule dépréciée** pour la transition (upgrade au login) ;
  - `verify_and_update` (:64) et `verify_password` (:47) : aveuglir contre les hashes illisibles — `try/except (ValueError, TypeError)` → retour `(False, None)` / `False` sans lever (arbitrage n°9 : jamais de 500 au login, même 401 générique) ;
  - docstrings : documenter la double lecture, l'upgrade automatique, les paramètres Argon2id **par défaut** de passlib/argon2-cffi (arbitrage n°2 — pas de surcharge), et le chemin de retraite de bcrypt (STORY-250) ;
  - `verify_and_update_user` (:98) : inchangé fonctionnellement (il écrit déjà le `new_hash` retourné) — vérifier uniquement que le re-hash pose bien `db.commit()` (déjà le cas).

**Sécurité (inline) :** aucun log de mot de passe/hash ; l'échec de vérification reste un `False` silencieux consommé par le 401 générique existant du login.

**Dépend de :** Aucune

### Tâche 2 : Correction des docstrings/OpenAPI « bcrypt » → Argon2id

**Objectif :** aligner la documentation embarquée (descriptions OpenAPI publiques) sur la réalité Argon2id — AC 3 (documentation de l'upgrade path), rules 20 (OpenAPI à jour).

**Fichiers :**
- [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py:96) — **Modifier** : description du login (:96-98 « Password hashing with bcrypt » → Argon2id + mention « automatic upgrade of legacy bcrypt hashes at login ») et du register (:674-676) ;
- [`backend/app/api/v1/users.py`](../../backend/app/api/v1/users.py:427) — **Modifier** : « Passwords are hashed with bcrypt before storage » → Argon2id ;
- vérifier à la génération (`/openapi.json` ou `make generate-openapi-docs`) que plus aucune description publique ne mentionne bcrypt.

**Dépend de :** Tâche 1 (cohérence du discours)

### Tâche 3 : Suppression des fichiers Celery + override mypy

**Objectif :** éliminer le double runtime fantôme (AC 1) — fichiers centraux d'abord, tout ce qui les référencera devenant temporairement orphelin jusqu'aux tâches 4-8.

**Fichiers :**
- `backend/app/celery_app.py` — **Supprimer** ;
- `infrastructure/docker/Dockerfile.worker` — **Supprimer** ;
- [`pyproject.toml`](../../pyproject.toml:108) — **Modifier** : retirer `"celery.*"` de l'override mypy (:108-136) ;
- vérifier : `grep -rn "celery_app\|Dockerfile.worker" backend/ cli/ frontend/ .gitea/ scripts/ dev/` → il ne doit rester que les références traitées par les tâches 4-8 (Makefile, compose, CI, monitoring) ;
- note : les artefacts de couverture obsolètes (`coverage.xml`, `backend/htmlcov/`, `.mypy_cache/`) seront régénérés en tâche 13 (`make clean-tests`) — rien à éditer à la main.

**Dépend de :** Aucune

### Tâche 4 : Purge Makefile

**Objectif :** retirer toutes les cibles/variables liées au worker (AC 1 : `make docker-build` ne build plus d'image worker).

**Fichiers :**
- [`Makefile`](../../Makefile:34) — **Modifier** :
  - supprimer `WORKER_IMAGE` (:34) ;
  - supprimer la cible `docker-build-worker` (:364-365) ;
  - `docker-build: docker-build-backend docker-build-frontend` (:367 — retirer `docker-build-worker` de la dépendance) ;
  - supprimer `enable-workers` (:471-479), `disable-workers` (:506-510) et le raccourci `enable-work` (:534) — cibles déjà mortes (profil `workers` inexistant, cf. état des lieux) ;
  - retirer la ligne d'aide `make enable-workers # Celery workers` (:405-406) ;
  - retirer la ligne de build local du worker (:628, `windflow/worker:local`) dans la cible de build local (:627-629) ;
  - vérifier `make help` (aucune référence pendante, mise en page intacte).

**Dépend de :** Tâche 3 (fichier Dockerfile.worker supprimé — les cibles ne doivent plus exister)

### Tâche 5 : Purge `docker-compose.prod.yml`

**Objectif :** retirer le service worker et son volume sans casser le compose de production (AC 1).

**Fichiers :**
- [`docker-compose.prod.yml`](../../docker-compose.prod.yml:303) — **Modifier** :
  - supprimer le service `windflow-worker` (bloc :303-345 jusqu'à sa fermeture exacte — healthcheck/labels inclus) ;
  - supprimer le volume `worker_data` (:690-691) — **et uniquement celui-là** ;
  - vérifier `depends_on` : aucun service restant ne référence `windflow-worker` (grep dans le fichier) ;
  - **ne pas toucher** `API_WORKERS: 4` (:262 — workers uvicorn, homonymie piège) ni la section Redis ;
  - validation : `docker compose -f docker-compose.prod.yml config -q` (syntaxe + résolution des références).

**Dépend de :** Tâche 3

### Tâche 6 : Purge CI `.gitea/`

**Objectif :** CI verte sans job worker (AC 1 : « CI et tests verts »).

**Fichiers :**
- [`.gitea/workflows/build.yml`](../../.gitea/workflows/build.yml:63) — **Modifier** : supprimer le job `build-worker` (:63-103) ; dans le job summary :159-168, `needs: [build-api, build-frontend]` et retirer `build-worker` de la condition ;
- [`.gitea/workflows/ci.yml`](../../.gitea/workflows/ci.yml:326) — **Modifier** : supprimer le step « 🏗️ Build Worker image » (:326-333) ;
- vérifier qu'aucun autre workflow `.gitea/` ne référence worker/celery (grep).

**Dépend de :** Tâche 3

### Tâche 7 : Purge monitoring (Prometheus)

**Objectif :** supprimer le scrape et les alertes d'un worker qui n'existera plus (observabilité cohérente, rules 45).

**Fichiers :**
- [`infrastructure/docker/prometheus.yml`](../../infrastructure/docker/prometheus.yml:33) — **Modifier** : supprimer le job `windflow-worker` (:33-35) ;
- [`infrastructure/docker/prometheus-alerts.yml`](../../infrastructure/docker/prometheus-alerts.yml:216) — **Modifier** : supprimer les règles `CeleryWorkerDown`, `CeleryQueueBacklog`, `CeleryHighTaskFailureRate` — retirer le **groupe entier** s'il ne contient plus rien ( YAML invalide sinon) ;
- validation : `docker run --rm -v $(pwd)/infrastructure/docker/prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus --config.file=/etc/prometheus/prometheus.yml --dryrun` (ou à minima relecture YAML) — si l'image n'est pas disponible localement, valider le YAML (`python -c "import yaml,sys; yaml.safe_load(open('infrastructure/docker/prometheus.yml'))"` + idem alerts).

**Dépend de :** Tâche 3

### Tâche 8 : Purge env exemples, scripts d'install, .gitignore

**Objectif :** supprimer les variables d'environnement et affichages liés à Celery/Flower (AC 1 : « env » sans référence).

**Fichiers :**
- [`env.example`](../../env.example:202) — **Modifier** : supprimer la section CELERY (:202-221) et Flower (:232-234) ; **conserver** Redis (rate limiting) ;
- [`.env.prod.example`](../../.env.prod.example:83) — **Modifier** : reformuler le commentaire Redis (:83-84 — « rate limiting, cache » sans mention Celery) ; supprimer la section CELERY (:216-231) et Flower (:258-260) ;
- [`scripts/install.sh`](../../scripts/install.sh:463) — **Modifier** : retirer la ligne « • Celery Worker » (:463) de l'affichage des services (le minimal n'a jamais contenu de worker — affichage mensonger) ;
- [`.gitignore`](../../.gitignore:118) — **Modifier** : retirer les entrées `celerybeat-schedule` / `celerybeat.pid` (:118-121).

**Dépend de :** Tâche 3

### Tâche 9 : Nettoyage des commentaires/docstrings backend (runtime asyncio assumé)

**Objectif :** abolir le framing « fallback Celery » dans le code vivant — le runtime asyncio devient le discours canonique (AC 1 : code sans référence).

**Fichiers (Modifier, commentaires/docstrings uniquement — zéro comportement) :**
- [`backend/app/main.py`](../../backend/app/main.py:150) : commentaire de la boucle de santé (:150) → « periodic target health check (asyncio runtime — arbitrage F1, Celery purgé par STORY-130) » ; commentaire purge refresh (:172-174) → actualiser la mention (arbitrage consommé) ;
- [`backend/app/config.py`](../../backend/app/config.py:51) : même actualisation (:51-53) ;
- [`backend/app/tasks/background_tasks.py`](../../backend/app/tasks/background_tasks.py:1) : docstring module (:1-12) et docstrings de fonctions (:31-35, :476-479, :534-536) → « runtime asyncio canonique » (supprimer toute mention de fallback Celery) ;
- [`backend/app/models/scheduled_task.py`](../../backend/app/models/scheduled_task.py:2) : docstrings (:1-2, :34-36) → « tâches planifiées (moteur scheduler — STORY-160) » sans mention Celery Beat ;
- [`backend/app/services/scheduler_service.py`](../../backend/app/services/scheduler_service.py:4) : docstrings (:3-4, :164-165) — idem ;
- [`backend/app/services/deployment_orchestrator.py`](../../backend/app/services/deployment_orchestrator.py:4) : docstring (:3-5) → retirer « Remplace Celery » (formuler positivement : orchestrateur asyncio des déploiements).

**Dépend de :** Tâche 3

### Tâche 10 : Rules `.roo` + docs générales hors specs + écran grep

**Objectif :** satisfaire l'écran de contrôle AC 1 sur tout le dépôt, hors exclusions documentées (arbitrage n°5) — sans toucher aux `general_specs` (STORY-252).

**Fichiers :**
- [`.roo/rules/05-tech-stack.md`](../../.roo/rules/05-tech-stack.md:10) — **Modifier** : supprimer la ligne Celery ; préciser sur la ligne Redis « cache + rate limiting » (retirer « Streams pour event-driven » si mentionné avec Celery — vérifier le contexte exact de la ligne) ;
- [`.roo/rules/50-dev-workflow.md`](../../.roo/rules/50-dev-workflow.md:108) — **Modifier** : retirer la ligne `enable-workers`/`disable-workers` du tableau Extensions ;
- [`.roo/rules/55-project-structure.md`](../../.roo/rules/55-project-structure.md:32) — **Modifier** : retirer `celery_app.py` de l'arborescence documentée (:32-33) ; renommer le commentaire du répertoire `tasks/` en « Tâches async (asyncio runtime) » (:57-59) ;
- [`docs/Roadmap.md`](../../docs/Roadmap.md:100) — **Modifier** : « Celery pour tâches asynchrones » → « runtime asyncio pour tâches asynchrones » (Roadmap historique : corriger la mention sans réécrire l'historique) ;
- [`docs/technical_specs/ARCHITECTURE-MODULAIRE.md`](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md:109) — **Modifier** : mettre à jour la note d'écart (le worker et `make enable-workers` sont désormais **supprimés** — l'écart documenté est résolu par STORY-130) ;
- [`docs/technical_specs/WEBSOCKET-REAL-TIME.md`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md:274) — **Modifier** : reformuler la note sans framing Celery (le chemin d'exécution est asyncio, point final) ;
- **Écran de contrôle final** (AC 1) :
  ```bash
  grep -ri celery . \
    --exclude-dir={.backlog,.git,.venv,.venv-test,.idea,.mypy_cache,.ruff_cache,node_modules,htmlcov} \
    --exclude=coverage.xml \
    | grep -v -e 'docs/general_specs/' -e 'docs/backend_status.md' -e 'docs/backend_remediation_plan.md' -e 'CHANGELOG.md'
  # → sortie vide attendue (exclusions documentées : specs P3-4, snapshots d'audit, trace historique)
  ```
- puis `make clean-tests` pour régénérer les artefacts de couverture obsolètes qui référencent encore celery_app.

**Dépend de :** Tâches 3-9

### Tâche 11 : Tests unitaires — hash/upgrade + login API + garde-fou

**Objectif :** couvrir le mécanisme de migration (AC 2) et verrouiller la non-régression Celery (AC 1). Cible ≥ 80 % sur les fichiers touchés (rules 35).

**Fichiers :**
- [`backend/tests/unit/test_services/test_user_service.py`](../../backend/tests/unit/test_services/test_user_service.py) — **Modifier (étendre)** — nouveau bloc « hashage Argon2 / migration bcrypt » :
  - `hash_password` produit un préfixe `$argon2id$` ;
  - `verify_password` round-trip Argon2 ;
  - `verify_and_update` sur hash **bcrypt** (fixture générée via `CryptContext(schemes=["bcrypt"])` locale au test) → `(True, new_hash)` avec `new_hash.startswith("$argon2id$")` — **cœur AC 2** ;
  - `verify_and_update` sur hash **argon2** → `(True, None)` (pas de re-hash superflu — arbitrage n°2) ;
  - `verify_and_update` mot de passe faux → `(False, None)` ;
  - `verify_and_update`/`verify_password` sur hash illisible (préfixe inconnu, ex. `$scrypt$...`) → `(False, None)`/`False` **sans lever** (arbitrage n°9) ;
  - `verify_and_update_user` (session `AsyncMock`) : bcrypt → `user.hashed_password` mis à jour + `commit` appelé ; argon2 → pas de `commit` superflu ;
- `backend/tests/unit/test_api/test_auth_login_hash_upgrade.py` — **Créer** (patterns `_jwt_mode`/fixtures du conftest, DB de test) :
  - utilisateur seedé avec hash bcrypt (écriture directe en base) → `POST /auth/login` → **200** ; relecture DB : `hashed_password.startswith("$argon2id$")` (AC 2) ;
  - deuxième login (hash désormais argon2) → 200 — la boucle est stable ;
  - mot de passe faux → **401 générique** — aucune fuite du schème du hash (rules 40) ;
  - réponse login sans hash ni mot de passe (champs sensibles absents) ;
- `backend/tests/unit/test_no_celery_residue.py` — **Créer** (garde-fou, arbitrage n°8) :
  - `importlib.util.find_spec("app.celery_app") is None` ;
  - lecture de `pyproject.toml` via `tomllib` : aucune dépendance `celery` dans `[tool.poetry.dependencies]` ;
  - (optional) `infrastructure/docker/Dockerfile.worker` absent du disque.

**Dépend de :** Tâches 1-3

### Tâche 12 : Tests d'intégration — migration de bout en bout

**Objectif :** valider le parcours complet en conditions réelles (AC 2 + AC 4 : non-régression des flux auth).

**Fichiers :**
- `backend/tests/integration/test_password_hash_migration.py` — **Créer** (DB réelle, patterns [`test_auth_password_flow.py`](../../backend/tests/integration/test_auth_password_flow.py)) :
  - **flux complet** : seed utilisateur bcrypt → `POST /auth/login` (200) → hash DB devenu `$argon2id$` → `PUT /auth/password` avec l'ancien mot de passe d'origine (200 — preuve que la vérification bcrypt fonctionne aussi sur ce chemin) → login avec le nouveau mot de passe (200) ;
  - **non-régression argon2** : utilisateur créé via `POST /auth/register` → hash `$argon2id$` dès la création (AC 2) → login 200 → hash **inchangé** en base (pas de re-hash superflu) ;
  - **non-régression flux existants** : jouer les suites auth déjà vertes (`test_auth_password_flow.py`, `test_auth_api.py`, `test_auth_refresh_security.py`) — login username/email, register, refresh, disable_auth couverts par ces suites (AC 4).

**Dépend de :** Tâches 1-2, 11

### Tâche 13 : CHANGELOG + validation finale

**Objectif :** tracer les changements et valider l'ensemble (AC 1, AC 3, AC 4).

**Fichiers :**
- [`CHANGELOG.md`](../../CHANGELOG.md) — **Modifier** : entrée sous `[Unreleased]` (pattern STORY-126.3/128/129) :
  - **Changed** : « Password hashing : double lecture bcrypt legacy + re-hash automatique Argon2id au login (aucun reset de mot de passe requis — arbitrage F2) ; dépendance `bcrypt` ajoutée en transition (lecture seule) » ;
  - **Removed** : « Runtime Celery fantôme : `celery_app.py`, `Dockerfile.worker`, service compose `windflow-worker`, cibles Makefile `docker-build-worker`/`enable-workers`, jobs CI worker, scrape + alertes Prometheus, variables `CELERY_*`/Flower (arbitrage F1 — runtime asyncio unique) » ;
- **Notes d'implémentation (AC 3)** : documenter l'upgrade path — paramètres Argon2id par défaut (arbitrage n°2), double lecture permanente, stratégie paresseuse au login (arbitrage n°3), retraite de `bcrypt` → STORY-250, renvoi des corrections consolidées de specs 04/05/07/15/16 → STORY-252 (avec arbitrages F5/F1) ;

**Validation :**
```bash
make backend-lint                                # isort + black + flake8 + mypy + bandit
make backend-test-unit                           # dont test_user_service étendu, login upgrade, garde-fou
make backend-test-integration                    # dont test_password_hash_migration
make backend-test                                # AC 4 — global (baseline STORY-128 : 12 échecs préexistants documentés acceptés)
docker compose -f docker-compose.prod.yml config -q
docker compose -f docker-compose.minimal.yml -f docker-compose.extensions.yml config -q
make lint                                        # AC 4 (backend + frontend + cli)
# Écran grep AC 1 (cf. tâche 10) → sortie vide
```

**Dépend de :** Tâches 1-12

## Tests à écrire

> Récapitulatif (détail dans les tâches 11-12). Patterns : rules 35 (`httpx.AsyncClient` + `ASGITransport`, fixtures DB du conftest), helpers `unwrap`/`error_code`. Sécurité rules 40 : cette story n'ouvre aucun endpoint — les obligations 401/403/422/404 sont couvertes par **non-régression** des suites existantes + cas génériques ci-dessous.

### Backend — unitaires

- `backend/tests/unit/test_services/test_user_service.py` (extension) — `$argon2id$` en écriture ; double lecture bcrypt→Argon2id via `verify_and_update` ; pas de re-hash superflu sur hash argon2 ; mot de passe faux → `(False, None)` ; hash illisible → échec silencieux sans exception ; `verify_and_update_user` persiste le re-hash (commit).
- `backend/tests/unit/test_api/test_auth_login_hash_upgrade.py` (création) — login d'un compte bcrypt → 200 + hash DB re-haché Argon2id (AC 2) ; login suivant 200 ; mot de passe faux → 401 générique (anti-énumération, aucune fuite du schème) ; réponse sans champ sensible.
- `backend/tests/unit/test_no_celery_residue.py` (création, garde-fou) — module `app.celery_app` absent ; aucune dépendance celery dans pyproject ; `Dockerfile.worker` absent.

### Backend — intégration

- `backend/tests/integration/test_password_hash_migration.py` (création) — flux complet bcrypt → login (re-hash) → `PUT /auth/password` → login nouveau mot de passe ; register → Argon2id dès création, hash stable ; non-régression des suites auth existantes (login username/email, register, refresh, disable_auth — AC 4).

### Frontend / CLI

- *(non applicable — aucun contrat API modifié : comportement interne de hashage + suppressions d'infra)*

### Commandes de validation

```bash
poetry run pytest backend/tests/unit/test_services/test_user_service.py backend/tests/unit/test_api/test_auth_login_hash_upgrade.py backend/tests/unit/test_no_celery_residue.py -v
poetry run pytest backend/tests/integration/test_password_hash_migration.py backend/tests/integration/test_auth_password_flow.py -v
make backend-lint
make backend-test
docker compose -f docker-compose.prod.yml config -q
```

## Notes d'implémentation

*(ajoutées à la clôture par treat-story — y consigner, pour l'AC 3 : paramètres Argon2id retenus, double lecture, renvois STORY-250/252)*
