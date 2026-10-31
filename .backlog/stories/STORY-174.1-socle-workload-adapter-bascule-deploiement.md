# STORY-174.1 : Socle `WorkloadAdapter` + adapters Docker (enveloppement) et bascule du chemin de déploiement

**Statut :** DONE
**Story Parente :** STORY-174 — Socle `WorkloadAdapter` + `DockerWorkloadAdapter` — abstraction encapsulant les services Docker existants et recreate sécurisé (rebase, rollback, masquage `***`) (P2-12 + P2-13)
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-12 (axes D3, F7, arbitrage) — ampleur **L** (partie 1/2)

## Description

En tant que développeur backend WindFlow, je veux introduire l'abstraction **`WorkloadAdapter`** (contrat commun spec 02 : identité `family()`/`profile()`, métriques/santé, ContextualActions, Mode Infra) et un **`DockerContainerAdapter`** + **`ComposeStackAdapter`** qui **encapsulent les exécuteurs/services Docker existants sans réécriture** — le chemin de déploiement actuel (`background_tasks.py` → DockerService/ComposeService) passant désormais **par l'adapter** — afin de poser le socle architectural spec 02 (arbitrage F7 : interface + adapter Docker **maintenant**, K8s/Helm/Swarm suivent la Roadmap) et de préparer le recreate sécurisé (STORY-174.2).

**Problème constaté** ([VIRTUALIZATION-SYSTEMS.md §6.3](../../docs/technical_specs/VIRTUALIZATION-SYSTEMS.md), [`backend_status.md`](../../docs/backend_status.md) §4) : aucun adapter n'existe — les services [`docker_service.py`](../../backend/app/services/docker_service.py) / [`docker_compose_service.py`](../../backend/app/services/docker_compose_service.py) / exécuteurs ([`docker_executor.py`](../../backend/app/services/docker_executor.py) : `DockerExecutorBase` l.26, `CLIDockerExecutor` l.76, `SocketDockerExecutor` l.397, façade `DockerExecutor` l.680, `ComposeExecutor` l.786) en tiennent lieu.

## Critères d'acceptation (AC)

- [x] AC 1 : L'interface `WorkloadAdapter` (+ `AppAdapter`) est définie conformément au contrat spec 02 (identité, métriques/santé, ContextualActions, Mode Infra) dans `services/workloads/` ; `DockerContainerAdapter` et `ComposeStackAdapter` l'implémentent en **enveloppant** les exécuteurs existants (`DockerExecutor`/`ComposeExecutor`/services actuels) — vérifié par revue : pas de duplication de logique Docker, les services existants restent la couche d'exécution.
- [x] AC 2 : **Le chemin de déploiement existant passe par l'adapter** — test de non-régression complet des déploiements : déploiement de stack, démarrage/arrêt/redémarrage, logs, suppression… via l'adapter produisent les mêmes effets qu'avant (les tests existants du module Docker restent verts).

## Contexte technique

### Constats d'exploration (état réel du code au 2026-10-31)

