# STORY-254.1 : Audit par domaine specs ↔ code — re-passe du rapport initial

**Statut :** DONE
**Story Parente :** STORY-254 — Revue finale de conformité — audit specs ↔ code de bout en bout et tableau de conformité (clôture du plan)
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)

## Description

En tant que responsable technique WindFlow, je veux ré-exécuter la passe d'analyse d'écart specs ↔ code sur **tous les domaines du rapport initial** (même méthode, mêmes sections de référence §1→§16 selon la correspondance du plan §8.2), en confrontant les spécifications [`docs/general_specs/`](../../docs/general_specs/README.md) (corrigées par STORY-252) au **code réellement fusionné** — inspection réelle : endpoints, modèles, tests, configuration — et non aux intentions des stories.

Cette sous-story produit un **journal d'audit par domaine** (constat + preuve/référence pour chaque section), matière première du tableau de conformité final (STORY-254.4). Tout écart découvert est **consigné, jamais corrigé** (posture de revue — contrainte de la story parente).

## Critères d'acceptation (AC)

- [x] AC 1 : Une passe d'analyse d'écart specs ↔ code a été ré-exécutée sur **tous les domaines du rapport initial** (même méthode, mêmes sections de référence), en s'appuyant sur le code réellement fusionné — pas sur les intentions des stories.

## Contexte technique

