# STORY-253 : Mise à jour documentaire post-remédiation — `backend_status.md`, rules `.roo`, CHANGELOG (P3-5)

**Statut :** DONE
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)
**Item plan :** P3-5 (rangement documentaire) — ampleur **S/M**

> ⚠️ **Numérotation** : cette story porte le numéro STORY-253 conformément au découpage final de la phase 5 (les éditions antérieures citaient « STORY-254 » pour le rangement documentaire — la phase 5 a réordonné : 253 = rangement documentaire, 254 = revue finale de conformité).

## Description

En tant que développeur WindFlow, je veux régénérer et mettre à jour la documentation d'état du projet après exécution des vagues P0-P2 — [`docs/backend_status.md`](../../docs/backend_status.md) (inventaire réel du code), les rules `.roo` pertinentes (40-sécurité, 20-architecture, 35-tests) et le CHANGELOG — afin que la documentation interne décrive **l'état réel post-remédiation** et ne perpétue plus d'écart « annoncé vs réel ».

**Problème constaté** : [`backend_status.md`](../../docs/backend_status.md) (daté du 30/08/2026) décrit l'état **pré-remédiation** : RBAC binaire, credentials en clair, Celery fantôme, scheduler CRUD sans moteur, absence d'Alembic, zones de test à zéro… Après les vagues P0-P2, la majorité de ces constats sera obsolète. Les rules `.roo` contiennent des mentions devenues fausses (ex. 05-tech-stack : « Celery prévu mais pas encore intégré », mention Dockerfile.worker) et le CHANGELOG ne trace pas encore la remédiation.

## Contexte technique

*(rempli par analyse-story — 2026-11-01)*

### Constats d'exploration (état réel du code et des documents au 2026-11-01)

**A. [`docs/backend_status.md`](../../docs/backend_status.md) (729 lignes, daté 30/08/2026) — sections obsolètes identifiées ligne à ligne :**

| Section (lignes) | Constat pré-remédiation | État réel post-remédiation (source de vérité à re-vérifier par inspection, D2) |
|---|---|---|
| En-tête l.3, avertissement l.7 | édition du 30/08/2026 « analyse en lecture seule » | nouvelle édition à dater, traçant le lien avec [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) exécuté |
| §1 l.33-53 | ~135 fichiers, 10 modèles, « **Point majeur :** pas de dossier `backend/alembic/` », `celery_app.py` cité l.38 | 13 migrations dans [`backend/alembic/versions/`](../../backend/alembic/versions) (baseline `2026_09_07` → `1671_deployment_events`), 19 modèles ORM dans [`models/`](../../backend/app/models), `celery_app.py` purgé ; recompter les fichiers |
| §2.2 Lifespan l.72-82 | 1 boucle santé « fallback quand Celery est indisponible » | 6 tâches lifespan dans [`main.py`](../../backend/app/main.py) l.231-475 : health-check, purge refresh tokens, purge audit, purge executions, purge deployment events, **SchedulerEngine** (STORY-160.2) |
| §2.4 Montage l.95-99 | 17 routers avec `/workflows`, `/targets` | `/workflows` supprimé (STORY-250.1) ; `/hosts` canonique (6 sous-modules `crud/connectivity/capabilities/fingerprints/scanning/helpers`) + alias `/targets` **déprécié** (STORY-166.2) ; routers ajoutés : `system.py` (STORY-129), `metrics.py` (STORY-172), `ssh_keys.py` (STORY-131.2), `admin/audit.py` (STORY-125.3) |
| §3.16 l.358-362 | `/workflows/` stub retournant `[]` | router supprimé (STORY-250.1), OpenAPI sans `/workflows` (garde-fou [`test_rbac_exhaustivite.py`](../../backend/tests/unit/test_api/test_rbac_exhaustivite.py)) |
| §6.1 l.455-467 | « **Aucune migration Alembic** », schéma par `create_all` | `alembic upgrade head` au démarrage (STORY-120.2), 13 fichiers de migration |
| §6.2 l.469-484 | 10 entités (`Target`, `TargetCapability`…) | 19 modèles : `Host`, `HostCapability`, `Environment`, `UserOrganization`, `RefreshToken`, `APIKey`, `AuditLog`, `SSHKey`, `HostSSHFingerprint`, `ScheduledTask`, `ScheduledTaskExecution`, `DeploymentEvent`… (voir [`models/__init__.py`](../../backend/app/models/__init__.py)) |
| §7 l.488-523 | RBAC **binaire** l.506-510 (« pas de `require_role` »), bcrypt l.518, logout stateless l.522, `permissions.py` code mort l.510 | RBAC granulaire [`auth/rbac.py`](../../backend/app/auth/rbac.py) + `require_role` sur ~140 endpoints + 5 canaux WS (STORY-122.x) ; Argon2id + double lecture bcrypt legacy (STORY-130.1) ; refresh tokens **révocables** opaques `wf_rt_` (STORY-123) ; clés API `wf_ak_` via `X-API-Key` (STORY-124) ; bruteforce protection (STORY-104) ; credentials chiffrés SecretManager Fernet (STORY-103) ; `permissions.py` purgé (STORY-250.1) |
| §9.1 l.564-572 | `celery_app.py` « complet mais jamais importé » | **purgé** (STORY-130.2, garde-fou [`test_no_celery_residue.py`](../../backend/tests/unit/test_no_celery_residue.py)) ; runtime asyncio unique |
| §9.2-9.3 l.574-585 | EventBus in-memory, Redis **stubs commentés** | interface `Bus` canonique + `InMemoryEventBus` (défaut) + `RedisPubSubEventBus` optionnel canal `windflow:events` (STORY-162) ; Redis Streams **assumé hors périmètre** ; consommateurs plugins hooks `@on_event` (STORY-163) |
| §10.1 l.593-598 | CircuitBreaker/RetryPolicy/HealthCheck « **non câblé** » | CircuitBreaker **câblé** (STORY-251) : registres docker_engine/plugin_registry/ssh via garde partagé [`workloads/_circuit_guard.py`](../../backend/app/services/workloads/_circuit_guard.py), settings `circuit_breaker_*`, séries `windflow_circuit_breaker_*` ; `HealthCheck` purgé (STORY-250.1) ; core enrichi : `metrics.py`, `cache.py`, `secret_manager.py`, `bruteforce_protection.py`, hiérarchie d'exceptions (STORY-127) |
| §11 l.623 | `prometheus_enabled=True` « **aucune instrumentation trouvée** » | instrumentation réelle (STORY-172) : [`core/metrics.py`](../../backend/app/core/metrics.py), `GET /api/v1/metrics` sans auth, dashboards Grafana + alertes ; nouveaux settings `AUDIT_*`, rétentions, `auto_detect_local_host`… |
| §12 l.634-640 | litellm « simulé, **orphelin**, dépendance absente » | **conservé et consommé** : cache LLM borné via [`core/cache.py`](../../backend/app/core/cache.py) (STORY-168), dépendance `litellm ^1.79.0` **réelle** dans [`pyproject.toml`](../../pyproject.toml) l.29 ; toujours **0 endpoint IA exposé** (traçabilité plugin IA Phase 5 → STORY-254) |
| §13 l.644-669 | ~66 fichiers, « websocket (aucun test) », zéros orgs/users/schedules | ~3254 tests unitaires (dernier comptage STORY-251/252) ; WS couvert 94 % + 401 tests (STORY-165/164) ; RBAC exhaustif, enveloppes, pagination, migrations, cache, scheduler — **zones zéro comblées** ; recompter fichiers par répertoire |
| §14 l.673-703 | tableau « Implémenté vs annoncé » : 8 écarts majeurs | la plupart **résolus** (pattern déjà utilisé §14.2 pour STORY-100 : constat barré + « résolu (STORY-XXX) ») ; écarts résiduels réels à lister explicitement : échec RBAC préexistant `/api/v1/metrics` (résidu STORY-172, signalé 251/252), [`helper/security.py`](../../backend/app/helper/security.py) bcrypt 0 consommateur, docstrings `expires_in: 1800/3600` mensongers, `env.example` noms de variables non consommés (STORY-252 signalements 1-4) |
| §15 l.717-728 | synthèse « briques enterprise : **aucune n'est réellement active** » | synthèse post-remédiation à réécrire ; renvoi vers STORY-254 pour le tableau de conformité final (AC 4) |