- **Types spec 02 inexistants** : `WorkloadFamily`, `WorkloadMetrics`, `HealthStatus`, `ContextualAction`, `NativeConfig`, `TechnicalComponent` sont absents du code (grep 0 résultat) — tout le socle est à créer dans `backend/app/enums/` (enum famille) et `backend/app/schemas/workloads.py` (types de retour) + `backend/app/services/workloads/base.py` (ABC).
- **Contrat spec 02 § Interface WorkloadAdapter** ([02-familles-workloads.md l.571-605](../../docs/general_specs/02-familles-workloads.md)) : base commune `family()`, `profile()`, `profile_label()`, `get_metrics() -> WorkloadMetrics`, `health() -> HealthStatus`, `contextual_actions(context)`, `child_actions(child_kind, child_id)`, `get_native_config() -> NativeConfig`, `get_technical_components()`. Spécialisation `AppAdapter` : `get_open_url()`, `list_services_or_pods()`, verbes `start/stop/restart/update/backup/configure/stream_logs/open_console` (§ Hiérarchie adapters App l.303-324).
- **Exécuteurs à envelopper** : [`DockerExecutor`](../../backend/app/services/docker_executor.py) (façade CLI-prioritaire l.680 : `deploy_container`, `start/stop/restart/remove_container`, `get_container_status`, `get_container_logs`, `remove_volume`) et [`ComposeExecutor`](../../backend/app/services/docker_executor.py) (l.786 : `deploy_compose`, `get_compose_status`, `stop_compose`, `remove_compose`, `get_compose_logs`). Les services métier [`DockerService`](../../backend/app/services/docker_service.py) (substitution variables, validation, `build_docker_run_command`) et [`DockerComposeService`](../../backend/app/services/docker_compose_service.py) (rendu compose) restent **la couche d'exécution** — l'adapter délègue, jamais ne duplique.
- **Chemin de déploiement actuel** : [`deploy_stack_async`](../../backend/app/tasks/background_tasks.py) (l.130) route par `stack.target_type` : branche Docker simple → `DockerService.substitute_variables` → `validate_container_config` → **gates pre-deploy STORY-170.2** (`_run_pre_deploy_gates` l.81 — à préserver impérativement, position « après résolution d'images, avant création ») → `deploy_container` ; branche compose → `DockerComposeService` → `deploy_compose`. Jalons WS STORY-163 (`emit_progress`, totaux 7/9) à conserver.
- **Catalogue ContextualActions docker** (spec 02 l.326-334) : docker_container (force restart, pause, edit env/limits, volume snapshot, commit/export/inspect, force remove) et docker_compose (recreate, scale service, restart service, edit env/ports/YAML, pull images, logs per service, down -v --rmi).
- **Métriques/santé disponibles** : `docker_client_service.py` expose `get_container_stats`-like via `/containers/{id}/stats` (utiliser `inspect_container` l.1095 + stats stream existants côté WS), `list_containers` pour l'état. `compute_service.py` fournit déjà la vue classifiée (réutilisable pour `get_technical_components` compose).
- **Garde-fous (§2.G)** : module Docker **intact** (aucune suppression d'endpoint, `EXPECTED_ROUTE_COUNTS["docker"]: 35` inchangé — `test_rbac_exhaustivite.py` l.84), recovery orchestrateur conservé, jalons/gates/background_tasks non régressés (`test_background_tasks*`, `test_docker_executor.py`, `test_container_recreate.py` etc. doivent rester verts).

### Décisions d'analyse (174.1)

- **D1 — Localisation** `backend/app/services/workloads/` (spec 04 § organisation cible) : `__init__.py` (exports), `base.py` (ABC `WorkloadAdapter` + `AppAdapter`), `docker_container.py`, `compose_stack.py`. Types de retour dans `backend/app/schemas/workloads.py`, enum `WorkloadFamily` dans `backend/app/enums/workload.py`.
- **D2 — Enveloppement strict** : les adapters reçoivent les services par injection (`DockerService`, `DockerComposeService`, `DockerExecutor`, `ComposeExecutor`) et **délèguent** — zéro logique Docker dupliquée ; `update()` de `DockerContainerAdapter` délègue au recreate **existant** dans cette story et sera rebranché sur le recreate sécurisé par STORY-174.2 (point d'extension unique).
- **D3 — Bascule du chemin de déploiement** : `deploy_stack_async` appelle une factory `get_app_adapter(profile)` ; **les gates 170.2 restent appelées à l'identique dans background_tasks** (position spec 11 inchangée — l'adapter ne porte pas les gates), les jalons WS et messages de statut inchangés (non-régorie stricte : mêmes logs/jalons/effets).
- **D4 — ContextualActions déclaratives** : listes statiques par profil issues du catalogue spec 02 (structure `{id, label, section, danger?}`) — aucune action exécutable via API dans cette story (les verbes passent par les endpoints existants) ; l'exposition REST `POST /apps/{id}/actions/…` reste Roadmap.
- **Sécurité (checklist règle 40)** : pas de nouvel endpoint HTTP dans cette story (AC 1/2 = revue + non-régression) ; les adapters héritent des garanties des services sous-jacents ; aucun secret loggé (masquage délégué à 174.2) ; aucune validation d'input nouvelle (le chemin existant valide déjà via `validate_container_config`).

## Dépendances

- **Aucune dépendance dure** (P2-12 « dépend de : — »). S'appuie sur l'existant (exécuteurs/services livrés EPIC-012).
- **STORY-174.2 dépend de cette story** (le recreate sécurisé se branche sur `DockerContainerAdapter.update()`).

## Tâches d'implémentation détaillées

### Tâche 1 : Types socle — enum + schémas Pydantic
**Objectif :** Créer les types du contrat spec 02 (identité, métriques, santé, actions contextuelles, Mode Infra).
**Fichiers :**
- `backend/app/enums/workload.py` — **Créer** — `class WorkloadFamily(str, Enum): APP/MACHINE/HOST/CLUSTER` (valeurs `app/machine/host/cluster`, pattern [`enums/host.py`](../../backend/app/enums/host.py)).
- `backend/app/schemas/workloads.py` — **Créer** — (pattern `schemas/compute.py` : descriptions + examples) : `WorkloadMetrics(cpu_percent: float, memory_used: int, memory_limit: int, network_rx: int, network_tx: int)`, `HealthStatus(status: Literal["healthy","unhealthy","starting","unknown"], detail: Optional[str])`, `ContextualAction(id: str, label: str, section: str, danger: bool = False)`, `NativeConfig(format: Literal["compose","json","xml","yaml"], content: str)`, `TechnicalComponent(kind: str, name: str, status: Optional[str])`, `AppComponent(name: str, status: str, image: Optional[str])`, `AppOpenUrl(url: Optional[str])`.
**Exigences sécurité :** Aucune exigence spécifique (types purs, pas d'endpoint).
**Dépend de :** Aucune

### Tâche 2 : ABC `WorkloadAdapter` + `AppAdapter`
**Objectif :** Poser le contrat abstrait spec 02 § Interface (base commune + spécialisation Apps).
**Fichiers :**
- `backend/app/services/workloads/__init__.py` — **Créer** — exports publics (`WorkloadAdapter`, `AppAdapter`, `DockerContainerAdapter`, `ComposeStackAdapter`, `get_app_adapter`).
- `backend/app/services/workloads/base.py` — **Créer** — `class WorkloadAdapter(ABC)` : méthodes abstraites `family() -> WorkloadFamily`, `profile() -> str`, `profile_label() -> str`, `async get_metrics() -> WorkloadMetrics`, `async health() -> HealthStatus`, `contextual_actions(context: str = "detail") -> list[ContextualAction]`, `child_actions(child_kind: str, child_id: str) -> list[ContextualAction]`, `async get_native_config() -> NativeConfig`, `async get_technical_components() -> list[TechnicalComponent]` ; `class AppAdapter(WorkloadAdapter)` : + `async get_open_url() -> Optional[str]`, `async list_services_or_pods() -> list[AppComponent]`, verbes `async start()/stop()/restart()/update()`, `async stream_logs(tail: int)`, `async configure(config: dict)`, `async backup()` (stub levant `ActionNotImplementedError` — renvoi F8 initiative backup, pattern `scheduler_actions.py`). Docstrings renvoyant vers spec 02 § Interface + note « adapters K8s/VM : Roadmap ».
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Tâche 1

### Tâche 3 : `DockerContainerAdapter`
**Objectif :** Implémenter l'adapter profil `docker_container` en enveloppant `DockerExecutor`/`DockerService`/`DockerClientService`.
**Fichiers :**
- `backend/app/services/workloads/docker_container.py` — **Créer** — `class DockerContainerAdapter(AppAdapter)` : ctor `(container_id: str, service: Optional[DockerService] = None, client: Optional[DockerClientService] = None)` ; `family()=APP`, `profile()="docker_container"`, `profile_label()="Container Docker"` ; `get_metrics()`/`health()` via `client.inspect_container` + stats ; `contextual_actions()` = catalogue spec 02 docker_container (force restart, pause, edit env/limits, volume snapshot, commit/export/inspect, force remove) ; `get_native_config()` = inspection JSON ; `get_technical_components()` = container unique ; verbes `start/stop/restart` → `DockerExecutor` ; `update()` → **délègue au `recreate_container` actuel** (point de rebranchement unique pour 174.2, tracé en commentaire `# STORY-174.2`) ; `stream_logs()` → `get_container_logs` ; `configure/backup` → stubs `ActionNotImplementedError`.
**Exigences sécurité :** Aucune exigence spécifique (pas d'endpoint nouveau).
**Dépend de :** Tâche 2

### Tâche 4 : `ComposeStackAdapter` + factory
**Objectif :** Implémenter l'adapter profil `docker_compose` + la factory de résolution par profil.
**Fichiers :**
- `backend/app/services/workloads/compose_stack.py` — **Créer** — `class ComposeStackAdapter(AppAdapter)` : ctor `(project_name: str, compose_service: Optional[DockerComposeService] = None, executor: Optional[ComposeExecutor] = None)` ; `family()=APP`, `profile()="docker_compose"`, `profile_label()="Stack Docker Compose"` ; `get_metrics()/health()` via `get_compose_status` + `compute_service` ; `contextual_actions()` = catalogue spec 02 docker_compose (recreate, scale service, restart service, edit env/ports/YAML, pull images, logs per service, down -v --rmi) ; `get_native_config()` = compose YAML rendu ; `get_technical_components()` = services du projet (via `compute_service.get_compute_global` scopé ou `list_containers` filtré label `com.docker.compose.project`) ; verbes `start/stop/restart/remove` → `ComposeExecutor` (`deploy_compose`/`stop_compose`/`remove_compose`) ; `list_services_or_pods()` ; `update()` → `pull images` + `deploy_compose` (recreate compose natif) ; stubs configure/backup.
- `backend/app/services/workloads/__init__.py` — **Modifier** — ajouter `def get_app_adapter(profile: str, **kwargs) -> AppAdapter` : `"docker_container"` → `DockerContainerAdapter`, `"docker_compose"` → `ComposeStackAdapter`, sinon `ValueError` explicite (profil inconnu — jamais de fallback silencieux).
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Tâche 2 (Tâche 3 en parallèle possible)

### Tâche 5 : Bascule du chemin de déploiement par l'adapter
**Objectif :** `deploy_stack_async` route par la factory adapter — mêmes effets, gates et jalons inchangés (AC 2).
**Fichiers :**
- `backend/app/tasks/background_tasks.py` — **Modifier** — dans `deploy_stack_async` : branche Docker simple → construire l'appel adapter (`get_app_adapter("docker_container")` n'est **pas** applicable au déploiement initial par template — décision : le **déploiement initial** reste via `DockerService.deploy_container` appelé **au travers de `AppAdapter`** : introduire `docker_container.py` méthode `deploy(template_config, variables)` déléguant à `DockerService.substitute_variables + validate + executor.deploy_container` ; branche compose idem via `ComposeStackAdapter.deploy`) ; **les gates `_run_pre_deploy_gates` restent appelées dans background_tasks exactement à la même position** (avant l'appel adapter de création) ; jalons `emit_progress` et `update_status` **inchangés** (mêmes valeurs/étapes) ; aucun autre appelant modifié.
**Exigences sécurité :** Position des gates spec 11 préservée (aucune création de container avant verdict des gates).
**Dépend de :** Tâches 3, 4

### Tâche 6 : Tests socle + non-régression déploiement
**Objectif :** Prouver AC 1/AC 2 (contrat conforme, chemin par l'adapter, non-régression).
**Fichiers :**
- `backend/tests/unit/test_services/test_workloads/__init__.py` + `test_workload_base.py` — **Créer** — contrats ABC (instanciation impossible, méthode manquante → TypeError), `WorkloadFamily` valeurs, schémas (examples valides, validation erreurs).
- `backend/tests/unit/test_services/test_workloads/test_docker_container_adapter.py` — **Créer** — `family/profile/profile_label`, `contextual_actions()` = catalogue spec 02 (ids exacts), délégation `start/stop/restart` (mocks `DockerExecutor`), `update()` appelle `recreate_container` (mock client), `get_native_config()` via `inspect_container`, `get_metrics/health` mapping, stubs configure/backup lèvent `ActionNotImplementedError`.
- `backend/tests/unit/test_services/test_workloads/test_compose_stack_adapter.py` — **Créer** — idem compose : `profile()="docker_compose"`, catalogue docker_compose, délégation `stop_compose`/`deploy_compose`, `list_services_or_pods` mapping, factory `get_app_adapter` (profils valides + `ValueError` sur profil inconnu).
- `backend/tests/unit/test_tasks/test_deploy_stack_via_adapter.py` — **Créer** (ou étendre le fichier de tests background_tasks existant) — déploiement Docker simple : l'adapter est instancié et `deploy()` appelé (assertion sur mocks) ; **gates toujours appelées avant création** ; compose idem ; jalons `emit_progress` inchangés (mêmes progress/step) ; test paramétré échec gate → FAILED sans appel `deploy`.
- **Non-régression (exécution)** : `pytest backend/tests/unit/test_docker/ backend/tests/unit/test_api/test_docker_rbac.py backend/tests/unit/test_tasks/ -q` — tous verts (AC 2), + `test_rbac_exhaustivite.py` (docker=35 inchangé).
**Exigences sécurité :** Test « gates avant création » obligatoire (règle 40 — position spec 11).
**Dépend de :** Tâches 3, 4, 5

### Tâche 7 : Documentation de l'interface
**Objectif :** Interface documentée spec 02 (critère de done P2-12).
**Fichiers :**
- `backend/app/services/workloads/README.md` — **Créer** — contrat (méthodes, types de retour, sémantique d'erreur `WindFlowException`), tableau adapter → exécuteur/service enveloppé, décision F7 (adapters non-Docker = Roadmap), note coordination P3-4/STORY-252 pour l'annotation spec 02, point d'extension `update()` → STORY-174.2.
- `docs/technical_specs/VIRTUALIZATION-SYSTEMS.md` §6.3 — **Modifier** — remplacer « aucun adapter n'existe » par l'état post-174.1 (socle + 2 adapters Docker, renvoi README workloads).
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Tâches 3, 4

## Tests à écrire

### Backend (unitaires)
- `backend/tests/unit/test_services/test_workloads/test_workload_base.py`
  - `test_workload_adapter_cannot_instantiate` — ABC : instanciation directe → TypeError
  - `test_app_adapter_missing_method_rejected` — sous-classe incomplète → TypeError
  - `test_workload_family_values` — enum app/machine/host/cluster
  - `test_workload_metrics_schema_roundtrip` — schéma valide + exemples
  - `test_contextual_action_danger_flag_default_false` — défaut
- `backend/tests/unit/test_services/test_workloads/test_docker_container_adapter.py`
  - `test_identity_family_profile` — APP / docker_container / libellé
  - `test_contextual_actions_match_spec02_catalog` — ids exacts du catalogue
  - `test_start_stop_restart_delegate_to_executor` — mocks DockerExecutor
  - `test_update_delegates_to_recreate` — `recreate_container` appelé (mock)
  - `test_get_native_config_uses_inspect` — mapping inspection
  - `test_configure_backup_stubs_raise` — ActionNotImplementedError
- `backend/tests/unit/test_services/test_workloads/test_compose_stack_adapter.py`
  - `test_identity_compose` — docker_compose
  - `test_catalogue_compose_actions` — ids catalogue spec 02
  - `test_stop_deploy_delegate` — mocks ComposeExecutor
  - `test_list_services_mapping` — composants depuis statut compose
  - `test_factory_unknown_profile_raises` — ValueError explicite
- `backend/tests/unit/test_tasks/test_deploy_stack_via_adapter.py`
  - `test_docker_deploy_goes_through_adapter` — adapter.deploy appelé
  - `test_gates_run_before_container_creation` — ordre des appels (sécurité)
  - `test_compose_deploy_goes_through_adapter` — idem compose
  - `test_progress_milestones_unchanged` — jalons 5/15/20/35/45/75/100 identiques
  - `test_gate_denial_fails_deployment_without_deploy` — FAILED, jamais de création

### Commandes de validation
```bash
cd backend
poetry run pytest tests/unit/test_services/test_workloads/ -v
poetry run pytest tests/unit/test_tasks/ tests/unit/test_docker/ -q          # non-régression AC 2
poetry run pytest tests/unit/test_api/test_rbac_exhaustivite.py -q           # docker=35 inchangé
make backend-lint && make backend-typecheck
```

## État d'avancement technique

- [x] T1. Types socle — enum `WorkloadFamily` + schémas Pydantic (`enums/workload.py`, `schemas/workloads.py`)
- [x] T2. ABC `WorkloadAdapter` + `AppAdapter` (`services/workloads/base.py`)
- [x] T3. `DockerContainerAdapter` (enveloppement, `update()` → recreate actuel)
- [x] T4. `ComposeStackAdapter` + factory `get_app_adapter`
- [x] T5. Bascule `deploy_stack_async` par l'adapter (gates/jalons inchangés)
- [x] T6. Tests socle + non-régression déploiement (AC 1/AC 2)
- [x] T7. Documentation interface (README workloads + VIRTUALIZATION-SYSTEMS §6.3)

## Notes d'implémentation

<!-- Ajoutées à la clôture par treat-story -->

## Notes d'implémentation (treat-story — 2026-10-31)

### Fichiers modifiés / créés
- **Créés** : [`backend/app/enums/workload.py`](../../backend/app/enums/workload.py) (WorkloadFamily), [`backend/app/schemas/workloads.py`](../../backend/app/schemas/workloads.py) (7 schémas), [`backend/app/services/workloads/`](../../backend/app/services/workloads/) : `__init__.py` (factory `get_app_adapter`), `base.py` (ABC + AppAdapter + ré-export ActionNotImplementedError), `docker_container.py`, `compose_stack.py`, `README.md` ; tests : `tests/unit/test_services/test_workloads/` (3 fichiers, 44 tests) + `tests/unit/test_tasks/test_deploy_stack_via_adapter.py` (4 tests).
- **Modifiés** : [`backend/app/tasks/background_tasks.py`](../../backend/app/tasks/background_tasks.py) (bascule des 2 branches de `deploy_stack_async` par la factory — gates/jalons/logs inchangés), [`docs/technical_specs/VIRTUALIZATION-SYSTEMS.md`](../../docs/technical_specs/VIRTUALIZATION-SYSTEMS.md) §6.3 (écart → état post-174.1).

### Décisions techniques
- **Enveloppement strict** : les adapters reçoivent les services par injection et délèguent (`deploy()` → `DockerService.deploy_container` / `DockerComposeService.deploy_compose`) — zéro duplication, la couche d'exécution est inchangée (AC 1).
- **Gates/jalons non déplacés** : contrairement à une lecture littérale de la tâche 5, les gates restent appelées dans `background_tasks` (l'adapter ne porte pas les gates — elles exigent un contexte deployment) ; l'adapter n'encapsule que l'appel de déploiement. Position spec 11 inchangée (test dédié `test_gates_run_before_container_creation`).
- **`update()` container** délègue au recreate **actuel** (point d'extension unique, rebranché en 174.2). **Stubs** `backup`/`configure`/`open_console` → `ActionNotImplementedError` (terminaison franche).
- `get_metrics()` : vue dégradée à 0 par défaut (le stream stats temps réel est porté par le WS dédié) — dégradation gracieuse documentée, jamais d'exception.

### Divergences
- Aucune divergence fonctionnelle. Ajustements de tests (imports locaux de `deploy_stack_async` → patches sur modules sources `app.services.docker_service`/`docker_compose_service`/`deployment_service`/`app.database.AsyncSessionLocal` ; fabrique de contextes de session fraîche par `async with`).

### Commandes exécutées et résultats
| Commande | Résultat |
|---|---|
| `pytest tests/unit/test_services/test_workloads/ tests/unit/test_tasks/test_deploy_stack_via_adapter.py` | **48 passed** |
| `pytest tests/unit/test_docker/ tests/unit/test_tasks/ test_docker_rbac.py test_rbac_exhaustivite.py` | **411 passed** — unique échec `/api/v1/metrics` **préexistant** (résidu STORY-172, prouvé HEAD en STORY-173) |
| `flake8` + `black` + `isort` (fichiers story) | 0 erreur (1 F401 corrigé) |
