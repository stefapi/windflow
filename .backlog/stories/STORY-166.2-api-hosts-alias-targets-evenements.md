# STORY-166.2 : Surface API `/api/v1/hosts/*` + alias `/targets` déprécié + émission réelle `host.*` (P2-4, partie API — STORY-166 découpée)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-166 ([ABANDONED — découpe proactive post-analyse le 2026-10-24](STORY-166-migration-target-vers-host-origin.md))
**Item plan :** P2-4 (F4 étape 2 — volet API, axes C13/F3) — ampleur **L**

> **Périmètre (découpe)** : cette sous-story reprend le **volet API** de STORY-166 — surface canonique `/api/v1/hosts/*` conformément à la spec 09 (liste filtrable, création, détail hardware/moteurs/statut, scan, health-check, capacités, test-reachability/test-connection), alias `/api/v1/targets/*` avec **header `Deprecation`** + note OpenAPI, et **émission réelle des événements `host.*`** (création/suppression/offline). Couvre l'**AC 2 de la mère** et la partie événements de son **AC 5**. Le modèle `Host` vient de [STORY-166.1](STORY-166.1-modele-host-enums-migration-alembic.md) (pré-requis dur) ; le renommage des services par [STORY-166.3](STORY-166.3-services-host-scanners-ws.md) (ordre libre — si 166.3 est traitée d'abord, l'API consomme directement `host_service`).

## Description

En tant qu'administrateur WindFlow, je veux que la surface API canonique `/api/v1/hosts/*` soit exposée conformément à la spec 09, avec l'ancien chemin `/api/v1/targets/*` maintenu en alias déprécié pendant la transition et les événements bus réellement émis en nomenclature `host.*` — afin d'aligner l'API sur le modèle directeur sans casser aucun consommateur existant.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §3.4) : les routes vivent sous `/api/v1/targets` (4 sous-modules, 7 fichiers) et l'événement de suppression émet encore `target.deleted` alors que l'infrastructure canonique `host.*` (STORY-162) est en place.

## Contexte technique

> Extrait de l'analyse STORY-166 (2026-10-24, `analyse-story`) — volet API, fondé sur le code réel du dépôt.

### État réel du code (exploration mère)

- [`api/v1/targets/`](../../backend/app/api/v1/targets) : 7 fichiers — `crud.py` (934 lignes), `capabilities.py`, `connectivity.py`, `fingerprints.py`, `scanning.py`, `helpers.py`, agrégés dans `__init__.py` ; montage dans [`api/v1/__init__.py`](../../backend/app/api/v1/__init__.py) (l.38, `prefix="/targets"`) ;
- **RBAC déjà systématique** : `require_viewer` (lecture), `require_operator` (connectivité), `require_admin` (gestion/scan/fingerprints) depuis [`auth/rbac.py`](../../backend/app/auth/rbac.py) — ⚠️ la mère mentionnait `require_role` : **conserver le pattern code réel `require_*` par rôle** (divergence documentée) ;
- Enveloppes/pagination STORY-128 déjà en place (`PaginatedResponse` + `build_meta`), rate limiting `conditional_rate_limiter` sur tous les endpoints, isolation organisationnelle via `_get_target_for_org` — **à reproduire à l'identique sur `/hosts`** ;
- Événement `target.deleted` émis dans [`crud.py`](../../backend/app/api/v1/targets/crud.py) (l.910) — point d'émission à basculer vers `host.removed` + ajouter `host.added` (création) et `host.offline` (health-check négatif) ;
- **Infra événements prête (STORY-162 ✔)** : [`core/events.py`](../../backend/app/core/events.py) (l.167) — `host.added`/`host.removed`/`host.offline` déjà canoniques, `LEGACY_EVENT_ALIASES` mappe `target.*`→`host.*`, `resolve_event_name()` consommé par le scheduler : **seule l'émission réelle côté CRUD hosts manque** ;
- Schémas [`schemas/target.py`](../../backend/app/schemas/target.py) : `TargetCreate/TargetResponse/TargetUpdate` + **`HostReachabilityRequest/Response` déjà préfixés « Host »** (divergence n°6 — renommage partiellement amorcé) ; cibles spec 09 : `HostCreateRequest`/`HostResponse` ;
- WS [`websocket/host_access.py`](../../backend/app/websocket/host_access.py) (STORY-164.2 ✔) résout déjà par « host » — non touché ici (voir 166.3).

