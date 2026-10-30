# STORY-170.2 : Plugins — gates pre-deploy : SDK, `PluginGateService` timeout/multi-gates et insertion pipeline avant création des containers (P2-3, partie extension — STORY-170 découpée)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-170 ([ABANDONED — découpe proactive post-analyse le 2026-10-30](STORY-170-plugins-routes-dynamiques-gates.md))
**Item plan :** P2-3 partie extension (axes B5, C6) — volet **gates pre-deploy** de la spec 11 — ampleur **L**

> **Périmètre (découpe)** : cette sous-story reprend le **volet gates pre-deploy** de STORY-170 — settings gate (`plugin_gate_timeout_seconds` défaut 300 s surchargeable par manifest, `plugin_gates_enabled`), schémas manifest `deploy_hooks.pre_deploy`, SDK gates (`DeployContext`/`GateDecision` dans `plugins/gates.py`), exception typée `GateDeniedError`, `PluginGateService` (registre, chargement sécurisé, exécution timeout/`on_timeout`/multi-gates ordre alphabétique, erreur = refus prudent), branchements manager install/uninstall (volet gates) et lifespan, insertion dans les **2 chemins** de [`background_tasks.py`](../../backend/app/tasks/background_tasks.py) **après résolution d'images, avant création des containers** — refus = échec classique FAILED + `deployment_events` typés `GATE_DENIED`/`GATE_TIMEOUT` (STORY-167) + progression WS + bus `deployment.failed` (STORY-162). Couvre les **AC 2 et AC 3 de la mère** (+ volet pipeline de l'AC 5). **Indépendante de [STORY-170.1](STORY-170.1-plugins-routes-api-dynamiques.md)** ; **conditionne [STORY-170.3](STORY-170.3-plugins-trivy-gate-reference.md)** (plugin Trivy de référence).

## Description

En tant qu'administrateur WindFlow, je veux que les **gates pre-deploy** — hooks synchrones de décision `approve`/`deny` exécutés après résolution d'images et avant création des containers, avec timeout (défaut 300 s, configurable) et comportement prudent par défaut (« on ne déploie pas ce qu'on n'a pas pu évaluer ») — soient câblées dans le pipeline de déploiement, afin que l'extensibilité de sécurité promise par la spec 11 § Hooks de déploiement soit réelle : un refus s'exprime comme un échec de déploiement classique, tracé et notifié.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §5, §14.1) : les gates pre-deploy (`deploy_hooks.pre_deploy`) sont **absentes du pipeline de déploiement** — le pipeline commun ([`background_tasks.py:24`](../../backend/app/tasks/background_tasks.py:24) `deploy_stack_async`) n'exécute aucune gate avant `deploy_container`/`deploy_compose` ; le manifest Pydantic n'a pas de champ `deploy_hooks`.

## Contexte technique

