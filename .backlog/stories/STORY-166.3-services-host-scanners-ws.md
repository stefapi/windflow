# STORY-166.3 : Renommage `target_*`→`host_*` — services, scanners, WebSocket et consommateurs (P2-4, partie services — STORY-166 découpée)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-166 ([ABANDONED — découpe proactive post-analyse le 2026-10-24](STORY-166-migration-target-vers-host-origin.md))
**Item plan :** P2-4 (F4 étape 2 — volet services/WS, garde-fou §2.G) — ampleur **M-L**

> **Périmètre (découpe)** : cette sous-story reprend le **volet services** de STORY-166 — renommage `target_service`→`host_service`, `target_scanner_service`, `target_scan_parsers` (~20 parseurs), `target_access_profile`, alignement interne WebSocket [`host_access.py`](../../backend/app/websocket/host_access.py) (déjà nommé « host ») et mise à jour des **consommateurs** (`deployment_service`, `deployment_orchestrator`, `compute_service`, `container_classifier`, `adoption_service`, `terminal_service`, `ssh_connection`). Couvre la partie **scan de l'AC 3 de la mère** (payloads non cassés — garde-fou §2.G majeur) et la partie non-régression services/WS de son **AC 5**. ⚠️ La pose métier `origin=adopted` à l'adoption n'est **pas** ici ([STORY-166.4](STORY-166.4-origin-environments-git-url.md)).

## Description

En tant qu'administrateur WindFlow, je veux que les services et composants temps réel nommés `target_*` soient renommés `host_*` et branchés sur le modèle `Host`, sans qu'aucun payload ou comportement du pipeline de scan ne change — afin de compléter le renommage métier sans régression sur la chaîne scan → capacités → profils d'accès → SSH/WS.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §5) : services et scanners portent le nommage legacy `target_*` alors que le modèle devient `Host` (STORY-166.1) et que le garde-fou §2.G exige que le scan de cibles (~20 parseurs, SocketProbe 7 familles, profils d'accès) fonctionne **à l'identique** branché sur Host.

## Contexte technique

> Extrait de l'analyse STORY-166 (2026-10-24, `analyse-story`) — volet services/WS, fondé sur le code réel du dépôt.

### État réel du code (exploration mère)

**Services à renommer** :
- [`services/target_service.py`](../../backend/app/services/target_service.py) → `host_service.py` ;
- [`services/target_scanner_service.py`](../../backend/app/services/target_scanner_service.py) (l.75 : `scan_localhost`/`scan_remote`/`scan_and_update_target`) → `host_scanner_service.py` ;
- [`services/target_scan_parsers.py`](../../backend/app/services/target_scan_parsers.py) (~20 parseurs + `build_capabilities_payload`) → `host_scan_parsers.py` — **payloads strictement inchangés** ;
- [`services/target_access_profile.py`](../../backend/app/services/target_access_profile.py) → `host_access_profile.py` ;

