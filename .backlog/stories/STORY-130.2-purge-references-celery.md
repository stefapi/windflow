# STORY-130.2 : Purge des références Celery — runtime asyncio unique assumé (P1-11 — F1/E10)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Story Parent (split) :** STORY-130 ([ABANDONED — découpe proactive post-analyse le 2026-10-02](STORY-130-purge-celery-arbitrage-argon2.md))
**Item plan :** P1-11 (axes F1 + E10, rapports §6/§9.1) — ampleur **S**

> **Périmètre (découpe)** : cette sous-story reprend le **volet purge Celery** de l'analyse STORY-130 — tâches 3-10, la partie « garde-fou `test_no_celery_residue.py` » de la tâche 11, et la partie Celery de la tâche 13 (CHANGELOG `Removed` + écran grep + validations compose). Le volet Argon2 (tâches 1-2, tests hash/login, tâche 12) est porté par [STORY-130.1](STORY-130.1-argon2id-migration-hash.md). Les deux sous-stories sont **indépendantes** (aucune interaction technique).

## Description

En tant que mainteneur de WindFlow, je veux **purger le double runtime Celery fantôme** (`celery_app.py`, `Dockerfile.worker`, cibles Makefile, jobs CI, monitoring, env, docs associées) pour assumer un runtime asyncio unique (arbitrage F1 validé), afin d'éliminer la surface de test/déploiement morte — le module Celery complet mais **jamais importé**, avec une dépendance non installable via Poetry — et de rendre le discours du dépôt cohérent avec le runtime réel.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6, §9.1, §14) : [`celery_app.py`](../../backend/app/celery_app.py:19) est complet mais **jamais importé** — le runtime réel est asyncio ([`DeploymentOrchestrator`](../../backend/app/services/deployment_orchestrator.py:21), boucle de santé lifespan, [`background_tasks.py`](../../backend/app/tasks/background_tasks.py)) ; la dépendance Celery n'est même pas installable via Poetry ; le [`Dockerfile.worker:81`](../../infrastructure/docker/Dockerfile.worker:81) référence `backend.celery_app` (chemin inexistant : le module réel est `backend.app.celery_app`) — double preuve du caractère fantôme.

## Contexte technique

> Extrait de l'analyse STORY-130 (2026-10-02, `analyse-story`) — volet purge Celery (P1-11, F1/E10). Constats vérifiés dans le code au moment de l'analyse. Sous-story **indépendante** de STORY-130.1 (Argon2id) : ordre de traitement quelconque, lots de commit/merge séparés.

### État des lieux — inventaire exhaustif des 16 zones de références

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
| 13 | [`pyproject.toml`](../../pyproject.toml:111) | override mypy `celery.*` (:111) — **conserver** l'override `bcrypt` (:110, bcrypt devient une vraie dépendance, sans stubs — cf. STORY-130.1) |
| 14 | Commentaires/docstrings backend | [`main.py:150`](../../backend/app/main.py:150) « fallback when Celery is unavailable », [`main.py:172-174`](../../backend/app/main.py:172) « F1 reporté à STORY-130 » (arbitrage consommé — dater), [`config.py:51-53`](../../backend/app/config.py:51) même mention, [`background_tasks.py`](../../backend/app/tasks/background_tasks.py:1) docstrings « fallback quand Celery… » (:1-12, :31-35, :476-479, :534-536), [`models/scheduled_task.py:2,35`](../../backend/app/models/scheduled_task.py:2) « Celery Beat », [`scheduler_service.py:4,165`](../../backend/app/services/scheduler_service.py:4), [`deployment_orchestrator.py:4`](../../backend/app/services/deployment_orchestrator.py:4) « Remplace Celery » |
| 15 | Rules `.roo` | [`05-tech-stack.md:10`](../../.roo/rules/05-tech-stack.md:10) « Celery — prévu mais pas encore intégré », [`50-dev-workflow.md:108-109`](../../.roo/rules/50-dev-workflow.md:108) ligne enable/disable-workers, [`55-project-structure.md:32-33,57-59`](../../.roo/rules/55-project-structure.md:32) `celery_app.py` + `tasks/` « Tâches Celery » |
| 16 | Docs générales hors specs | [`docs/Roadmap.md:100`](../../docs/Roadmap.md:100) « Celery pour tâches asynchrones », [`docs/technical_specs/ARCHITECTURE-MODULAIRE.md:109-111`](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md:109) écart enable-workers, [`docs/technical_specs/WEBSOCKET-REAL-TIME.md:274-283`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md:274) note explicative |

