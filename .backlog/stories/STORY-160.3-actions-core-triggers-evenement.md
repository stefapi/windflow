# STORY-160.3 : Actions core réelles du scheduler et triggers événement (P2-1, partie exécution)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-160 ([ABANDONED — découpe proactive post-analyse le 2026-10-21](STORY-160-moteur-scheduler-asyncio.md))
**Item plan :** P2-1 (axe A8, rapport §12) — ampleur **M**

> **Périmètre (découpe)** : cette sous-story reprend le **volet exécution** de STORY-160 — implémentation réelle des actions core (`host.scan` via `TargetScannerService`, `compute.docker.prune` avec dry-run par défaut et liste protégée `windflow-plugin-*`), stubs tracés `stack.backup`/`admin.backup` (renvoi F8) et `notification.send` (renvoi P2-15), et **abonnement `EventBus`** pour les triggers événement (données de l'événement en paramètres additionnels). Couvre l'AC 2 de la mère (partie exécution/triggers événement). Le volet définition (registre/modèle/API) est porté par [STORY-160.1](STORY-160.1-modele-registre-actions-api-schedules.md) (**pré-requis**) ; le volet moteur runtime par [STORY-160.2](STORY-160.2-moteur-runtime-asyncio.md) (**pré-requis** — le moteur invoque les handlers enregistrés ici).

## Description

En tant qu'administrateur WindFlow, je veux que les actions du registre scheduler soient **réellement exécutées** — `host.scan` (scan de cible réel via le service existant), `compute.docker.prune` (prune Docker images/volumes protégé, dry-run par défaut) — et que les tâches à trigger **événement** soient déclenchées par le bus (`EventBus`) avec les données de l'événement en paramètres additionnels, afin que l'automatisation core (spec 17 § Actions core) produise des effets concrets et vérifiables, sans jamais exécuter d'action destructive non protégée.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §5) : aucune action n'est implémentée — le CRUD de définitions ne mène à aucune exécution ; le plan exige des actions core réelles (`host.scan`, `compute.docker.prune`) et des triggers événement (ex. `deployment.failed` → `notification.send`).

## Contexte technique

> Extrait de l'analyse STORY-160 (2026-10-21, `analyse-story`) — volet actions/triggers. Fondée sur le code réel du dépôt (fichiers/lignes cités). Aucun code modifié.

### Patterns existants à réutiliser (directs)

- **Action `host.scan`** : [`TargetScannerService`](../../backend/app/services/target_scanner_service.py) — `scan_localhost()` ([`:90`](../../backend/app/services/target_scanner_service.py)), `scan_remote()` ([`:99`](../../backend/app/services/target_scanner_service.py), TOFU STRICT), `scan_and_update_target()` ([`:145`](../../backend/app/services/target_scanner_service.py)) **directement consommables** par le handler.
- **Action `compute.docker.prune`** : ⚠️ [`docker_client_service.py`](../../backend/app/services/docker_client_service.py) n'expose que `remove_image(force, no_prune)` ([`:1199`](../../backend/app/services/docker_client_service.py)) — **aucun wrapper** `images.prune()`/`volumes.prune()` : l'action exige soit de **nouveaux wrappers** (docker SDK), soit la **consommation du prune protégé de STORY-173** (sémantique : liste `windflow-plugin-*` épargnée, dry-run, confirmation) — coordination à tracer (cf. Risques hérités).
- **Bus événementiel** : [`EventType`](../../backend/app/core/events.py:18) (~33 événements, nomenclature legacy `target.*`, `deployment.completed`…) + `EventBus.subscribe/emit` — point d'accroche des triggers événement ; STORY-162 fera migrer la nomenclature (période de double émission, risque §7.3).
- **Registre d'actions** : posé par [STORY-160.1](STORY-160.1-modele-registre-actions-api-schedules.md) (`action_registry` + schémas de paramètres par action) — cette story **enregistre les handlers réels** au registre (remplacement des stubs pour `host.scan`/`compute.docker.prune` ; les stubs `stack.backup`/`admin.backup`/`notification.send` restent explicites et tracés).
- **Moteur** : posé par [STORY-160.2](STORY-160.2-moteur-runtime-asyncio.md) (`SchedulerEngine` — dispatch via le registre, exécution en tâche dédiée, timeout, verrou) — cette story **ne modifie pas le moteur**, elle alimente le registre et s'abonne au bus.
- **Transversal** : exceptions [`WindFlowException`](../../backend/app/core/exceptions.py) ; audit [`AuditService.log`](../../backend/app/services/audit_service.py) (`_sanitize_details`) pour les actions destructrices ; logs structurés sans `parameters` bruts ni secrets.