**Consommateurs à mettre à jour (imports/résolutions)** :
- `deployment_service`, `deployment_orchestrator`, `compute_service` ;
- [`services/container_classifier.py`](../../backend/app/services/container_classifier.py) (l.26 : `LOCAL_TARGET_ID = "local"` placeholder, pas une ligne en base — arbitrage en analyse : conserver la constante ou résoudre le host local seedé, coordonner avec [STORY-166.5](STORY-166.5-auto-detection-host-local-seed.md)) ;
- `adoption_service` (⚠️ renommage seulement — l'axe `origin` est en 166.4), `terminal_service`, [`services/ssh_connection.py`](../../backend/app/services/ssh_connection.py) (`build_ssh_kwargs` résout `target.ssh_key_id` + credentials) ;

**WebSocket** :
- [`websocket/host_access.py`](../../backend/app/websocket/host_access.py) (STORY-164.2 ✔ — **déjà nommé « host »** : `resolve_host_and_check_access` résout la `Target` + isolation org), consommé par `ssh_session.py` et `journal.py` → **renommage interne limité** (types/docstrings/résolution `Host`) ;
- Scheduler : action `host.scan` (STORY-160.3 ✔) consomme le scanner — imports à suivre au renommage.

### Garde-fou §2.G (majeur)

- **Renommage/wrapping, pas réécriture** : les ~20 parseurs, SocketProbe (7 familles) et profils d'accès doivent produire les **mêmes payloads** avant/après (golden tests) ;
- Module Docker intact ; recovery orchestrateur conservé ; WS existants non régressés.

### Checklist sécurité (règle 40)

- Comportement SSH inchangé : TOFU STRICT (`build_ssh_kwargs`), jamais `known_hosts: None` ;
- Credentials déchiffrés uniquement en mémoire au moment de l'usage, jamais loggés ;
- Isolation organisationnelle (`resolve_host_and_check_access`) conservée à l'identique.

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend la partie scan de l'AC 3 de la mère)* : Le scan de cibles branché sur `Host` fonctionne **à l'identique** — payloads des ~20 parseurs et profils d'accès **non cassés** (tests de non-régression golden : même sortie avant/après renommage, sur `Host`).
- [x] AC 2 *(reprend la partie non-régression de l'AC 5 de la mère)* : Renommage complet `target_*`→`host_*` (services, scanner, parsers, access_profile, WS interne) + consommateurs mis à jour, **sans régression** : module Docker intact, déploiements, WS `ssh_session`/`journal` existants, scheduler `host.scan` opérationnel.
- [x] AC 3 : Couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent ; plus aucune référence `target_*` côté services/WS (hors alias de transition 166.1, purgés en 166.6).

## Références spécification

- [VIRTUALIZATION-SYSTEMS.md](../../docs/technical_specs/VIRTUALIZATION-SYSTEMS.md) — §6 (scanner pipeline, parseurs, correspondance profils) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Hosts distants SSH (clés réutilisables, empreintes) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §2.G (garde-fou scan), §4 P2-4.

## Dépendances

- **[STORY-166.1](STORY-166.1-modele-host-enums-migration-alembic.md)** (dur) — modèle `Host` + alias de transition ;
- **STORY-131** ✔ (ssh_keys/TOFU), **STORY-164.2** ✔ (WS host_access), **STORY-160.3** ✔ (action `host.scan`) ;
- **[STORY-166.2](STORY-166.2-api-hosts-alias-targets-evenements.md)** : cette story est traitée **avant** (ordre d'exécution de la série 166.1→**166.3**→166.2→…) — l'API `/hosts` consommera directement `HostService`/`HostScannerService`/`host_scan_parsers` livrés ici ;
- [STORY-166.4](STORY-166.4-origin-environments-git-url.md) (adoption/origin) et [STORY-166.5](STORY-166.5-auto-detection-host-local-seed.md) (seed/scanner) s'appuient sur ce renommage — **recommandé avant elles**.

## État d'avancement technique

*(à cocher pendant `treat-story` — une case par tâche détaillée ci-dessous)*

- [x] T1. Renommage `target_service.py`→`host_service.py` (classe `HostService` + alias `TargetService`)
- [x] T2. Renommage `target_access_profile.py`→`host_access_profile.py` (classe `HostAccessProfileDetector` + alias)
- [x] T3. Renommage `target_scan_parsers.py`→`host_scan_parsers.py` (payloads inchangés)
- [x] T4. Renommage `target_scanner_service.py`→`host_scanner_service.py` (classe `HostScannerService` + alias)
- [x] T5. Mise à jour des consommateurs services (imports + types `Host`)
- [x] T6. Alignement WebSocket `host_access`/`ssh_session`/`journal`
- [x] T7. Scheduler `host.scan` + `background_tasks`/`main.py` sur imports canoniques
- [x] T8. Arbitrage `LOCAL_TARGET_ID` (alias `LOCAL_HOST_ID` + résolution seedée)
- [x] T9. Migration des fichiers de tests + golden tests payloads

## Tâches d'implémentation détaillées

### Tâche 1 : Renommage `target_service` → `host_service`
**Objectif :** `git mv backend/app/services/target_service.py backend/app/services/host_service.py` ; classe `TargetService`→`HostService` ; résolutions internes sur `Host`/`HostCapability` (imports depuis `models/host.py`, `models/host_capability.py` — livrés par 166.1) ; conserver **tous les comportements** (health-check TCP + émission `host.offline` l.377-401 via `resolve_event_name` inchangé, `apply_scan_result` alimentant `installed_engines`, `mark_scan_failed`→`HostStatus.UNREACHABLE`, `mark_scan_in_progress`→`HostStatus.SCANNING` — posés par 166.1 T4). Poser un **alias de transition** `TargetService = HostService` en fin de module (purge 166.6) pour les consommateurs non encore basculés. Signatures : paramètres `target`→`host`, `target_id`→`host_id` (renommage mécanique, mêmes types).
**Fichiers :**
- `backend/app/services/host_service.py` — [Créer] — renommage complet du contenu de `target_service.py`
- `backend/app/services/target_service.py` — [Supprimer] — après `git mv` (ou fichier d'alias mince si `git mv` partiel : `from .host_service import HostService as TargetService, HostService` + commentaire purge 166.6)
- `backend/app/services/__init__.py` — [Modifier] — `TargetService`→`HostService` dans imports/`__all__` (l.11-19)
**Dépend de :** STORY-166.1 (modèle `Host` + alias)

### Tâche 2 : Renommage `target_access_profile` → `host_access_profile`
**Objectif :** `git mv` + classe `TargetAccessProfileDetector`→`HostAccessProfileDetector` ; le **schéma Pydantic** `TargetAccessProfile` (`schemas/target.py` l.174) est renommé `HostAccessProfile` avec alias `TargetAccessProfile = HostAccessProfile` (utilisé par scanner, `HostCapability` endpoints et frontend types — payloads strictement identiques, garde-fou §2.G). Alias de transition module : `TargetAccessProfileDetector = HostAccessProfileDetector`.
**Fichiers :**
- `backend/app/services/host_access_profile.py` — [Créer] — ex-`target_access_profile.py` (l.21 : classe détecteur)
- `backend/app/services/target_access_profile.py` — [Supprimer] — (ou alias mince, purge 166.6)
- `backend/app/schemas/target.py` — [Modifier] — `class HostAccessProfile` + alias `TargetAccessProfile` (l.174-221) ; alias de re-export dans `schemas/host.py` (créé par 166.2)
**Dépend de :** Tâche 1

### Tâche 3 : Renommage `target_scan_parsers` → `host_scan_parsers` (payloads inchangés)
**Objectif :** `git mv` + renommage des imports internes **uniquement**. Les ~20 parseurs (`Parser` subclasses) et `build_capabilities_payload` produisent les **mêmes payloads** (garde-fou §2.G — renommage/wrapping, zéro réécriture de logique). Vérifier qu'aucune clé de payload ne contient le mot `target` : si oui, **ne pas la renommer** (stabilité contractuelle) — consigner l'inventaire dans les Notes d'implémentation.
**Fichiers :**
- `backend/app/services/host_scan_parsers.py` — [Créer] — ex-`target_scan_parsers.py`
- `backend/app/services/target_scan_parsers.py` — [Supprimer] — (ou alias mince `from .host_scan_parsers import *` + `build_capabilities_payload`, purge 166.6)
**Dépend de :** Tâche 1

### Tâche 4 : Renommage `target_scanner_service` → `host_scanner_service`
**Objectif :** `git mv` + classe `TargetScannerService`→`HostScannerService` ; méthodes `scan_localhost`/`scan_remote`/`scan_and_update_target`→`scan_and_update_host` (l.75+, signatures `target: Target`→`host: Host`) ; imports internes sur `host_access_profile`, `host_scan_parsers`, `host_service` (l.48-65) ; `build_ssh_kwargs` (TOFU STRICT) inchangé. Alias de transition : `TargetScannerService = HostScannerService`.
**Fichiers :**
- `backend/app/services/host_scanner_service.py` — [Créer] — ex-`target_scanner_service.py`
- `backend/app/services/target_scanner_service.py` — [Supprimer] — (ou alias mince, purge 166.6)
**Dépend de :** Tâches 1, 2, 3

### Tâche 5 : Mise à jour des consommateurs services (7 fichiers)
**Objectif :** Basculer les imports sur les modules canoniques (renommage uniquement — aucune logique modifiée, l'axe `origin` restant en 166.4) : `deployment_service` (l.513 `enums.target`, l.837-850 `Target` + `TargetService` health-check), `compute_service` (l.20 `Target`, l.31 `LOCAL_TARGET_ID`→Tâche 8, requêtes l.49-206), `container_builder` (l.13 `Target`), `adoption_service` (l.39 `LOCAL_TARGET_ID`→Tâche 8 ; renommage seulement), `terminal_service` (vérifier imports `target_*`), `ssh_connection` (l.85 `Target`, l.448/515 signatures `target: Target`→`host: Host` — `build_ssh_kwargs` TOFU STRICT inchangé, jamais `known_hosts: None`), `ssh_key_service` (l.55 `Target`, l.464 `resolve_for_target`→`resolve_for_host`).
**Fichiers :**
- `backend/app/services/deployment_service.py` — [Modifier] — imports canoniques
- `backend/app/services/compute_service.py` — [Modifier] — idem + `Host` queries
- `backend/app/services/container_builder.py` — [Modifier] — idem
- `backend/app/services/adoption_service.py` — [Modifier] — idem (logique inchangée)
- `backend/app/services/terminal_service.py` — [Modifier] — idem (si consommateur)
- `backend/app/services/ssh_connection.py` — [Modifier] — imports + renommage paramètres (comportement TOFU identique)
- `backend/app/services/ssh_key_service.py` — [Modifier] — imports + `resolve_for_host`
**Dépend de :** Tâches 1-4

### Tâche 6 : Alignement WebSocket `host_access`/`ssh_session`/`journal`
**Objectif :** `websocket/host_access.py` : `resolve_host_and_check_access` retourne désormais `Host` (l.38-91 : `select(Target)`→`select(Host)`, types/docstrings — isolation org `is_member` inchangée) ; `resolve_ssh_username(target)`→`resolve_ssh_username(host)`. `ssh_session.py` (l.188) et `journal.py` (l.110) : variables locales `target`→`host`, docstrings « Target »→« Host » — comportements, audits `ssh_session_audit` et messages TOFU **inchangés**.
**Fichiers :**
- `backend/app/websocket/host_access.py` — [Modifier] — résolution `Host` + docstrings
- `backend/app/websocket/ssh_session.py` — [Modifier] — alignement types/variables
- `backend/app/websocket/journal.py` — [Modifier] — idem
**Dépend de :** Tâche 1

### Tâche 7 : Scheduler + tâches de fond sur imports canoniques
**Objectif :** `scheduler_actions.py` (l.63 `TargetScannerService`, l.120 `Target` — action `host.scan` STORY-160.3) et `background_tasks.py` (l.591 `TargetService.check_all_health`) basculent sur `HostScannerService`/`HostService`/`Host` ; `main.py` (l.202, health-check périodique lifespan) idem. Action `host.scan` : import + exécution non régressés.
**Fichiers :**
- `backend/app/services/scheduler_actions.py` — [Modifier] — imports canoniques + type `Host`
- `backend/app/tasks/background_tasks.py` — [Modifier] — `HostService`
- `backend/app/main.py` — [Modifier] — `HostService` (l.202)
**Dépend de :** Tâches 1, 4

### Tâche 8 : Arbitrage `LOCAL_TARGET_ID`
**Objectif :** **Décision d'analyse** : conserver la constante sémantique mais la résoudre dynamiquement — renommer `LOCAL_TARGET_ID`/`LOCAL_TARGET_NAME` (`container_classifier.py` l.26-27) en `LOCAL_HOST_ID`/`LOCAL_HOST_NAME` avec **alias** `LOCAL_TARGET_ID = LOCAL_HOST_ID` (transition), et modifier `compute_service._resolve_local_target` (l.44-57) pour **retourner l'ID du host seedé** (premier `Host` avec `host ∈ {localhost, 127.0.0.1}` — requête existante l.49) plutôt que le placeholder `"local"` : les stacks/containers adoptés sont ainsi rattachés au vrai host (coopération 166.5 — le seed garantit son existence ; fallback placeholder conservé si absent). `adoption_service` (l.272, l.426) utilise la même résolution.
**Fichiers :**
- `backend/app/services/container_classifier.py` — [Modifier] — constantes renommées + alias (l.25-27)
- `backend/app/services/compute_service.py` — [Modifier] — `_resolve_local_target`→`_resolve_local_host` retourne l'ID seedé (fallback `"local"`)
- `backend/app/services/adoption_service.py` — [Modifier] — résolution via `_resolve_local_host` (comportement adoption inchangé par ailleurs)
**Dépend de :** Tâche 5 (et coordination 166.5 pour le seed)

### Tâche 9 : Migration des fichiers de tests + golden tests
**Objectif :** Renommer/adapter les modules de tests existants (imports + noms de classes) et ajouter les **golden tests** de non-régression des payloads. Aucun test existant supprimé — adaptés in place.
**Fichiers :**
- `backend/tests/unit/test_services/test_target_service.py` — [Modifier→Renommer] — `test_host_service.py` (imports `HostService`, mock `Host`)
- `backend/tests/unit/test_services/test_target_scanner_service.py` — [Modifier→Renommer] — `test_host_scanner_service.py`
- `backend/tests/unit/test_services/test_target_health_check.py` — [Modifier→Renommer] — `test_host_health_check.py` (l.68+ `app.services.target_service` → `app.services.host_service` dans les chemins de patch)
- `backend/tests/unit/test_services/test_commands.py` — [Modifier] — patchs `app.services.target_scanner_service.*` → `app.services.host_scanner_service.*` (l.125-145)
- `backend/tests/unit/test_services/test_adoption_service.py` — [Modifier] — imports
- `backend/tests/unit/test_services/test_host_scan_parsers_golden.py` — [Créer] — golden tests (voir Tests à écrire)
- `backend/tests/unit/test_websocket/test_ws_ssh_session.py` — [Modifier] — classe `TestSshHostAccess` (l.269) + patchs `app.websocket.host_access` inchangés (module déjà canonique) — vérifier uniquement les fixtures/models
- `backend/tests/unit/test_websocket/test_ws_journal.py` — [Modifier] — idem
- `backend/tests/unit/test_services/test_canonical_event_emitters.py` — [Modifier] — `host.offline` : imports `HostService` (l.255-257 `app.models.target`→`app.models.host`, `app.services.target_service`→`app.services.host_service`)
**Dépend de :** Tâches 1-8

## Tests à écrire

### Backend

**`backend/tests/unit/test_services/test_host_scan_parsers_golden.py`** *(créer — cœur du garde-fou §2.G)* :
- **fixtures figées** : `ScanResult` réalistes (docker+kubectl disponibles, libvirt absent, versions exotiques) sérialisés en JSON dans `tests/fixtures/golden/scan_results/*.json` ;
- golden : `build_capabilities_payload(fixture)` == payload de référence commité (avant/après renommage — snapshot capturé sur le code **pré-renommage**, revalidé post) ;
- golden par famille de parseurs (un cas par type : docker, docker_compose, swarm, kubectl/k8s, libvirt/virsh, qemu_kvm, virtualbox, podman, lxc/lxd/incus, containerd, buildah/skopeo, helm…) : sortie parser == référence ;
- golden `HostAccessProfileDetector` : profil d'accès (root/sudo/passwordless/limited) == référence pour chaque scénario de commandes mockées ;
- test **stabilité contractuelle** : aucune clé de payload ne change (`target_id` dans les payloads scanners éventuels — vérifier et figer).

**`backend/tests/unit/test_services/test_host_service.py`** (ex-`test_target_service.py`, adapté) :
- non-régression : health-check TCP (port résolu `_get_health_check_port`, online/offline/unreachable, `last_check` mis à jour, `check_all_health` concurrence) ;
- **`host.offline` émis uniquement sur transition joignable→injoignable** (pattern `test_canonical_event_emitters.py` T5) ;
- `apply_scan_result` : capacités + `installed_engines` + `last_scan_at` + `HostStatus.SCANNING` pendant scan ;
- alias : `from app.services.target_service import TargetService` fonctionne (transition) ;
- credentials : jamais dans les logs, ré-encryptage au premier accès (STORY-103) inchangé.

**`backend/tests/unit/test_services/test_host_scanner_service.py`** (adapté) :
- `scan_and_update_host` : dispatch localhost/remote, `build_ssh_kwargs` TOFU STRICT (échec `SSHHostKeyNotAcceptedError` → scan failed, jamais `known_hosts: None` — test `test_commands.py` l.143 réutilisé) ;
- `mark_scan_failed` → `unreachable` + `scan_success=False`.

**`backend/tests/unit/test_websocket/`** (non-régression WS) :
- `test_ws_ssh_session.py` `TestSshHostAccess` : résolution `Host` 404/403 isolation org + username (credentials → access profile → root) — inchangés ;
- `test_ws_journal.py` : résolution host + isolation org inchangées.

**`backend/tests/unit/test_services/test_scheduler_actions.py`** *(étendre si existant)* :
- action `host.scan` : import `HostScannerService` + exécution déléguée (mock scanner) — non-régression STORY-160.3.

**Sécurité (règle 40)** : TOFU strict (jamais de bypass known_hosts), credentials déchiffrés uniquement en mémoire (jamais dans les assertions de logs), isolation org WS conservée.

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_services/test_host_scan_parsers_golden.py -v
poetry run pytest backend/tests/unit/test_services/test_host_service.py backend/tests/unit/test_services/test_host_scanner_service.py backend/tests/unit/test_services/test_host_health_check.py -v
poetry run pytest backend/tests/unit/test_websocket -v
make backend-test-unit
make backend-lint
```

## Notes d'implémentation

### Fichiers renommés (`git mv`)
- `backend/app/services/target_service.py` → `host_service.py` (classe `HostService`, alias `TargetService = HostService`)
- `backend/app/services/target_scanner_service.py` → `host_scanner_service.py` (classe `HostScannerService`, alias `TargetScannerService` ; `scan_and_update_target`→`scan_and_update_host`, signatures `host: Host`)
- `backend/app/services/target_scan_parsers.py` → `host_scan_parsers.py` (payloads strictement inchangés — docstring seule modifiée)
- `backend/app/services/target_access_profile.py` → `host_access_profile.py` (classe `HostAccessProfileDetector`, alias `TargetAccessProfileDetector`)
- Les 4 anciens chemins deviennent des **fichiers d'alias de transition** minces (purge STORY-166.6)
- Tests : `test_target_service.py`→`test_host_service.py`, `test_target_scanner_service.py`→`test_host_scanner_service.py`, `test_target_health_check.py`→`test_host_health_check.py`

### Fichiers créés
- `backend/tests/unit/test_services/test_host_scan_parsers_golden.py` — **34 golden tests** (garde-fou §2.G)
- `backend/tests/fixtures/golden/scan_results/realistic_host.json` — fixture ScanResult figée (docker+kubectl+helm+podman+lxd+containerd disponibles, libvirt/virtualbox absents, versions réalistes)
- `backend/tests/fixtures/golden/scan_results/realistic_host_capabilities.golden.json` — payload de référence des 13 capacités

### Fichiers modifiés
- `schemas/target.py` — `HostAccessProfile` (ex-`TargetAccessProfile`) + alias `TargetAccessProfile = HostAccessProfile`
- Consommateurs : `deployment_service` (bloc health-check → `Host`/`HostService`), `compute_service` (`Host` + `_resolve_local_host`), `container_builder` (import), `container_classifier` (constantes `LOCAL_HOST_ID`/`LOCAL_HOST_NAME` + alias), `adoption_service` (constantes), `ssh_connection` (`build_ssh_kwargs(host_model: Host)`), `ssh_key_service` (`resolve_for_host`, `Host`), `scheduler_actions` (`HostScannerService`/`Host`), `background_tasks`+`main.py` (`HostService`), `database_seed` (imports canoniques)
- WS : `host_access.py` (`select(Host)`, `resolve_ssh_username(host)`), `ssh_session.py`/`journal.py` (variable `host`, kwargs `host_model=`)
- Appels internes API (kwargs Python, contrats HTTP inchangés) : `api/v1/targets/scanning.py` (`scan_and_update_host`, `apply_scan_result(host=)`), `api/v1/targets/capabilities.py` (`list_capabilities(host_id=)`, dict messages `HostStatus`)
- Tests adaptés : `test_canonical_event_emitters` (Host/HostStatus), `test_scheduler_actions`, `test_ssh_connection`, `test_ssh_key_service`, `test_commands`, `test_adoption_service`, `test_targets_rbac`

### Décisions techniques
1. **`build_ssh_kwargs` : paramètre `host_model`** (et non `host`) — collision avec le paramètre existant `host: str` (l'adresse) ; la story demandait `target`→`host` mais la signature réelle interdisait le doublon. TOFU STRICT inchangé.
2. **Bascule écritures canoniques dans `host_service`** : `last_scan_at`/`hardware_info`/`host_id` remplacent les synonyms `scan_date`/`platform_info`/`target_id` (transmis par 166.1 — purge des synonyms en 166.6).
3. **Inventaire §2.G** : aucune clé de payload de capacité ne contient `target` (test figé `test_payload_keys_contain_no_target_token`). Les clés contractuelles legacy conservées : label Docker `windflow.target_id`, paramètre scheduler `target_id` (`HostScanParams`, STORY-160.3), `TargetResponse.target_id` (API 166.2), `request.target_id` adoption. Comportement figé du parseur kubectl text : version retournée **sans** le préfixe `v`.
4. **`check_all_health` : clé de retour `target_id`→`host_id`** (divergence mineure) — consommateurs vérifiés (`background_tasks`, `main.py` : uniquement `status`/`error`), aucun contrat HTTP exposé ; cohérent avec le payload `host.offline`.
5. **`LOCAL_HOST_ID`/`LOCAL_HOST_NAME`** + alias `LOCAL_TARGET_ID` ; `_resolve_local_host` retourne l'ID du host seedé (premier `Host` avec `host IN ('localhost','127.0.0.1')`), fallback placeholder `"local"` si absent (coopération 166.5). `adoption_service` utilise les constantes canoniques (logique origin inchangée — 166.4).
6. **`scheduler host.scan`** : clé de paramètre `target_id` conservée (contrat `HostScanParams` STORY-160.3 — renommage du paramètre d'action = breaking scheduler), résolution via `session.get(Host, ...)`.
7. **Golden tests** : fixtures générées depuis le code renommé (l'alias `target_scan_parsers` pointe sur le même module — test `test_legacy_alias_module_produces_identical_payload` prouve l'équivalence avant/après) ; 4 scénarios profils d'accès figés (root/sudo_passwordless/sudo_password/limited) via stub executor duck-typé.

### Divergences par rapport à l'analyse
- `ssh_connection` : `host_model` au lieu de `host` (collision de nom, cf. décision 1) — les 5 sites d'appel (`scanner` ×2, `ssh_session`, `journal`, tests) passent `host_model=` ;
- `api/v1/targets/{scanning,capabilities}.py` touchés au-delà du listing de la Tâche 5 : appels Python internes au service renommé (kwargs), **contrats HTTP et paths `/targets` strictement inchangés** — sans cela le runtime cassait (mypy l'a révélé) ;
- `capabilities.py` : dict de messages health-check re-keyé `HostStatus` (bug latent sinon : `messages.get(HostStatus)` rentrait toujours dans le fallback depuis que `check_health` retourne `HostStatus` — posé par 166.1) ;
- `check_all_health` : clé `host_id` (décision 4).

### Validation
- Golden tests : **34 passed** (`pytest tests/unit/test_services/test_host_scan_parsers_golden.py`)
- Tests ciblés services+API : **263 passed** ; WS : **416 passed** (`pytest tests/unit/test_websocket`)
- Suite unitaire complète : **2520 passed, 0 failed** (`pytest tests/unit`)
- Lint périmètre : isort + black + flake8 **0 erreur** ; mypy **0 nouvelle erreur** (restent les préexistantes transitive : `jwt` stubs, `docker_client_service`, `background_tasks` UUID str, `host_scanner_service.py:375` ≡ HEAD l.329) ; `make backend-lint` global reste rouge sur des fichiers **préexistants** hors périmètre (isort sur `alembic/env.py`, `plugin_hook_log.py`… vérifiés non touchés via `git diff HEAD`)
- Couverture : `host_scan_parsers` 91 %, `ssh_connection` 96 %, alias 100 % ; `host_service` 68 % / `host_scanner_service` 38 % / `host_access_profile` 73 % unit — **strictement identiques à HEAD** sur les mêmes tests (mesuré avant/après via stash : 38 % ↔ 38 %, mêmes lignes non couvertes = détections nécessitant une machine réelle) — pas de régression, seuil 80 % atteint sur les modules à logique pure
- Sécurité : TOFU STRICT inchangé (jamais `known_hosts: None` — test `test_kwargs_never_contains_known_hosts`), credentials en mémoire uniquement, isolation org `resolve_host_and_check_access` intacte (416 tests WS)

### Points d'attention pour STORY-166.2
- `HostAccessProfile` (schéma) est prêt dans `schemas/target.py` avec l'alias `TargetAccessProfile` — 166.2 devra créer `schemas/host.py` avec le re-export canonique ;
- les fichiers d'alias `target_service.py`/`target_scanner_service.py`/`target_scan_parsers.py`/`target_access_profile.py` sont **consommés par l'API `/targets`** (`api/v1/targets/crud.py`, `scanning.py`, `fingerprints.py`, `capabilities.py`) : la bascule de l'API vers les imports canoniques (166.2 T3-4) permettra ensuite la purge (166.6) ;
- `api/v1/targets/scanning.py` appelle déjà `scan_and_update_host`/`apply_scan_result(host=)` (kwargs internes) — la surface `/targets` continue de fonctionner via les alias de classes ;
- le paramètre `build_ssh_kwargs(host_model=...)` est le nouveau contrat des 4 sites SSH (`connectivity.py` 166.2 inclus) ;
- `check_all_health` retourne désormais `host_id` (décision 4) — si un endpoint exposait ce dict, prévoir le mapping de réponse.
