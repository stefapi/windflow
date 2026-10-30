# STORY-170 : [ABANDONED] Plugins — routes API dynamiques `/api/v1/plugins/{name}/…` et gates pre-deploy (approve/deny, timeout, Trivy) (P2-3, partie extension — axes B5, C6)

**Statut :** ABANDONED
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-3 partie extension (axes B5, C6, rapports §10/§7) — ampleur **L**

> **Note de clôture — découpe `split-story` (2026-10-30, mode proactif)** : cette story a été **découpée à l'issue de la phase d'analyse** (`analyse-story`), qui a conclu à une **complexité excessive** (13 tâches détaillées au-delà du seuil de ~8 tâches majeures, sur **trois périmètres faiblement couplés** — routes dynamiques, gates pre-deploy, plugin Trivy de référence ; verdict §Sous-stories ci-dessous). Conformément au pipeline (règles 01 §5.1, étape 2b), elle est refermée `ABANDONED` selon le pattern STORY-160/164/166/169 (Règle d'Or : fichier conservé pour l'historique) et **remplacée sans perte d'information** par 3 sous-stories autonomes :
>
> - [STORY-170.1](STORY-170.1-plugins-routes-api-dynamiques.md) — **Routes API dynamiques** : setting `plugin_dynamic_routes_enabled`, SDK `plugin_router` (`plugins/api.py`, préfixe `/api/v1/plugins/{name}` + tag `plugin-{name}`), `PluginApiRouterService` (snapshot/diff, invalidation `app.openapi_schema`, garde de préfixe, JWT défense en profondeur), branchements manager install/uninstall + rollback `extension_load_failed` (3e cas différé par 169.3) et lifespan, tests API 200/401/403/422/OpenAPI/404 post-uninstall (couvre l'**AC 1** + volet routes de l'AC 5)
> - [STORY-170.2](STORY-170.2-plugins-gates-pre-deploy-pipeline.md) — **Gates pre-deploy** : settings gate (timeout 300 s surchargeable, flag), schémas manifest `deploy_hooks.pre_deploy`, SDK gates (`plugins/gates.py` : `DeployContext`/`GateDecision`), `GateDeniedError`, `PluginGateService` (timeout/`on_timeout`/multi-gates ordre alphabétique, erreur = refus prudent), branchements manager + lifespan, insertion dans les **2 chemins** de `background_tasks.py` **avant création des containers** — refus = FAILED + events typés `GATE_DENIED`/`GATE_TIMEOUT` + progression WS + bus `deployment.failed`, tests pipeline (couvre les **AC 2 et AC 3** + volet pipeline de l'AC 5)
> - [STORY-170.3](STORY-170.3-plugins-trivy-gate-reference.md) — **Plugin Trivy de référence** : `demo_trivy_gate.py` — gate `never` réelle + bloquant simulé documenté, matrice de critères `never|any|critical_high|critical|more_than_current`, conventions image épinglée/volume cache `windflow-plugin-trivy-cache`/flux tag temporaire `<tag>-windflow-pending` (couvre l'**AC 4**) — **dépend de 170.2**
>
> **Redistribution des 13 tâches détaillées** (la numérotation de la recommandation initiale portait deux inversions — T11 = pipeline gates, T12 = tests routes — corrigées dans la découpe exécutée ; T3 SDK gates y était omis, réintégré) : **170.1** ← T1-partie (flag routes), T4, T7, T8-partie (volet routes), T9-partie (volet routes), T12 ; **170.2** ← T1-partie (settings gate), T2, T3, T5, T6, T8-partie (volet gates), T9-partie (volet gates), T11, T13 ; **170.3** ← T10. **Tests redistribués** : 170.1 ← `test_plugin_api_router_service.py`, `test_plugin_dynamic_routes.py` ; 170.2 ← `test_plugin_gate_service.py`, `test_plugin_manifest.py` (partie `deploy_hooks`), `test_deployment_service_events.py` (modif), `test_deploy_stack_gates.py` ; 170.3 ← `test_demo_trivy_gate.py`. **Divergences réparties** : n°3/n°6 → 170.1 (n°6 partagée 170.1/170.2, process-local) ; n°1/n°2/n°4 → 170.2 ; n°5 → 170.3.
>
> Le contexte technique, les dépendances vérifiées et les tâches détaillées ci-dessous ont été **intégralement répartis** dans ces sous-stories — **se reporter à elles pour le détail d'implémentation** (exécution directe `treat-story`, sans nouvelle phase d'analyse : les tâches y sont reprises avec leur numérotation d'origine). Ordre recommandé : **170.1 et 170.2 indépendants et parallélisables ; 170.3 après 170.2**.

## Description

En tant que développeur de plugins WindFlow, je veux que les extension/hybrid plugins montent **dynamiquement leurs routes API** sous `/api/v1/plugins/{name}/…` (préfixées, protégées par l'auth JWT et le RBAC du core, documentées OpenAPI, désenregistrées à la désinstallation) et que les **gates pre-deploy** — hooks synchrones de décision `approve`/`deny` exécutés après résolution d'images et avant création des containers, avec timeout (défaut 300 s) et plugin Trivy comme implémentation de référence — soient câblées dans le pipeline de déploiement, afin que l'extension du core promise par la spec 11 soit réelle.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §5, §14.1) : aucune route dynamique de plugin n'existe — le chargement d'extensions (api_module) de la spec 11 n'est pas implémenté ; les gates pre-deploy (`deploy_hooks.pre_deploy`) sont absentes du pipeline de déploiement.

## Contexte technique

### Constat d'analyse (2026-10-30)

La story couvre **trois périmètres faiblement couplés** partageant uniquement le socle d'import dynamique posé par STORY-163 :

**A. Routes API dynamiques** — inexistantes aujourd'hui. Le SDK plugins actuel ([`backend/app/plugins/hooks.py`](../../backend/app/plugins/hooks.py)) ne couvre que les hooks `@on_event` ; il n'y a pas de factory `plugin_router`. Le montage se fera sur l'app FastAPI racine ([`main.py:721`](../../backend/app/main.py:721) `app.include_router(api_router)`) : FastAPI/Starlette accepte `include_router` à chaud ; le **démontage** exige de tracker les routes ajoutées (snapshot avant/après de `app.router.routes`) et de les retirer. **Point critique** : `custom_openapi()` ([`main.py:725-764`](../../backend/app/main.py:725)) met le schéma en cache dans `app.openapi_schema` → **toute modification dynamique du set de routes doit invalider ce cache** (`app.openapi_schema = None`) pour que la route apparaisse/disparaisse de `/openapi.json` (AC 1).

**B. Gates pre-deploy** — absentes du pipeline. Le pipeline commun ([`background_tasks.py:24`](../../backend/app/tasks/background_tasks.py:24) `deploy_stack_async`) a deux chemins : docker simple (validation jalon 45 → `deploy_container` jalon 75) et compose (labels 55 → fichier généré 65 → `deploy_compose` 75). **Point d'insertion unique par chemin** : après validation, avant `deploy_container`/`deploy_compose` — aucune création de container n'a eu lieu à ce stade (AC 2). Le manifest Pydantic ([`schemas/plugin_manifest.py:262`](../../backend/app/schemas/plugin_manifest.py:262), `extra: "ignore"`) **n'a pas de champ `deploy_hooks`** : sans extension du schéma, la déclaration serait silencieusement ignorée. Le mécanisme d'import sécurisé existe et se réutilise : `_resolve_hooks_module_path` / `_module_name_from_path` ([`services/plugin_hooks_service.py:401-469`](../../backend/app/services/plugin_hooks_service.py:401)) — anti path-traversal, préfixe `windflow_plugin_` anti-masquage — à adapter au format `module:fonction` du handler de gate.

**C. Plugin Trivy de référence** — à créer dans [`backend/app/plugins/examples/`](../../backend/app/plugins/examples/) (pattern `demo_logger_hooks.py` de STORY-163) : gate `never` réelle + mode bloquant **simulé** (AC 4), matrice de critères exposée dans la config du manifest.

### Éléments existants à réutiliser / contraintes

- **Routes dynamiques spec 11 § Extension de l'API** : `plugin_router("{name}")` préfixé `/api/v1/plugins/{name}/` ; enregistrées au chargement du plugin (étape INSTALL de STORY-169), automatiquement : préfixées, **protégées JWT + RBAC core** (permissions endpoints plugin : lecture Viewer, écriture Operator, config Admin — spec 08), **documentées dans OpenAPI** (visibles `/docs`, tag dédié), **désenregistrées à la désinstallation** ; échec de chargement → rollback (désenregistrement des routes partiellement chargées, STORY-169 AC 3) ;
- **Gates pre-deploy spec 11 § Hooks de déploiement** : exécution **après résolution d'image, avant création des containers** — le plugin connaît les images exactes (nom, tag, digest) ; contrat d'entrée (`deployment_id`, `target`, `images[]`, `trigger` `manual|scheduled|webhook|batch`) et sortie (`approve()` / `deny(reason)`) ; **comportements par défaut** : aucun plugin n'implémente la gate → déploiement suit son cours (le core ne bloque jamais par défaut) ; **timeout** (défaut 300 s, configurable) → refus prudent `GATE_TIMEOUT` (« on ne déploie pas ce qu'on n'a pas pu évaluer ») sauf `on_timeout: approve` déclaré ; un refus = échec de déploiement classique : événement `deployment.failed` (code `GATE_DENIED`, plugin, raison), progression WebSocket et **lignes `deployment_events`** (STORY-167) ;
- **La gate s'applique à tous les chemins de déploiement** : stack deploy, recreate/Mettre à jour, batch-update, synchro Git future — brancher au niveau du pipeline commun ([`background_tasks.py:24`](../../backend/app/tasks/background_tasks.py:24) / [`docker_service.py:20`](../../backend/app/services/docker_service.py:20)) ;
- **Plugin Trivy de référence** : matrice de critères de blocage (`never` défaut / `any` / `critical_high` / `critical` / `more_than_current`), flux protégé par **tag temporaire** `<tag>-windflow-pending` (image candidate tirée puis scannée, image refusée supprimée, tag original restauré à l'approbation), image du scanner **épinglée par version** (jamais `:latest`), cache dans un volume `windflow-plugin-trivy-*` protégé du prune — implémenter au moins la gate + un mode `never` fonctionnel ; le scan complet (report vulnérabilités) peut rester simplifié à ce stade (le plugin complet relève du catalogue) ;
- **Distinction hooks vs gates** : `@on_event` (STORY-163) = asynchrone non bloquant ; gate = décision bloquante synchrone — ne pas mélanger ;
- Zones : pipeline de déploiement, nouveau support `plugin_api`/`plugin_gates`, [`plugin_manager_service.py:27`](../../backend/app/services/plugin_manager_service.py:27) (chargement extensions), OpenAPI multi-interfaces (garde-fou : maintenu à jour).

### Réutilisation proposée (réutilisation intelligente du legacy)

- **Directe** : `_resolve_hooks_module_path`/`_module_name_from_path` ([`plugin_hooks_service.py:401`](../../backend/app/services/plugin_hooks_service.py:401)) pour l'import sécurisé des `api_module`/handlers de gates ; pattern `load_installed_hooks` (requête `type IN (extension, hybrid) AND status IN (installed, running)`, best-effort WARNING sans crash startup) pour les chargements lifespan ; `require_viewer`/`require_operator`/`require_admin` ([`auth/rbac.py`](../../backend/app/auth/rbac.py)) et `get_current_active_user` pour la défense en profondeur JWT ; `DeploymentEventStore.append_event` + double écriture [`deployment_service.py:758-791`](../../backend/app/services/deployment_service.py:758) pour les traces typées ; `emit_progress_update`/`emit_status_change` pour la progression WS ; `AuditService.log` pour l'audit ; `EventType.DEPLOYMENT_FAILED` ([`core/events.py:104`](../../backend/app/core/events.py:104)) déjà déclaré dans le canon ; settings `plugins_base_dir`/`plugin_hooks_*` ([`config.py:556-580`](../../backend/app/config.py:556)) comme modèle des nouveaux settings.
- **Adaptation** : le pipeline d'échec de [`background_tasks.py:375-389`](../../backend/app/tasks/background_tasks.py:375) (except → `update_status(FAILED)`) est réutilisé tel quel mais alimenté par une exception typée gate portant code/plugin/raison, avec enrichissement du `data` de l'event (nouveau paramètre optionnel de `update_status`) ; `PluginHooksService.register` (idempotence par classe) inspire l'API de `PluginGateService.register` (par nom de plugin) ; le pattern rollback `_rollback_install` ([`plugin_manager_service.py:425`](../../backend/app/services/plugin_manager_service.py:425)) est étendu au 3e cas différé par 169.3 (échec de chargement d'extension).
- **Réécriture** : aucune — aucun équivalent n'existe (c'est l'objet de la story).

### Divergences identifiées par l'analyse (à consigner à l'implémentation)

1. **Résolution tag→digest inexistante** : le pipeline actuel ne résout pas les digests (le pull est implicite dans `deploy_container`/`deploy_compose`). Le contrat `images[]` sera alimenté **au mieux des données de la config finale** (`image` du container / `services.*.image` du compose — nom:tag, digest si explicitement fourni). La résolution complète relève de STORY-174 (WorkloadAdapter) — divergence documentée dans la docstring du contexte de gate.
2. **`deployment.failed` bus non émis au passage FAILED** : `update_status` émet WS + audit mais pas l'événement canonique bus (seul `stack.deployed` l'est au succès). Recommandation : émission best-effort post-commit `EventType.DEPLOYMENT_FAILED` pour tout passage FAILED (payload standard + `code`/`plugin`/`reason` si gate) — comble le trou STORY-162 au passage, reste conforme « un refus s'exprime comme un échec classique ».
3. **Montage process-wide vs multi-tenant** : `plugins.name` est **unique globalement** (arbitrage 169.3 n°5) → les routes dynamiques sont montées process-wide ; la confidentialité repose sur JWT + RBAC core (rôle global). Le scoping par organisation par route n'est pas mis en œuvre (coût par requête, aucune colonne d'appartenance exploitable au niveau HTTP) — divergence documentée dans le SDK (`plugins/api.py`), les plugins sensibles appliquent leur propre vérification.
4. **Gate en erreur = refus prudent** : une gate qui lève une exception (hors timeout) est traitée comme `deny` raison `gate_error` (même logique prudente que le timeout par défaut — on ne déploie pas ce qu'on n'a pas pu évaluer). Comportement à documenter dans le SDK.
5. **Trivy simplifié** : scan réel hors périmètre (AC 4) — `never` réel, bloquant simulé ; flux tag temporaire `<tag>-windflow-pending`, image épinglée et volume `windflow-plugin-trivy-cache` **documentés comme conventions** (constants + docstrings), non exécutés à ce stade.
6. **Multi-workers** : montage à chaud et registre de gates sont process-local — cohérent avec l'arbitrage F1 (déploiement supporté single-worker, déjà documenté pour le scheduler).

## Critères d'acceptation (AC)

- [ ] AC 1 : Un plugin extension (démonstrateur) déclarant `extensions.api_module` voit ses routes montées sous `/api/v1/plugins/{name}/…` — test : appel authentifié → 200 ; **sans token → 401** ; rôle insuffisant → 403 (RBAC core appliqué) ; la route apparaît dans `/openapi.json` avec son tag ; à la désinstallation, la route disparaît (404) et de l'OpenAPI.
- [ ] AC 2 : Les gates pre-deploy s'exécutent **après résolution d'images, avant création des containers** — test : une gate `deny(reason)` fait annuler le déploiement **avant toute création de container** (aucun conteneur créé), avec événement `deployment.failed` portant code `GATE_DENIED` + plugin + raison, progression WS et lignes `deployment_events` typées (STORY-167).
- [ ] AC 3 : **Comportements par défaut** : aucune gate enregistrée → déploiement suit son cours (non-régression) ; gate qui timeout (défaut 300 s, test avec timeout court simulé) → refus prudent `GATE_TIMEOUT` ; `on_timeout: approve` déclaré → déploiement autorisé au timeout ; plusieurs gates → approbation de toutes requise (premier `deny` l'emporte).
- [ ] AC 4 : Le **plugin Trivy** (gate de référence) fonctionne au moins en mode `never` (jamais bloquant) et en mode bloquant simulé — la matrice de critères est exposée dans sa config ; le flux tag temporaire et l'image épinglée sont implémentés ou documentés comme simplifiés à ce stade (écart noté pour le plugin catalogue complet) ; le cache scanner vit dans un volume protégé du prune (convention `windflow-plugin-*`).
- [ ] AC 5 : Tests de sécurité : routes dynamiques soumises au RBAC (401/403/422 sur échantillon), secrets du plugin jamais exposés ; non-régression des déploiements sans plugin ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Extension de l'API (`plugin_router`, préfixe, auth/RBAC/OpenAPI/désenregistrement), § **Hooks de déploiement (gates)** (moment d'exécution, contrat entrée/sortie, comportements par défaut, déclaration manifest `deploy_hooks.pre_deploy`), § Plugin Trivy (exemple, matrice de critères, flux tag temporaire, image épinglée), § Extension plugin / Hybrid plugin (types) ;
- [`08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — § Permissions sur les endpoints plugin (lecture Viewer, écriture Operator, config Admin) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Routes dynamiques des plugins (exemples Traefik/PostgreSQL/IA/Restic), § Prune des images/volumes (liste protégée `windflow-plugin-*`) ;
- [`02-familles-workloads.md`](../../docs/general_specs/02-familles-workloads.md) — § Sémantique de mise à jour / recreate (la gate s'applique au chemin de recréation) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité des plugins (isolation, permissions), § Plugin Trivy (blocage optionnel via gate) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-3 (« routes dynamiques d'extension `/api/v1/plugins/{name}/…` documentées OpenAPI »), §2.B B5, §2.C C6 ;
- [`backend_status.md`](../../docs/backend_status.md) — §5 (plugin_* services), §3.14, §4.4 (pipeline `background_tasks`).

## Dépendances

- **STORY-169.1→169.4** (installation réelle — ✔ DONE) : le pipeline s'arrête à « laisser l'extension chargeable » (statut `installed` pour les extensions, cf. [`plugin_manager_service.py:434-441`](../../backend/app/services/plugin_manager_service.py:434)) ; cette story branche le chargement (`api_module`/`deploy_hooks`) au même pipeline.
- **STORY-163** (✔ DONE) : mécanique d'import sécurisé des `hooks_module` réutilisée telle quelle pour `api_module` et les handlers de gates ; distinction contractuelle hooks (non bloquants) / gates (bloquantes) déjà documentée dans [`plugins/hooks.py`](../../backend/app/plugins/hooks.py).
- **STORY-167** (✔ DONE) : `DeploymentEventStore.append_event` + double écriture `update_status` consomment la trace typée des refus (data `code`/`plugin`/`reason`).
- **STORY-162** (✔ DONE) : `EventType.DEPLOYMENT_FAILED` canonique + bus `publish` best-effort.
- **STORY-122** (✔ DONE) : `require_viewer/operator/admin` appliqués aux routes dynamiques (RBAC core).
- **STORY-125** (✔ DONE) : audit `deployment.failed` déjà émis au passage FAILED (aucune modification nécessaire).
- **Aucune migration DB** : tout est persistant via `manifest_data` existant ; **aucun service externe nouveau** (Trivy exécuté = hors périmètre, simulé).
- Interactions descendantes : **STORY-174** (WorkloadAdapter — la gate s'appliquera au recreate ; la résolution digest complète s'y fera), **STORY-173** (prune épargne `windflow-plugin-*` — convention Trivy).

## Sous-stories

*(section réservée — story L : découpe possible routes dynamiques / gates ; plage réservée STORY-175-199)*

**Recommandation d'analyse (split-story mode proactif)** : la story dépasse le seuil de ~8 tâches majeures (13 tâches ci-dessous) sur **trois périmètres faiblement couplés** → découpe recommandée en :
- **STORY-170.1** — Routes API dynamiques : SDK `plugin_router`, service montage/désenregistrement + invalidation cache OpenAPI, branchement install/uninstall/lifespan, RBAC + OpenAPI + 404 post-uninstall — couvre AC 1 ;
- **STORY-170.2** — Gates pre-deploy : SDK gates, `deploy_hooks` manifest, `PluginGateService` (timeout/`on_timeout`/multi-gates), branchement pipeline `background_tasks` + échecs typés `GATE_DENIED`/`GATE_TIMEOUT` + traces `deployment_events`/bus, tests — couvre AC 2, AC 3 ;
- **STORY-170.3** — Plugin Trivy de référence : gate réelle mode `never` + bloquant simulé, matrice de critères, conventions tag temporaire/image épinglée/volume cache — couvre AC 4 ; dépend de 170.2.
Suffixes `.1/.2/.3` pattern STORY-160/164/166/169. **Aucun fichier de sous-story créé par l'analyse** — décision laissée au pipeline (`split-story`).

**Découpe exécutée — STORY-170.1 → 170.3** (2026-10-30, `split-story` mode proactif ; fichiers créés dans `.backlog/stories/`) : la redistribution réelle des tâches figure dans la note de clôture en tête de fichier — elle corrige deux inversions de numéros de la recommandation ci-dessus (T11 = branchement pipeline **gates** → 170.2 ; T12 = tests API **routes** → 170.1) et réintègre la tâche 3 (SDK gates, omise) dans 170.2.

## État d'avancement technique

> ⚠️ **Story refermée `ABANDONED` (découpe `split-story` 2026-10-30) — les cases ci-dessous ne seront jamais cochées ici** : les 13 tâches ont été redistribuées vers [STORY-170.1](STORY-170.1-plugins-routes-api-dynamiques.md) / [STORY-170.2](STORY-170.2-plugins-gates-pre-deploy-pipeline.md) / [STORY-170.3](STORY-170.3-plugins-trivy-gate-reference.md) (voir note de clôture pour la correspondance exacte) ; le suivi se fait dans les sous-stories.

- 2026-10-30 (`analyse-story`) : exploration terminée — `## Contexte technique`, `## Dépendances`, `## Tâches d'implémentation détaillées` (T1→T13) et `## Tests à écrire` rédigées à partir du code réel ; verdict complexité excessive → découpe recommandée (voir « Sous-stories »).
- 2026-10-30 (`split-story`, mode proactif) : **découpe exécutée** conformément au verdict — création de STORY-170.1 (routes dynamiques), 170.2 (gates pre-deploy + pipeline), 170.3 (plugin Trivy de référence) ; AC, contexte technique, dépendances et les 13 tâches **intégralement répartis** (AC1 → .1 ; AC2/3 → .2 ; AC4 → .3 ; AC5 → volets répartis .1/.2/.3), divergences réparties (n°3/6 → .1 ; n°1/2/4 → .2 ; n°5 → .3) ; story refermée `ABANDONED` (Règle d'Or : fichier conservé) ; epic EPIC-013 et kanban synchronisés ; **aucun fichier de code modifié** — le suivi se fait dans les sous-stories.

- [ ] Tâche 1 : Settings gate timeout + flag routes dynamiques (`config.py` + `env.example`)
- [ ] Tâche 2 : Schémas manifest `deploy_hooks.pre_deploy` (handler/timeout/on_timeout validés)
- [ ] Tâche 3 : SDK gates `plugins/gates.py` (DeployContext, GateDecision)
- [ ] Tâche 4 : SDK `plugin_router` `plugins/api.py` (préfixe + tag standardisés)
- [ ] Tâche 5 : Exceptions typées gate (`core/exceptions.py`)
- [ ] Tâche 6 : `PluginGateService` (registre, chargement sécurisé, exécution timeout/multi-gates)
- [ ] Tâche 7 : `PluginApiRouterService` (montage/démontage + invalidation OpenAPI + JWT défense en profondeur)
- [ ] Tâche 8 : Branchement `plugin_manager_service` (montage à l'install + rollback échec extension, démontage à l'uninstall)
- [ ] Tâche 9 : Branchement lifespan `main.py` (chargement routes + gates au startup, shutdown propre)
- [ ] Tâche 10 : Plugin Trivy de référence (`plugins/examples/` — gate never + simulé, matrice, conventions)
- [ ] Tâche 11 : Branchement pipeline `background_tasks` (2 chemins, refus typé avant création, traces events/bus)
- [ ] Tâche 12 : Tests API routes dynamiques (200/401/403/422, OpenAPI tag, 404 post-uninstall)
- [ ] Tâche 13 : Tests pipeline gates (deny/timeout/on_timeout/multi-gates/erreur, non-régression sans gate) + validation lint/typecheck/coverage

## Tâches d'implémentation détaillées

### Tâche 1 : Settings — timeout gate + flag routes dynamiques
**Objectif :** Ajouter la configuration nécessaire : `plugin_gate_timeout_seconds` (défaut 300, spec 11 — surchargeable par manifest), `plugin_gates_enabled` (défaut True), `plugin_dynamic_routes_enabled` (défaut True). Documenter dans `env.example` (section PLUGINS, pattern STORY-169.1 lignes 206-215).
**Fichiers :**
- `backend/app/config.py` — Modifier — settings section `=== Plugins Hooks ===` (ligne ~556) : 3 nouveaux champs Field avec description + bornes (timeout 1-3600).
- `env.example` — Modifier — entrées commentées `# PLUGIN_GATE_TIMEOUT_SECONDS=300`, `# PLUGIN_GATES_ENABLED=true`, `# PLUGIN_DYNAMIC_ROUTES_ENABLED=true`.
**Dépend de :** Aucune

### Tâche 2 : Manifest — schémas `deploy_hooks`
**Objectif :** Permettre la déclaration spec 11 § Hooks de déploiement dans le manifest (sinon `extra: "ignore"` la dropped silencieusement). `PluginDeployHookGate` : `handler` str **requis** au format `module:fonction` (chemin relatif `.py` + attribut — validé : refus chemins absolus et segments `..`, anti path-traversal cohérent `_resolve_hooks_module_path` ; regex du nom de fonction python), `timeout` int optionnel (1-3600, borne le défaut settings), `on_timeout` Literal["deny", "approve"] défaut "deny" (refus prudent). `PluginDeployHooks` : `pre_deploy` optionnel. Champ `deploy_hooks` sur `PluginManifest`. Les gates ne concernent que les types extension/hybrid → validation croisée en tâche 6 (warning + ignorée pour `service`, pas un rejet — le manifest peut être partagé).
**Fichiers :**
- `backend/app/schemas/plugin_manifest.py` — Modifier — classes `PluginDeployHookGate`, `PluginDeployHooks` (près de `PluginHook` ligne 239) + champ sur `PluginManifest` (près de `hooks` ligne 331).
**Dépend de :** Aucune

### Tâche 3 : SDK gates — `plugins/gates.py`
**Objectif :** Contrat public spec 11 exposé aux plugins (miroir de `plugins/hooks.py`) : `DeployImage` (dataclass : `name`, `tag`, `digest: Optional[str]`), `DeployContext` (dataclass : `deployment_id`, `target: dict` (id/nom/host), `images: list[DeployImage]`, `trigger: str` — docstring documentant la divergence n°1 : digest au mieux des données de config), `GateDecision` (dataclass : `approved: bool`, `reason: Optional[str]` ; `approve()` / `deny(reason)` classmethods). Docstring : contrat synchrone bloquant ≠ `@on_event`, timeout/`on_timeout`, comportement en erreur (divergence n°4), payload sans secret (rules 40). Aucune logique d'exécution ici (c'est le service).
**Fichiers :**
- `backend/app/plugins/gates.py` — Créer — SDK dataclasses + docstrings contrat.
**Dépend de :** Aucune

### Tâche 4 : SDK `plugin_router` — `plugins/api.py`
**Objectif :** Factory spec 11 § Extension de l'API : `plugin_router(name: str) -> APIRouter` retournant un router **préfixé** `/api/v1/plugins/{name}` et tagué `plugin-{name}` (visible `/docs`). Valider `name` kebab-case au moment de la factory (erreur explicite sinon). Les dépendances d'auth : le SDK ré-exporte `get_current_active_user`, `require_viewer`, `require_operator`, `require_admin` (imports depuis `app.auth`) pour que les plugins déclarent le RBAC par endpoint (spec 08 : lecture Viewer, écriture Operator, config Admin) ; **défense en profondeur** garantie par le service de montage (tâche 7) qui injecte `get_current_active_user` au niveau du `include_router` même si le plugin l'oublie. Docstring : divergence n°3 (montage process-wide, unicité globale de name, confidentialité via RBAC global), désenregistrement à l'uninstall.
**Fichiers :**
- `backend/app/plugins/api.py` — Créer — factory + ré-exports auth + docstrings.
**Dépend de :** Aucune

### Tâche 5 : Exceptions typées gate
**Objectif :** `GateDeniedError(WindFlowException)` — levée par le pipeline quand une gate refuse : `details = {"error_type": "gate_denied", "code": "GATE_DENIED"|"GATE_TIMEOUT"|"gate_error", "plugin": str, "reason": str}`. Exception **interne pipeline** (pas de mapping HTTP dédié — elle est interceptée par le `except` existant de `deploy_stack_async` qui passe en FAILED ; les endpoints ne l'exposent jamais en réponse). Pattern : sous-classe de `WindFlowException` de `core/exceptions.py`.
**Fichiers :**
- `backend/app/core/exceptions.py` — Modifier — nouvelle exception + docstring.
**Dépend de :** Aucune

### Tâche 6 : `PluginGateService` — registre et exécution
**Objectif :** Service singleton (`get_plugin_gate_service()` — pattern instances module-level des routers) : `register(plugin_name, handler, timeout_override, on_timeout)` / `unregister(plugin_name)` / `registered_count`. `load_installed_gates(session_factory)` : pattern `load_installed_hooks` ([`plugin_hooks_service.py:265`](../../backend/app/services/plugin_hooks_service.py:265)) — plugins `extension|hybrid` + `installed|running`, lecture `manifest_data.deploy_hooks.pre_deploy`, import sécurisé du handler : split `module:fonction`, résolution chemin via `_resolve_hooks_module_path` (import depuis `plugin_hooks_service` ou refactor helper partagé — pas de copier-coller), `getattr` de la fonction (absente → WARNING + ignoré, startup intact). `async run_gates(ctx: DeployContext) -> GateOutcome` : itération **ordre alphabétique des noms de plugins** (déterminisme), par gate `asyncio.wait_for(handler(ctx), timeout=manifest_override or settings)` ; timeout → `on_timeout == "approve"` sinon `deny` code `GATE_TIMEOUT` ; exception handler → `deny` code `gate_error` (divergence n°4) ; premier deny **court-circuite** (AC 3) ; retour `{decision, plugin_name, code, reason}` ; aucune gate enregistrée → approve immédiat (le core ne bloque jamais par défaut). Logging structuré sans payload sensible.
**Fichiers :**
- `backend/app/services/plugin_gate_service.py` — Créer — service complet.
- `backend/tests/unit/test_services/test_plugin_gate_service.py` — Créer — tests (voir § Tests).
**Dépend de :** Tâches 2, 3, 5

### Tâche 7 : `PluginApiRouterService` — montage/démontage
**Objectif :** Service singleton (`get_plugin_api_router_service()`) : `mount(plugin_name, router)` sur l'app FastAPI (résolue via `fastapi.FastAPI` courante — référence stockée au startup, tâche 9) : **snapshot** de `app.router.routes` avant `app.include_router(router, dependencies=[Depends(get_current_active_user)])` — défense en profondeur JWT — puis diff pour tracker les routes ajoutées par plugin ; **invalidation** `app.openapi_schema = None` (point critique `custom_openapi`, AC 1). `unmount(plugin_name)` : retrait des routes trackées de `app.router.routes` + invalidation OpenAPI ; idempotent. Garde : prefix du router monté **doit** être `/api/v1/plugins/{plugin_name}` (refus sinon — un plugin ne peut pas injecter de routes hors de son espace de noms, sécurité). `load_installed_routers(session_factory)` : pattern `load_installed_hooks` — plugins `extension|hybrid` actifs avec `extensions.api_module`, import sécurisé (réutilisation tâche 6), le module doit exposer un `router` (ou une variable `router` issue de `plugin_router(...)`) → montage best-effort WARNING sinon.
**Fichiers :**
- `backend/app/services/plugin_api_router_service.py` — Créer — service complet.
- `backend/tests/unit/test_services/test_plugin_api_router_service.py` — Créer — tests (voir § Tests).
**Dépend de :** Tâches 1, 4

### Tâche 8 : Branchement `plugin_manager_service` — install/uninstall
**Objectif :** Boucler le pipeline 169.3 avec l'extension : à l'**install**, après le statut final (service/hybrid `running`, extension `installed` — [`plugin_manager_service.py:434-443`](../../backend/app/services/plugin_manager_service.py:434)) : si `extensions.api_module` → montage des routes ; si `deploy_hooks.pre_deploy` → enregistrement de la gate. **Échec de chargement extension (3e cas AC 2 de 169.3, différé à cette story)** : montage partiel → `unmount` immédiat des routes déjà montées + unregister gate + déclenchement du `_rollback_install` existant (rollback complet DB/FS/conteneur) + erreur typée `extension_load_failed` cause+suggestion. À l'**uninstall** ([`plugin_manager_service.py:556`](../../backend/app/services/plugin_manager_service.py:556)) : `unmount(plugin.name)` + `unregister(plugin.name)` **avant** `db.delete` (la route disparaît, AC 1). Best-effort : l'échec du démontage ne fait pas échouer l'uninstall (WARNING — la ligne DB disparaît, le restart nettoie via le chargement lifespan).
**Fichiers :**
- `backend/app/services/plugin_manager_service.py` — Modifier — branchement install (after statut final) + uninstall (avant delete) + gestion `extension_load_failed`.
**Dépend de :** Tâches 6, 7

### Tâche 9 : Branchement lifespan `main.py`
**Objectif :** Au startup (bloc plugin hooks, lignes 125-155) : si `plugin_dynamic_routes_enabled` → initialiser `PluginApiRouterService` avec l'app + `load_installed_routers()` ; si `plugin_gates_enabled` → `PluginGateService` singleton + `load_installed_gates()`. Best-effort try/except pattern existant (un échec ne compromet pas le startup). Logs comptages. Au shutdown : rien de dédié (routes process-local, bus déjà arrêté par le shutdown existant) — le démonstrateur demo (`plugin_hooks_demo_enabled`) n'est PAS étendu ici (pas de montage démo par défaut).
**Fichiers :**
- `backend/app/main.py` — Modifier — startup block après plugin hooks bridge.
**Dépend de :** Tâches 6, 7

### Tâche 10 : Plugin Trivy de référence
**Objectif :** Extension plugin démonstrateur dans `backend/app/plugins/examples/` (pattern `demo_logger_hooks.py`) : module `demo_trivy_gate.py` exposant `pre_deploy(ctx) -> GateDecision` — lit `block_criteria` dans la config reçue : `never` (défaut) → `approve()` réel ; tout autre critère → **deny simulé** documenté (AC 4 : `critical_high` simulé par exemple, raison descriptive `"<image> : [SIMULÉ] 2 CRITICAL, 5 HIGH (critère critical_high)"`). Le **manifest fixture** (dans les tests + docstring) expose la matrice complète spec 11 : config `block_criteria` enum `never|any|critical_high|critical|more_than_current`. Conventions codées en constantes + docstrings : `TRIVY_IMAGE = "aquasec/trivy:<version-épinglée>"` (jamais `:latest`), volume cache `windflow-plugin-trivy-cache` (protégé du prune via pattern `windflow-plugin-*`, STORY-173), flux tag temporaire `<tag>-windflow-pending` documenté simplifié (divergence n°5).
**Fichiers :**
- `backend/app/plugins/examples/demo_trivy_gate.py` — Créer — gate de référence + constantes conventions + manifest d'exemple en docstring.
- `backend/tests/unit/test_plugins/test_demo_trivy_gate.py` — Créer — tests (voir § Tests).
**Dépend de :** Tâches 3, 6

### Tâche 11 : Branchement pipeline `background_tasks` — gates + échec typé
**Objectif :** Insérer les gates dans `deploy_stack_async` aux **deux chemins** avant création de container : helper `_extract_images(config) -> list[DeployImage]` (docker : `image` du final_config ; compose : `services.*.image` — divergence n°1 digest) ; helper `_run_pre_deploy_gates(db, deployment_id, stack, target_id, images, user_id)` : construit `DeployContext` (trigger `manual` — les autres triggers viendront avec scheduler/batch), appelle `run_gates`, sur refus lève `GateDeniedError` (code/plugin/raison). Docker : insertion après le jalon 45 `validated`, avant `deploy_container` (jalon 75). Compose : après le jalon 65 `compose_generated`, avant `deploy_compose`. **Refus = échec classique** : le `except` existant (lignes 375-389) passe FAILED via `update_status` — étendre `update_status` ([`deployment_service.py:686`](../../backend/app/services/deployment_service.py:686)) d'un paramètre `event_data_extra: dict | None = None` fusionné dans `event_data` de l'event STORY-167 (data `code`/`plugin`/reason`) ; le message de log porte `[ERROR] Déploiement refusé par la gate du plugin {plugin} : {reason}` (code GATE_*) ; **émission bus** `EventType.DEPLOYMENT_FAILED` best-effort post-commit au passage FAILED (divergence n°2 — payload IDs + code/plugin/raison si gate, jamais de secrets) ; progression WS : l'exception interrompt avant le jalon 75, `emit_status_change` existant notifie le FAILED (contrat AC 2 « progression WebSocket » satisfait par les canaux existants). La gate s'applique aussi au chemin recreate quand il passera par ce pipeline (STORY-174 — branchement au niveau commun déjà couvert).
**Fichiers :**
- `backend/app/tasks/background_tasks.py` — Modifier — helpers + 2 insertions + refus typé.
- `backend/app/services/deployment_service.py` — Modifier — paramètre `event_data_extra` + émission bus `deployment.failed` post-commit.
**Dépend de :** Tâches 3, 5, 6

### Tâche 12 : Tests API — routes dynamiques
**Objectif :** Valider AC 1 + la moitié routes de AC 5 sur une app de test (pattern `conftest` client ASGITransport) avec un plugin extension démonstrateur (module temporaire `tmp_path` + montage via `PluginApiRouterService`, plugin fixtures DB) : 200 authentifié, **401 sans token**, **403 rôle insuffisant** (endpoint `require_operator` appelé viewer), **422 body invalide** sur un POST Pydantic (échantillon AC 5), présence du path + tag `plugin-{name}` dans `/openapi.json` après montage, **404 + disparition OpenAPI** après `unmount` (uninstall), refus de montage d'un router au prefix étranger (garde sécurité), secrets : la réponse du plugin démo ne contient jamais `config_values` bruts ni tokens (assertion `not.toContain` équivalent Python).
**Fichiers :**
- `backend/tests/unit/test_api/test_plugin_dynamic_routes.py` — Créer — suite complète.
**Dépend de :** Tâches 7, 8, 9

### Tâche 13 : Tests pipeline — gates + non-régression + validation
**Objectif :** Valider AC 2, AC 3 + moitié pipeline de AC 5 : `deny(reason)` → **`deploy_container`/`deploy_compose` jamais appelés** (mocks assert_not_called), statut FAILED, `deployment_events` ligne `error` avec data `code=GATE_DENIED`/`plugin`/`reason` (requête store), bus `deployment.failed` émis avec le payload gate, audit `deployment.failed` existant intact ; timeout court simulé (gate `asyncio.sleep` + timeout 0.1 s) → `GATE_TIMEOUT` ; `on_timeout: approve` → déploiement poursuit ; deux gates (A approve, B deny) → deny l'emporte, court-circuit (A n'est pas ré-exécutée après B — ordre alphabétique) ; gate qui lève → refus prudent `gate_error` ; **aucune gate enregistrée → déploiement nominal inchangé** (non-régression AC 5, suite `test_deployments.py`/`test_deploy_stack*` existante repassée). Validation finale : `make backend-test-unit`, `make lint`, `make backend-typecheck`, couverture ≥ 80 % sur `plugin_gate_service`, `plugin_api_router_service`, `plugins/gates.py`, `plugins/api.py` (modules touchés AC 5).
**Fichiers :**
- `backend/tests/unit/test_tasks/test_deploy_stack_gates.py` — Créer — suite gates pipeline.
- `backend/tests/unit/test_services/test_deployment_service_events.py` — Modifier — tests du paramètre `event_data_extra` + émission bus `deployment.failed`.
**Dépend de :** Tâches 8, 9, 10, 11, 12

## Tests à écrire

### Backend

- `backend/tests/unit/test_services/test_plugin_gate_service.py` — registre register/unregister/idempotence ; `load_installed_gates` : handler valide chargé, manifest sans `deploy_hooks` ignoré (nominal sans log), handler chemin invalide/traversal → WARNING + ignoré (startup intact), gate pour plugin `service` ignorée ; `run_gates` : aucune gate → approve, approve pass-through, deny court-circuit (2e gate non exécutée), timeout → `GATE_TIMEOUT` deny, `on_timeout: approve` → approve, exception handler → `gate_error` deny, ordre alphabétique déterministe, timeout manifest override > settings.
- `backend/tests/unit/test_services/test_plugin_api_router_service.py` — montage : routes présentes sous `/api/v1/plugins/{name}/…` uniquement, tag OpenAPI, cache OpenAPI invalidé (path visible dans `/openapi.json` après montage) ; démontage : routes retirées, idempotent, OpenAPI re-généré sans le path ; garde : router au prefix étranger refusé ; JWT défense en profondeur : endpoint de plugin sans dependency → 401 sans token quand même.
- `backend/tests/unit/test_api/test_plugin_dynamic_routes.py` — **sécurité obligatoire (rules 40)** : `test_route_200_authenticated`, `test_route_401_without_token`, `test_route_403_insufficient_role`, `test_route_422_invalid_body`, `test_openapi_contains_plugin_tag`, `test_uninstall_removes_route_404_and_openapi`, `test_response_does_not_expose_plugin_secrets` (aucun token Fernet/mot de passe dans la réponse).
- `backend/tests/unit/test_plugins/test_demo_trivy_gate.py` — Trivy AC 4 : `never` → approve quelle que soit l'image ; `critical_high` simulé → deny avec raison contenant `[SIMULÉ]` et le nom d'image ; critère inconnu → comportement `never` (fail-safe) ; constantes conventions (image épinglée sans `:latest`, volume `windflow-plugin-trivy-cache`).
- `backend/tests/unit/test_tasks/test_deploy_stack_gates.py` — AC 2/AC 3 : `test_deny_cancels_before_container_creation` (deploy_container/compose `assert_not_called` + FAILED + event `GATE_DENIED`/plugin/raison + bus `deployment.failed`), `test_timeout_denies_gate_timeout`, `test_on_timeout_approve_deploys`, `test_multiple_gates_first_deny_wins`, `test_gate_error_denies_prudently`, `test_no_registered_gate_deploys_nominal` (non-régression), chemin compose couvert en miroir du chemin docker.
- `backend/tests/unit/test_schemas/test_plugin_manifest.py` — Modifier — `deploy_hooks` : handler `module:fonction` valide/invalide (absolu, `..`, sans `:`), timeout bornes, `on_timeout` enum, valeur par défaut deny.
- `backend/tests/unit/test_services/test_deployment_service_events.py` — Modifier — `event_data_extra` fusionné dans le data de l'event ; émission bus `deployment.failed` au passage FAILED (best-effort, payload sans secret).

### Frontend

- Aucun — périmètre backend uniquement (la vue [`Plugins.vue`](../../frontend/src/views/Plugins.vue) existante consomme l'API plugins sans changement de contrat ; les routes dynamiques sont consommées par les clients des plugins, pas par le core).

### Commandes de validation
```bash
# Tests ciblés (modules touchés)
poetry run pytest backend/tests/unit/test_services/test_plugin_gate_service.py backend/tests/unit/test_services/test_plugin_api_router_service.py backend/tests/unit/test_api/test_plugin_dynamic_routes.py backend/tests/unit/test_plugins/test_demo_trivy_gate.py backend/tests/unit/test_tasks/test_deploy_stack_gates.py -v

# Non-régression déploiements + plugins existants
poetry run pytest backend/tests/unit/test_tasks/ backend/tests/unit/test_api/test_plugins.py backend/tests/unit/test_api/test_plugins_rbac.py backend/tests/unit/test_services/test_deployment_service_events.py -v

# Quality gates (AC 5)
make backend-test-unit
make lint
make backend-typecheck
poetry run pytest backend/tests/unit/test_services/test_plugin_gate_service.py backend/tests/unit/test_services/test_plugin_api_router_service.py --cov=backend/app/services/plugin_gate_service.py,backend/app/services/plugin_api_router_service.py --cov-fail-under=80
```