### Points d'attention

- **Double nommage** : `/hosts` = surface canonique documentée OpenAPI ; `/targets` = alias avec header de dépréciation (RFC provisional `Deprecation`/`Sunset` ou header simple documenté) + `deprecated=True` OpenAPI — **aucun consommateur cassé** (contrats testés sur les deux chemins) ;
- Ne pas régresser : rate limiting, enveloppes, pagination, isolation organisationnelle sur les nouveaux chemins ;
- Schémas de réponse : **jamais** `credentials`/`connection_config` en clair (exclusion explicite, règle 40).

### Checklist sécurité (règle 40)

- `require_viewer/operator/admin` sur chaque endpoint `/hosts` (RBAC source de vérité côté API) ;
- Isolation organisationnelle (`_get_target_for_org` → `_get_host_for_org`) : 404/403 pour host d'une autre organisation ;
- Validation Pydantic complète (`HostCreateRequest` etc.), 422 sur body invalide ;
- Champs sensibles exclus des réponses ; logs structurés sans credentials ; audit des actions critiques (suppression) conservé.

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend l'AC 2 de la mère)* : La surface API canonique `/api/v1/hosts/*` est exposée conformément à la spec 09 (liste filtrable, création, détail hardware/moteurs/statut, scan, health-check, capacités, test-reachability/test-connection) avec **RBAC** (pattern `require_*` : lecture viewer+, gestion admin+) et enveloppes/pagination (STORY-126/128) ; `/api/v1/targets/*` répond en **alias avec header `Deprecation`** et note OpenAPI — **aucun consommateur cassé** (tests de contrat sur les deux chemins).
- [x] AC 2 *(reprend la partie événements de l'AC 5 de la mère)* : Les événements bus sont émis en `host.*` — `host.added` (création), `host.removed` (suppression), `host.offline` (health-check négatif) — via l'infra STORY-162 (pattern `resolve_event_name`/émetteurs canoniques), testés.
- [x] AC 3 : Non-régression — rate limiting, enveloppes, pagination et isolation organisationnelle identiques sur les deux chemins ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`09-api.md`](../../docs/general_specs/09-api.md) — § Famille Hosts — `/api/v1/hosts/` (endpoints complets, `HostCreateRequest`/`HostResponse`) ;
- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Host (champs exposés : hardware/moteurs/statut) ;
- [`06-rbac-permissions.md`](../../docs/general_specs/06-rbac-permissions.md) — rôles viewer/operator/admin ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §3 F3 (double nommage), §4 P2-4, §7.1.

## Dépendances