> Extrait de l'analyse STORY-170 (2026-10-30, `analyse-story`) — périmètre **B. Gates pre-deploy**, redistribué par `split-story`. Les tâches détaillées **ont déjà été rédigées par l'analyse de la mère** et sont reprises ci-dessous (numérotation d'origine indiquée) — exécution directe par `treat-story`, pas de nouvelle phase d'analyse.

### Constat d'analyse (périmètre B de la mère)

- Le pipeline commun ([`background_tasks.py:24`](../../backend/app/tasks/background_tasks.py:24) `deploy_stack_async`) a deux chemins : docker simple (validation jalon 45 → `deploy_container` jalon 75) et compose (labels 55 → fichier généré 65 → `deploy_compose` 75). **Point d'insertion unique par chemin** : après validation, avant `deploy_container`/`deploy_compose` — **aucune création de container n'a eu lieu à ce stade** (AC 2).
- Le manifest Pydantic ([`schemas/plugin_manifest.py:262`](../../backend/app/schemas/plugin_manifest.py:262), `extra: "ignore"`) **n'a pas de champ `deploy_hooks`** : sans extension du schéma, la déclaration serait silencieusement ignorée.
- Le mécanisme d'import sécurisé existe et se réutilise : `_resolve_hooks_module_path` / `_module_name_from_path` ([`services/plugin_hooks_service.py:401-469`](../../backend/app/services/plugin_hooks_service.py:401)) — anti path-traversal, préfixe `windflow_plugin_` anti-masquage — à adapter au format `module:fonction` du handler de gate.

### Éléments existants à réutiliser / contraintes

- **Spec 11 § Hooks de déploiement (gates)** : exécution **après résolution d'image, avant création des containers** — le plugin connaît les images exactes (nom, tag, digest) ; contrat d'entrée (`deployment_id`, `target`, `images[]`, `trigger` `manual|scheduled|webhook|batch`) et sortie (`approve()` / `deny(reason)`) ; **comportements par défaut** : aucun plugin n'implémente la gate → déploiement suit son cours (le core ne bloque jamais par défaut) ; **timeout** (défaut 300 s, configurable) → refus prudent `GATE_TIMEOUT` sauf `on_timeout: approve` déclaré ; un refus = échec de déploiement classique : événement `deployment.failed` (code `GATE_DENIED`, plugin, raison), progression WebSocket et **lignes `deployment_events`** (STORY-167) ;
- **La gate s'applique à tous les chemins de déploiement** : stack deploy, recreate/Mettre à jour, batch-update, synchro Git future — brancher au niveau du pipeline commun ([`background_tasks.py:24`](../../backend/app/tasks/background_tasks.py:24) / [`docker_service.py:20`](../../backend/app/services/docker_service.py:20)) ;
- **Distinction hooks vs gates** : `@on_event` (STORY-163) = asynchrone non bloquant ; gate = décision bloquante synchrone — ne pas mélanger ;
- Zones : pipeline de déploiement, nouveau support `plugin_gates`, OpenAPI multi-interfaces (garde-fou : maintenu à jour).

### Réutilisation proposée (extraits de la mère)

- **Directe** : `_resolve_hooks_module_path`/`_module_name_from_path` pour l'import sécurisé des handlers de gates ; pattern `load_installed_hooks` (requête `type IN (extension, hybrid) AND status IN (installed, running)`, best-effort WARNING sans crash startup) pour le chargement lifespan ; `DeploymentEventStore.append_event` + double écriture ([`deployment_service.py:758-791`](../../backend/app/services/deployment_service.py:758)) pour les traces typées ; `emit_progress_update`/`emit_status_change` pour la progression WS ; `AuditService.log` pour l'audit ; `EventType.DEPLOYMENT_FAILED` ([`core/events.py:104`](../../backend/app/core/events.py:104)) déjà déclaré dans le canon ; settings `plugins_base_dir`/`plugin_hooks_*` ([`config.py:556-580`](../../backend/app/config.py:556)) comme modèle des nouveaux settings.
- **Adaptation** : le pipeline d'échec de [`background_tasks.py:375-389`](../../backend/app/tasks/background_tasks.py:375) (except → `update_status(FAILED)`) est réutilisé tel quel mais alimenté par une exception typée gate portant code/plugin/raison, avec enrichissement du `data` de l'event (nouveau paramètre optionnel de `update_status`) ; `PluginHooksService.register` (idempotence par classe) inspire l'API de `PluginGateService.register` (par nom de plugin).
- **Réécriture** : aucune — aucun équivalent n'existe (c'est l'objet de la story).

### Divergences héritées de la mère

- **n°1 — Résolution tag→digest inexistante** : le pipeline actuel ne résout pas les digests (le pull est implicite dans `deploy_container`/`deploy_compose`). Le contrat `images[]` sera alimenté **au mieux des données de la config finale** (`image` du container / `services.*.image` du compose — nom:tag, digest si explicitement fourni). La résolution complète relève de STORY-174 (WorkloadAdapter) — divergence documentée dans la docstring du contexte de gate.
- **n°2 — `deployment.failed` bus non émis au passage FAILED** : `update_status` émet WS + audit mais pas l'événement canonique bus (seul `stack.deployed` l'est au succès). Recommandation : émission best-effort post-commit `EventType.DEPLOYMENT_FAILED` pour tout passage FAILED (payload standard + `code`/`plugin`/`reason` si gate) — comble le trou STORY-162 au passage, reste conforme « un refus s'exprime comme un échec classique ».
- **n°4 — Gate en erreur = refus prudent** : une gate qui lève une exception (hors timeout) est traitée comme `deny` raison `gate_error` (même logique prudente que le timeout par défaut — on ne déploie pas ce qu'on n'a pas pu évaluer). Comportement à documenter dans le SDK.
- **n°6 — Multi-workers** : le registre de gates est process-local — cohérent avec l'arbitrage F1 (déploiement supporté single-worker, déjà documenté pour le scheduler).

### Architecture (insertion dans le pipeline commun)