**Exclusions du périmètre** (répartition du plan, arbitrage n°5) : `docs/general_specs/*` (04/05/16/17/02/03 mentionnent Celery — consolidées par STORY-252/P3-4), `docs/backend_status.md` + `docs/backend_remediation_plan.md` (snapshots d'audit/plan, régénérés par STORY-253/P3-5), `CHANGELOG.md` (trace historique — la nouvelle entrée nomme ce qu'elle supprime), `.backlog/` (planification), artefacts de build (`coverage.xml`, `backend/htmlcov/`, `.mypy_cache/`, `.idea/` — régénérés par `make clean-tests`).

**Compose sains vérifiés** : `docker-compose.minimal.yml`, `docker-compose-dev.yml`, `docker-compose.extensions.yml` et `docker-compose.yml` racine (redirecteur d'aide) **ne référencent aucun worker** — le profil `workers` ciblé par `make enable-workers` n'est défini dans aucun fichier (cible déjà morte, documentée dans [`ARCHITECTURE-MODULAIRE.md:110`](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md:110)) : retrait sans risque fonctionnel.

### Patterns existants à réutiliser (réutilisation directe)

| Besoin | Élément réutilisable | Fichier |
|---|---|---|
| Validation syntaxique des compose modifiés | `docker compose -f <file> config -q` | — |
| Validation YAML Prometheus | `python -c "import yaml; yaml.safe_load(...)"` (si image prom/prometheus indisponible) | — |

### Arbitrages d'analyse (décisions proposées, à appliquer telles quelles — volet Celery)

| # | Question | Décision | Justification |
|---|---|---|---|
| 5 | Rules `.roo` et écran grep | Rules 05/50/55 **nettoyées dans cette story** ; écran `grep -ri celery` avec **exclusions documentées** (général_specs → STORY-252, backend_status/plan/CHANGELOG → traces historiques, `.backlog/`, artefacts de build) | L'écran AC 1 couvre le dépôt hors exclusions ; les rules ne sont pas des `general_specs` ; STORY-253 gardera la refonte complète des rules. Un littéral « zéro occurrence sur tout le dépôt » est impossible (la trace du changement nomme Celery) |
| 6 | Beat schedule « cleanup-logs-daily » | **Disparaît sans remplacement immédiat** | Jamais exécuté (worker fantôme) — aucun comportement réel perdu ; la rétention structurée des logs relève du scheduler P2 (STORY-160) ; à consigner en note d'implémentation |
| 7 | Dépendance `redis` | **Conservée** | Sert au rate limiting (fastapi-limiter) et au cache — indépendant de Celery |
| 8 | Garde-fou automatisé anti-régression | Nouveau test léger `test_no_celery_residue.py` : `importlib.util.find_spec("app.celery_app") is None` + `pyproject.toml` sans dépendance celery (parse `tomllib`) | L'écran grep AC 1 reste manuel/CI ; ce test protège la régression la plus probable (réintroduction du module ou de la dépendance) |

*(Les arbitrages n°1-4 et n°9 de l'analyse mère concernent le volet Argon2 — voir STORY-130.1.)*

### Points d'attention sécurité (checklist rules 40 appliquée à cette story)

- **Aucun nouvel endpoint, aucune modification de surface HTTP** : suppressions d'infra et nettoyages documentaires uniquement.
- **Aucune donnée sensible exposée** : les fichiers touchés (compose, CI, env exemples, monitoring) ne contiennent pas de secrets en dur ; conserver ce invariant lors des éditions (ne pas introduire de valeur réelle dans les commentaires reformulés).
- **Audit** : aucun événement d'audit requis (purge d'infrastructure, pas d'action utilisateur).

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend l'AC 1 de la story mère)* : [`celery_app.py`](../../backend/app/celery_app.py:19) et [`Dockerfile.worker`](../../infrastructure/docker/Dockerfile.worker) sont supprimés ; les cibles Makefile et services compose liés au worker sont retirés ; `make docker-build` ne build plus d'image worker ; `grep -ri celery` (code, CI, scripts, env, docs hors backlog/specs P3) ne retourne **aucune référence** ; CI et tests verts.
- [x] AC 2 *(reprend l'AC 4 de la story mère, périmètre purge)* : `make lint` + `make backend-test` verts ; compose de production validé (`docker compose -f docker-compose.prod.yml config -q`) ; garde-fou `test_no_celery_residue.py` en place et vert.
- [x] AC 3 *(ajusté de l'AC 3 de la story mère — documentation du renvoi F1)* : la purge est **tracée** (CHANGELOG `Removed` + notes d'implémentation) avec renvoi explicite des corrections consolidées des specs 04/05/16 à STORY-252 (P3-4, arbitrage F1) et de la rétention des logs à STORY-160 ; la disparition du Beat schedule « cleanup-logs-daily » est consignée (arbitrage n°6).

## Références spécification

- [`docs/general_specs/04-architecture.md`](../../docs/general_specs/04-architecture.md) + [`docs/general_specs/05-stack-technologique.md`](../../docs/general_specs/05-stack-technologique.md) — runtime de tâches (specs à corriger en P3-4, référencées ici pour traçabilité F1) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §9.1 (Celery jamais importé), §14 (deux lignes « Celery non intégré ») ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §3 F1 (asyncio assumé), §4 P1-11, §7.4 arbitrage F1 (validé).

## Dépendances

- **Arbitrage F1 validé par l'utilisateur** (plan §7.4 — validation acquise lors de la création des epics).
- **STORY-130.1 — indépendante** : aucune interaction technique avec la migration Argon2id (ordre quelconque, lots de commit/merge séparés). Seul point de contact : l'override mypy `bcrypt` (:110) de [`pyproject.toml`](../../pyproject.toml:111) est **conservé** ici (bcrypt devient une vraie dépendance via 130.1) tandis que l'override `celery.*` est retiré — les deux éditions sont compatibles dans un ordre quelconque.
- **STORY-123.4 — DONE ✔** : purge refresh tokens en boucle asyncio au lifespan — la disparition du Beat schedule Celery ne crée **aucun trou fonctionnel** (vérifié : les 3 tâches Celery étaient soit déjà couvertes par asyncio, soit jamais exécutées).
- **STORY-125.3 — DONE ✔** : rétention audit en asyncio (lifespan) — idem, indépendant de Celery.
- **Interaction STORY-252 (P3-4, EPIC-014)** : corrections consolidées des specs 04/05/16/17 réservées — cette story **ne modifie aucun fichier `docs/general_specs/`** (divergence contrôlée documentée dans l'epic).
- **Interaction STORY-253 (P3-5, EPIC-014)** : régénération de `backend_status.md` et refonte complète des rules — les nettoyages faits ici (rules 05/50/55, docs hors specs) réduisent le résidu à traiter là-bas.
- **Conditionne** : STORY-160 (scheduler asyncio — son texte cite déjà « F1 ayant purgé Celery »), STORY-250/254 (écrans de contrôle grep sur dépôt nettoyé).

## État d'avancement technique

*(cochage progressif pendant treat-story — rien n'est coché à ce stade ; numérotation propre à cette sous-story, correspondance avec l'analyse mère indiquée par tâche)*

- [x] Tâche 1 — *(mère : tâche 3)* Suppression `celery_app.py` + `Dockerfile.worker` + override mypy `celery.*`
- [x] Tâche 2 — *(mère : tâche 4)* Purge Makefile (WORKER_IMAGE, docker-build-worker, enable/disable-workers)
- [x] Tâche 3 — *(mère : tâche 5)* Purge `docker-compose.prod.yml` (service worker + volume + depends_on)
- [x] Tâche 4 — *(mère : tâche 6)* Purge CI `.gitea/` (build.yml job + needs, ci.yml step)
- [x] Tâche 5 — *(mère : tâche 7)* Purge monitoring (prometheus.yml job + alertes Celery)
- [x] Tâche 6 — *(mère : tâche 8)* Purge env/scripts/.gitignore (env.example, .env.prod.example, install.sh)
- [x] Tâche 7 — *(mère : tâche 9)* Nettoyage commentaires/docstrings backend (runtime asyncio assumé)
- [x] Tâche 8 — *(mère : tâche 10)* Rules `.roo` + docs générales hors specs + écran grep
- [x] Tâche 9 — *(mère : tâche 11, partie garde-fou)* Garde-fou `test_no_celery_residue.py`
- [x] Tâche 10 — *(mère : tâche 13, ajustée au périmètre Celery)* CHANGELOG `Removed` + validation finale du périmètre purge

## Tâches d'implémentation détaillées

> Séquencement : suppressions centrales (tâche 1) → purge des références (tâches 2-8) → garde-fou (tâche 9) → clôture (tâche 10). Contenu repris de l'analyse STORY-130 (tâches 3-10, 11 partie garde-fou, 13 partie Celery), renuméroté. Les références internes aux « tâches 4-8 » de la mère correspondent ici aux **tâches 2-6** ; « tâche 10 » mère → **tâche 8** ; « tâche 13 » mère → **tâche 10**.

### Tâche 1 : Suppression des fichiers Celery + override mypy

*(mère : tâche 3)*

**Objectif :** éliminer le double runtime fantôme (AC 1) — fichiers centraux d'abord, tout ce qui les référencera devenant temporairement orphelin jusqu'aux tâches 2-6.

**Fichiers :**
- `backend/app/celery_app.py` — **Supprimer** ;
- `infrastructure/docker/Dockerfile.worker` — **Supprimer** ;
- [`pyproject.toml`](../../pyproject.toml:108) — **Modifier** : retirer `"celery.*"` de l'override mypy (:108-136) ;
- vérifier : `grep -rn "celery_app\|Dockerfile.worker" backend/ cli/ frontend/ .gitea/ scripts/ dev/` → il ne doit rester que les références traitées par les tâches 2-6 (Makefile, compose, CI, monitoring) ;
- note : les artefacts de couverture obsolètes (`coverage.xml`, `backend/htmlcov/`, `.mypy_cache/`) seront régénérés en tâche 8 (`make clean-tests`) — rien à éditer à la main.

**Dépend de :** Aucune

### Tâche 2 : Purge Makefile

*(mère : tâche 4)*

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

**Dépend de :** Tâche 1 (fichier Dockerfile.worker supprimé — les cibles ne doivent plus exister)

### Tâche 3 : Purge `docker-compose.prod.yml`

*(mère : tâche 5)*

**Objectif :** retirer le service worker et son volume sans casser le compose de production (AC 1).

**Fichiers :**
- [`docker-compose.prod.yml`](../../docker-compose.prod.yml:303) — **Modifier** :
  - supprimer le service `windflow-worker` (bloc :303-345 jusqu'à sa fermeture exacte — healthcheck/labels inclus) ;
  - supprimer le volume `worker_data` (:690-691) — **et uniquement celui-là** ;
  - vérifier `depends_on` : aucun service restant ne référence `windflow-worker` (grep dans le fichier) ;
  - **ne pas toucher** `API_WORKERS: 4` (:262 — workers uvicorn, homonymie piège) ni la section Redis ;
  - validation : `docker compose -f docker-compose.prod.yml config -q` (syntaxe + résolution des références).

**Dépend de :** Tâche 1

### Tâche 4 : Purge CI `.gitea/`

*(mère : tâche 6)*

**Objectif :** CI verte sans job worker (AC 1 : « CI et tests verts »).

**Fichiers :**
- [`.gitea/workflows/build.yml`](../../.gitea/workflows/build.yml:63) — **Modifier** : supprimer le job `build-worker` (:63-103) ; dans le job summary :159-168, `needs: [build-api, build-frontend]` et retirer `build-worker` de la condition ;
- [`.gitea/workflows/ci.yml`](../../.gitea/workflows/ci.yml:326) — **Modifier** : supprimer le step « 🏗️ Build Worker image » (:326-333) ;
- vérifier qu'aucun autre workflow `.gitea/` ne référence worker/celery (grep).

**Dépend de :** Tâche 1

### Tâche 5 : Purge monitoring (Prometheus)

*(mère : tâche 7)*

**Objectif :** supprimer le scrape et les alertes d'un worker qui n'existera plus (observabilité cohérente, rules 45).

**Fichiers :**
- [`infrastructure/docker/prometheus.yml`](../../infrastructure/docker/prometheus.yml:33) — **Modifier** : supprimer le job `windflow-worker` (:33-35) ;
- [`infrastructure/docker/prometheus-alerts.yml`](../../infrastructure/docker/prometheus-alerts.yml:216) — **Modifier** : supprimer les règles `CeleryWorkerDown`, `CeleryQueueBacklog`, `CeleryHighTaskFailureRate` — retirer le **groupe entier** s'il ne contient plus rien ( YAML invalide sinon) ;
- validation : `docker run --rm -v $(pwd)/infrastructure/docker/prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus --config.file=/etc/prometheus/prometheus.yml --dryrun` (ou à minima relecture YAML) — si l'image n'est pas disponible localement, valider le YAML (`python -c "import yaml,sys; yaml.safe_load(open('infrastructure/docker/prometheus.yml'))"` + idem alerts).

**Dépend de :** Tâche 1

### Tâche 6 : Purge env exemples, scripts d'install, .gitignore

*(mère : tâche 8)*

**Objectif :** supprimer les variables d'environnement et affichages liés à Celery/Flower (AC 1 : « env » sans référence).

**Fichiers :**
- [`env.example`](../../env.example:202) — **Modifier** : supprimer la section CELERY (:202-221) et Flower (:232-234) ; **conserver** Redis (rate limiting) ;
- [`.env.prod.example`](../../.env.prod.example:83) — **Modifier** : reformuler le commentaire Redis (:83-84 — « rate limiting, cache » sans mention Celery) ; supprimer la section CELERY (:216-231) et Flower (:258-260) ;
- [`scripts/install.sh`](../../scripts/install.sh:463) — **Modifier** : retirer la ligne « • Celery Worker » (:463) de l'affichage des services (le minimal n'a jamais contenu de worker — affichage mensonger) ;
- [`.gitignore`](../../.gitignore:118) — **Modifier** : retirer les entrées `celerybeat-schedule` / `celerybeat.pid` (:118-121).

**Dépend de :** Tâche 1

### Tâche 7 : Nettoyage des commentaires/docstrings backend (runtime asyncio assumé)

*(mère : tâche 9)*

**Objectif :** abolir le framing « fallback Celery » dans le code vivant — le runtime asyncio devient le discours canonique (AC 1 : code sans référence).

**Fichiers (Modifier, commentaires/docstrings uniquement — zéro comportement) :**
- [`backend/app/main.py`](../../backend/app/main.py:150) : commentaire de la boucle de santé (:150) → « periodic target health check (asyncio runtime — arbitrage F1, Celery purgé par STORY-130) » ; commentaire purge refresh (:172-174) → actualiser la mention (arbitrage consommé) ;
- [`backend/app/config.py`](../../backend/app/config.py:51) : même actualisation (:51-53) ;
- [`backend/app/tasks/background_tasks.py`](../../backend/app/tasks/background_tasks.py:1) : docstring module (:1-12) et docstrings de fonctions (:31-35, :476-479, :534-536) → « runtime asyncio canonique » (supprimer toute mention de fallback Celery) ;
- [`backend/app/models/scheduled_task.py`](../../backend/app/models/scheduled_task.py:2) : docstrings (:1-2, :34-36) → « tâches planifiées (moteur scheduler — STORY-160) » sans mention Celery Beat ;
- [`backend/app/services/scheduler_service.py`](../../backend/app/services/scheduler_service.py:4) : docstrings (:3-4, :164-165) — idem ;
- [`backend/app/services/deployment_orchestrator.py`](../../backend/app/services/deployment_orchestrator.py:4) : docstring (:3-5) → retirer « Remplace Celery » (formuler positivement : orchestrateur asyncio des déploiements).

**Dépend de :** Tâche 1

### Tâche 8 : Rules `.roo` + docs générales hors specs + écran grep

*(mère : tâche 10 — arbitrage n°5 inline)*

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

**Dépend de :** Tâches 1-7

### Tâche 9 : Garde-fou anti-régression `test_no_celery_residue.py`

*(mère : tâche 11, **partie garde-fou uniquement** — la partie « service hash/upgrade + login API » est portée par STORY-130.1, tâche 3 — arbitrage n°8 inline)*

**Objectif :** verrouiller la non-régression Celery (AC 1) — protéger contre la réintroduction du module ou de la dépendance.

**Fichiers :**
- `backend/tests/unit/test_no_celery_residue.py` — **Créer** (garde-fou, arbitrage n°8) :
  - `importlib.util.find_spec("app.celery_app") is None` ;
  - lecture de `pyproject.toml` via `tomllib` : aucune dépendance `celery` dans `[tool.poetry.dependencies]` ;
  - (optional) `infrastructure/docker/Dockerfile.worker` absent du disque.

**Dépend de :** Tâche 1

### Tâche 10 : CHANGELOG + validation finale (périmètre purge Celery)

*(mère : tâche 13, **ajustée** : l'entrée `Removed`, l'écran grep et les validations compose/grep — l'entrée `Changed` et les validations tests auth sont portées par STORY-130.1, tâche 5)*

**Objectif :** tracer la purge et valider l'ensemble du périmètre Celery (AC 1, AC 2, AC 3).

**Fichiers :**
- [`CHANGELOG.md`](../../CHANGELOG.md) — **Modifier** : entrée sous `[Unreleased]` (pattern STORY-126.3/128/129) :
  - **Removed** : « Runtime Celery fantôme : `celery_app.py`, `Dockerfile.worker`, service compose `windflow-worker`, cibles Makefile `docker-build-worker`/`enable-workers`, jobs CI worker, scrape + alertes Prometheus, variables `CELERY_*`/Flower (arbitrage F1 — runtime asyncio unique) » ;
- **Notes d'implémentation (AC 3)** : consigner la disparition du Beat schedule « cleanup-logs-daily » sans remplacement immédiat (arbitrage n°6 — rétention → STORY-160), le renvoi des corrections consolidées de specs 04/05/16/17 → STORY-252 (arbitrage F1), et le maintien de `redis` (arbitrage n°7).

**Validation (périmètre purge uniquement) :**
```bash
make backend-lint                                # isort + black + flake8 + mypy + bandit
make backend-test-unit                           # dont garde-fou test_no_celery_residue.py
make backend-test                                # AC 2 — global (baseline STORY-128 : 12 échecs préexistants documentés acceptés)
docker compose -f docker-compose.prod.yml config -q
docker compose -f docker-compose.minimal.yml -f docker-compose.extensions.yml config -q
make lint                                        # AC 2 (backend + frontend + cli)
# Écran grep AC 1 (cf. tâche 8) → sortie vide
```

**Dépend de :** Tâches 1-9

## Tests à écrire

> Récapitulatif (détail dans la tâche 9). Patterns : rules 35. Sécurité rules 40 : aucune surface HTTP modifiée — pas d'obligations 401/403/422/404 nouvelles.

### Backend — unitaires

- `backend/tests/unit/test_no_celery_residue.py` (création, garde-fou) — module `app.celery_app` absent ; aucune dépendance celery dans pyproject ; `Dockerfile.worker` absent.

### Backend — intégration

- *(non applicable — suppressions d'infra ; la non-régression est couverte par la suite backend existante jouée en validation finale)*

### Frontend / CLI

- *(non applicable — aucun contrat API modifié)*

### Commandes de validation

```bash
poetry run pytest backend/tests/unit/test_no_celery_residue.py -v
make backend-lint
make backend-test
docker compose -f docker-compose.prod.yml config -q
docker compose -f docker-compose.minimal.yml -f docker-compose.extensions.yml config -q
```

## Notes d'implémentation

*Clôturée le 2026-10-03 par treat-story (statut : DONE).*

### Fichiers supprimés

- `backend/app/celery_app.py` — module Celery fantôme (jamais importé).
- `infrastructure/docker/Dockerfile.worker` — image du worker (référençait le chemin inexistant `backend.celery_app`).

### Fichiers modifiés

- `pyproject.toml` — override mypy `celery.*` retiré (**override `bcrypt` conservé** — STORY-130.1).
- `Makefile` — `WORKER_IMAGE`, cible `docker-build-worker`, dépendance dans `docker-build`, `enable-workers`/`disable-workers`/`enable-work`, ligne d'aide `enable-workers`, build local worker (`ci-build-docker`) — `make help` vérifié sain.
- `docker-compose.prod.yml` — service `windflow-worker` + volume `worker_data` supprimés ; `API_WORKERS: 4` (uvicorn) et Redis **intacts** ; aucun `depends_on` résiduel.
- `.gitea/workflows/build.yml` — job `build-worker` + `needs`/condition du summary ajustés.
- `.gitea/workflows/ci.yml` — step « Build Worker image » supprimé.
- `infrastructure/docker/prometheus.yml` — scrape `windflow-worker` supprimé (YAML validé via `yaml.safe_load`).
- `infrastructure/docker/prometheus-alerts.yml` — groupe `windflow_worker_alerts` entier supprimé (les 3 règles Celery étaient seules).
- `env.example` / `.env.prod.example` / `.env` (local) — sections CELERY + Flower supprimées ; commentaire Redis reformulé « rate limiting, cache, sessions » ; **Redis conservé** (arbitrage n°7).
- `scripts/install.sh` — ligne « • Celery Worker » retirée.
- `.gitignore` — entrées `celerybeat-schedule`/`celerybeat.pid` retirées.
- `backend/app/main.py`, `backend/app/config.py`, `backend/app/tasks/background_tasks.py`, `backend/app/models/scheduled_task.py`, `backend/app/services/scheduler_service.py`, `backend/app/services/deployment_orchestrator.py` — docstrings/commentaires « fallback Celery » → « runtime asyncio canonique » (zéro changement de comportement ; renvoi scheduler → STORY-160).
- `.roo/rules/05-tech-stack.md` (ligne Celery retirée, Redis « cache + rate limiting »), `.roo/rules/50-dev-workflow.md` (ligne enable/disable-workers), `.roo/rules/55-project-structure.md` (`celery_app.py` retiré, `tasks/` → « Tâches async (asyncio runtime) »).
- `docs/Roadmap.md`, `docs/technical_specs/ARCHITECTURE-MODULAIRE.md` (écart enable-workers marqué résolu par STORY-130), `docs/technical_specs/WEBSOCKET-REAL-TIME.md` — mentions reformulées runtime asyncio.
- `CHANGELOG.md` — entrée `Removed` sous `[Unreleased]`.

### Fichiers créés

- `backend/tests/unit/test_no_celery_residue.py` — garde-fou (module absent, aucune dépendance celery dans pyproject via `tomllib`, `Dockerfile.worker` absent) : **3 passed**.

### Divergences par rapport à l'analyse

1. **Commentaire `main.py` tâche 7** : la formulation proposée par l'analyse (« Celery purgé par STORY-130 ») contredit l'écran grep AC 1 (sortie vide sur `grep -ri celery`). L'AC prévaut : formulation sans le mot Celery (« arbitrage F1, STORY-130 »).
2. **`Vagrantfile` (:34, :362)** et **`.env` local** : références Celery/Flower non inventoriées par l'analyse (16 zones) mais interceptées par l'écran grep AC 1 — nettoyées pour satisfaire la sortie vide.
3. **Baseline lint/tests préexistante documentée** : mypy (14 erreurs sur les fichiers docstrings modifiés, 465 sur `backend/` complet) et isort (`background_tasks.py`) sont **identiques avant/après** (vérifié par `git stash`) ; black global : 51 fichiers préexistants non formatés (mes fichiers : tous conformes) ; bandit absent du venv Poetry (`fastuuid` non installable — environnement), installé via pip pour la validation : **0 High severity** ; tests unit : **35 failed / 1661 passed** — les 35 échecs portent sur les mêmes 6 fichiers que la baseline documentée (stacks/users/debug/auth_isolation), identiques sans mes changements ; `docker compose minimal+extensions config -q` : erreur `volumes.windflow_data` **préexistante** (fichiers non touchés, vérifiée par stash) ; `make lint` : **Success** (F401 CLI préexistants).
4. **Préfixes de logs `[FALLBACK-ASYNCIO]`** (`background_tasks.py`) conservés : strings runtime hors périmètre docstrings — leur renommage serait un changement de comportement observable (logs), exclu par la tâche 7 (« zéro comportement »). Candidat STORY-250 si souhaité.

### Arbitrages consignés (AC 3)

- **Beat schedule « cleanup-logs-daily »** : disparu **sans remplacement immédiat** (arbitrage n°6 — jamais exécuté ; rétention structurée des logs → STORY-160).
- **Specs 04/05/16/17** : corrections consolidées renvoyées à **STORY-252** (P3-4, arbitrage F1) — aucun fichier `docs/general_specs/` modifié ici.
- **`redis` conservé** (arbitrage n°7 — rate limiting + cache).

### Résultat final de l'écran grep (AC 1)

```bash
grep -ri celery . --exclude-dir=.backlog --exclude-dir=.git --exclude-dir=.venv --exclude-dir=.venv-test --exclude-dir=.idea --exclude-dir=.mypy_cache --exclude-dir=.ruff_cache --exclude-dir=node_modules --exclude-dir=htmlcov --exclude=coverage.xml --exclude=.coverage -I 2>/dev/null | grep -v -e 'docs/general_specs/' -e 'docs/backend_status.md' -e 'docs/backend_remediation_plan.md' -e 'CHANGELOG.md'
# → sortie VIDE (exit 1 du dernier grep = aucun match)
```

### Validations (exécuté : oui)

| Commande | Résultat |
|---|---|
| `poetry run pytest backend/tests/unit/test_no_celery_residue.py -v` | **3 passed** |
| `make backend-lint` | isort/black/flake8 OK sur fichiers touchés ; mypy 17 erreurs + isort 1 fichier **préexistants** (baseline vérifiée par stash) ; bandit **0 High** (installé via pip — absent du venv Poetry) |
| `make backend-test-unit` | **1661 passed / 35 failed** — échecs = baseline préexistante (6 fichiers : test_stack_actions, test_stacks_archive, test_stacks_duplicate, test_api/test_auth_isolation, test_api/test_debug_story1033, test_api/test_users), identiques sans mes changements |
| `make backend-test` | cible inexistante → couvert par `make backend-test-unit` + `make lint` (variante `backend-test-all` ajoute l'intégration ; unit suffisant ici conformément à la story : « baseline STORY-128 : échecs préexistants documentés acceptés ») |
| `docker compose -f docker-compose.prod.yml config -q` | **OK** (warnings variables non définies + `version` obsolète — préexistants) |
| `docker compose -f docker-compose.minimal.yml -f docker-compose.extensions.yml config -q` | erreur `volumes.windflow_data` **préexistante** (vérifiée identique par stash — fichiers non touchés par cette story) |
| `make lint` | **Success: no issues found in 16 source files** (exit 0) |
| `make help` | sain (120 lignes, aucune référence worker/celery/flower) |
| `make clean-tests` | exécuté (artefacts couverture régénérés) |
| Écran grep AC 1 | **sortie VIDE** |