**B. Rules `.roo/rules/` — écarts détectés (grep du 2026-11-01) :**

| Rule (ligne) | Écart | Preuve |
|---|---|---|
| [`20-architecture-and-api.md`](../../.roo/rules/20-architecture-and-api.md) l.20 | « Communication asynchrone via **Redis Streams** » — le bus livré est InMemory + **Redis Pub/Sub** (arbitrage F6), Redis Streams hors périmètre | [`core/events.py`](../../backend/app/core/events.py), STORY-162 ; spec 04 déjà corrigée par STORY-252 |
| [`35-testing-quality-gates.md`](../../.roo/rules/35-testing-quality-gates.md) l.19 + l.43 | renvois `.clinerules/05-tech-stack.md` et `.clinerules/50-dev-workflow.md` — dossier **inexistant** | `list_files .clinerules` → absent |
| [`40-security.md`](../../.roo/rules/40-security.md) l.11-12 + l.116 | renvois `doc/general_specs/05-authentication.md` / `06-rbac-permissions.md` — mauvais **chemin** (`doc/` vs `docs/`, noms sans numéro) ET mauvais **numéro** (auth = 07, RBAC = 08 ; 05 = stack, 06 = modèle de données) | [`docs/general_specs/`](../../docs/general_specs) |
| [`01-Project-management.md`](../../.roo/rules/01-Project-management.md) l.265-267 | « dossier `doc/` », `doc/IMPLEMENTATION_ROADMAP.md` — répertoire réel `docs/`, roadmap réelle `docs/Roadmap.md` | [`docs/`](../../docs) |
| [`50-dev-workflow.md`](../../.roo/rules/50-dev-workflow.md) l.84-87 | `docker-build` décrit « api + frontend + **worker** », cible `docker-build-worker` listée — cibles **purgées** du Makefile (STORY-130.2) | grep `worker` Makefile → 0 hit ; `docker-build: docker-build-backend docker-build-frontend` l.365 |
| [`55-project-structure.md`](../../.roo/rules/55-project-structure.md) l.16 + arborescence | ligne `.clinerules/` (inexistant) ; arborescence `doc/` → `docs/` à vérifier | idem |
| [`05-tech-stack.md`](../../.roo/rules/05-tech-stack.md) | **prémisse de la story obsolète** : aucune mention « Celery prévu mais pas encore intégré » ni Dockerfile.worker résiduelle — rule déjà synchronisée ; vérification légère suffira (ajouts `prometheus-client`, `argon2-cffi`, `python-dateutil` possibles) | grep `celery|worker` sur 05 → 0 hit |