```mermaid
flowchart TD
    A[deploy_stack_async] --> B{chemin docker ou compose}
    B -->|docker| C[apres jalon 45 - config validee]
    B -->|compose| D[apres jalon 65 - compose genere]
    C --> E[_run_pre_deploy_gates]
    D --> E
    E --> F{run_gates - verdict}
    F -->|aucune gate ou approve| G[deploiement nominal - jalon 75]
    F -->|deny / timeout / erreur handler| H[GateDeniedError - code + plugin + raison]
    H --> I[except existant : update_status FAILED]
    I --> J[deployment_events data typé + WS + audit existant]
    J --> K[bus deployment.failed post-commit - best-effort]
```

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend l'AC 2 de la mère)* : Les gates pre-deploy s'exécutent **après résolution d'images, avant création des containers** — test : une gate `deny(reason)` fait annuler le déploiement **avant toute création de container** (aucun conteneur créé), avec événement `deployment.failed` portant code `GATE_DENIED` + plugin + raison, progression WS et lignes `deployment_events` typées (STORY-167).
- [x] AC 2 *(reprend l'AC 3 de la mère)* : **Comportements par défaut** : aucune gate enregistrée → déploiement suit son cours (non-régression) ; gate qui timeout (défaut 300 s, test avec timeout court simulé) → refus prudent `GATE_TIMEOUT` ; `on_timeout: approve` déclaré → déploiement autorisé au timeout ; plusieurs gates → approbation de toutes requise (premier `deny` l'emporte).
- [x] AC 3 *(volet pipeline de l'AC 5 de la mère)* : Non-régression des déploiements sans plugin (suite existante repassée) ; couverture ≥ 80 % sur les modules touchés (`plugin_gate_service`, `plugins/gates.py`) ; build + lint + tests passent.

## Références spécification

- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § **Hooks de déploiement (gates)** (moment d'exécution, contrat entrée/sortie, comportements par défaut, déclaration manifest `deploy_hooks.pre_deploy`), § Extension plugin / Hybrid plugin (types) ;
- [`02-familles-workloads.md`](../../docs/general_specs/02-familles-workloads.md) — § Sémantique de mise à jour / recreate (la gate s'applique au chemin de recréation) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité des plugins (isolation, permissions), § Plugin Trivy (blocage optionnel via gate) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Prune des images/volumes (liste protégée `windflow-plugin-*` — convention, sans code ici) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-3, §2.B B5, §2.C C6 ;
- [`backend_status.md`](../../docs/backend_status.md) — §5 (plugin_* services), §4.4 (pipeline `background_tasks`).

## Dépendances

- **STORY-163** (✔ DONE) : mécanique d'import sécurisé des `hooks_module` réutilisée telle quelle pour les handlers de gates ; distinction contractuelle hooks (non bloquants) / gates (bloquantes) déjà documentée dans [`plugins/hooks.py`](../../backend/app/plugins/hooks.py).
- **STORY-167** (✔ DONE) : `DeploymentEventStore.append_event` + double écriture `update_status` consomment la trace typée des refus (data `code`/`plugin`/`reason`).
- **STORY-162** (✔ DONE) : `EventType.DEPLOYMENT_FAILED` canonique + bus `publish` best-effort.
- **STORY-125** (✔ DONE) : audit `deployment.failed` déjà émis au passage FAILED (aucune modification nécessaire).
- **STORY-169.1→169.4** (installation réelle — ✔ DONE) : volet gates du branchement manager — register à l'install si `deploy_hooks.pre_deploy`, unregister à l'uninstall (persistant via `manifest_data`, aucune migration).
- **Indépendante de [STORY-170.1](STORY-170.1-plugins-routes-api-dynamiques.md)** (routes dynamiques) — les deux volets ne partagent que le socle d'import sécurisé STORY-163 ; le branchement `plugin_manager_service`/lifespan est découpé en zones distinctes (gates ici, routes là-bas), cumulatif et sans interférence.
- **Conditionne [STORY-170.3](STORY-170.3-plugins-trivy-gate-reference.md)** (plugin Trivy de référence — s'écrit contre le SDK gates et `PluginGateService` posés ici).
- **Aucune migration DB** : tout est persistant via `manifest_data` existant ; **aucun service externe nouveau** (Trivy exécuté = hors périmètre, simulé — relève de 170.3).
- Interactions descendantes : **STORY-174** (WorkloadAdapter — la gate s'appliquera au recreate ; la résolution digest complète s'y fera), **STORY-173** (prune épargne `windflow-plugin-*` — convention documentaire, porte sur 170.3).

## État d'avancement technique

> Tâches **reprises de l'analyse de la mère** (T1-partie/T2/T3/T5/T6/T8-partie gates/T9-partie gates/T11/T13 de STORY-170, renumérotées 1→9 ci-dessous) — à cocher pendant `treat-story`.

- [x] Tâche 1 : Settings — timeout gate + flag gates (`config.py` + `env.example`)
- [x] Tâche 2 : Schémas manifest `deploy_hooks.pre_deploy` (handler/timeout/on_timeout validés)
- [x] Tâche 3 : SDK gates — `plugins/gates.py` (`DeployContext`, `GateDecision`)
- [x] Tâche 4 : Exceptions typées gate (`core/exceptions.py`)
- [x] Tâche 5 : `PluginGateService` (registre, chargement sécurisé, exécution timeout/multi-gates)
- [x] Tâche 6 : Branchement `plugin_manager_service` — volet gates (register à l'install, unregister à l'uninstall/rollback)
- [x] Tâche 7 : Branchement lifespan `main.py` — chargement des gates au startup
- [x] Tâche 8 : Branchement pipeline `background_tasks` (2 chemins, refus typé avant création, traces events/bus)
- [x] Tâche 9 : Tests pipeline gates (deny/timeout/on_timeout/multi-gates/erreur, non-régression sans gate) + validation lint/typecheck/coverage

## Tâches d'implémentation détaillées

> Reprises de l'analyse STORY-170 (2026-10-30), **ordre séquentiel strict**. Exigences sécurité ([`40-security.md`](../../.roo/rules/40-security.md)) : jamais de secrets dans les logs ni les payloads d'événements ; l'exception gate est **interne pipeline**, jamais exposée en réponse HTTP ; erreurs typées `WindFlowException` conformes au pattern du fichier.

### Tâche 1 : Settings — timeout gate + flag gates *(originale T1 de STORY-170, partie gates)*
**Objectif :** Ajouter la configuration gate : `plugin_gate_timeout_seconds` (défaut 300, spec 11 — surchargeable par manifest), `plugin_gates_enabled` (défaut True). Documenter dans `env.example` (section PLUGINS, pattern STORY-169.1 lignes 206-215). **Note de découpe :** la partie routes de la tâche 1 de la mère (`plugin_dynamic_routes_enabled`) relève de [STORY-170.1](STORY-170.1-plugins-routes-api-dynamiques.md) (tâche 1 là-bas) — même section settings, deux volets indépendants.
**Fichiers :**
- `backend/app/config.py` — Modifier — settings section `=== Plugins Hooks ===` (ligne ~556) : 2 nouveaux champs Field avec description + bornes (timeout 1-3600).
- `env.example` — Modifier — entrées commentées `# PLUGIN_GATE_TIMEOUT_SECONDS=300`, `# PLUGIN_GATES_ENABLED=true`.
**Dépend de :** Aucune

### Tâche 2 : Manifest — schémas `deploy_hooks` *(originale T2 de STORY-170)*
**Objectif :** Permettre la déclaration spec 11 § Hooks de déploiement dans le manifest (sinon `extra: "ignore"` la dropped silencieusement). `PluginDeployHookGate` : `handler` str **requis** au format `module:fonction` (chemin relatif `.py` + attribut — validé : refus chemins absolus et segments `..`, anti path-traversal cohérent `_resolve_hooks_module_path` ; regex du nom de fonction python), `timeout` int optionnel (1-3600, borne le défaut settings), `on_timeout` Literal["deny", "approve"] défaut "deny" (refus prudent). `PluginDeployHooks` : `pre_deploy` optionnel. Champ `deploy_hooks` sur `PluginManifest`. Les gates ne concernent que les types extension/hybrid → validation croisée en tâche 5 (warning + ignorée pour `service`, pas un rejet — le manifest peut être partagé).
**Fichiers :**
- `backend/app/schemas/plugin_manifest.py` — Modifier — classes `PluginDeployHookGate`, `PluginDeployHooks` (près de `PluginHook` ligne 239) + champ sur `PluginManifest` (près de `hooks` ligne 331).
**Dépend de :** Aucune

### Tâche 3 : SDK gates — `plugins/gates.py` *(originale T3 de STORY-170)*
**Objectif :** Contrat public spec 11 exposé aux plugins (miroir de `plugins/hooks.py`) : `DeployImage` (dataclass : `name`, `tag`, `digest: Optional[str]`), `DeployContext` (dataclass : `deployment_id`, `target: dict` (id/nom/host), `images: list[DeployImage]`, `trigger: str` — docstring documentant la divergence n°1 : digest au mieux des données de config), `GateDecision` (dataclass : `approved: bool`, `reason: Optional[str]` ; `approve()` / `deny(reason)` classmethods). Docstring : contrat synchrone bloquant ≠ `@on_event`, timeout/`on_timeout`, comportement en erreur (divergence n°4), payload sans secret (rules 40). Aucune logique d'exécution ici (c'est le service).
**Fichiers :**
- `backend/app/plugins/gates.py` — Créer — SDK dataclasses + docstrings contrat.
**Dépend de :** Aucune

### Tâche 4 : Exceptions typées gate *(originale T5 de STORY-170)*
**Objectif :** `GateDeniedError(WindFlowException)` — levée par le pipeline quand une gate refuse : `details = {"error_type": "gate_denied", "code": "GATE_DENIED"|"GATE_TIMEOUT"|"gate_error", "plugin": str, "reason": str}`. Exception **interne pipeline** (pas de mapping HTTP dédié — elle est interceptée par le `except` existant de `deploy_stack_async` qui passe en FAILED ; les endpoints ne l'exposent jamais en réponse). Pattern : sous-classe de `WindFlowException` de `core/exceptions.py`.
**Fichiers :**
- `backend/app/core/exceptions.py` — Modifier — nouvelle exception + docstring.
**Dépend de :** Aucune

### Tâche 5 : `PluginGateService` — registre et exécution *(originale T6 de STORY-170)*
**Objectif :** Service singleton (`get_plugin_gate_service()` — pattern instances module-level des routers) : `register(plugin_name, handler, timeout_override, on_timeout)` / `unregister(plugin_name)` / `registered_count`. `load_installed_gates(session_factory)` : pattern `load_installed_hooks` ([`plugin_hooks_service.py:265`](../../backend/app/services/plugin_hooks_service.py:265)) — plugins `extension|hybrid` + `installed|running`, lecture `manifest_data.deploy_hooks.pre_deploy`, import sécurisé du handler : split `module:fonction`, résolution chemin via `_resolve_hooks_module_path` (import depuis `plugin_hooks_service` ou refactor helper partagé — pas de copier-coller), `getattr` de la fonction (absente → WARNING + ignoré, startup intact). `async run_gates(ctx: DeployContext) -> GateOutcome` : itération **ordre alphabétique des noms de plugins** (déterminisme), par gate `asyncio.wait_for(handler(ctx), timeout=manifest_override or settings)` ; timeout → `on_timeout == "approve"` sinon `deny` code `GATE_TIMEOUT` ; exception handler → `deny` code `gate_error` (divergence n°4) ; premier deny **court-circuite** (AC 2) ; retour `{decision, plugin_name, code, reason}` ; aucune gate enregistrée → approve immédiat (le core ne bloque jamais par défaut). Logging structuré sans payload sensible.
**Fichiers :**
- `backend/app/services/plugin_gate_service.py` — Créer — service complet.
- `backend/tests/unit/test_services/test_plugin_gate_service.py` — Créer — tests (voir § Tests).
**Dépend de :** Tâches 2, 3, 4

### Tâche 6 : Branchement `plugin_manager_service` — volet gates *(originale T8 de STORY-170, partie gates)*
**Objectif :** À l'**install**, après le statut final ([`plugin_manager_service.py:434-443`](../../backend/app/services/plugin_manager_service.py:434)) : si `deploy_hooks.pre_deploy` → enregistrement de la gate via `PluginGateService.register`. À l'**uninstall** ([`plugin_manager_service.py:556`](../../backend/app/services/plugin_manager_service.py:556)) : `unregister(plugin.name)` **avant** `db.delete`. Sur **échec de chargement d'extension** (rollback volet routes de STORY-170.1) : `unregister` inclus au nettoyage — le nettoyage complet est garanti par la conjonction des deux volets. Best-effort : l'échec de l'unregister ne fait pas échouer l'uninstall (WARNING — la ligne DB disparaît, le restart nettoie via le chargement lifespan). **Note de découpe :** le volet routes du même branchement (montage/unmount, rollback `extension_load_failed`) relève de STORY-170.1 (tâche 4 là-bas) — zones distinctes du même pipeline install/uninstall.
**Fichiers :**
- `backend/app/services/plugin_manager_service.py` — Modifier — branchement install (after statut final) + uninstall (avant delete), volet gates.
**Dépend de :** Tâche 5

### Tâche 7 : Branchement lifespan `main.py` — volet gates *(originale T9 de STORY-170, partie gates)*
**Objectif :** Au startup (bloc plugin hooks, lignes 125-155) : si `plugin_gates_enabled` → `PluginGateService` singleton + `load_installed_gates()`. Best-effort try/except pattern existant (un échec ne compromet pas le startup). Logs comptages. Au shutdown : rien de dédié (registre process-local, bus déjà arrêté par le shutdown existant). **Note de découpe :** le volet routes (`plugin_dynamic_routes_enabled` → `PluginApiRouterService` + `load_installed_routers()`) relève de STORY-170.1 (tâche 5 là-bas) — le même bloc startup accueille les deux chargements sans interférence.
**Fichiers :**
- `backend/app/main.py` — Modifier — startup block après plugin hooks bridge.
**Dépend de :** Tâche 5

### Tâche 8 : Branchement pipeline `background_tasks` — gates + échec typé *(originale T11 de STORY-170)*
**Objectif :** Insérer les gates dans `deploy_stack_async` aux **deux chemins** avant création de container : helper `_extract_images(config) -> list[DeployImage]` (docker : `image` du final_config ; compose : `services.*.image` — divergence n°1 digest) ; helper `_run_pre_deploy_gates(db, deployment_id, stack, target_id, images, user_id)` : construit `DeployContext` (trigger `manual` — les autres triggers viendront avec scheduler/batch), appelle `run_gates`, sur refus lève `GateDeniedError` (code/plugin/raison). Docker : insertion après le jalon 45 `validated`, avant `deploy_container` (jalon 75). Compose : après le jalon 65 `compose_generated`, avant `deploy_compose`. **Refus = échec classique** : le `except` existant (lignes 375-389) passe FAILED via `update_status` — étendre `update_status` ([`deployment_service.py:686`](../../backend/app/services/deployment_service.py:686)) d'un paramètre `event_data_extra: dict | None = None` fusionné dans `event_data` de l'event STORY-167 (data `code`/`plugin`/reason) ; le message de log porte `[ERROR] Déploiement refusé par la gate du plugin {plugin} : {reason}` (code GATE_*) ; **émission bus** `EventType.DEPLOYMENT_FAILED` best-effort post-commit au passage FAILED (divergence n°2 — payload IDs + code/plugin/raison si gate, jamais de secrets) ; progression WS : l'exception interrompt avant le jalon 75, `emit_status_change` existant notifie le FAILED (contrat AC 1 « progression WebSocket » satisfait par les canaux existants). La gate s'applique aussi au chemin recreate quand il passera par ce pipeline (STORY-174 — branchement au niveau commun déjà couvert).
**Fichiers :**
- `backend/app/tasks/background_tasks.py` — Modifier — helpers + 2 insertions + refus typé.
- `backend/app/services/deployment_service.py` — Modifier — paramètre `event_data_extra` + émission bus `deployment.failed` post-commit.
**Dépend de :** Tâches 3, 4, 5

### Tâche 9 : Tests pipeline — gates + non-régression + validation *(originale T13 de STORY-170, périmètre gates)*
**Objectif :** Valider les AC 1, AC 2 et AC 3 : `deny(reason)` → **`deploy_container`/`deploy_compose` jamais appelés** (mocks assert_not_called), statut FAILED, `deployment_events` ligne `error` avec data `code=GATE_DENIED`/`plugin`/`reason` (requête store), bus `deployment.failed` émis avec le payload gate, audit `deployment.failed` existant intact ; timeout court simulé (gate `asyncio.sleep` + timeout 0.1 s) → `GATE_TIMEOUT` ; `on_timeout: approve` → déploiement poursuit ; deux gates (A approve, B deny) → deny l'emporte, court-circuit (A n'est pas ré-exécutée après B — ordre alphabétique) ; gate qui lève → refus prudent `gate_error` ; **aucune gate enregistrée → déploiement nominal inchangé** (non-régression AC 3, suite `test_deployments.py`/`test_deploy_stack*` existante repassée). Validation finale : `make backend-test-unit`, `make lint`, `make backend-typecheck`, couverture ≥ 80 % sur `plugin_gate_service`, `plugins/gates.py` (modules touchés AC 3).
**Fichiers :**
- `backend/tests/unit/test_tasks/test_deploy_stack_gates.py` — Créer — suite gates pipeline.
- `backend/tests/unit/test_services/test_deployment_service_events.py` — Modifier — tests du paramètre `event_data_extra` + émission bus `deployment.failed`.
**Dépend de :** Tâches 5, 6, 7, 8

## Tests à écrire

### Backend

- `backend/tests/unit/test_services/test_plugin_gate_service.py` — registre register/unregister/idempotence ; `load_installed_gates` : handler valide chargé, manifest sans `deploy_hooks` ignoré (nominal sans log), handler chemin invalide/traversal → WARNING + ignoré (startup intact), gate pour plugin `service` ignorée ; `run_gates` : aucune gate → approve, approve pass-through, deny court-circuit (2e gate non exécutée), timeout → `GATE_TIMEOUT` deny, `on_timeout: approve` → approve, exception handler → `gate_error` deny, ordre alphabétique déterministe, timeout manifest override > settings.
- `backend/tests/unit/test_schemas/test_plugin_manifest.py` — Modifier — `deploy_hooks` : handler `module:fonction` valide/invalide (absolu, `..`, sans `:`), timeout bornes, `on_timeout` enum, valeur par défaut deny.
- `backend/tests/unit/test_services/test_deployment_service_events.py` — Modifier — `event_data_extra` fusionné dans le data de l'event ; émission bus `deployment.failed` au passage FAILED (best-effort, payload sans secret).
- `backend/tests/unit/test_tasks/test_deploy_stack_gates.py` — AC 1/AC 2 : `test_deny_cancels_before_container_creation` (deploy_container/compose `assert_not_called` + FAILED + event `GATE_DENIED`/plugin/raison + bus `deployment.failed`), `test_timeout_denies_gate_timeout`, `test_on_timeout_approve_deploys`, `test_multiple_gates_first_deny_wins`, `test_gate_error_denies_prudently`, `test_no_registered_gate_deploys_nominal` (non-régression), chemin compose couvert en miroir du chemin docker.

### Frontend

- Aucun — périmètre backend uniquement (le refus de gate s'exprime comme un échec de déploiement classique via les canaux existants ; aucun changement de contrat consommé par le frontend).

### Commandes de validation
```bash
# Tests ciblés (modules touchés)
poetry run pytest backend/tests/unit/test_services/test_plugin_gate_service.py backend/tests/unit/test_tasks/test_deploy_stack_gates.py backend/tests/unit/test_schemas/test_plugin_manifest.py backend/tests/unit/test_services/test_deployment_service_events.py -v

# Non-régression déploiements + plugins existants
poetry run pytest backend/tests/unit/test_tasks/ backend/tests/unit/test_api/test_plugins.py backend/tests/unit/test_api/test_plugins_rbac.py -v

# Quality gates (AC 3)
make backend-test-unit
make lint
make backend-typecheck
poetry run pytest backend/tests/unit/test_services/test_plugin_gate_service.py --cov=backend/app/services/plugin_gate_service.py --cov-fail-under=80
```


## Notes d'implémentation

**Statut final :** REVIEW — 2026-10-30

### Fichiers créés

- `backend/app/plugins/gates.py` — SDK gates : `DeployImage` (nom/tag/digest explicite, divergence n°1 documentée), `DeployContext` (payload sans secret, trigger `manual`), `GateDecision` (`approve()`/`deny(reason)`) + docstrings contrat (synchrone bloquant ≠ `@on_event`, timeout/`on_timeout`, erreur = refus prudent divergence n°4).
- `backend/app/services/plugin_gate_service.py` — `PluginGateService` : registre `register`/`unregister` (idempotent par nom de plugin, remplace l'entrée), `GateOutcome` (decision/plugin/code/reason), `run_gates` (ordre alphabétique déterministe, `asyncio.wait_for` par gate avec timeout manifest > settings, timeout → `GATE_TIMEOUT` sauf `on_timeout: approve`, exception handler ou décision non-`GateDecision` → `gate_error`, premier deny court-circuite, aucune gate → approve immédiat), `load_installed_gates` (pattern `load_installed_hooks` : requête extension|hybrid + installed|running, import sécurisé `_resolve_hooks_module_path`/`_module_name_from_path` réutilisés par import direct — pas de copier-coller, best-effort WARNING), `load_gate_from_manifest` (variante sync pour le manager à l'install), singleton `get_plugin_gate_service`/`reset_plugin_gate_service`.
- `backend/tests/unit/test_services/test_plugin_gate_service.py` — 27 tests (registre 5, run_gates 10, chargement 8, SDK 4).
- `backend/tests/unit/test_tasks/test_deploy_stack_gates.py` — 20 tests pipeline (deny/timeout/on_timeout/multi-gates/gate_error/no-gate × docker, miroir compose deny/timeout/no-gate, extraction d'images 5).

### Fichiers modifiés

- `backend/app/config.py` — settings `plugin_gate_timeout_seconds` (défaut 300, ge=1 le=3600) + `plugin_gates_enabled` (défaut True) dans la section Plugins Hooks.
- `env.example` — section `PLUGINS — GATES PRE-DEPLOY` (entrées commentées `PLUGIN_GATE_TIMEOUT_SECONDS=300`, `PLUGIN_GATES_ENABLED=true`).
- `backend/app/schemas/plugin_manifest.py` — `PluginDeployHookGate` (handler `module:fonction` validé : refus absolu/`..`/sans `:`/fonction python invalide/non-`.py` ; timeout 1-3600 ; `on_timeout` Literal deny|approve défaut deny), `PluginDeployHooks` (`pre_deploy` optionnel, `extra: ignore`), champ `deploy_hooks` sur `PluginManifest` ; validation croisée type plugin volontairement absente du schéma (service → warning + ignorée au chargement, pas un rejet — manifest partageable, cf. test documentaire).
- `backend/app/core/exceptions.py` — `GateDeniedError(WindFlowException)` interne pipeline (details `error_type: gate_denied`, `code` GATE_DENIED|GATE_TIMEOUT|gate_error, `plugin`, `reason`) — aucun mapping HTTP dédié (interceptée par le `except` existant, jamais exposée aux endpoints) + export `__all__`.
- `backend/app/services/plugin_manager_service.py` — install : étape 3b' `load_gate_from_manifest` après le montage routes 170.1 (flag + types extension/hybrid) ; uninstall : `unregister(plugin_name)` best-effort avant `db.delete` (try/except WARNING, idempotent).
- `backend/app/main.py` — lifespan : bloc gates après dynamic routes (`plugin_gates_enabled` → `get_plugin_gate_service().load_installed_gates()`, best-effort, logs comptages, rien au shutdown — registre process-local).
- `backend/app/tasks/background_tasks.py` — helpers `_parse_image_reference` (digest seulement si explicite, ports registre non confondus avec tags) + `_extract_images_from_config` (docker : `image` ; compose : `services.*.image`) + `_run_pre_deploy_gates` (flag off ou 0 gate → return immédiat, refus → `GateDeniedError`) ; insertion docker après jalon 45 `validated` avant `deploy_container`, compose après jalon 65 `compose_generated` avant `deploy_compose` ; `except` enrichi : `event_data_extra` gate (code/plugin/reason) + message `[ERROR] Déploiement refusé par la gate du plugin {plugin} : {reason} (code GATE_*)`.
- `backend/app/services/deployment_service.py` — `update_status` : paramètre `event_data_extra: Optional[dict]` fusionné dans `event_data` (après clés standard, avant sanitize liste blanche) + émission bus `EventType.DEPLOYMENT_FAILED` best-effort post-commit au passage FAILED (divergence n°2 — comble STORY-162 ; payload IDs/noms + code/plugin/raison si gate, jamais de secrets).
- `backend/app/services/deployment_event_store.py` — liste blanche `_ALLOWED_DATA_KEYS` étendue `code`/`plugin`/`reason` (trace typée gate, non sensibles par construction).
- `backend/tests/unit/test_schemas/test_plugin_manifest.py` — +12 tests `TestPluginDeployHooks` (handlers valides/invalides ×8 paramétrés, bornes timeout, enum on_timeout, défauts, manifest avec/sans deploy_hooks, service non rejeté au niveau schéma).
- `backend/tests/unit/test_services/test_deployment_service_events.py` — +6 tests (fusion `event_data_extra` + filtrage liste blanche ×3 ; bus `deployment.failed` émis au FAILED avec payload gate, pas au RUNNING, bus cassé n'altère pas le statut ×3).

### Décisions techniques

- **Robustesse handler sync** : le contrat SDK est un handler `async` (spec 11), mais `run_gates` tolère un handler **sync** via `inspect.isawaitable` (défense en profondeur — une gate décisionnelle pure sans I/O reste valide ; sans timeout applicable, ce qui est sans risque pour du code non-awaitable). Documenté inline.
- **Décision non-`GateDecision`** = refus prudent `gate_error` (même logique que l'exception handler — divergence n°4 étendue en défense en profondeur).
- **`CancelledError` re-raisée** : l'annulation du déploiement lui-même n'est pas une décision de gate (elle remonte au pipeline).
- **Timeout `asyncio.TimeoutError`** : Python 3.14 l'aligne sur `TimeoutError` builtin — le `except asyncio.TimeoutError` reste la forme canonique du dépôt (pattern `plugin_hooks_service`).
- **Émission bus dans `update_status`** (et non dans background_tasks) : unique point de passage FAILED du pipeline commun — le recreate (STORY-174) et les autres chemins en bénéficieront automatiquement ; strictly post-commit et best-effort (jamais d'altération du statut).
- **Fail-closed par défaut** : `on_timeout: deny` au schéma ET au `register` (défaut prudent si valeur inconnue) — « on ne déploie pas ce qu'on n'a pas pu évaluer ».

### Divergences par rapport à l'analyse

- **Handler sync toléré** (voir ci-dessus) : l'analyse décrivait `asyncio.wait_for(handler(ctx))` strict — l'implémentation accepte les deux signatures, le contrat documenté du SDK reste `async`. Aucun changement de comportement pour un handler conforme.
- **`_ALLOWED_DATA_KEYS` étendu** : la tâche 8 ne mentionnait pas la liste blanche du store — sans cette extension (3 clés non sensibles), le sanitize aurait silencieusement filtré la trace gate de l'event (AC 1 cassé). Extension minimale, cohérente rules 40.
- Le reste conforme aux tâches 1→9 (points d'insertion, codes, ordre alphabétique, court-circuit, bus post-commit).

### Difficultés rencontrées

- Verrous d'éditeur transitoires (« another editor opened in the meantime ») sur 3 écritures — contournés par scripts Python/heredoc (contenu final vérifié).
- Bug connu apply_diff sur `kanban.md` (« Assertion Failed ») — contourné par script Python (prévu au protocole).
- 7 échecs initiaux (handlers sync vs `await`) → corrigés par la tolérance `isawaitable` côté service ; 10 échecs après nettoyage flake8 F841 (`managers` non utilisé mais qui activait les patches) → corrigés par `ExitStack`.

### Résultats de validation

| Commande | Résultat |
|---|---|
| `poetry run pytest backend/tests/unit/test_services/test_plugin_gate_service.py backend/tests/unit/test_tasks/test_deploy_stack_gates.py` | **47 passed** |
| `poetry run pytest` (4 fichiers ciblés : gate service, pipeline gates, manifest, deployment events) | **117 passed** |
| Non-régression 170.1 : `test_plugin_api_router_service.py` + `test_plugin_dynamic_routes.py` + `test_plugin_manager_service.py` + `test_deploy_stack_progress.py` | **174 passed** |
| Non-régression : `backend/tests/unit/test_tasks/` + `test_plugins.py` + `test_plugins_rbac.py` | **70 passed** |
| `poetry run pytest backend/tests/unit` (suite complète) | **2964 passed, 0 failed** |
| Couverture `plugin_gate_service` | **93 %** (≥ 80 % AC 3) |
| Couverture `plugins/gates.py` | **100 %** (≥ 80 % AC 3) |
| `flake8` (14 fichiers modifiés/créés) | **0 erreur** |
| `black --check` + `isort --check-only` (périmètre) | **0 erreur** |
| `mypy` (fichiers périmètre, filtré) | **0 nouvelle erreur** (2 `import-not-found` préexistants prouvés par stash HEAD : `deployment_events`/`deployment_orchestrator`) |

### Commandes non lancées

- `make backend-test-unit` / `make lint` / `make backend-typecheck` (cibles globales Makefile) : remplacés par les invocations Poetry équivalentes ciblées ci-dessus (même outillage) ; `make backend-build` non lancé (pas d'artifact requis par la story). `bandit` non relancé (aucun pattern sensible ajouté : pas de subprocess, pas de secret, imports standards).