### Points d'intégration & contraintes (arbitrages d'analyse)

- **Wrappers prune (arbitrage d'entrée)** : si **STORY-173 est fusionnée**, consommer son service de prune protégé (liste `windflow-plugin-*` épargnée, dry-run, confirmation) ; **sinon** ajouter des wrappers minimaux `images.prune()`/`volumes.prune()` au [`docker_client_service.py`](../../backend/app/services/docker_client_service.py) **avec dry-run par défaut** et liste protégée — la sémantique de 173 doit être respectée dès maintenant pour éviter une divergence ultérieure (décision à tracer en note d'implémentation).
- **Triggers événement** : abonnement `EventBus.subscribe(event_type, callback)` — la callback résout les définitions `trigger_type="event"` + `event_name` correspondant, puis **exécute l'action avec les données de l'événement en paramètres additionnels** (ex. `deployment.failed` → `notification.send` avec payload de l'événement). Exécution via le même chemin moteur que le cron (tâche dédiée, verrou, timeout, store) — jamais inline dans la callback du bus.
- **Double nomenclature (si STORY-162 non fusionnée)** : se brancher sur l'enum `EventType` **legacy** existant ([`events.py:18`](../../backend/app/core/events.py)) avec **période de double émission** documentée (risque §7.3 — STORY-162 harmonisera ; l'`event_name` des définitions est validé contre la liste canonique par 160.1).
- **Stubs explicites** : `stack.backup`/`admin.backup` (renvoi F8/initiative backup) et `notification.send` (renvoi P2-15) restent enregistrés en **stub explicite** — à l'exécution ils se terminent en `skipped`/`failed` **documenté** (jamais de succès silencieux) ; comportement tracé dans les journaux d'exécution.
- **Actions destructrices** : `compute.docker.prune` — dry-run **par défaut** dans le schéma de paramètres (posé en 160.1), exécution réelle (`dry_run=false`) réservée à des définitions créées par Admin (RBAC à la création) ; audit systématique de l'exécution (pattern `_sanitize_details`).
- **Secrets & paramètres** : les paramètres additionnels issus d'un événement sont **re-validés** par le schéma Pydantic de l'action avant exécution (jamais d'injection de payload brut non validé) ; jamais de secrets dans les journaux d'exécution.

### Risques hérités (de l'analyse mère, périmètre actions/triggers)

- **Wrappers docker manquants** : `images.prune()`/`volumes.prune()` inexistants ([`docker_client_service.py:1199`](../../backend/app/services/docker_client_service.py)) — dépend de la disponibilité de STORY-173 ; arbitrage d'entrée à tracer (cf. ci-dessus).
- **Double nomenclature événements** : branche sur `EventType` legacy tant que STORY-162 n'est pas fusionnée — période de double émission à documenter (risque §7.3 de l'epic).
- **P2-15 non matérialisée** : `notification.send` reste un stub — l'arbitrage EPIC-013 (plage réservée STORY-175-199 ou vague suivante) doit être tracé avant la finalisation de la famille 160.
- **Aucun Docker/SSH/réseau réel en tests** : tous les handlers sont testés avec **mocks** (docker SDK, scanner) — règle 35 ; les tests E2E réels relèvent des environnements d'intégration, hors périmètre.

### Checklist sécurité (règle 40) — volet actions/triggers