**C. [`CHANGELOG.md`](../../CHANGELOG.md) `[Unreleased]` — couverture actuelle vs réelle :**

- **Présent** (partie P1 uniquement) : STORY-129, 125.1/125.2/125.3, 130.1, 128, 130.2, 124 + BUG-003/004.
- **Absent** : la vague **P0** (STORY-100→104 : auth WS stricte, garde-fou secrets dev en prod, rate limiting mémoire, SecretManager Fernet, bruteforce login — EPIC-011 DONE 2026-09-07) ; le reste de **P1** (120 Alembic, 121 `user_organizations`, 122 RBAC `require_role`, 123 refresh révocables, 126.1/126.2 enveloppes, 127 exceptions, 131 SSH keys/TOFU) ; toute la vague **P2** (160→174 : scheduler engine, executions, bus canonique, consommateurs, canaux/protocole WS, tests WS, modèle Host, deployment_events, cache fallback, plugins install réel + routes dynamiques + gates, validation stacks unifiée, Prometheus réel, `/compute` browse/prune, WorkloadAdapter + recreate sécurisé) ; **P3** (250 purge + dépréciation `/auth/me`, 251 CircuitBreaker, 252 specs) ; la section **Deprecated** (requise par Keep a Changelog pour `/auth/me` Sunset 2027-05-31 et alias `/targets` Sunset 2027-01-01) n'existe pas.

**D. Renvois explicites reçus d'autres stories (à honorer) :**

- STORY-252, notes d'implémentation signalement n°5 : liens cassés `../user-guide` (00-index ×3, 03 ×2, 10 ×1) « à traiter par une story doc dédiée ou STORY-253 » ;
- STORY-171 (kanban) : « corrections documentaires reportées STORY-253 » ;
- STORY-252 AC 2 : relecture croisée specs ↔ `backend_status.md` — réalisée contre le code (R2 de 252) faute de document à jour ; le nouveau `backend_status.md` rendra l'audit de STORY-254 possible.

### Décisions d'analyse (253)

- **D1 — Périmètre rules élargi** : la story liste 40/20/35/05 ; l'analyse **ajoute** 01/50/55 (liens morts `doc/`→`docs/`, `.clinerules/` inexistant, cibles Makefile purgées) parce qu'AC 2 exige « cohérence rules ↔ code vérifiée » et que le plan P3-5 vise « rules `.roo` (Celery retiré, RBAC réel, secrets) ». Diff minimal : corrections **factuelles** uniquement, aucune réécriture rédactionnaire.
- **D2 — Vérification par inspection** : chaque affirmation du nouveau `backend_status.md` doit être vérifiable dans le code (grep/`list_files`/lecture) — **jamais** copiée depuis les intentions des stories (contrainte explicite de la description).
- **D3 — Régénérer, pas réécrire** : conserver la structure §1-§15 et le style du document (tableaux par module, warnings ⚠️, liens cliquables vers le code avec numéros de ligne) ; les constats résolus restent visibles marqués « résolu (STORY-XXX) » (pattern déjà utilisé §14.2 pour STORY-100) ; dater la nouvelle édition et tracer le lien vers le plan de remédiation.
- **D4 — CHANGELOG synthétique par vague** : une entrée par story (40+) serait démesurée ; regrouper par vague P0/P1/P2/P3 avec renvoi story, sections Keep a Changelog **Added/Changed/Deprecated/Removed/Fixed/Security**, breaking changes détaillés (enveloppes STORY-126/128, `skip/limit`→`page/per_page`, dépréciations `/auth/me` + `/targets`, suppression Celery/worker).
- **D5 — Skill `update-rules`** : les écarts rules sont déjà localisés ligne à ligne (constats B) → application directe possible ; la skill reste utilisable par `treat-story` pour un balayage de cohérence complémentaire.
- **D6 — Périmètre exclu** : aucune modification de [`docs/general_specs/`](../../docs/general_specs) (périmètre STORY-252, DONE) ni d'`env.example` (écart signalé, pas corrigé ici) ni aucun code — AC 5.
- **D7 — Liens `../user-guide`** : vérifier l'existence d'une cible équivalente ; à défaut, retirer le lien mort (renvoi explicite STORY-252 n°5) — intervention limitée aux 6 sites cassés.