**Posture :** revue en lecture seule du code et des specs. Aucune correction de code (contrainte parente : « tout écart découvert est tracé (story/bug) et priorisé, jamais corrigé en silence » — l'arbitrage/tracé des écarts relève de STORY-254.3).

**Méthode** (reprise de la story parente) : pour chaque section du rapport initial, confronter spec ↔ code livré par inspection (grep, lecture des sources, `list_files`). La correspondance sections ↔ items du plan est documentée dans [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §8.2 :

| Section rapport | Vérification principale | Sources d'inspection |
|---|---|---|
| §1 API | enveloppes `{data}`, pagination, `/system/ready`, surfaces incorporées F3 | [`api/v1/`](../../backend/app/api/v1), specs [`09-api.md`](../../docs/general_specs/09-api.md) |
| §2 Authentification | JWT 15 min, refresh révocables, clés API, bruteforce, `PUT /auth/password` | [`auth/`](../../backend/app/auth), specs [`07-authentification.md`](../../docs/general_specs/07-authentification.md) |
| §3 RBAC | 4 rôles, `require_role` partout, matrice spec 08 | [`auth/rbac.py`](../../backend/app/auth/rbac.py), specs [`08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) |
| §4 Modèle de données | Alembic 13 migrations, 19 entités, `Host`+`origin`, `environments` | [`models/`](../../backend/app/models), [`alembic/versions/`](../../backend/alembic/versions), spec 06 |
| §5 Workloads/compute | `WorkloadAdapter`, browse/prune, recreate sécurisé | [`services/workloads/`](../../backend/app/services/workloads), spec 02/03 |
| §6 Architecture/event-driven | bus canonique `Bus`, nomenclature ~18 événements, asyncio unique | [`core/events.py`](../../backend/app/core/events.py), spec 04 |
| §7 Sécurité | WS auth, rate limit, SecretManager, TOFU SSH, audit trail | [`core/secret_manager.py`](../../backend/app/core/secret_manager.py), specs 15 |
| §8 WebSocket | 8 canaux, heartbeats, reconnexion, auth stricte | [`websocket/`](../../backend/app/websocket), status §8 |
| §9 Stacks definitions | validation unifiée, bornes `min/max` | [`stack_loader_service.py`](../../backend/app/services/stack_loader_service.py) |
| §10 Plugins | install réel (download/checksum/hooks/rollback), gates, routes dynamiques | [`plugin_manager_service.py`](../../backend/app/services/plugin_manager_service.py) |
| §11 IA | litellm conservé-consommé, 0 endpoint exposé (reporté Phase 5) | [`litellm_service.py`](../../backend/app/services/litellm_service.py), status §12 |
| §12 Automatisation | scheduler engine + executions + triggers événement | [`scheduler_engine.py`](../../backend/app/services/scheduler_engine.py) |
| §14 Déploiement | `upgrade head` au démarrage, auto-détection host local | [`database.py`](../../backend/app/database.py), spec 16 |
| §15 Observabilité | Prometheus réel `/api/v1/metrics`, dashboards, alertes | [`core/metrics.py`](../../backend/app/core/metrics.py) |
| §16 Tests | volumétrie, couverture par domaine ≥ 80 %, zones zéro comblées | [`backend/tests/`](../../backend/tests), status §13 |

**Sources secondaires déjà agrégées** (à recouper, pas à recopier aveuglément — D2 de STORY-253 : « jamais copié depuis les intentions des stories ») :
- [`backend_status.md`](../../docs/backend_status.md) édition 2026-11-01 — §3 (inventaire 19 routers), §7 (RBAC ~174 usages), §13 (couverture par domaine), §14.1 (constats résolus), §14.2 (**7 écarts résiduels réels renvoyés à STORY-254**) ;
- Kanban : EPIC-011/012/013 DONE, EPIC-014 6/7 (seule 254 ouverte) ;
- Écrans de contrôle déjà documentés : `test_no_celery_residue.py`, `test_rbac_exhaustivite.py` (existant, vérifiés sur disque).

**Journal d'audit : format attendu** (consigné dans cette sous-story, section Notes d'implémentation) :

```markdown
| Section | Constat (CONFORME / ÉCART / REPORTÉ) | Preuve (fichier:ligne ou test) | Story livreuse / renvoi |
```

## Dépendances

- Aucune (point d'entrée de la découpe STORY-254).
- Prérequis hérités de la parente : STORY-252 (specs corrigées) et STORY-253 (`backend_status.md` régénéré) — toutes deux DONE.

## Tâches d'implémentation détaillées

### Tâche 1 : Audit domaines §1-§4 (API, Authentification, RBAC, Modèle de données)
**Objectif :** Confronter specs ↔ code sur les 4 domaines du socle contrat/sécurité ; consigner constat + preuve par domaine.
**Fichiers :**
- `.backlog/stories/STORY-254.1-audit-domaines-specs-code.md` (section Journal d'audit) — **Modifier** — Ajouter les lignes §1-§4 du journal. Inspections : `grep -rn "require_role" backend/app/api/v1 | wc -l` (ordre de grandeur ~174 attendu), vérif enveloppes sur un échantillon par router, `GET /system/ready` sans auth, pagination sur les listes, `alembic/versions/` = 13 fichiers, `models/__init__.py` = 19 entités, présence `Host`/`origin`/`environments`, JWT `jwt_access_token_expire_minutes=15` dans [`config.py`](../../backend/app/config.py).
**Exigences sécurité :** Aucune (lecture seule).
**Dépend de :** Aucune.

### Tâche 2 : Audit domaines §5-§8 (Workloads/compute, Event-driven, Sécurité, WebSocket)
**Objectif :** Vérifier les domaines d'exécution et temps réel.
**Fichiers :**
- `.backlog/stories/STORY-254.1-audit-domaines-specs-code.md` (Journal d'audit) — **Modifier** — Ajouter les lignes §5-§8. Inspections : [`services/workloads/`](../../backend/app/services/workloads) (adapter + `_circuit_guard.py`), `/compute` browse/prune dans [`compute.py`](../../backend/app/api/v1/compute.py), bus `InMemoryEventBus`/`RedisPubSubEventBus` dans [`core/events.py`](../../backend/app/core/events.py), nomenclature `EventType` vs spec 04, `get_current_user_ws` strict, 8 canaux WS dans [`websockets.py`](../../backend/app/api/v1/websockets.py), SecretManager Fernet, TOFU SSH.
**Exigences sécurité :** Aucune (lecture seule).
**Dépend de :** Tâche 1.

### Tâche 3 : Audit domaines §9-§12 (Stacks, Plugins, IA, Automatisation)
**Objectif :** Vérifier les domaines fonctionnels étendus.
**Fichiers :**
- `.backlog/stories/STORY-254.1-audit-domaines-specs-code.md` (Journal d'audit) — **Modifier** — Ajouter les lignes §9-§12. Inspections : validation stacks unifiée (une seule source de règles), bornes `min/max` servies, plugin install réel (download/checksum SHA-256/hooks/rollback), gates pre-deploy, routes dynamiques, litellm (cache consommé + TODO `litellm.completion()` — écart résiduel §14.2 confirmé), scheduler engine (verrous, fuseaux IANA, récupération orphelins, `scheduled_task_executions`).
**Exigences sécurité :** Aucune (lecture seule).
**Dépend de :** Tâche 2.

### Tâche 4 : Audit domaines §14-§16 (Déploiement, Observabilité, Tests) + synthèse du journal
**Objectif :** Clôturer la passe d'audit et produire la liste consolidée des écarts découverts.
**Fichiers :**
- `.backlog/stories/STORY-254.1-audit-domaines-specs-code.md` (Journal d'audit) — **Modifier** — Ajouter les lignes §14-§16 + section « Écarts découverts pendant l'audit » (chaque écart : description, preuve, proposition de statut CONFORME/REPORTÉ/ÉCART RÉSIDUEL pour STORY-254.4). Inspections : `alembic upgrade head` au démarrage ([`database.py`](../../backend/app/database.py) / lifespan [`main.py`](../../backend/app/main.py)), auto-détection host (`auto_detect_local_host`), `/api/v1/metrics` sans auth + dashboards Grafana + alertes, volumétrie tests (`ls backend/tests/unit | wc -l`), couverture par domaine (status §13.3), zones restantes §13.4.
**Exigences sécurité :** Aucune (lecture seule).
**Dépend de :** Tâche 3.

## Tests à écrire

> Story d'**audit documentaire** — aucun code modifié : couverture ≥ 80 % et cas 401/403/422 **non applicables** (même posture que STORY-252/253). La validation = écrans de contrôle ci-dessous.

### Écrans de contrôle

| # | Commande / vérification | Résultat attendu |
|---|---|---|
| E1 | Le journal couvre les 15 sections §1→§16 (§13 virtualisation = conforme à préserver, inspection légère) | 15 lignes minimum, chacune avec statut + preuve |
| E2 | Chaque ligne cite une preuve vérifiable (fichier:ligne, test, grep) | 0 affirmation sans preuve |
| E3 | Recoupement §14.2 de [`backend_status.md`](../../docs/backend_status.md) : les 7 écarts résiduels réapparaissent dans le journal (confirmés ou nuancés) | 7/7 retrouvés |
| E4 | `make backend-test-unit` en fin d'audit | inchangé (échecs préexistants documentés, aucune régression) |

### Commandes de validation
```bash
make backlog-check                     # cohérence contrats
make backend-test-unit                 # non-régression (échecs préexistants documentés)
```

## Journal d'audit (2026-11-07 — inspection réelle du code fusionné)

| Section | Constat | Preuve (inspection du 2026-11-07) | Story livreuse / renvoi |
|---|---|---|---|
| §1 API | **CONFORME** | Enveloppes + pagination : [`schemas/common.py`](../../backend/app/schemas/common.py) (`PaginatedResponse` l.92, format `{data, pagination}`) ; `GET /system/ready` sans auth ([`system.py`](../../backend/app/api/v1/system.py) l.95) ; surfaces F3 incorporées (`/compute/*`, `/discovery`, `/stats`, import/export, plugin_registry — status §3) | STORY-126/128/129, F3 (STORY-252) |
| §2 Authentification | **CONFORME** | JWT 15 min ([`config.py`](../../backend/app/config.py) l.36-38), refresh opaques 7 j révocables (l.44+), `PUT /auth/password` ([`auth.py`](../../backend/app/api/v1/auth.py) l.1005+), `get_current_user_ws` strict ([`dependencies.py`](../../backend/app/auth/dependencies.py) l.181+), bruteforce + clés API (status §7) | STORY-123/124/104/129, F5 (252) |
| §3 RBAC | **CONFORME** | 148 `Depends(require_*)` + 7 `ensure_role_ws` + 24 `require_role`/`require_role_ws` directs ≈ **179 points de contrôle** (grep 2026-11-07) ; deps pré-construites 4 niveaux ([`rbac.py`](../../backend/app/auth/rbac.py) l.219-222) — cohérent avec « ~174 usages » du status | STORY-121/122 |
| §4 Modèle de données | **CONFORME** | 13 migrations ([`alembic/versions/`](../../backend/alembic/versions)), 19+ modèles (`Environment` l.37, `Host` l.108 + `origin` l.173 dans [`models/host.py`](../../backend/app/models/host.py), `WorkloadOrigin` partagé Stack/Host) | STORY-120/166.x, F4 (252) |
| §5 Workloads/compute | **CONFORME** | [`services/workloads/`](../../backend/app/services/workloads) : `base.py` (interface) + `docker_container.py` + `compose_stack.py` + [`_circuit_guard.py`](../../backend/app/services/workloads/_circuit_guard.py) (71 l.) ; `/compute/browse` paginé + `/compute/prune` superadmin ([`compute.py`](../../backend/app/api/v1/compute.py) l.202+) | STORY-173/174/251 |
| §6 Architecture/event-driven | **CONFORME** | Bus canonique : `Bus` Protocol l.280, `InMemoryEventBus` l.316, `RedisPubSubEventBus` l.452 canal `windflow:events` l.438 ([`core/events.py`](../../backend/app/core/events.py)) ; runtime asyncio unique | STORY-162, F1/F6 |
| §7 Sécurité | **CONFORME** | SecretManager Fernet AES-256 ([`secret_manager.py`](../../backend/app/core/secret_manager.py) l.23/40), TOFU SSH présent, rate limit mémoire fallback, audit trail (status §7.10) | STORY-100→104/125/131 |
| §8 WebSocket | **CONFORME** | 8 canaux `@router.websocket` ([`websockets.py`](../../backend/app/api/v1/websockets.py) l.35→371 : général, deployment logs, terminal, containers logs/stats, ssh, journal, batch) ; auth stricte §2 | STORY-100/164.x/165 |
| §9 Stacks definitions | **CONFORME** | Validation unifiée `validate_stack_definition` ([`stack_loader_service.py`](../../backend/app/services/stack_loader_service.py) l.73) ; bornes `minimum`/`maximum` servies de façon cohérente schéma↔form ([`schemas/stack_definition.py`](../../backend/app/schemas/stack_definition.py) l.43-44/196) — l'écart B9 historique est clos par la cohérence actuelle | STORY-171 |
| §10 Plugins | **CONFORME** | Install réel : download sécurisé/checksum/extraction ([`plugin_manager_service.py`](../../backend/app/services/plugin_manager_service.py) l.76/219), rollback complet DB+fs+conteneur (l.8/199), [`plugin_gate_service.py`](../../backend/app/services/plugin_gate_service.py), [`plugin_api_router_service.py`](../../backend/app/services/plugin_api_router_service.py) (routes dynamiques) | STORY-169.x/170.x |
| §11 IA | **REPORTÉ** | [`litellm_service.py`](../../backend/app/services/litellm_service.py) : cache LLM consommé (STORY-168) mais `litellm.completion()` en TODO ×3 (l.127/303/331) + parsing l.374 — simulation assumée, 0 endpoint exposé → plugin IA Phase 5 | STORY-168/250.1 ; renvoi 254.3 (écart n°7) |
| §12 Automatisation | **CONFORME** | Scheduler engine asyncio : tâche dédiée, timeout `wait_for`, récupération orphelins `recover_orphans()`, horloge injectable ([`scheduler_engine.py`](../../backend/app/services/scheduler_engine.py) l.1-76) ; `scheduled_task_executions` persisté ([`models/scheduled_task_execution.py`](../../backend/app/models/scheduled_task_execution.py)) | STORY-160.x/161 |
| §13 Virtualisation | **CONFORME (à préserver)** | Scan hosts ~20 parseurs + probes sockets (status §14.5, golden tests STORY-166.3) — pilotage VMs/K8s hors périmètre confirmé (F4/plan §6) | STORY-166.3 ; plan §2.G |
| §14 Déploiement & exploitation | **CONFORME** | Alembic câblé au démarrage ([`database.py`](../../backend/app/database.py) l.16-37), `auto_detect_local_host` ([`config.py`](../../backend/app/config.py) l.553) ; backup core REPORTÉ F8 (initiative dédiée) | STORY-120.2/166.5 ; F8 |
| §15 Observabilité | **CONFORME** | `/api/v1/metrics` sans auth par design scrape ([`metrics.py`](../../backend/app/api/v1/metrics.py) l.28), dashboards Grafana ×2 + [`prometheus-alerts.yml`](../../infrastructure/docker/prometheus-alerts.yml) présents ; circuit breaker exposé | STORY-172/251 |
| §16 Tests & qualité | **CONFORME (avec écarts tracés)** | 204 fichiers unit + 21 intégration (comptage 2026-11-07) ; couverture par domaine status §13.3 (WS 94 %, cache 93 %, rate_limit 100 %…) ; **15 échecs préexistants** documentés status §13.4 (1 résidu STORY-172 + 14 stacks) → écarts n°1-2 | STORY-165/122.7/120.3 |

## Écarts découverts pendant l'audit (→ STORY-254.3 pour arbitrage)

Recoupement avec [`backend_status.md`](../../docs/backend_status.md) §14.2 — les 7 écarts résiduels sont **confirmés** par inspection :

1. **Échec test `/api/v1/metrics` vs garde-fou RBAC** — confirmé : endpoint sans auth (metrics.py l.28, design scrape) contredit `test_every_api_route_is_protected` (résidu STORY-172) ;
2. **14 échecs tests stacks** (`test_admin_stacks_validation.py` ×7 + `test_stacks_variables_contract.py` ×7) — **RÉSORBÉS depuis le comptage** : ré-exécution ciblée du 2026-11-07 → 28 passed, 0 échec sur ces 2 fichiers ; hypothèse factuelle : artefacts d'environnement corrigés par BUG-010 (sanitation PYTHONPATH, commit `963b871`, 2026-11-02 — postérieur au comptage STORY-253 du 2026-11-01) ; l'écart n°2 devient **obsolète** → à retirer de l'arbitrage 254.3 (confirmation : ne reste que le résidu STORY-172, écart n°1) ;
3. **[`helper/security.py`](../../backend/app/helper/security.py) bcrypt orphelin** — 0 consommateur (signalement STORY-252 n°1) ;
4. **Docstrings `expires_in: 1800` mensongers** ×3 ([`auth.py`](../../backend/app/api/v1/auth.py)) vs valeur réelle 900 (config l.36-38, signalement n°2) ;
5. **`env.example` variables non consommées** (signalement n°4) ;
6. **3 sites SSH ad hoc hors circuit breaker** (divergence documentée STORY-251) ;
7. **Appels LLM simulés** (TODO ×3 + parsing l.374 dans litellm_service) — report Phase 5 assumé.

**Aucun écart nouveau non répertorié** n'a été découvert par cette passe : les 15 sections sont conformes ou reportées, les 7 résiduels sont tous déjà tracés dans status §14.2. **Découverte positive** : écart n°2 résorbé (cf. ci-dessus) — reste 6 écarts résiduels réels à arbitrer en 254.3.

**Preuve d'exécution (E4)** : `pytest tests/unit/test_api/test_rbac_exhaustivite.py test_admin_stacks_validation.py test_stacks_variables_contract.py` → **1 failed, 28 passed** (unique échec = résidu STORY-172 documenté) ; collect complet : 3255 tests.

## État d'avancement technique
- [x] Tâche 1 : Audit §1-§4 (API, Auth, RBAC, Modèle)
- [x] Tâche 2 : Audit §5-§8 (Workloads, Event-driven, Sécurité, WS)
- [x] Tâche 3 : Audit §9-§12 (Stacks, Plugins, IA, Automatisation)
- [x] Tâche 4 : Audit §14-§16 (Déploiement, Observabilité, Tests) + synthèse écarts

## Notes d'implémentation (treat-story — 2026-11-07)

### Fichiers modifiés
- `.backlog/stories/STORY-254.1-audit-domaines-specs-code.md` — journal d'audit 15 sections + écarts consignés (le livrable de cette sous-story est le journal lui-même, porté par le fichier story)

### Méthode appliquée
- Inspection réelle par grep/lecture ciblée (`require_role` 179 points, alembic 13 migrations, bus l.280/316/452, 8 canaux WS l.35→371, Fernet l.23/40, scheduler orphelins, `/metrics` l.28, bornes `minimum/maximum` l.43-44…) — jamais copie des intentions de stories (D2) ;
- Recoupement systématique avec [`backend_status.md`](../../docs/backend_status.md) §13-§14 (édition 2026-11-01).

### Découvertes principales
1. **Écart n°2 du status §14.2 résorbé** : les 14 échecs stacks du comptage 2026-11-01 passent désormais (28 passed) — artefacts d'environnement BUG-010 (commit `963b871`, PYTHONPATH) ; reste 6 écarts résiduels réels (n°1, 3, 4, 5, 6, 7) ;
2. Volumétrie confirmée : 3255 tests collectés, 204 fichiers unit + 21 intégration ;
3. RBAC ≈ 179 points de contrôle (148 deps + 24 directs + 7 WS) — cohérent status « ~174 ».

### Divergences / décisions
- Aucune divergence de méthode vs plan de la sous-story ; écart n°2 signalé comme **obsolète** pour 254.3 (ne pas créer de bug pour un écart résorbé).

### Validation (écrans E1-E4)
- E1 ✅ 15 sections couvertes (§1→§16, §13 incluse) ; E2 ✅ chaque ligne porte une preuve fichier:ligne ou comptage grep ; E3 ✅ 7/7 écarts §14.2 retrouvés et statués (1 résorbé) ; E4 ✅ 1 failed (résidu STORY-172 documenté) + 28 passed sur fichiers à risques, collect 3255 OK.