- **AuthN/AuthZ** : exécution **sans contexte utilisateur** (système) — actions destructrices (`prune` réel) réservées à des définitions créées par Admin (RBAC à la création via 160.1, verrouillé par le registre) ; aucune surface HTTP nouvelle.
- **Validation & injection** : paramètres d'action (définition **et** payload d'événement) re-validés par le schéma Pydantic de l'action avant exécution ; jamais d'exécution shell/SSH avec paramètres non validés ; action inconnue → `failed` explicite (moteur, 160.2).
- **Données sensibles** : journaux d'exécution sans secrets ni `parameters` bruts ; payload d'événement potentiellement sensible masqué dans les logs (`_sanitize_details`).
- **Audit & traçabilité** : audit des exécutions d'actions destructrices (prune réel — qui/quoi/quand via la définition) ; exécutions matérialisées via le contrat `ExecutionStore` (160.2/161).

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend la partie exécution de l'AC 2 de la mère)* : actions core **réelles** en place — `host.scan` appelle [`scan_and_update_target()`](../../backend/app/services/target_scanner_service.py:145) ; `compute.docker.prune` exécute le prune (images/volumes) **en dry-run par défaut** avec liste protégée `windflow-plugin-*` épargnée (wrappers SDK ou service STORY-173 — arbitrage tracé) ; stubs `stack.backup`/`admin.backup`/`notification.send` **tracés** (terminaison documentée `skipped`/`failed`, jamais de succès silencieux) ; action inconnue dans une définition → exécution `failed` avec erreur explicite. *(validé : terminaison stubs = `failed` documenté, divergence tracée ci-dessous)*
- [x] AC 2 *(reprend la partie triggers de l'AC 2 de la mère)* : les triggers **événement** déclenchent l'action avec les **données de l'événement en paramètres additionnels** — test : émission de `DEPLOYMENT_FAILED` sur le bus → la tâche `trigger_type="event"`/`event_name` correspondant exécute `notification.send` (stub) avec le payload en paramètres ; l'exécution passe par le chemin moteur (tâche dédiée, verrou, timeout — jamais inline dans la callback).
- [x] AC 3 *(découpe locale : sécurité & résilience, hérite de l'esprit AC 5 de la mère)* : un échec d'action **n'affecte pas la boucle** ni les autres tâches (isolation par exécution) ; prune réel audité ; tous les tests avec **mocks** (aucun Docker/SSH/réseau réel) ; couverture ≥ 80 % sur les nouveaux modules ; build + lint + tests passent.

## Références spécification

- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — § Actions core (liste canonique, sémantique des actions), § Scheduler core (triggers événement), § Bonnes pratiques (idempotence, secrets jamais dans les logs) ;
- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Liste canonique des événements (nomenclature des triggers) ;
- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Bus d'événements internes (triggers événement) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-1, §2.A A8 ; [`backend_status.md`](../../docs/backend_status.md) §5.

## Dépendances

- **[STORY-160.1](STORY-160.1-modele-registre-actions-api-schedules.md) — pré-requis obligatoire** : registre d'actions + schémas de paramètres (les handlers réels s'y enregistrent), nomenclature canonique arbitrée, modèle `trigger_type`/`event_name`.
- **[STORY-160.2](STORY-160.2-moteur-runtime-asyncio.md) — pré-requis obligatoire** : moteur `SchedulerEngine` (dispatch, verrou, timeout, tâche dédiée, contrat `ExecutionStore`) — les triggers événement réutilisent son chemin d'exécution.
- **STORY-173** (prune protégé `/compute`) — coordination : si fusionnée, consommer son service (sémantique `windflow-plugin-*` épargnée, dry-run) ; sinon wrappers minimaux docker SDK avec dry-run par défaut (décision à tracer) ; l'alignement final reste à coordonner avec 173.
- **STORY-162** (nomenclature canonique du bus) — non bloquante : abonnement sur l'`EventType` legacy avec période de double émission documentée tant que 162 n'est pas fusionnée (risque §7.3) ; 162 harmonisera.
- **Story notifications P2-15** — `notification.send` reste en **stub explicite** ; arbitrage EPIC-013 (matérialisation plage STORY-175-199 ou report) à tracer avant finalisation de la famille 160.
- **F8 / initiative backup** — `stack.backup`/`admin.backup` en stubs tracés (renvoi explicite).
- **Conditionne** : démontre la valeur métier du moteur (160.2) ; participe à la chaîne critique n°3 (P3-1 purge croniter — via 160.1/160.2).

## État d'avancement technique

*(cochage progressif pendant treat-story ; origine mère indiquée par tâche — volet actions/triggers de l'analyse STORY-160)*

- [x] Tâche 1 — Arbitrage d'entrée prune (STORY-173 fusionnée ? sinon wrappers) + wrappers `images.prune`/`volumes.prune` si requis
- [x] Tâche 2 — Handler `host.scan` (consommation `TargetScannerService`)
- [x] Tâche 3 — Handler `compute.docker.prune` (dry-run défaut, liste protégée, audit)
- [x] Tâche 4 — Stubs tracés `stack.backup`/`admin.backup`/`notification.send` (terminaison documentée)
- [x] Tâche 5 — Enregistrement des handlers au registre (remplacement stubs → réel)
- [x] Tâche 6 — Triggers événement : abonnement `EventBus` + exécution via le chemin moteur
- [x] Tests — Handlers mockés (scanner/docker), triggers événement, isolation d'échec, audit prune

## Tâches d'implémentation détaillées

> Séquence issue de l'analyse STORY-160 (volet actions/triggers), renumérotée. Périmètre : handlers réels + abonnement bus — aucune modification du moteur (160.2) ni du registre/schémas (160.1, hormis l'enregistrement des handlers).

### Tâche 1 : Arbitrage prune + wrappers docker SDK (si requis)

**Objectif :** trancher la source du prune (STORY-173 vs wrappers locaux) et poser les wrappers manquants le cas échéant.

**Fichiers :**
- `backend/app/services/docker_client_service.py` — **Modifier** *(uniquement si STORY-173 non fusionnée)* : ajouter les wrappers `images_prune(filters=…)` / `volumes_prune(filters=…)` (docker SDK `client.images.prune()`/`client.volumes.prune()`) — **dry-run par défaut** (retourne l'estimation sans exécution : `dry_run=true` simule via filtres/listage), **liste protégée `windflow-plugin-*` épargnée** (filtres label/name), résultats bornés et typés ; **décision d'arbitrage tracée en note d'implémentation** (si 173 est fusionnée, consommer son service et ne pas dupliquer).

**Dépend de :** Arbitrage d'entrée (état STORY-173) — à tracer

### Tâche 2 : Handler `host.scan`

**Objectif :** action réelle de scan de cible via le service existant (zéro réécriture).

**Fichiers :**
- `backend/app/services/scheduler_actions.py` — **Créer** : handler `host_scan(ctx)` — valide les paramètres (`HostScanParams {target_id}` posé en 160.1), résout la cible, appelle [`TargetScannerService.scan_and_update_target()`](../../backend/app/services/target_scanner_service.py:145) (dispatch interne localhost/remote [`scan_localhost()`](../../backend/app/services/target_scanner_service.py:90)/[`scan_remote()`](../../backend/app/services/target_scanner_service.py:99) — TOFU STRICT), retourne un résultat typé (machines découvertes, durée) ; erreurs → `WindFlowException` (exécution `failed` par le moteur) ; logs sans credentials.

**Dépend de :** STORY-160.1 (schéma `HostScanParams`), STORY-160.2 (chemin d'exécution)

### Tâche 3 : Handler `compute.docker.prune`

**Objectif :** action destructive protégée — dry-run par défaut, liste protégée, audit.

**Fichiers :**
- `backend/app/services/scheduler_actions.py` — **Modifier** (complément) : handler `compute_docker_prune(ctx)` — valide `DockerPruneParams {resource: images|volumes, dry_run: bool = True, …}` (160.1), exécute via le service de la tâche 1 (wrappers locaux ou STORY-173), **jamais de suppression hors dry-run sans `dry_run=false` explicite** ; **audit systématique** de l'exécution réelle ([`AuditService.log`](../../backend/app/services/audit_service.py), `_sanitize_details`) ; résultat typé (espace récupéré estimé/réel, éléments épargnés `windflow-plugin-*`).

**Dépend de :** Tâche 1, STORY-160.1 (schéma), STORY-160.2

### Tâche 4 : Stubs tracés `stack.backup`/`admin.backup`/`notification.send`

**Objectif :** terminaison explicite et journalée pour les actions non implémentables à ce stade (jamais de succès silencieux).

**Fichiers :**
- `backend/app/services/scheduler_actions.py` — **Modifier** (complément) : handlers stubs — `stack_backup`/`admin_backup` (renvoi **F8/initiative backup**) et `notification_send` (renvoi **P2-15** — accepte le payload d'événement en paramètres additionnels et le journalise **masqué**) ; terminaison en `skipped` avec raison explicite « action non implémentée (renvoi F8/P2-15) » via le store (160.2) ; renvois tracés pour la matérialisation future.

**Dépend de :** STORY-160.1 (registre — statuts `implemented=False`), STORY-160.2 (store/`mark_skipped`)

### Tâche 5 : Enregistrement des handlers au registre

**Objectif :** basculer les actions du statut stub vers réel dans le registre (source de vérité du dispatch).

**Fichiers :**
- `backend/app/services/action_registry.py` — **Modifier** (posé par 160.1) : enregistrer les handlers réels `host.scan`/`compute.docker.prune` (`implemented=True`) et les stubs tracés (`implemented=False` — comportement exécutable documenté) ; cohérence : aucune définition ne peut référencer une action non enregistrée (validation 160.1 inchangée).

**Dépend de :** Tâches 2-4

### Tâche 6 : Triggers événement — abonnement `EventBus`

**Objectif :** déclencher les définitions `trigger_type="event"` depuis le bus, via le chemin moteur (jamais inline).

**Fichiers :**
- `backend/app/services/scheduler_event_triggers.py` — **Créer** : composant d'abonnement — `EventBus.subscribe(event_type, on_event)` pour les événements concernés (enum `EventType` legacy [`events.py:18`](../../backend/app/core/events.py), double nomenclature documentée si STORY-162 non fusionnée) ; `on_event` : re-valide le payload par le schéma de l'action, résout les définitions `trigger_type="event"`/`event_name` correspondantes (relecture défensive — existence + `enabled`), puis **délègue l'exécution au chemin moteur** (tâche dédiée, verrou, timeout, `ExecutionStore` avec `triggered_by="event"`) — jamais d'exécution inline dans la callback (un handler lent/erreur ne bloque pas le bus) ;
- `backend/app/main.py` ou `backend/app/services/scheduler_engine.py` — **Modifier** (point d'accroche minimal) : démarrage de l'abonnement avec le moteur (si `scheduler_enabled`) — au choix de l'implémentation, tracer la décision ; shutdown propre avec le moteur.

**Dépend de :** Tâches 2-5, STORY-160.2 (chemin moteur)

## Tests à écrire

> Règles 35/40 : **mocks uniquement** (docker SDK, scanner — aucun Docker/SSH/réseau réel), time travel/monkeypatch si besoin. Familles issues de l'analyse mère (famille 160.3-actions/triggers).

### Backend — unitaires

- `backend/tests/unit/test_services/test_scheduler_actions.py` : `host.scan` — appelle [`scan_and_update_target`](../../backend/app/services/target_scanner_service.py:145) avec le bon `target_id` (mock `TargetScannerService`), résultat typé, erreur scanner → `failed` ; `compute.docker.prune` — **dry-run par défaut** (aucun appel suppressif mocké), `dry_run=false` → appel prune mocké, **liste `windflow-plugin-*` épargnée** (assert sur les filtres mockés), **audit écrit** sur exécution réelle (assert base, pattern [`test_audit_emission.py`](../../backend/tests/unit/test_api/test_audit_emission.py)) ; stubs — `stack.backup`/`admin.backup`/`notification.send` → terminaison `skipped` avec raison explicite (jamais succès silencieux), payload événement journalisé **masqué** (caplog — aucun secret/`parameters` brut).
- `backend/tests/unit/test_services/test_scheduler_event_triggers.py` : émission de `DEPLOYMENT_FAILED` sur le bus → la définition `trigger_type="event"`/`event_name` correspondante est exécutée avec le **payload en paramètres additionnels** (handler `notification.send` stub — assert sur les paramètres reçus) ; définition désactivée/supprimée → **jamais exécutée** (relecture défensive) ; payload invalide rejeté par le schéma (pas d'exécution) ; exécution **déléguée au chemin moteur** (tâche dédiée — jamais inline : assert qu'une erreur/latence du handler ne bloque pas la callback) ; événement sans définition → no-op.
- **Action inconnue** : définition référençant une clé absente du registre → exécution `failed` erreur explicite (complément AC — déjà couvert côté moteur 160.2, assert de bout en bout ici).
- **Isolation d'échec** (AC 3) : un handler qui lève n'affecte ni la boucle ni les autres tâches (exécutions suivantes normales).
- **Couverture ≥ 80 %** sur `scheduler_actions.py` + `scheduler_event_triggers.py` (AC 3).

### Commandes de validation

```bash
poetry run pytest backend/tests/unit/test_services/test_scheduler_actions.py backend/tests/unit/test_services/test_scheduler_event_triggers.py -v
make lint && make backend-typecheck
```

## Notes d'implémentation

*(ajoutées à la clôture par treat-story, 2026-10-23)*

### Fichiers créés

- [`backend/app/services/scheduler_actions.py`](../../backend/app/services/scheduler_actions.py) — handlers d'actions : `host_scan` (scan réel via `TargetScannerService.scan_and_update_target`, `NotFoundError` si cible inexistante, erreur scanner wrappée sans credentials), `compute_docker_prune` (dispatch images/volumes vers les wrappers protégés, audit de l'exécution réelle), stubs `stack_backup`/`admin_backup`/`notification_send` (`ActionNotImplementedError` avec raison F8/P2-15, payload journalisé masqué — clés uniquement), `register_scheduler_actions()` (liaison au registre, idempotente).
- [`backend/app/services/scheduler_event_triggers.py`](../../backend/app/services/scheduler_event_triggers.py) — `SchedulerEventTriggers` : abonnement à tous les `EventType`, résolution des définitions `trigger_type="event"`/`event_name`, fusion définition+payload **projetée sur les champs du schéma** (`extra="forbid"` — clés étrangères ignorées) puis re-validation, `event_type` alimenté quand le schéma l'expose, relecture défensive + verrou + délégation au chemin moteur (`_execute`) dans une tâche dédiée — jamais inline.
- `backend/tests/unit/test_services/test_scheduler_actions.py` — 17 tests (host.scan ×3, prune handler ×3, wrappers ×3, stubs ×4, registre ×4).
- `backend/tests/unit/test_services/test_scheduler_event_triggers.py` — 13 tests (dispatch/payload, chemin moteur, relecture défensive, payload invalide/extra, non-blocage, isolation, action inconnue, chevauchement, cycle de vie).

### Fichiers modifiés

- [`backend/app/services/docker_client_service.py`](../../backend/app/services/docker_client_service.py) — wrappers prune protégé : `prune_images()`/`prune_volumes()` (dry-run défaut = estimation par listage sans appel suppressif ; exécution réelle = suppressions individuelles des candidates uniquement), `PruneResult` borné, `PROTECTED_RESOURCE_PREFIX`/`is_protected_resource`, `_volume_names_in_use` (volumes montés via `list_containers`).
- [`backend/app/main.py`](../../backend/app/main.py) — lifespan : `register_scheduler_actions()` + `SchedulerEventTriggers(engine).start()` au démarrage du scheduler (si `scheduler_enabled`), `stop()` avant l'annulation du moteur au shutdown.

### Décisions techniques

1. **Arbitrage prune (Tâche 1)** : STORY-173 **non fusionnée** à ce stade (aucun service prune protégé dans le dépôt) → wrappers locaux posés dans `docker_client_service.py` avec la sémantique 173 d'entrée : dry-run par défaut, liste `windflow-plugin-*` épargnée **par construction** (les protégés ne sont jamais candidates), filtre `dangling` Engine pour les images, cartes des montages pour les volumes (le filtre `dangling` volumes exige Engine ≥ 1.42, non garanti), suppressions **individuelles** (jamais de `POST /prune` global qui contournerait la liste protégée), bornage `PRUNE_MAX_ITEMS=500`. L'alignement final (endpoint `/compute` browse/prune) reste à coordonner avec STORY-173.
2. **Enregistrement au registre (Tâche 5)** : `register_scheduler_actions()` explicite appelé **au lifespan** (pas d'effet de bord d'import) — hors `scheduler_enabled`, le registre reste en état « pré-160.3 » et le moteur échoue proprement « attendu STORY-160.3 » ; les stubs restent `implemented=False` avec handler exécutable à terminaison documentée.
3. **Triggers événement (Tâche 6)** : composant dédié `SchedulerEventTriggers` branché sur le **singleton** `get_event_bus()` (même instance que les émetteurs — `publish_event`/`DeploymentEventsService`), abonné aux ~33 `EventType` legacy (double nomenclature documentée, STORY-162 harmonisera). L'exécution passe par `engine._execute` (store, timeout, retries, politique d'erreur, `record_run`) après relecture défensive + verrou — la callback ne fait que résoudre et déléguer.

### Divergences par rapport à l'analyse

1. **Terminaison des stubs = `failed` (et non `skipped`)** : la story demande « terminaison `skipped` via le store (160.2) », mais `mark_skipped` n'est atteignable que depuis le moteur (`_trigger`), qui intercepte toute exception de handler comme un échec — y produire un `skipped` exigerait de **modifier le moteur** (interdit : 160.2 DONE, périmètre exclu). Les handlers stub lèvent donc `ActionNotImplementedError` portant la raison (« non implémentée (renvoi F8/P2-15) ») → exécution `failed` **documentée et journalisée**, jamais de succès silencieux — l'esprit de l'AC (terminaison explicite traçable) est préservé.
2. **`triggered_by` des exécutions événementielles = `"schedule"`** : `_execute` (160.2) code en dur `TRIGGERED_BY_SCHEDULE` ; distinguer `"event"` exigerait de modifier le moteur. La distinction est un point d'entrée **STORY-161** (impl DB du store), à tracer dans cette story.
3. **Préambule défensif dupliqué** : `_trigger` du moteur re-snapshotterait les paramètres depuis la base, perdant la fusion définition+payload ; `SchedulerEventTriggers._dispatch_one` reproduit donc la relecture défensive + le verrou (~15 lignes, miroir de `_trigger`) puis délègue l'exécution intégralement à `_execute` — l'orchestration d'exécution reste 100 % celle du moteur.
4. **`host.scan` : résultat borné** — le retour du handler est un résumé typé (capabilities, durée), pas le `ScanResult` complet (surface minimale côté journaux d'exécution).

### Tests & validation (tout vert)

- `poetry run pytest backend/tests/unit/test_services/test_scheduler_actions.py backend/tests/unit/test_services/test_scheduler_event_triggers.py -v` : **30 passed**.
- Non-régression : `poetry run pytest backend/tests/unit -q` : **1951 passed** (barre 1921 + 30 nouveaux, 0 échec).
- Couverture nouveaux modules : `scheduler_actions.py` **100 %**, `scheduler_event_triggers.py` **92 %** (≥ 80 % exigé).
- black/isort appliqués (6 fichiers reformatés) ; flake8 : 0 erreur sur les fichiers modifiés/créés ; mypy `backend/app` : **23 erreurs préexistantes, 0 nouvelle** (aucune sur les nouveaux modules) ; bandit `-ll` : **0 finding** sur les nouveaux modules (3 préexistants main.py:708/docker — hors périmètre).

### Restes à traiter ailleurs

- **STORY-161** : impl DB de l'ExecutionStore — en profiter pour distinguer `triggered_by="event"` des exécutions cron (divergence n°2) etbrancher `mark_skipped` stubs si la sémantique `skipped` doit être matérialisée en base.
- **STORY-173** : rapprochement `/compute`↔`/docker` — le handler prune consommera le service 173 à fusion (l'interface `PruneResult`/wrappers est prête à être déléguée).
- **STORY-252** : corrections de nomenclature spec 17 (`stack.*` vs `app.*`, clé unique prune) — déjà tracées par 160.1.
- **Activation** : `scheduler_enabled` reste `False` par défaut (opt-in) — l'activation production suppose le single-worker documenté (160.2) et la relecture de l'arbitrage P2-15/backup.