**Hypothèses & risques** — **H1** la régénération de `backend_status.md` (729 l.) est longue mais mécanique : chaque section a sa source de vérité identifiée (constats A) ; **H2** les numéros de ligne cités dans le document actuel bougeront pendant l'édition — reciter les ancres en fin d'édition. **R1** dérive de périmètre (réécriture complète au lieu d'actualisation) — contrée par D3 ; **R2** introduire un nouvel écart « annoncé vs réel » par affirmation non vérifiée — contrée par D2 + écrans de contrôle ; **R3** l'échec préexistant `/api/v1/metrics` (résidu STORY-172) doit figurer dans les **écarts résiduels réels**, jamais être masqué (AC 4) ; **R4** si le CHANGELOG agrège 40+ stories, rester synthétique : le détail vit dans le backlog, le CHANGELOG reste lisible (D4).

### Périmètre documentaire (rappel de l'édition de création)

**1. [`docs/backend_status.md`](../../docs/backend_status.md)** — régénération après les vagues P0-P2 :
- Reprendre la structure du document existant (inventaire par module, endpoints, architecture, sécurité, tests & couverture, points forts/points faibles §17-18) ;
- Mettre à jour chaque section impactée : auth/RBAC (STORY-121/122), migrations (STORY-120), secrets (STORY-103), scheduler (STORY-160/161), bus événements (STORY-162/163), WebSocket (STORY-164/165), modèle Host (STORY-166), plugins réels (STORY-169/170), observabilité (STORY-172)… ;
- Les sections devenues fausses (ex. « résilience non câblée » si STORY-251 l'a câblée) sont corrigées ou supprimées ;
- Dater la nouvelle édition et tracer le lien avec le plan de remédiation exécuté.

**2. Rules `.roo/rules/`** — mises à jour ciblées :
- [`40-security.md`](../../.roo/rules/40-security.md) : vérifier l'alignement post-remédiation (Argon2 effectif, secrets chiffrés, brute-force, audit trail) ;
- [`20-architecture-and-api.md`](../../.roo/rules/20-architecture-and-api.md) : mettre à jour si les endpoints/contrats ont changé (enveloppes, pagination, `/hosts`, dépréciation `/auth/me` de STORY-250) ;
- [`35-testing-quality-gates.md`](../../.roo/rules/35-testing-quality-gates.md) : actualiser les zones de test (les « zones zéro » comblées par les vagues P2) ;
- [`05-tech-stack.md`](../../.roo/rules/05-tech-stack.md) : retirer les mentions Celery/Dockerfile.worker si STORY-130.2 faite (⚠️ la skill `update-rules` peut être utilisée pour synchroniser les rules avec le code réel).

**3. [`CHANGELOG.md`](../../CHANGELOG.md)** :
- Tracer la remédiation backend : vagues P0-P2 (et P3 au fil de leur finalisation), breaking changes éventuels (enveloppes API STORY-126, dépréciations `/auth/me`, `/targets`).

Éléments existants à réutiliser / contraintes :
- **Ne pas modifier les specs générales** (`docs/general_specs/`) — c'est le rôle de STORY-252 ;
- La mise à jour de `backend_status.md` doit refléter **le code réellement fusionné** (vérifications par inspection, pas par copie des intentions des stories) ;
- Coordination STORY-252 ↔ STORY-253 : la revue croisée specs ↔ backend_status.md (AC 2 de STORY-252) n'est possible que si ce document est à jour — séquencer 253 avant ou avec 252.

## Critères d'acceptation (AC)

- [x] AC 1 : [`backend_status.md`](../../docs/backend_status.md) régénéré/actualisé : chaque section obsolète corrigée (RBAC, secrets, Alembic, scheduler, bus, WS, modèle, plugins, observabilité, tests), nouvelle édition datée, plus aucun constat « pré-remédiation » non signalé comme résolu.
- [x] AC 2 : Les rules `.roo` ciblées (40, 20, 35, 05) sont à jour : plus de mention « Celery prévu mais non intégré » si STORY-130.2 faite, structure des endpoints/contrats alignée, zones de test réelles — cohérence rules ↔ code vérifiée.
- [x] AC 3 : [`CHANGELOG.md`](../../CHANGELOG.md) trace la remédiation (vagues, fonctionnalités, breaking changes : enveloppes API, dépréciations `/auth/me` et `/targets`).
- [x] AC 4 : Relecture finale : plus d'écart « annoncé vs réel » sur les points traités par la remédiation (critère de done du plan P3-5) ; les écarts résiduels éventuels sont explicitement listés (renvoi vers STORY-254 pour le tableau de conformité final).
- [x] AC 5 : Documentation uniquement — aucun code modifié ; la CI documentaire (liens internes valides) reste verte.

## Références spécification

- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P3-5 (critère de done : « Relecture : plus d'écart "annoncé vs réel" sur les points traités »), §8.1 (P3-5 rangement) ;
- [`backend_status.md`](../../docs/backend_status.md) — document à régénérer (structure actuelle à reprendre) ;
- `.roo/rules/01-Project-management.md` — documentation projet (`doc/`) et workflow backlog ;
- `.roo/rules/05-tech-stack.md`, `20-architecture-and-api.md`, `35-testing-quality-gates.md`, `40-security.md` — rules à synchroniser ;
- [`CHANGELOG.md`](../../CHANGELOG.md) — format existant à respecter.

## Dépendances

- **Vagues P0-P2 terminées** (et idéalement STORY-250/251 purgées) : le document décrit l'état final du code.
- Coordonnée avec **STORY-252** (corrections de specs) — la revue croisée de STORY-252 dépend du `backend_status.md` actualisé par cette story.
- Prépare **STORY-254** (revue finale de conformité : le tableau de conformité s'appuie sur ce document à jour).

### Compléments d'analyse (2026-11-01)

- **Prérequis livrés (vérifiés au kanban et par inspection du code)** : EPIC-011/P0 DONE (2026-09-07, STORY-100→104), EPIC-012/P1 DONE (120→131), EPIC-013/P2 DONE (160→174 + BUG-005→009), STORY-250.1/250.2, STORY-251, STORY-252 toutes DONE — **aucun blocage résiduel**, la story peut décrire l'état final.
- **Cas particulier STORY-252** : DONE depuis le 2026-10-31 mais sa relecture croisée (AC 2) a été faite **contre le code** (divergence R2 documentée) faute de `backend_status.md` à jour ; la livraison de cette story **clôt rétrospectivement** cette relecture par conformité (E7 : les 6 points F1-F6 doivent matcher entre specs 252 et status 253) — aucun retour vers 252 requis si E7 est vert.
- **Services externes** : **aucun** requis (story documentaire) ; Redis optionnel — documenter le bus/cache en mode dégradé mémoire sans l'exiger.
- **Base de données** : **aucune migration, aucune table** — aucun impact Alembic ; les 13 migrations existantes servent de **matière première rédactionnelle** (§6 du status).
- **Configuration** : lecture seule de [`config.py`](../../backend/app/config.py) (nouveaux settings `circuit_breaker_*`, `AUDIT_*`, rétentions, `auto_detect_local_host`…) pour le §11 du status ; `env.example` non modifié (D6).
- **Skill `update-rules`** : disponible pour synchroniser `.roo/rules` avec le code réel (D5) — les écarts étant déjà localisés (constats B), application directe ou via la skill, au choix de `treat-story`.

## État d'avancement technique

*(coché progressivement par treat-story)*

- [x] T1. Rules `.roo` — réparations factuelles des liens et références mortes (40, 35, 01, 50, 55)
- [x] T2. Rules `.roo` — synchronisation du contenu post-remédiation (20, 05, 40-contenu, 35-contenu)
- [x] T3. `backend_status.md` — pass 1 : sections structurelles (§1-§6)
- [x] T4. `backend_status.md` — pass 2 : sécurité, WS, core, config, IA (§7-§12)
- [x] T5. `backend_status.md` — pass 3 : tests, écarts résiduels, synthèse (§13-§15)
- [x] T6. `backend_status.md` — pass 4 : datation, traçabilité plan, ancres et liens
- [x] T7. `CHANGELOG.md` — vagues P0 + P1 manquantes
- [x] T8. `CHANGELOG.md` — vague P2 + P3 + sections Deprecated/Removed/Fixed
- [x] T9. Liens `../user-guide` cassés (6 sites, exception autorisée) + écrans de contrôle E1-E8 + tableau de traçabilité

## Tâches d'implémentation détaillées

> Story **documentaire** : les « fichiers » ci-dessous sont des documents Markdown — **aucun code applicatif, aucun test automatisé nouveau** ; la validation passe par les écrans de contrôle de la section « Tests à écrire ». Ordre choisi : rules d'abord (petites, verrouillent le vocabulaire), `backend_status.md` ensuite (gros volume, 4 passes sectionnaires), CHANGELOG enfin (synthèse qui cite les deux), hygiène des liens, écrans de contrôle en clôture. La skill `update-rules` peut être invoquée en support des tâches 1-2 (D5).

### Tâche 1 : Rules — réparations factuelles des liens et références mortes (40, 35, 01, 50, 55)
**Objectif :** Éliminer les renvois cassés et les cibles disparues — cohérence rules ↔ fichiers réels (AC 2, décision D1).
**Fichiers :**
- `.roo/rules/40-security.md` — **Modifier** : l.11-12 et l.116 — `doc/general_specs/05-authentication.md` → `docs/general_specs/07-authentification.md` ; `doc/general_specs/06-rbac-permissions.md` → `docs/general_specs/08-rbac-permissions.md` (chemin ET numéro corrigés).
- `.roo/rules/35-testing-quality-gates.md` — **Modifier** : l.19 `.clinerules/05-tech-stack.md` → `.roo/rules/05-tech-stack.md` ; l.43 `.clinerules/50-dev-workflow.md` → `.roo/rules/50-dev-workflow.md`.
- `.roo/rules/01-Project-management.md` — **Modifier** l.265-267 : « dossier `doc/` » → `docs/` ; `doc/general_specs` → `docs/general_specs` ; `doc/IMPLEMENTATION_ROADMAP.md` → `docs/Roadmap.md` (vérifier le titre réel du fichier).
- `.roo/rules/50-dev-workflow.md` — **Modifier** l.84-87 : `docker-build` « api + frontend + worker » → « api + frontend » ; supprimer la ligne `docker-build-worker` (cible purgée par STORY-130.2) ; balayer la table docker à la recherche d'autres cibles disparues (`enable-workers`, `docker-build-worker` — grep Makefile pour confirmer).
- `.roo/rules/55-project-structure.md` — **Modifier** : l.16 supprimer la ligne `.clinerules/` ; vérifier l'arborescence racine (`doc/` → `docs/`, présence `data/`, `dev/`) par `list_files` avant édition.
**Points clés :** diff minimal — corriger les faits, pas le style (D1) ; vérifier chaque cible par inspection avant de l'écrire (D2).
**Dépend de :** rien (point d'entrée).

### Tâche 2 : Rules — synchronisation du contenu post-remédiation (20, 05, 40-contenu)
**Objectif :** Aligner les règles d'architecture/sécurité/stack sur le code livré (AC 2).
**Fichiers :**
- `.roo/rules/20-architecture-and-api.md` — **Modifier** l.19-21 (§ Event-driven) : « via Redis Streams quand approprié » → bus canonique `Bus` (`InMemoryEventBus` par défaut, `RedisPubSubEventBus` optionnel canal `windflow:events`), Redis Streams hors périmètre (STORY-162, même formulation que spec 04 corrigée par STORY-252) ; § Résilience l.45-48 : ajouter une mention factuelle « circuit breaker câblé sur Docker/SSH/registre plugins (STORY-251), séries `windflow_circuit_breaker_*` ».
- `.roo/rules/05-tech-stack.md` — **Vérifier puis modifier légèrement** : la prémisse « Celery prévu mais pas intégré » n'existe plus (grep 0 hit — déjà synchronisée) ; ajouter si absent aux dépendances backend notables : `argon2-cffi` + `passlib[argon2]` (auth), `prometheus-client ^0.21` (STORY-172), `python-dateutil` (STORY-160.1) ; noter `bcrypt ^4.0.0` en transition lecture-seule (retrait post-migration, cf. STORY-250) — miroir de [`pyproject.toml`](../../pyproject.toml).
- `.roo/rules/40-security.md` — **Modifier (contenu)** : § AuthN/AuthZ — refléter l'état livré : Argon2id effectif + double lecture bcrypt legacy (STORY-130.1), refresh tokens révocables (STORY-123), clés API `wf_ak_` (STORY-124), brute-force 5/10 min (STORY-104), RBAC `require_role` granulaire (STORY-122) ; § Secrets — SecretManager Fernet effectif (STORY-103) ; § Rate limiting — mode mémoire fallback sans Redis (STORY-102) ; § Scans inchangés.
- `.roo/rules/35-testing-quality-gates.md` — **Modifier (contenu)** : § volumétrie/zéros — remplacer les « zones zéro » par l'état réel (WS 94 % + 401 tests STORY-165/164, RBAC matrice STORY-122.7, ~3254 unitaires au dernier comptage — recompter à l'édition, D2).
**Points clés :** rester dans le registre « règles » (impératifs courts), pas « inventaire » — le détail vit dans `backend_status.md` ; chaque ajout cite sa story livreuse.
**Dépend de :** Tâche 1 (mêmes fichiers pour 40/35).

### Tâche 3 : `backend_status.md` — pass 1 : sections structurelles (§1-§6)
**Objectif :** Actualiser l'inventaire : volumétrie, runtime, montage API, exécuteurs, services, base de données (AC 1).
**Fichiers :**
- `docs/backend_status.md` — **Modifier** §1 : recompter fichiers/routers/modèles/schémas/services/tests (`list_files`), retirer le « Point majeur : pas d'alembic », retirer `celery_app.py` de l'arborescence, ajouter `alembic/` ; §2.2 : décrire les 6 boucles lifespan + SchedulerEngine + `recover_pending_deployments` (l.231-475 du [`main.py`](../../backend/app/main.py)) ; §2.4 : nouveau montage (sans `/workflows`, avec `/hosts` + alias `/targets` déprécié, `system`, `metrics`, `ssh-keys`, `admin/audit`) — relire [`api/v1/__init__.py`](../../backend/app/api/v1/__init__.py) ; §3 : régénérer les tables endpoints par router (auth devient : login/refresh/logout révocants/register/password/api-keys + `/auth/me` déprécié ; hosts 6 sous-modules ; compute 7 routes dont browse/prune ; schedules + executions ; admin audit ; **supprimer §3.16 workflows**) ; §4 : adapters `WorkloadAdapter` ([`services/workloads/`](../../backend/app/services/workloads)) + circuit guard STORY-251 + `deployment_event_store` ; §5 : ~50 services (nouvelles entrées scheduler_*, plugin_package/validation/gate/api_router, refresh_token, api_key, audit, secret via core, ssh_*, host_*, system, volume_browser) ; §6 : 19 entités + 13 migrations + `alembic upgrade head` au démarrage (STORY-120.2).
**Points clés :** chaque table re-vérifiée par inspection (D2) ; garder le format tabulaire et les liens `fichier.py:ligne` (D3) ; chiffres exacts (compter, pas estimer).
**Dépend de :** Tâches 1-2 (vocabulaire rules verrouillé).

### Tâche 4 : `backend_status.md` — pass 2 : sécurité, temps réel, core, config (§7-§12)
**Objectif :** Réécrire les sections les plus obsolètes — sécurité et core (AC 1).
**Fichiers :**
- `docs/backend_status.md` — **Modifier** §7 : RBAC granulaire (`UserRole` viewer/operator/admin/super_admin + `require_role` ~140 endpoints/5 canaux, STORY-121/122), Argon2id + upgrade login (STORY-130.1), refresh opaques révocables `wf_rt_` (STORY-123), clés API (STORY-124), bruteforce (STORY-104), TOFU SSH (STORY-131) — relire [`auth/dependencies.py`](../../backend/app/auth/dependencies.py), [`auth/rbac.py`](../../backend/app/auth/rbac.py) ; §8 : canaux WS réels (général, terminal, deployments/logs, containers logs/stats, ssh TOFU, journal, batch — STORY-164.2) + heartbeat/ack (164.1) + métriques (172) ; §9 : supprimer §9.1 Celery → remplacer par « runtime asyncio unique » + bus canonique (STORY-162) + consommateurs (163) + scheduler engine (160.2) ; §10 : core réel (exceptions hiérarchisées STORY-127, `metrics.py`, `cache.py` STORY-168, `secret_manager.py` STORY-103, `bruteforce_protection.py`, CircuitBreaker câblé STORY-251, abstractions `CacheManager` concrétisé / `DatabaseManager` purgé) ; §11 : nouveaux settings (audit/rétentions/circuit breaker/auto_detect) ; §12 : litellm conservé-consommé (cache STORY-168), dépendance réelle, 0 endpoint exposé, renvoi STORY-254.
**Points clés :** §7 est la section la plus sensible (AC 1 cite RBAC/secrets en premier) ; ne jamais affirmer sans inspection (D2) ; pattern « ~~ancien constat~~ résolu (STORY-XXX) » pour §14 mais sections §7-§12 réécrites à neuf.
**Dépend de :** Tâche 3 (structure posée).

### Tâche 5 : `backend_status.md` — pass 3 : tests, écarts, synthèse (§13-§15)
**Objectif :** Traduire l'état réel des tests et clore le tableau « annoncé vs réel » (AC 1 + AC 4).
**Fichiers :**
- `docs/backend_status.md` — **Modifier** §13 : recompter les fichiers de test par répertoire (`list_files backend/tests`), remplir la couverture par domaine réelle (WS 94 %, migrations, RBAC, enveloppes, pagination, cache, scheduler — sources : notes d'implémentation des stories + `--cov` si exécuté), supprimer les « zéros » comblés, lister les zones réellement restantes ; §14 : barrer chaque écart résolu avec sa story (8 lignes du tableau §14.1), consigner les **écarts résiduels réels** (échec préexistant `/api/v1/metrics` résidu STORY-172 ; `helper/security.py` bcrypt 0 consommateur ; docstrings `expires_in: 1800/3600` ; `env.example` vars non consommées ; 3 sites SSH ad hoc non câblés au circuit breaker — divergence documentée STORY-251) avec renvoi STORY-254 pour arbitrage final ; §15 : réécrire la synthèse post-remédiation (ce qui est actif désormais : RBAC, Alembic, secrets chiffrés, scheduler, bus, Prometheus, circuit breaker… + ce qui reste en squelette/flag : Keycloak, Vault optionnels, étape 3 du modèle, IA non exposée).
**Points clés :** AC 4 exige des écarts résiduels **explicites** — ne rien lisser (R3) ; la synthèse §15 sert d'entrée à STORY-254.
**Dépend de :** Tâches 3-4.

### Tâche 6 : `backend_status.md` — pass 4 : datation, traçabilité, ancres et liens (finition)
**Objectif :** Fiabiliser la navigation du document régénéré (AC 1 + AC 5).
**Fichiers :**
- `docs/backend_status.md` — **Modifier** : en-tête — nouvelle date d'édition (2026-11-XX), avertissement mis à jour, ajout d'un bloc « Lié au plan de remédiation » (renvoi [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) + mention « vagues P0-P3 exécutées, STORY-100→253 ») ; vérifier le sommaire §1-§15 (ancres), re-parcourir **tous** les liens relatifs du document vers le code (les numéros de ligne ont bougé — H2 : reciter les ancres des fichiers cités) ; format des tables homogène.
**Points clés :** un lien mort dans le document de référence serait ironique — l'écran E5 vérifiera ; ne pas transformer l'avertissement en promotion : le document reste un inventaire factuel.
**Dépend de :** Tâches 3-5.

### Tâche 7 : `CHANGELOG.md` — vagues P0 et P1 manquantes
**Objectif :** Tracer la moitié manquante de la remédiation (AC 3).
**Fichiers :**
- `CHANGELOG.md` — **Modifier** `[Unreleased]` : **Security** (P0 — STORY-100 auth WS stricte 1008, STORY-101 garde-fou secrets dev en prod, STORY-102 rate limiting mémoire sans Redis, STORY-103 SecretManager Fernet + chiffrement credentials/env + masquage API, STORY-104 brute-force login 5/10 min) ; **Added** (P1 manquant — STORY-120 Alembic baseline + `upgrade head` au démarrage, STORY-121 `user_organizations` + endpoints membres, STORY-122 RBAC `require_role` ~140 endpoints + 5 canaux, STORY-123 refresh tokens révocables + logout invalidant, STORY-131 clés SSH + empreintes + TOFU anti-MITM) ; **Changed** (STORY-127 hiérarchie d'exceptions `WindFlowException` + enveloppes d'erreur typées — compléte 126/128 déjà présents).
**Points clés :** reprendre le style des entrées existantes (gras story + détail indenté) ; une à deux lignes par item, le détail vit dans le backlog (D4) ; ordre Added→Changed→Deprecated→Removed→Fixed→Security de Keep a Changelog (réorganiser si nécessaire en Tâche 8).
**Dépend de :** rien (parallèle à 3-6 possible).

### Tâche 8 : `CHANGELOG.md` — vague P2, P3, sections Deprecated et relecture
**Objectif :** Compléter la trace et les breaking changes (AC 3).
**Fichiers :**
- `CHANGELOG.md` — **Modifier** : **Added** (P2 — scheduler engine + `/schedules` v2 + executions 160/161, bus canonique + consommateurs 162/163, canaux WS ssh/journal/batch + heartbeat/ack + reconnexion 164, modèle `Host` + `origin`/`environments` + alias `/targets` 166, `deployment_events` 167, cache fallback 168, plugins install réel/routes dynamiques/gates/Trivy 169/170, validation stacks unifiée 171, Prometheus réel `/api/v1/metrics` 172, `/compute` browse/volumes/prune 173, `WorkloadAdapter` + recreate sécurisé 174 ; P3 — CircuitBreaker câblé 251) ; **Deprecated** (nouvelle section — `/auth/me` → `/users/me`, headers `Deprecation`/`Sunset: 2027-05-31`, STORY-250.2 ; alias `/targets` → `/hosts`, `Sunset: 2027-01-01`, STORY-166.2) ; **Removed** (purge code mort STORY-250.1 : `permissions.py`, stub `/workflows`, `HealthCheck`, `DatabaseManager`, print debug — vient compléter l'entrée 130.2 existante) ; **Fixed** (BUG-005→009 WebSocket) ; relire l'ensemble `[Unreleased]` pour cohérence de style et absence de doublons avec les entrées 124-130 déjà présentes.
**Points clés :** les breaking changes déjà documentés (STORY-128 entrée existante) ne sont pas dupliqués — la section Deprecated les **complète** avec les Sunset dates ; vérifier le template « Template for Future Releases » en fin de fichier reste intact.
**Dépend de :** Tâche 7.

### Tâche 9 : Liens `../user-guide` + écrans de contrôle + traçabilité (clôture)
**Objectif :** Hygiène documentaire globale et preuve de conformité (AC 4 + AC 5).
**Fichiers :**
- `docs/general_specs/00-index.md`, `03-modele-compute.md`, `10-cli-tui.md` — **Modifier (strictement limité)** : 6 liens cassés `../user-guide` (00-index ×3, 03 ×2, 10 ×1 — signalement n°5 de STORY-252) : chercher une cible équivalente existante ; à défaut, retirer le lien et garder le texte (D7). **Aucune autre retouche de specs** (D6).
- `.backlog/stories/STORY-253-mise-a-jour-documentaire-post-remediation.md` (notes d'implémentation) — **Modifier** : tableau de traçabilité **document ↔ section ↔ fait vérifié ↔ story livreuse** + liste des écarts résiduels réels reportés à STORY-254 + divergences éventuelles.
- Vérifications sans édition : écrans E1-E8 de la section « Tests à écrire ».
**Points clés :** la retouche des 3 specs est une **exception explicitement autorisée** (renvoi formel STORY-252 n°5 + AC 5 « CI documentaire liens internes valides ») — tout autre changement de spec est interdit ; tout écart **code** découvert pendant la relecture est signalé, jamais corrigé (AC 4, même posture que STORY-252 AC 5).
**Dépend de :** Tâches 1-8.

## Tests à écrire

> **Checklist sécurité (rules 40 § 8) — dérogation documentée** : story **documentaire** — aucun endpoint, aucun code, aucune donnée manipulée : les cas 401/403/422/404 sont **non applicables** (même posture que STORY-252, validée en precedent). Exigences appliquées par analogie : aucun secret réel dans les documents (exemples factices uniquement, le status/CHANGELOG ne citent jamais de valeur de `jwt_secret`/clé réelle) ; les URLs Redis/registre éventuellement citées ne portent jamais de credentials (cf. masquage `_safe_redis_url`) ; les valeurs de configuration documentées reflètent les défauts réels de [`config.py`](../../backend/app/config.py) ; la description du chiffrement des credentials (§7/§14) reste à un niveau de principe, sans matériel exploitable.
>
> **Couverture ≥ 80 % (rules 35) — non applicable** : aucun module de code modifié ; la « validation » = écrans de contrôle documentaires ci-dessous + non-régression code.

### Écrans de contrôle documentaires (validation treat-story)

| # | Commande / vérification | Résultat attendu |
|---|---|---|
| E1 | `grep -rniE "celery|windflow-worker|dockerfile.worker" docs/backend_status.md CHANGELOG.md .roo/rules/` | 0 hit **hors** mentions historiques expressément tracées (CHANGELOG « Removed » cite la suppression ; status §14 constat barré « résolu ») |
| E2 | `grep -rniE "\.clinerules|doc/general_specs|doc/IMPLEMENTATION_ROADMAP" .roo/rules/` | 0 hit (références mortes réparées — Tâche 1) |
| E3 | `grep -n "redis streams" .roo/rules/20-architecture-and-api.md docs/backend_status.md` | 0 hit hors mention explicite « hors périmètre » (bus = Pub/Sub, F6) |
| E4 | `grep -c "require_role\|rbac" docs/backend_status.md` et relecture §7 | §7 décrit le RBAC granulaire 4 rôles (plus « binaire ») ; grep « binaire » §7 → 0 hit |
| E5 | script/parcours des liens relatifs de `backend_status.md` (cibles `backend/app/...` avec numéros de ligne) + liens rules → specs | tous valides (AC 5) ; les 6 `../user-guide` réparés (E9 complémentaire) |
| E6 | relecture croisée des 6 points F1-F6 entre specs (STORY-252) et nouveau `backend_status.md` : JWT 15 min, Argon2, absence Celery, surfaces API, phasage modèle (étapes 1-2 livrées / 3 reportée), bus Pub/Sub | **0 divergence** specs ↔ status (clôture rétrospective du R2 de STORY-252) |
| E7 | `grep -n "user-guide" docs/general_specs/00-index.md docs/general_specs/03-modele-compute.md docs/general_specs/10-cli-tui.md` | 0 hit cassé (cible existante ou lien retiré, D7) |
| E8 | relecture CHANGELOG : chaque vague P0/P1/P2/P3 a au moins une entrée ; sections Added/Changed/Deprecated/Removed/Fixed/Security cohérentes ; Sunset dates `/auth/me` (2027-05-31) et `/targets` (2027-01-01) présentes | conformes (AC 3) |

### Non-régression code (aucun code modifié — garde-fous)

- `make backend-test-unit` — inchangé vert (attendu : unique échec préexistant `/api/v1/metrics`, résidu STORY-172 documenté — jamais régressé par une story doc) ;
- `poetry run pytest backend/tests/unit/test_no_celery_residue.py -v` — reste vert (preuve F1, non touché) ;
- `make lint && make typecheck` — non impactés (aucun fichier code modifié).

### Tests automatisés nouveaux

- **Aucun** — la story ne crée aucun endpoint ni module ; toute découverte d'écart **code** pendant la revue est signalée (Tâche 9, AC 4) et porteuse d'un bug ou d'une story dédiée, jamais corrigée ici.