- **[STORY-166.1](STORY-166.1-modele-host-enums-migration-alembic.md)** (dur) — modèle `Host` + migration ;
- **[STORY-166.3](STORY-166.3-services-host-scanners-ws.md)** (dur — **traitée avant**, ordre d'exécution de la série) : cette story consomme directement les modules renommés `host_service`, `host_scanner_service`, `host_scan_parsers`, `host_access_profile` et le schéma `HostAccessProfile` (cf. Tâches 1-2) ;
- **STORY-121/122** (RBAC avant ouverture des nouveaux chemins) ✔ livrées ; **STORY-126/128** (enveloppes/pagination) ✔ livrées ; **STORY-162** (bus canonique) ✔ livrée ;
- Conditionne [STORY-166.6](STORY-166.6-frontend-cli-synchronisation-hosts.md) (consommateurs) ; la chaîne critique du plan (Alembic→RBAC→Host) passe par cette sous-story avant STORY-173.

## État d'avancement technique

*(à cocher pendant `treat-story` — une case par tâche détaillée ci-dessous)*

- [x] T1. Schémas `schemas/host.py` (`HostCreateRequest`/`HostResponse`/`HostUpdate`, exclusions sensibles)
- [x] T2. Renommage du package router `api/v1/targets/`→`api/v1/hosts/` (5 modules, `host_id`)
- [x] T3. Endpoints canoniques branchés sur `HostService` (RBAC/rate-limit/enveloppes identiques)
- [x] T4. Router alias `/targets` avec header `Deprecation` + montage dans `api/v1/__init__.py`
- [x] T5. Émission `host.added` à la création + `host.removed` sur alias et canonique
- [x] T6. OpenAPI : canonique documenté, alias `deprecated=True`
- [x] T7. Tests API `/hosts` + contrats croisés + événements + OpenAPI

## Tâches d'implémentation détaillées

### Tâche 1 : Schémas canoniques `schemas/host.py`
**Objectif :** Créer `HostCreateRequest`, `HostResponse`, `HostUpdate` (cibles spec 09) — miroir de `TargetCreate`/`TargetResponse`/`TargetUpdate` (`schemas/target.py` l.227-302) avec champs canoniques : `profile` (défaut `host_baremetal` — remplace `type`), `status`, `hardware_info`, `installed_engines`, `last_scan_at`, `origin` en lecture seule. `HostResponse` **exclut explicitement** `credentials`/`connection_config` (règle 40 : le schéma ne définit tout simplement pas ces champs — aucun secret en réponse) et garde les champs dérivés `auth_method`/`username`/`has_sudo`/`ssh_key_id` (comportement identique à `TargetResponse`). Valider bornes identiques (`host` min 1 max 255, `port` 1-65535, `name` 1-255). Re-export `HostReachability*`/`ConnectionTest*` (déjà préfixés Host, divergence n°6) et `HostAccessProfile` (posé par 166.3 T2) ; `HealthCheckResponse.target_id`→`host_id`. `schemas/target.py` devient alias de transition (`TargetCreate = HostCreateRequest`, etc. — purge 166.6).
**Fichiers :**
- `backend/app/schemas/host.py` — [Créer] — schémas canoniques complets + re-exports
- `backend/app/schemas/target.py` — [Modifier] — alias de transition + commentaire purge 166.6
- `backend/app/schemas/__init__.py` — [Modifier] — exports
**Dépend de :** STORY-166.1 (enums), STORY-166.3 T2 (`HostAccessProfile`)

### Tâche 2 : Renommage du package router `targets/` → `hosts/`
**Objectif :** `git mv backend/app/api/v1/targets backend/app/api/v1/hosts` (5 modules : `crud.py`→`crud.py`, `capabilities.py`, `connectivity.py`, `fingerprints.py`, `scanning.py` + `__init__.py`) ; handlers `list_targets`→`list_hosts`, `get_target`→`get_host`, `create_target`→`create_host`, `update_target`→`update_host`, `delete_target`→`delete_host` ; paramètres de chemin `target_id: str`→`host_id: str` (16 endpoints recensés : CRUD 5, health-check 1, capabilities 3, fingerprints 3, discover 1, scan 1, test-reachability 1, test-connection 1) ; helper `_get_target_for_org` (`fingerprints.py` l.54)→`_get_host_for_org` ; tags OpenAPI `["targets"]`→`["hosts"]`. Imports internes : `....services.host_service import HostService` (livré 166.3), `....services.host_scanner_service`/`host_scan_parsers` (`scanning.py` l.36-38), schémas depuis `schemas/host`.
**Fichiers :**
- `backend/app/api/v1/hosts/__init__.py` — [Créer] — ex-`targets/__init__.py` (agrégation 5 sous-routers)
- `backend/app/api/v1/hosts/crud.py` — [Créer] — ex-`targets/crud.py` (934 l.)
- `backend/app/api/v1/hosts/capabilities.py` — [Créer] — ex-`targets/capabilities.py`
- `backend/app/api/v1/hosts/connectivity.py` — [Créer] — ex-`targets/connectivity.py`
- `backend/app/api/v1/hosts/fingerprints.py` — [Créer] — ex-`targets/fingerprints.py`
- `backend/app/api/v1/hosts/scanning.py` — [Créer] — ex-`targets/scanning.py`
- `backend/app/api/v1/targets/` — [Supprimer] — package remplacé (le router alias de Tâche 4 reprend la surface `/targets`)
**Dépend de :** Tâche 1, STORY-166.3 (services renommés)

### Tâche 3 : Endpoints canoniques — RBAC, rate limiting, enveloppes à l'identique
**Objectif :** Reproduire **exactement** les garde-fous existants sur les chemins canoniques : `require_viewer` (lecture : list/get/capabilities), `require_operator` (connectivité : test-reachability/test-connection), `require_admin` (gestion : create/update/delete/discover/scan/fingerprints + health-check — vérifier par fichier : `capabilities.py` l.92/281/450/618 viewer ; `connectivity.py` l.75/300 operator ; `crud.py` l.145/289 viewer, l.505/747/878 admin ; `scanning.py` l.270/570 admin ; `fingerprints.py` l.144/237/356 admin) ; `conditional_rate_limiter` mêmes quotas (100/60 liste, 20/60 création, 50/60 update, 30/60 delete) ; `PaginatedResponse`+`build_meta` (STORY-128) ; isolation org `UserOrganizationService.is_member`/`_get_host_for_org` (403 host d'une autre org, 404 introuvable) ; logs structurés avec `correlation_id` **sans credentials** ; audit `AuditService.log_from_request` conservé (l.909-917) avec `resource_type="host"`.
**Fichiers :**
- `backend/app/api/v1/hosts/*.py` — [Modifier] — (dans le cadre de la Tâche 2 : reprise à l'identique des dépendances sécurité de chaque endpoint)
**Dépend de :** Tâche 2

### Tâche 4 : Router alias `/targets` (Dépréciation) + montage
**Objectif :** Créer un **router alias mince** `api/v1/targets_legacy.py` : `APIRouter(prefix="/targets", deprecated=True, include_in_schema=True)` qui `include_router(hosts.router)` et ajoute le header `Deprecation: true` (+ `Sunset` indicatif documenté) via un petit middleware/dépendance de réponse — **aucune logique dupliquée** (les handlers restent ceux de `hosts/`). Monter dans `api/v1/__init__.py` : `api_router.include_router(hosts_router, prefix="/hosts", tags=["hosts"])` (l.38 remplacée) + `api_router.include_router(targets_alias_router, prefix="/targets", tags=["targets"])`. Aucun consommateur cassé : contrats identiques (testés Tâche 7).
**Fichiers :**
- `backend/app/api/v1/targets_legacy.py` — [Créer] — router alias + injection header `Deprecation`/`Sunset`
- `backend/app/api/v1/__init__.py` — [Modifier] — montage `/hosts` canonique + alias `/targets` (l.24, l.38)
**Dépend de :** Tâches 2, 3

### Tâche 5 : Émissions `host.added` / `host.removed` (+ `host.offline` vérifié)
**Objectif :** Dans `hosts/crud.py` : émettre `EventType.HOST_ADDED` après création réussie (`create_host`, payload `{host_id, name, organization_id}` — sans secret, best-effort try/except pattern l.922-933) ; l'émission `HOST_REMOVED` (l.925-931) est **conservée à l'identique** (déjà canonique). Vérifier `host.offline` : émetteur = `HostService.check_health` (166.3 — déjà en place, STORY-162), et l'endpoint health-check (`capabilities.py` l.127) déclenche `check_health` → l'émission passe par le service : **rien à ajouter côté API, à tester seulement**. Action d'audit : aligner `"target.deleted"`→`"host.removed"` (`resource_type="host"`) après vérification des consommateurs de l'audit trail (`test_audit_emission.py` l.297-317, dashboards Grafana) ; si un consommateur filtre sur l'ancienne valeur, conserver temporairement l'ancienne action et tracer la divergence en Notes d'implémentation.
**Fichiers :**
- `backend/app/api/v1/hosts/crud.py` — [Modifier] — émission `HOST_ADDED` post-création + action audit alignée
**Dépend de :** Tâche 3

### Tâche 6 : OpenAPI — canonique documenté, alias déprécié
**Objectif :** Vérifier la spéc générée : routes `/api/v1/hosts/*` avec summaries/descriptions/examples complets (docstrings riches existantes reprises) ; routes `/api/v1/targets/*` marquées `deprecated: true` + description « Alias déprécié — utilisez /api/v1/hosts (removal: plan F3) ». `make generate-openapi-docs` + vérification manuelle `/docs` (Scalar).
**Fichiers :**
- `backend/app/api/v1/hosts/*.py` — [Modifier] — docstrings/`openapi_extra` examples conservés et enrichis
- `backend/app/api/v1/targets_legacy.py` — [Modifier] — description alias déprécié
**Dépend de :** Tâche 4

### Tâche 7 : Tests API + contrats croisés + événements + OpenAPI
**Objectif :** Écrire les tests d'endpoints `/hosts` (pattern `test_api/` existant), les contrats croisés `/hosts`≡`/targets`, les émissions d'événements, la marque OpenAPI.
**Fichiers :**
- `backend/tests/unit/test_api/test_hosts_crud.py` — [Créer]
- `backend/tests/unit/test_api/test_hosts_alias_contract.py` — [Créer]
- `backend/tests/unit/test_api/test_hosts_events.py` — [Créer]
- `backend/tests/unit/test_api/test_openapi.py` — [Modifier] — assertions `/hosts` documenté + `/targets` deprecated (extension)
- `backend/tests/unit/test_api/test_targets_rbac.py` — [Modifier→Renommer] — `test_hosts_rbac.py` (matrice 401/403/200 reprise sur chemin canonique, alias testé sur un sous-ensemble)
- `backend/tests/unit/test_api/test_targets_fingerprints.py` — [Modifier→Renommer] — `test_hosts_fingerprints.py` (idem)
- `backend/tests/integration/test_secret_encryption.py` — [Modifier] — GET `/api/v1/targets/{id}` l.364 → aussi `/hosts/{id}` (aucun secret en réponse)
**Dépend de :** Tâches 4, 5, 6

## Tests à écrire

### Backend

**`backend/tests/unit/test_api/test_hosts_crud.py`** *(créer)* — surface canonique :
- nominaux : GET liste vide/avec éléments + pagination (`data`/`pagination` enveloppe STORY-128, `page`/`per_page`), GET détail complet (profile, status, hardware_info, installed_engines, origin), POST création 201+objet, PUT mise à jour, DELETE 204 ;
- **sécurité obligatoire** : 401 sans token (chaque verbe), 403 viewer sur POST/PUT/DELETE (admin requis), 403 operator sur create (selon matrice), 422 body invalide (`{}`, `host` manquant, `port: 0`/`70000`, `name` vide), 404 host introuvable, **403 isolation organisationnelle** (host d'une autre org), 409 doublon de nom dans l'org ;
- **absence de champs sensibles** : `credentials`/`connection_config`/`password`/`ssh_private_key` absents de toutes les réponses (GET liste, GET détail, POST réponse) ;
- rate limiting : quotas identiques à l'existant (liste 100/60).

**`backend/tests/unit/test_api/test_hosts_alias_contract.py`** *(créer)* — double nommage :
- contrat identique : GET/POST/PUT/DELETE sur `/hosts/{id}` et `/targets/{id}` → mêmes payloads (comparaison JSON des réponses) ;
- **header `Deprecation` présent sur `/targets` uniquement** (absent de `/hosts`) ;
- les 16 endpoints répondent sur les deux chemins (test paramétré sur un sous-ensemble représentatif : liste, détail, create, delete, health-check, capabilities, scan, test-reachability, fingerprints).

**`backend/tests/unit/test_api/test_hosts_events.py`** *(créer — pattern `test_canonical_event_emitters.py`)* :
- POST `/hosts` → événement `host.added` émis (payload `{host_id, name, organization_id}` — pas de secret) ;
- DELETE `/hosts/{id}` → `host.removed` émis (existant l.925, revalidé) ;
- POST `/hosts/{id}/health-check` avec host devenant injoignable → `host.offline` émis (via `HostService.check_health` — transition online→offline uniquement) ;
- émission best-effort : échec bus n'altère pas la réponse API.

**`backend/tests/unit/test_api/test_openapi.py`** *(étendre)* :
- routes `/api/v1/hosts` présentes et non-dépréciées, avec examples ;
- routes `/api/v1/targets` présentes avec `deprecated: true`.

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_api/test_hosts_crud.py backend/tests/unit/test_api/test_hosts_alias_contract.py backend/tests/unit/test_api/test_hosts_events.py -v
poetry run pytest backend/tests/unit/test_api/test_openapi.py -v
make backend-test-unit
make backend-lint
```

## Notes d'implémentation (2026-10-29, treat-story)

### Fichiers créés
- `backend/app/schemas/host.py` — schémas canoniques (`HostCreateRequest`/`HostResponse`/`HostUpdate`/`HostHealthCheckResponse`/`HostCapabilitiesResponse` + reachability/connection-test/access-profile re-déclarés canoniques). Arbitrage `profile`/`type` par `model_validator` (canonique prioritaire, défaut `host_baremetal`) ; `HostResponse` n'expose jamais `credentials`/`connection_config` (règle 40) et conserve les alias legacy (`type`, `scan_date`, `platform_info`) pour le contrat `/targets` figé.
- `backend/app/api/v1/targets_legacy.py` — router alias `/targets` (`deprecated=True`) re-montant les handlers `hosts/` sans duplication + `DeprecationHeadersMiddleware` (ASGI pur — cf. décisions).
- `backend/tests/unit/test_api/test_hosts_crud.py` (24 tests), `test_hosts_alias_contract.py` (16 tests), `test_hosts_events.py` (8 tests).

### Fichiers renommés (git mv — historique préservé)
- `backend/app/api/v1/targets/` → `backend/app/api/v1/hosts/` (5 modules + helpers + `__init__`).
- Tests : `test_targets_rbac.py` → `test_hosts_rbac.py`, `test_targets_fingerprints.py` → `test_hosts_fingerprints.py`, `test_targets_crud_ssh_key_ref.py` → `test_hosts_crud_ssh_key_ref.py`, `test_test_connection_tofu.py` → `test_hosts_test_connection_tofu.py`.

### Fichiers modifiés
- `backend/app/schemas/target.py` — devient alias de transition (re-exports `Host*`, `TargetCreate = HostCreateRequest`, etc. — purge 166.6).
- `backend/app/schemas/__init__.py` — exports `Host*` canoniques.
- `backend/app/api/v1/hosts/*` — handlers renommés (`list_hosts`…), `target_id`→`host_id` (16 endpoints), imports services canoniques (`host_service`, `host_scanner_service`, `host_scan_parsers`), tags OpenAPI `["hosts"]`, prose OpenAPI « hosts » + exemples enrichis champs canoniques spec 06.
- `backend/app/api/v1/__init__.py` — double montage `/hosts` + `/targets` (alias).
- `backend/app/main.py` — `DeprecationHeadersMiddleware` (position la plus externe) + tags OpenAPI `hosts`/`targets` documentés.
- `backend/app/core/events.py` — commentaire émetteurs `host.*` mis à jour (l.107).
- Tests consommateurs : `test_canonical_event_emitters.py` (chemins/patches canoniques), `test_audit_emission.py` (action `host.removed` + chemin `/hosts`), `test_host_health_check.py` (`HostHealthCheckResponse(host_id=…)`), `test_rbac_exhaustivite.py` (`EXPECTED_ROUTE_COUNTS`: `hosts: 16` + `targets_legacy: 16`), `tests/integration/test_openapi.py` (+3 tests 166.2), `tests/integration/test_secret_encryption.py` (garanties secrets étendues à `/hosts` + `/hosts/{id}`).

### Décisions techniques
1. **Middleware ASGI pur pour la dépréciation** : une dépendance FastAPI (`Depends(Response)`) posait bien les headers sur les 2xx, mais l'error handler externe reconstruit ses `JSONResponse` **sans copier les headers** → headers perdus sur 401/403/404/422. Le middleware ASGI (`DeprecationHeadersMiddleware`) injecte au niveau `http.response.start` (le plus proche du protocole, après toutes les reconstructions) : la marque `Deprecation: true` + `Sunset` (indicatif `2027-01-01`, non contractuel) survit à toute réponse de l'alias, y compris les erreurs. Vérifié par test (`test_deprecation_header_also_on_errors`).
2. **Audit suppression aligné** : `target.deleted`/`resource_type="target"` → **`host.removed`/`resource_type="host"`**. Recensement consommateurs (2026-10-29) : aucun dashboard Grafana ni consommateur métier ne filtre sur l'ancienne action (grep `target.deleted` : uniquement `LEGACY_EVENT_ALIASES` events.py — bus, pas audit — le test `test_audit_emission.py` l.314 [mis à jour] et une migration Alembic passée). L'historique d'audit en base reste lisible (anciennes lignes inchangées). Décision conforme à la story (bascule si aucun consommateur).
3. **Actions audit fingerprints inchangées** (`target.fingerprint_accepted`/`target.fingerprint_reset`) : hors périmètre T5 (story ne vise que la suppression) — la cohérence globale des actions audit sera arbitrée par 166.6.
4. **Compatibilité contrat `/targets`** : `HostCreateRequest` accepte `type` legacy en entrée (arbitrage vers `profile`, écho fidèle `migrated_type`) ; `HostResponse` expose les deux nomenclatures ; `HostHealthCheckResponse.host_id` canonique + `target_id` en `computed_field` (le frontend lit `result.target_id` — stores/targets.ts l.125 : aucun consommateur cassé). Payload événement fingerprint : clé `host_id` (renommage mécanique cohérent, test mis à jour) + clé `target_id` conservée dans le payload emit initial.
5. **`Sunset` au 2027-01-01** : indicatif (fin de transition plan F3/166.6), documenté comme non contractuel dans le docstring — ajustable sans casseur.

### Divergences par rapport à l'analyse
1. **`test_openapi.py`** : la story visait `backend/tests/unit/test_api/test_openapi.py` (inexistant) → assertions intégrées dans le réel `backend/tests/integration/test_openapi.py` (+3 tests : canonique documenté ≥16 ops avec summaries, alias `deprecated: true` ≥16 ops, tag déprécié documenté). Divergence annoncée dans la mission, appliquée.
2. **`make generate-openapi-docs`** : échoue sur l'absence du script `dev/scripts/generate_openapi_junie.py` (problème **préexistant**, hors périmètre — non corrigé pour ne pas élargir la story ; la validité OpenAPI est couverte par les tests d'intégration `test_openapi.py` qui passent).
3. **Divers isort préexistants** : `backend-lint` échoue sur des fichiers non touchés (`alembic/env.py`, `schemas/target_scan.py`, `schemas/plugin_hook_log.py`, `services/docker_*.py`, `services/commands.py`, `api/v1/compute.py`) — dettes antérieures à la story, non corrigées (périmètre). Tous les fichiers touchés par la story passent isort/black/flake8/mypy (mypy : 4 erreurs préexistantes dans `hosts/` = mêmes que la baseline `targets/`, zéro nouvelle).

### Difficultés rencontrées
- Le paramètre de chemin est devenu `{host_id}` sur les deux surfaces (renommage du handler partagé) : sans impact consommateur (paramètre positionnel), documenté ici.
- Enveloppe STORY-128 : la liste paginée n'est **pas** ré-enveloppée (`{data, pagination, message}` direct) — tests alignés sur ce comportement réel.

### Validation
- `pytest backend/tests/unit -q` : **2570 passed** (dont 50 nouveaux tests `/hosts` : 24 crud + 16 alias-contract + 8 events + 3 openapi intégration + extension secret-encryption).
- `pytest backend/tests/integration/test_openapi.py test_secret_encryption.py test_api_contract.py` : passants.
- Lint périmètre touché : isort ✓, black ✓, flake8 ✓, mypy ✓ (0 nouvelle erreur).
- Vérification runtime OpenAPI : 13 paths × 2 surfaces, 16 ops `/targets` `deprecated: true`, 0 op `/hosts` dépréciée, tags `hosts`/`targets` documentés.
