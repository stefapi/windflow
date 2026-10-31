# STORY-173 : Compute `browse`/`prune` — endpoints manquants, prune protégé (superadmin + confirmation + dry-run + audit) et rapprochement de la surface `/compute` avec l'existant `/docker` (P2-11 + P2-14 partie tests — axes D1, F3, C9)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-11 (axes D1, F3, rapports §1/§5) + contribution P2-14 (C9 — couverture des zones tests liées) — ampleur **M**

## Description

En tant qu'administrateur WindFlow, je veux que la surface `/compute/*` (Mode Infra) gagne les endpoints manquants — **`browse`** (inventaire détaillé paginé et filtrable, dont le browse des volumes) et **`prune`** Docker (images/volumes/conteneurs stoppés, avec sémantique protégée) — le prune étant réservé au **superadmin avec confirmation explicite** et exposable en **dry-run**, afin de compléter la surface Compute spécifiée en réutilisant l'inventaire Docker existant plutôt qu'en créant un nouveau runtime.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §3.7-3.8, §13.4) : le router [`compute.py:25`](../../backend/app/api/v1/compute.py:25) n'expose que `stats` et `global` — ni `browse`, ni `prune`, ni la sous-surface volumes du spec 09 ; parallèlement le module [`docker.py:69`](../../backend/app/api/v1/docker.py:69) porte 40 endpoints riches (dont prune-ish) — le rapprochement des deux surfaces (arbitrage F3 : incorporation des surfaces HORS SPEC dans la spec 09) est à documenter ; les tests compute sont partiels (§13.4).

## Contexte technique

### Constats d'exploration (état réel du code au 2026-10-31)

- **Router compute minimal confirmé** : [`compute.py`](../../backend/app/api/v1/compute.py) expose exactement 2 routes — `/stats` ([l.42](../../backend/app/api/v1/compute.py)) et `/global` ([l.101](../../backend/app/api/v1/compute.py)) — toutes deux `require_viewer` + pattern organisation (paramètre `organization_id` vérifié par `UserOrganizationService.is_member` sinon `PermissionDeniedError` 403 ; sinon scoping multi-appartenance STORY-121.3). Monté sous `/compute` ([`api/v1/__init__.py:59`](../../backend/app/api/v1/__init__.py)). Garde-fou de non-régression : `"compute": 2` et `"docker": 35` dans `EXPECTED_ROUTE_COUNTS` ([`test_rbac_exhaustivite.py:84-85`](../../backend/tests/unit/test_api/test_rbac_exhaustivite.py)) — ces compteurs reflètent tout ajout de route.
- **Le socle prune protégé EXISTE DÉJÀ (livré par STORY-160.3 — la story a été rédigée avant)** : [`docker_client_service.py`](../../backend/app/services/docker_client_service.py) porte `PROTECTED_RESOURCE_PREFIX = "windflow-plugin-"` (l.311), `PRUNE_MAX_ITEMS = 500` (l.315), `is_protected_resource()` (l.318), la dataclass `PruneResult` (l.323 : `resource/dry_run/pruned_count/space_reclaimed_bytes/spared_count`) et les wrappers **`prune_images()` (l.1428) / `prune_volumes()` (l.1475)** : dry-run par défaut via listage (aucun appel suppressif), liste protégée épargnée **par construction**, suppressions unitaires `DELETE` un-à-un, carte des montages `_volume_names_in_use()` (l.1528 — construite via `list_containers(all=True)` : **un volume monté par un container arrêté est bien « utilisé »**, sémantique spec 09 respectée), `dangling=true` pour les images (l.1448), `space_reclaimed_bytes=0` pour les volumes (taille non exposée par l'API Docker — limite documentée l.1493-1495). Consommé par le handler scheduler `compute_docker_prune` ([`scheduler_actions.py:168`](../../backend/app/services/scheduler_actions.py)) + `_audit_prune` (l.224, acteur système).
- **Deltas réels restants sur ce socle** (ce que 173 ajoute) : (a) **conteneurs stoppés absents** — `DockerPruneParams.resource` est `Literal["images", "volumes"]` ([`schemas/actions.py:58-79`](../../backend/app/schemas/actions.py)) ; (b) **échecs interruptifs** — les boucles de suppression (l.1461-1473 images, l.1513-1521 volumes) n'attrapent pas l'erreur par item : un volume devenu utilisé entre la liste et la suppression **lève et interrompt la file**, et `PruneResult` n'a **aucun champ échec** ; (c) **aucun endpoint API** n'expose ces wrappers (aucune route prune sous `/compute` ni `/docker`) ; (d) le rapport ne porte que des **comptages**, pas les noms — l'AC 2 / spec 09 §Prune exigent supprimés / épargnés / échecs.
- **Inventaire réutilisable pour `browse`** : `get_compute_global` ([`compute_service.py:170`](../../backend/app/services/compute_service.py)) construit déjà la vue classifiée (managed/discovered/standalone via `classify_containers`, builders de [`container_builder.py`](../../backend/app/services/container_builder.py), filtres `apply_filters` type/technology/target_id/status/search de [`compute_helpers.py`](../../backend/app/helper/compute_helpers.py)) — `browse` = **aplatissement paginé** de cet inventaire (sur-fonction, aucun nouveau runtime). Le filtre « par Host » s'appuie sur `target_id` (label `windflow.target_id` / host local seedé STORY-166.5, `_resolve_local_host` l.40).
- **Volumes** : `list_volumes()` (l.1356) + dataclass `VolumeInfo` (l.164 : name/driver/mountpoint/created_at/labels/scope — **pas de taille par volume**). Le router [`docker.py`](../../backend/app/api/v1/docker.py) expose déjà GET/POST/DELETE `/docker/volumes` (l.1947/2004/2057 — viewer/admin/admin, `paginate_sequence`) et `VolumeResponse`/`VolumeCreateRequest` existent ([`schemas/docker.py:690/703`](../../backend/app/schemas/docker.py)) : miroir parfait pour la sous-surface `/compute/volumes`. **Aucun browse de contenu n'existe nulle part** : ni `get_archive`/`put_archive` dans le service, ni conteneur éphémère — le chemin au socle existant est **conteneur éphémère + exec** : `create_container()` (l.554, paramètre `mounts`), `exec_in_container()` (l.1793), `remove_container()` (l.916).
- **Superadmin** : la protection canonique est le **flag** `is_superuser` via `require_superuser` ([`dependencies.py:157`](../../backend/app/auth/dependencies.py), alias `get_current_superadmin` — lève `PermissionDeniedError` 403), déjà utilisée pour les surfaces destructrices (admin audit STORY-125.3). `require_role("super_admin")` ([`rbac.py:51`](../../backend/app/auth/rbac.py)) teste le rôle global hiérarchique — le flag est le marqueur le plus strict (décision D7).
- **Audit** : `AuditService.log(action, *, user_id, organization_id, resource_type, resource_id, details, ip_address, correlation_id, db)` ([`audit_service.py:132`](../../backend/app/services/audit_service.py)) — best-effort (ne lève jamais), `details` systématiquement sanitizé. L'endpoint API audite avec l'**acteur utilisateur** (`user_id=current_user.id`, `correlation_id` du middleware) — contrairement à `_audit_prune` scheduler (acteur système).
- **Pagination/enveloppes** : `PaginationQuery` (page 1, per_page 20, max 100 → 422 au-delà) + `paginate_sequence()` ([`helper/pagination.py:47/111`](../../backend/app/helper/pagination.py)) — pattern exact de `docker.py list_volumes` (l.1960-1995 : source non-SQL, slicing mémoire). Enveloppe STORY-126 automatique (middleware `api_response` enveloppe le JSON `/api/v1/*` — les routers retournent le modèle sérialisé via `model_dump()`).
- **Rate limiting** : pattern `dependencies=[Depends(conditional_rate_limiter(N, 60))]` sur chaque route docker (l.1958 : 100/60 en lecture, 20-30/60 en écriture) — à répliquer sur les nouvelles routes.
- **Tests existants compute** (§13.4 — partiels) : [`test_compute_api.py`](../../backend/tests/unit/test_compute_api.py) (401, enveloppes, org check, mocks `app.api.v1.compute.compute_service.*`), [`test_misc_rbac.py`](../../backend/tests/unit/test_api/test_misc_rbac.py) (viewer 200), [`test_api_contract.py`](../../backend/tests/integration/test_api_contract.py) (enveloppe), [`test_compute_service.py`](../../backend/tests/unit/test_services/test_compute_service.py) / [`test_container_builder.py`](../../backend/tests/unit/test_services/test_container_builder.py) / [`test_compute_helpers.py`](../../backend/tests/unit/test_services/test_compute_helpers.py) (services). Les tests scheduler prune existants ([`test_scheduler_actions.py`](../../backend/tests/unit/test_services/test_scheduler_actions.py), [`test_action_registry.py`](../../backend/tests/unit/test_services/test_action_registry.py)) doivent rester verts (évolution compatible — D5).

### Décisions d'analyse

- **D1 — `GET /compute/browse` = aplatissement paginé de l'inventaire existant** : réutiliser le chemin `get_compute_global` et aplatir en items uniformes `{id, name, kind: managed_service|discovered|standalone, status, target_id, target_name, image, …}` ; filtres `type`/`target_id`/`status`/`search` identiques à `/global` + pagination `PaginationQuery`/`paginate_sequence` — **aucun appel Docker nouveau** ; viewer+ (cohérent stats/global) + org check identique.
- **D2 — Sous-surface volumes minimale** : `GET /compute/volumes` (liste paginée — miroir de `docker.py:1947`), `GET /compute/volumes/{name}` (détail, 404 si absent), `GET /compute/volumes/{name}/browse` (contenu). **Upload/download/PUT browse/{path} différés** (exigent des wrappers `get_archive`/`put_archive` inexistants + validation binaire — renvoi explicite Roadmap Phase 5, conforme au « minimum viable : listing paginé du contenu » fixé par la story).
- **D3 — Browse de contenu par conteneur éphémère sécurisé** : image **épinglée** (`busybox:1.37` — jamais `:latest`), montage du volume **read-only** (`mounts=[{"type": "volume", "source": <name>, "destination": "/vol", "mode": "ro"}]`), `network_mode="none"`, **pas de privileged**, nom `windflow-browse-{uuid8}` + labels `windflow.transient=true`, exec `ls -1p /vol[/<subpath>]` (args en **liste**, jamais de shell), sortie parsée en entrées fichier/dossier, **pagination mémoire**, nettoyage `remove_container` en `finally` garanti (même sur erreur exec). Validations d'entrée : nom de volume regex Docker `^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$` (422 sinon), sous-chemin éventuel **anti-traversal** (rejet `..` et chemins absolus). Docker indisponible → erreur métier explicite (`WindFlowException` — pas de 200 vide trompeur). Le pull de l'image au premier appel est un comportement documenté.
- **D4 — `POST /compute/prune` : confirmation ET dry-run** : body `ComputePruneRequest{resource: Literal["images","volumes","containers"], dry_run: bool = False, confirm: bool = False, force: bool = False}`, `extra="forbid"` — exécution réelle **seulement si `confirm=true`** ; sans confirm → `InvalidInputError` **400** avec message actionnable (AC 3) ; `dry_run=true` → rapport prévisionnel **sans aucun appel suppressif** (toujours disponible, même sans confirm). RBAC : `require_superuser` (D7). Réponse `ComputePruneResponse` : `{resource, dry_run, pruned: [names], spared: [names], failed: [{name, error}], pruned_count, spared_count, failed_count, space_reclaimed_bytes}` — **aucune taille fabriquée pour les volumes** (0, limite documentée), réelle pour les images.
- **D5 — Évolution du socle 160.3 compatible ascendante** : `PruneResult` gagne `pruned_names`/`spared_names`/`failed_names: list[str]` (`field(default_factory=list)`) et `failed_count: int = 0` ; les boucles de suppression attrapent l'erreur **par item** (aiohttp 409/500 → item passé en échec, la file continue) — l'AC 2 « un échec n'interrompt pas la file » devient structurel. Les consommateurs scheduler (`compute_docker_prune`/`_audit_prune`) reçoivent les nouveaux champs sans casse (champs à défauts) et l'audit gagne `failed_count`. **Aucune suppression d'endpoint** (garde-fou §2.G).
- **D6 — `prune_stopped_containers()` nouveau wrapper** : candidates = containers `state != "running"` **sans label `windflow.managed=true`** (une stack WindFlow arrêtée n'est pas du déchet — décision propre à WindFlow, tracée ici), ressources `windflow-plugin-*` épargnées (nom/labels), suppression unitaire `force=False`, même contrat `PruneResult`. `DockerPruneParams.resource` étendu à `Literal["images","volumes","containers"]` (registre scheduler aligné — le test existant « networks → 422 » reste vert) + dispatch dans `compute_docker_prune`.
- **D7 — Superadmin = `require_superuser`** (flag `is_superuser`, le marqueur le plus strict — spec 08 « opérations destructrices globales = Super Admin ») ; 403 attendu pour admin/operator/viewer (tests AC 3).
- **D8 — Rapprochement `/compute` ↔ `/docker` documenté** : table de correspondance complète dans un document dédié `docs/technical_specs/COMPUTE-DOCKER-MAPPING.md` (**créer** : mapping route à route volumes/images/containers/prune, côté canonique `/compute` cible spec 09, période de convergence, décision explicite « aucune suppression d'endpoint Docker ») + renvoi depuis la section compute de [`09-api.md`](../../docs/general_specs/09-api.md). La correction consolidée F3 reste portée par STORY-252 si non fusionnée (« coordination P3-4 ») — cette story livre la table et le renvoi.
- **D9 — Comptage/non-régression** : `EXPECTED_ROUTE_COUNTS["compute"]` 2 → **7** (+`/browse`, `/volumes`, `/volumes/{name}`, `/volumes/{name}/browse`, `/prune`) avec commentaire STORY-173 ; `"docker": 35` **inchangé** ; `/compute/stats|global` non modifiés (tests existants verts).
- **Sécurité (checklist règle 40 évaluée — intégrée aux tâches)** : authN sur toutes les routes (viewer+ lecture / superadmin prune) ; isolation organisation sur browse/volumes (pattern `stats/global`, 403 org étrangère) ; validation Pydantic stricte (`Literal` resource, regex noms de volumes, `per_page` borné, `extra="forbid"`) ; **aucune injection** (exec en args liste sans shell, sous-chemins anti-traversal, jamais de concaténation de chaîne vers le démon) ; réponses sans données sensibles (rapport = noms/comptages/octets ; contenu de fichiers jamais loggé) ; **audit de l'exécution réelle** (`compute.prune`, `user_id`, `correlation_id` — jamais `force`/params bruts) ; rate limiting sur les 5 routes (100/60 lectures, 10/60 prune — destructeur) ; logs sans secrets.

Éléments existants à réutiliser / contraintes :
- **Réutilisation, pas nouveau runtime** : `browse`/`prune` sont des **sur-fonctions de l'inventaire existant** — [`compute_service.py:58`](../../backend/app/services/compute_service.py:58) (`get_compute_stats`/`get_compute_global`), [`container_classifier.py:61`](../../backend/app/services/container_classifier.py:61), [`container_builder.py:99`](../../backend/app/services/container_builder.py:99), [`docker_client_service.py:312`](../../backend/app/services/docker_client_service.py:312) (dataclasses VolumeInfo/ImageInfo + accès socket) — s'y brancher ;
- **`browse` volumes** : contrat spec 09 § Volumes — `GET /compute/volumes` (liste, filtre host), `GET /compute/volumes/{id}/browse` (contenu), `browse/{path}` (fichier/dossier), + upload/download si périmètre raisonnable (sinon noté différé) ; minimum viable : listing paginé du contenu d'un volume ;
- **`prune` — sémantique protégée spec 09** : s'applique aux **volumes orphelins** et **images inutilisées** (+ conteneurs stoppés) : « inutilisé = sans aucun utilisateur, **y compris un container arrêté** » ; **liste protégée par convention de nommage** `windflow-plugin-*` (caches plugins — bases de vulnérabilités, state des helpers) **épargnée** ; suppression **unitaire, sans force** — un volume devenu utilisé entre la liste et la suppression échoue et est **passé** ; **rapport explicite** : supprimés / épargnés (protégés) / échecs ; l'espace libéré n'est **pas fabriqué** pour les volumes (l'API Docker ne fournit pas la taille par volume), réellement rapporté pour les images ; `dangling=true` par défaut pour les images ;
- **Protection** : `prune` réservé **superadmin** (`require_role("super_admin")` ou `require_superuser` selon l'état STORY-122), **confirmation explicite** (paramètre `confirm=true` requis), **dry-run** (liste ce qui serait supprimé sans supprimer), **audit** (ligne d'audit STORY-125 sur exécution réelle) ;
- **Rapprochement `/compute` ↔ `/docker` (F3)** : documenter la correspondance des endpoints dupliqués/voisins (ex. prune volumes/images des deux côtés) et faire converger vers la nomenclature cible `/compute` (le double nommage style targets→hosts de STORY-166 sert de modèle si nécessaire) ; **aucune suppression d'endpoint Docker** (garde-fou §2.G) ;
- **Hors périmètre noté (D1)** : le check-updates (digest sans pull, semver, pending-updates) et le **graphe de dépendances complet** `/compute/graph` restent hors périmètre (Roadmap Phase 5 / §6 du plan) ;
- Endpoints nouveaux = enveloppes (STORY-126) + pagination (STORY-128) dès l'ouverture.

## Critères d'acceptation (AC)

- [x] AC 1 : `browse` est exposé de façon **paginée et filtrable** (vue détaillée de l'inventaire compute : filtres par type/Host/statut, recherche libre ; listing du contenu d'un volume via `GET /compute/volumes/{id}/browse`) — tests : liste vide, liste avec données, filtres, enveloppe `pagination{}`, 401/403 (RBAC lecture viewer+) /422.
- [x] AC 2 : `prune` (images/volumes/conteneurs stoppés) respecte la **sémantique protégée** : les éléments `windflow-plugin-*` sont **épargnés** ; un volume monté par un container **arrêté** n'est **pas** éligible ; la suppression est unitaire — un échec n'interrompt pas la file ; le **rapport** liste supprimés / épargnés / échecs sans valeur fabriquée (tailles volumes absentes du rapport).
- [x] AC 3 : `prune` est **protégé** : réservé superadmin (403 pour admin/operator/viewer), **confirmation explicite** requise (sans `confirm=true` → 400/422 avec message), **dry-run** disponible (aucune suppression, rapport prévisionnel), exécution réelle **auditée** (STORY-125) ; tests 401/403/400.
- [x] AC 4 : Le **rapprochement `/compute` ↔ `/docker` est documenté** (table de correspondance des endpoints, décision de convergence sans suppression d'endpoint Docker) ; la spec 09 (incorporation F3) est mise à jour sur ces surfaces — livré dans les corrections de specs (coordination P3-4 si non fusionné).
- [x] AC 5 : Tests complémentaires sur compute (contribution P2-14 : couverture de la zone `compute` ≥ 80 % avec les nouveaux endpoints) ; non-régression des 40 endpoints Docker et de `/compute/stats|global` ; build + lint + tests passent.

## Références spécification

- [`09-api.md`](../../docs/general_specs/09-api.md) — **§ Volumes — `/api/v1/compute/volumes/`** (endpoints browse/upload/download, **§ Prune des volumes — sémantique protégée** complète), **§ Images** (prune dangling, liste protégée, espace réellement libéré), § Vue Compute (surface `/compute/*` Mode Infra) ;
- [`03-modele-compute.md`](../../docs/general_specs/03-modele-compute.md) — § Vue Compute (Mode Infra — onglets, filtres), § Actions par type d'objet (Volume Browser ✓ containers) ;
- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Plugin Trivy (volumes `windflow-plugin-trivy-*` protégés du prune — justification de la liste protégée) ;
- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — § Prunes planifiés (actions `compute.images.prune`/`compute.volumes.prune` — la sémantique protégée est spécifiée ch. 09 et servira STORY-160) ;
- [`08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — (renvoi) matrice : opérations destructrices globales = Super Admin ;
- `.roo/rules/35-testing-quality-gates.md` — cas obligatoires par verbe (dont DELETE : 401/403/404) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-11 (+ P2-14 pour les tests), §2.D D1, §2.A A16/F3, §5 chaîne critique n°1 et n°4 (RBAC + enveloppes/pagination avant élargissement) ;
- [`backend_status.md`](../../docs/backend_status.md) — §3.7-3.8 (compute/docker), §5 (compute_service, classifier, builder), §13.4 (compute API partiel).

## Dépendances

- **STORY-121/122** (RBAC — dépendance explicite du plan) et **STORY-126/128** (enveloppes + pagination — le plan exige P1-5/6 avant l'élargissement) ; idéalement après **STORY-166** (entité Host pour les filtres par Host).
- Interagit avec **STORY-160** (action `compute.docker.prune` du registre scheduler) et **STORY-125** (audit du prune) ; ses tests complémentaires contribuent à l'objectif P2-14 (couverture des zones zéro, coordination avec STORY-165 pour websocket et avec les zones organizations/users/discovery/import_export/stats à couvrir au fil des vagues).

**Constats post-exploration (statuts réels au 2026-10-31)** :

- Pré-requis P1 **tous livrés** : STORY-121/122 (RBAC — `require_role`/matrice vérifiés dans le code), STORY-126/128 (enveloppes + `PaginationQuery`/`paginate_sequence` actifs sur docker.py). **Non bloquante.**
- **STORY-166** livré côté backend (modèle `Host` consommé par `compute_service._resolve_local_host`, seed du host local 166.5) — les filtres par Host fonctionnent via `target_id` ; les volets frontend/CLI (166.6) non bloquants pour l'API.
- **STORY-160.1/160.2/160.3 DONE** : le socle prune protégé (`PruneResult`, `prune_images`/`prune_volumes`, action scheduler + audit) **existe déjà**. L'« arbitrage d'entrée » de 160.3 (« wrappers locaux si 173 non fusionnée ») est **tranché : les wrappers locaux deviennent le socle commun** — l'endpoint `/compute/prune` consomme exactement les mêmes wrappers que le scheduler (une seule implémentation de la sémantique, D5).
- **STORY-125 DONE** : `AuditService.log` disponible pour l'audit avec acteur utilisateur.
- **STORY-164.2** : le canal `/ws/batch` « émetteur-ready » attendait check-updates — **hors périmètre confirmé** (renvoi D1 de la story) : le prune est synchrone (réponse = rapport), aucune émission batch dans cette story.
- ⚠️ **Incohérence backlog détectée** : [`STORY-252`](STORY-252-corrections-consolidees-specifications.md) (§ Dépendances, l.63) liste déjà « STORY-173 (compute — F3) » parmi les vagues « P0-P2 terminées » alors que la story est TODO — à corriger lors de la revue de 252 (aucune action ici, statut 173 inchangé).
- **Services externes** : Docker Engine local via socket (systématiquement mocké dans les tests unitaires — pattern `DockerClientService` AsyncMock de [`test_compute_service.py`](../../backend/tests/unit/test_services/test_compute_service.py)) ; image `busybox:1.37` requise au browse (pull au premier appel — documenté). **Aucune migration DB**, **aucune dépendance Poetry nouvelle**.

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

*(à cocher pendant `treat-story` — analyse terminée le 2026-10-31, verdict : complexité OK, pas de découpe — périmètre homogène backend « compute », réutilisation massive du socle STORY-160.3)*

- [x] T1. Schémas compute étendus (item browse, volumes, prune request/response)
- [x] T2. Socle prune étendu : tolérance échecs + noms dans `PruneResult` + `prune_stopped_containers` + `DockerPruneParams.resource` étendu
- [x] T3. Service `get_compute_browse` (aplatissement paginé/filtrable)
- [x] T4. Service `volume_browser` (conteneur éphémère sécurisé, listing paginé)
- [x] T5. Endpoints lecture : `GET /browse`, `GET /volumes`, `GET /volumes/{name}`, `GET /volumes/{name}/browse`
- [x] T6. Endpoint `POST /prune` (superadmin + confirm + dry-run + audit)
- [x] T7. Garde-fous : compteur routes compute 2→7 + OpenAPI tags/examples
- [x] T8. Rapprochement `/compute`↔`/docker` documenté (COMPUTE-DOCKER-MAPPING.md + renvoi spec 09)
- [x] T9. Tests écrits et passants (unitaires, sécurité, intégration, couverture ≥ 80 % zone compute)
- [x] T10. Vérifications finales (lint/mypy/bandit, non-régression docker 35 + scheduler, OpenAPI)
- [x] T11. Clôture story (REVIEW→DONE, kanban, epic, notes d'implémentation)

## Tâches d'implémentation détaillées

> Analyse du 2026-10-31 — verdict complexité : **OK** (11 tâches, un seul domaine backend « compute », socle prune déjà posé par STORY-160.3 ; pas de SPLIT-STORY). Décisions D1→D9 dans « Contexte technique ».

**Tâche 1 — Schémas Pydantic compute (D1, D2, D4).**
- **Fichier** : [`backend/app/schemas/compute.py`](../../backend/app/schemas/compute.py) — **Modifier**
- **Objectif** : ajouter (tous avec descriptions + examples OpenAPI, pattern des schémas existants du fichier) :
  - `ComputeBrowseItem` — item aplati : `id`, `name`, `kind: Literal["managed_service", "discovered", "standalone"]`, `status`, `target_id`, `target_name`, `image`, `technology: Optional[str]`, `stack_id: Optional[str]` ;
  - `ComputeVolumeResponse` — miroir de [`VolumeResponse`](../../backend/app/schemas/docker.py) docker (name/driver/mountpoint/created_at/labels/scope) ;
  - `VolumeBrowseEntry` — `name`, `is_dir: bool`, `path` ; `VolumeBrowseResponse` non nécessaire (liste enveloppée paginée) ;
  - `ComputePruneRequest` — `resource: Literal["images", "volumes", "containers"]`, `dry_run: bool = False`, `confirm: bool = False`, `force: bool = False`, **`model_config = ConfigDict(extra="forbid")`** ;
  - `PruneItemFailure` — `name`, `error` ; `ComputePruneResponse` — `resource`, `dry_run`, `pruned: list[str]`, `spared: list[str]`, `failed: list[PruneItemFailure]`, `pruned_count`, `spared_count`, `failed_count`, `space_reclaimed_bytes` (docstring : 0 pour les volumes — taille non exposée par l'API Docker, **aucune valeur fabriquée**).
- **Dépend de :** Aucune

**Tâche 2 — Socle prune étendu (D5, D6).**
- **Fichiers** :
  - [`backend/app/services/docker_client_service.py`](../../backend/app/services/docker_client_service.py) — **Modifier**
  - [`backend/app/schemas/actions.py`](../../backend/app/schemas/actions.py) — **Modifier** (`DockerPruneParams.resource` → `Literal["images", "volumes", "containers"]`)
  - [`backend/app/services/scheduler_actions.py`](../../backend/app/services/scheduler_actions.py) — **Modifier** (dispatch `containers` dans `compute_docker_prune` + `failed_count` dans `_audit_prune` details et le dict retourné)
- **Objectif** : (a) `PruneResult` : ajouter `pruned_names: list[str] = field(default_factory=list)`, `spared_names`, `failed_names`, `failed_count: int = 0` (compat ascendante — champs à défauts, tests 160.3 verts) ; (b) `prune_images`/`prune_volumes` : boucles de suppression avec `try/except` **par item** — erreur (aiohttp `ClientResponseError` 409/500 ou autre) → `failed_names.append(...)` et **continue** (AC 2) ; collecter `pruned_names`/`spared_names` ; (c) **créer** `prune_stopped_containers(*, dry_run=True, force=False)` : candidates = `list_containers(all=True)` avec `state != "running"` **et sans label `windflow.managed=true`** **et non protégées** (`windflow-plugin-*` — nom ou label `com.docker.compose.project`), suppression unitaire `remove_container(force=force)` (jamais `remove_volumes=True`), même contrat `PruneResult` (`space_reclaimed_bytes=0`) ; (d) docstrings : sémantique protégée spec 09 §Prune (référence croisée STORY-173).
- **Dépend de :** Tâche 1 (aucune — peut aller en parallèle, le dataclass est autonome)

**Tâche 3 — Service `get_compute_browse` (D1).**
- **Fichier** : [`backend/app/services/compute_service.py`](../../backend/app/services/compute_service.py) — **Modifier**
- **Objectif** : nouvelle fonction `get_compute_browse(db, org_ids, *, type_filter, target_id_filter, status_filter, search, page, per_page) -> PaginatedResponse` : réutiliser le chemin de `get_compute_global` (stacks DB + classification + builders — factoriser si dupliqué, sinon appeler et aplatir) pour produire une `list[ComputeBrowseItem]` uniforme (services des stacks managées → `kind=managed_service`, items découverts → `discovered`, standalone → `standalone`), appliquer les **mêmes filtres** (`apply_filters` puis aplatissement, ou filtrage post-aplatissement — le plus simple sans duplication), retourner via `paginate_sequence(items, page, per_page)` (source non-SQL, slicing mémoire — pattern docker.py). Graceful degradation Docker inchangé.
- **Dépend de :** Tâche 1

**Tâche 4 — Service `volume_browser` sécurisé (D2, D3).**
- **Fichier** : `backend/app/services/volume_browser_service.py` — **Créer**
- **Objectif** : module dédié (sécurité isolée, testable) : `async def browse_volume(name: str, subpath: Optional[str], page: int, per_page: int) -> PaginatedResponse`. Étapes : validation regex nom (`^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$` → `UnprocessableEntityError` 422) et subpath anti-traversal (rejet `..`/absolu → 422) ; vérifier l'existence (`list_volumes` → `NotFoundError` 404) ; créer le conteneur éphémère `windflow-browse-{uuid4().hex[:8]}` via `create_container(image="busybox:1.37", mounts=[{type volume, source name, destination /vol, mode ro}], network_mode="none", labels={"windflow.transient": "true"})` ; `exec_in_container` avec `["ls", "-1p", f"/vol/{subpath}"]` (**args liste, aucun shell**) ; parser la sortie (suffixe `/` = dossier) en `VolumeBrowseEntry` ; `paginate_sequence` ; **`finally: remove_container(force=True)`** garanti même sur erreur exec ; Docker indisponible → `WindFlowException` explicite (pas de 200 vide). Constantes épinglées en tête de module (`BROWSE_IMAGE = "busybox:1.37"` — jamais `:latest`), docstring sécurité complète (D3).
- **Dépend de :** Tâche 1

**Tâche 5 — Endpoints lecture `/compute` (D1, D2).**
- **Fichier** : [`backend/app/api/v1/compute.py`](../../backend/app/api/v1/compute.py) — **Modifier**
- **Objectif** : 4 routes `require_viewer` + org check (copier le bloc `organization_id` de `get_compute_stats` l.62-73) + `conditional_rate_limiter(100, 60)` :
  - `GET /browse` — `summary`/`description` riches (exemples), filtres `type` (pattern `^(managed_service|discovered|standalone)$`… ou valeurs existantes `managed|discovered|standalone` alignées sur `/global`), `target_id`, `status`, `search`, `PaginationQuery` ; appelle `compute_service.get_compute_browse` ; retour `PaginatedResponse` ;
  - `GET /volumes` — miroir de [`docker.py list_volumes`](../../backend/app/api/v1/docker.py) (l.1947-2001) : `client.list_volumes()` → `ComputeVolumeResponse.model_dump()` → `paginate_sequence` ; `finally: client.close()` ;
  - `GET /volumes/{volume_name}` — détail : `NotFoundError` si absent (comparaison de liste), `VolumeInfo` → `ComputeVolumeResponse` ;
  - `GET /volumes/{volume_name}/browse` — `subpath: Optional[str] = Query(None)`, `PaginationQuery` ; délègue à `volume_browser_service.browse_volume` ; 404/422 gérés par les exceptions métier (error handler central).
  - Docstrings « Access Control » (STORY-122) + exemples JSON d'enveloppe (`data` + `pagination{}`) sur chaque route — cohérent stats/global.
- **Dépend de :** Tâches 3, 4

**Tâche 6 — Endpoint `POST /compute/prune` protégé (D4, D7).**
- **Fichier** : [`backend/app/api/v1/compute.py`](../../backend/app/api/v1/compute.py) — **Modifier**
- **Objectif** : route `POST /prune` — `current_user: User = Depends(require_superuser)`, `dependencies=[Depends(conditional_rate_limiter(10, 60))]`, body `ComputePruneRequest`. Logique : si `not confirm and not dry_run` → `InvalidInputError` 400 (« confirmation explicite requise : confirm=true » — AC 3) ; sinon `DockerClientService()` → dispatch `resource` vers `prune_images`/`prune_volumes`/`prune_stopped_containers` (`dry_run=dry_run, force=force`) dans `try/finally close` ; mapper `PruneResult` → `ComputePruneResponse` ; **si exécution réelle** (`not dry_run`) : `await AuditService.log("compute.prune", user_id=current_user.id, resource_type="docker", resource_id=resource, details={"dry_run": False, "pruned_count": …, "spared_count": …, "failed_count": …, "space_reclaimed_bytes": …, "protected_prefix": "windflow-plugin-*"}, ip_address=…, correlation_id=request.state.correlation_id)` — **jamais les noms complets ni `force` dans les logs** (les noms vont dans la réponse API uniquement) ; log INFO avec comptages + correlation_id. `request: Request` en paramètre pour l'IP/correlation.
- **Dépend de :** Tâches 1, 2

**Tâche 7 — Garde-fous routes & OpenAPI (D9).**
- **Fichiers** : [`backend/tests/unit/test_api/test_rbac_exhaustivite.py`](../../backend/tests/unit/test_api/test_rbac_exhaustivite.py) — **Modifier** (`"compute": 2` → `"compute": 7` + commentaire `# STORY-173 : +5 routes (browse, volumes×3, prune)` ; `"docker": 35` **inchangé**) ; [`backend/app/main.py`](../../backend/app/main.py) — **Modifier** si le tag `compute` de `openapi_tags` mérite une description étendue (surface complète).
- **Objectif** : le garde-fou §2.G reflète l'élargissement explicite ; vérifier `make generate-openapi-docs` : les 5 nouvelles routes documentées (summary/description/examples), `confirm`/`dry_run` visibles, erreurs 400/401/403/404/422 décrites.
- **Dépend de :** Tâches 5, 6

**Tâche 8 — Rapprochement `/compute` ↔ `/docker` documenté (D8, AC 4).**
- **Fichiers** : `docs/technical_specs/COMPUTE-DOCKER-MAPPING.md` — **Créer** ; [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — **Modifier** (renvoi depuis la section compute vers la table)
- **Objectif** : table de correspondance exhaustive route à route : `/docker/volumes` GET/POST/DELETE ↔ `/compute/volumes` (+browse/prune), `/docker/images` ↔ `/compute/images` (prune), `/docker/containers` ↔ `/compute/containers`… avec pour chaque paire : statut (les deux actifs / seul docker / seul compute), **côté canonique cible = `/compute`** (spec 09), période de convergence, et la **décision explicite : aucune suppression d'endpoint Docker** (garde-fou §2.G — dépréciation future arbitrée hors story, modèle du double nommage targets→hosts STORY-166 cité en précédent). Différés notés : upload/download/PUT browse, check-updates, `/compute/graph` (Roadmap Phase 5). Renvoi depuis spec 09 + note que la consolidation F3 reste coordonnée avec STORY-252/P3-4.
- **Dépend de :** Tâches 5, 6 (la table documente l'état final)

**Tâche 9 — Tests (AC 1-5, règle 35 + checklist sécurité règle 40).**
- **Fichiers** : `backend/tests/unit/test_api/test_compute_browse_api.py` — **Créer** ; `backend/tests/unit/test_api/test_compute_prune_api.py` — **Créer** ; `backend/tests/unit/test_services/test_compute_browse_service.py` — **Créer** ; `backend/tests/unit/test_services/test_volume_browser_service.py` — **Créer** ; [`backend/tests/unit/test_services/test_scheduler_actions.py`](../../backend/tests/unit/test_services/test_scheduler_actions.py) — **Modifier** (extension containers + non-régression) ; [`backend/tests/integration/test_api_contract.py`](../../backend/tests/integration/test_api_contract.py) — **Modifier** (classe compute : contrats enveloppe des nouvelles routes)
- **Objectif** : couvrir le détail de « Tests à écrire » ci-dessous — cas obligatoires par verbe (GET liste/détail, POST destructeur) + tests sécurité obligatoires (401/403 RBAC/400 confirmation/422 validation/404) + sémantique protégée unitaire (épargne `windflow-plugin-*`, volume monté par container arrêté non éligible, échec isolé passé, suppression unitaire) + couverture ≥ 80 % sur la zone compute (`--cov=app.api.v1.compute --cov=app.services.compute_service --cov=app.services.volume_browser_service`).
- **Dépend de :** Tâches 5, 6

**Tâche 10 — Vérifications finales.**
- **Fichiers** : aucun nouveau (exécution)
- **Objectif** : `make backend-lint` (black/isort/flake8/mypy/bandit — 0 nouvelle erreur), `make backend-test-unit` complet (non-régression : suite compute existante, `test_rbac_exhaustivite`, `test_scheduler_actions`, `test_action_registry` verts), couverture zone compute ≥ 80 % (AC 5), `make generate-openapi-docs` (doc à jour). Vérifier manuellement qu'**aucun endpoint `/docker` ni `/compute/stats|global` n'a changé de comportement** (diff des routes + tests existants).
- **Dépend de :** Tâches 7, 8, 9

**Tâche 11 — Clôture story.**
- **Fichiers** : cette story + [`.backlog/kanban.md`](../kanban.md) + [`EPIC-013`](../epics/EPIC-013-remediation-p2-conformite-fonctionnelle.md)
- **Objectif** : cocher les AC (preuves : tests + mapping doc), statut `REVIEW` → validation → `DONE` ; kanban : BACKLOG → IN PROGRESS → REVIEW → DONE ; cocher STORY-173 dans l'epic ; section « Notes d'implémentation » (fichiers modifiés, décisions D1→D9 appliquées ou divergences, renvois : upload/download différés Phase 5, incohérence STORY-252 signalée, commandes exécutées + résultats).
- **Dépend de :** Tâche 10

## Tests à écrire

> Patterns [`35-testing-quality-gates.md`](../../.roo/rules/35-testing-quality-gates.md) : client `httpx.AsyncClient` + `ASGITransport` ; mocks `app.api.v1.compute.compute_service.*` / `volume_browser_service.*` (pattern [`test_compute_api.py`](../../backend/tests/unit/test_compute_api.py)) ; `DockerClientService` AsyncMock (pattern [`test_compute_service.py`](../../backend/tests/unit/test_services/test_compute_service.py)). Cas obligatoires par verbe (règle 35) + tests sécurité (règle 40) intégrés.

### Backend — unitaires (endpoints)

**Fichier `backend/tests/unit/test_api/test_compute_browse_api.py`** (AC 1) :
1. `test_browse_returns_empty_list` — 200, `data: []`, `pagination{page=1, total=0}` (service mocké → liste vide).
2. `test_browse_returns_items_with_filters` — mock → 3 items ; filtres `type`/`status`/`search`/`target_id` passés au service (assertion des kwargs) ; enveloppe `data` + `pagination{}` complète.
3. `test_browse_pagination_envelope` — `per_page=2, page=2` → slicing correct, `pages`/`total` exacts ; `per_page=101` → **422**.
4. `test_browse_returns_401_without_token` / `test_browse_viewer_200` — RBAC lecture viewer+ (401 sans token, 200 viewer).
5. `test_browse_returns_403_for_foreign_organization` — `organization_id` d'une org non membre → 403 (pattern stats l.172-178).
6. `test_browse_returns_422_on_invalid_type` — `type=unknown` → 422 (pattern `/global` l.250-252).
7. `test_volumes_list_paginated` / `test_volumes_list_401` — miroir docker : 200 + enveloppe pagination (client mocké), 401 sans token.
8. `test_volume_detail_404_when_missing` / `test_volume_detail_200` — NotFoundError → 404 ; présent → 200 schéma complet.
9. `test_volume_browse_200_entries` — service mocké → entrées fichier/dossier paginées.
10. `test_volume_browse_422_invalid_name` — `volume_name="../etc"` → 422 (anti-traversal/injection).
11. `test_volume_browse_422_invalid_subpath` — `subpath=../../host` → 422.
12. `test_volume_browse_404_unknown_volume` — service lève NotFoundError → 404.

**Fichier `backend/tests/unit/test_api/test_compute_prune_api.py`** (AC 2/AC 3 — sécurité lourde) :
13. `test_prune_returns_401_without_token` — **obligatoire règle 40**.
14. `test_prune_returns_403_for_admin_operator_viewer` — superadmin seul : admin **403**, operator **403**, viewer **403** (`require_superuser` — flag `is_superuser`).
15. `test_prune_returns_400_without_confirm` — `{resource: "volumes"}` sans `confirm`/`dry_run` → **400** avec message explicite (AC 3).
16. `test_prune_dry_run_returns_report_without_confirm` — `dry_run=true` sans confirm → 200 rapport prévisionnel, **aucun appel suppressif** (assertion sur le mock).
17. `test_prune_real_with_confirm_returns_report` — `confirm=true, dry_run=false` → 200, rapport supprimés/épargnés/échecs + compteurs.
18. `test_prune_real_audited` — `confirm=true` → `AuditService.log` appelé avec `action="compute.prune"`, `user_id` du superadmin, `dry_run: False` (mock `app.services.audit_service.AuditService.log`).
19. `test_prune_dry_run_not_audited` — dry-run → aucun appel d'audit.
20. `test_prune_returns_422_on_invalid_body` — `resource: "networks"` → 422 ; champ inconnu (`extra="forbid"`) → 422.
21. `test_prune_audit_details_contain_no_names_nor_force` — l'audit ne persiste que comptages/préfixe (assertion sur `details` — pas de noms de volumes complets, pas de `force`).
22. `test_prune_response_contains_no_fabricated_volume_sizes` — `resource="volumes"` → `space_reclaimed_bytes == 0` (AC 2, aucune valeur inventée).

### Backend — unitaires (services)

**Fichier `backend/tests/unit/test_services/test_compute_browse_service.py`** (AC 1) :
23. `test_browse_flattens_all_kinds` — inventaire managé + découvert + standalone → items aplatis avec `kind` correct.
24. `test_browse_applies_filters_type_status_search` — chaque filtre réduit la liste aplatie (réutilise `apply_filters`).
25. `test_browse_pagination_slicing` — slicing `paginate_sequence` exact (page au-delà → `data: []` + métadonnées).
26. `test_browse_graceful_degradation_docker_down` — Docker indisponible → stacks DB seules, pas d'exception.

**Fichier `backend/tests/unit/test_services/test_volume_browser_service.py`** (AC 1, sécurité D3) :
27. `test_browse_validates_volume_name_regex` — nom invalide → `UnprocessableEntityError` (422), **aucun conteneur créé** (mock jamais appelé).
28. `test_browse_rejects_traversal_subpath` — `../` et chemin absolu → 422.
29. `test_browse_unknown_volume_404` — `list_volumes` vide → `NotFoundError`.
30. `test_browse_uses_pinned_image_readonly_none_network` — assertions de configuration : `image="busybox:1.37"`, mount `mode="ro"` (ou `ReadOnly`), `network_mode="none"`, pas de `privileged`, label transitoire (sécurité — garde structurelle).
31. `test_browse_parses_ls_output_dirs_and_files` — sortie `ls -1p` (suffixe `/`) → `is_dir` correct + pagination.
32. `test_browse_cleans_up_container_on_exec_error` — exec lève → `remove_container` appelé quand même (`finally`), erreur propagée.
33. `test_browse_exec_uses_arg_list_no_shell` — assertion sur la commande passée à `exec_in_container` : liste `["ls", "-1p", …]`, aucun string shell.

**Extension [`test_scheduler_actions.py`](../../backend/tests/unit/test_services/test_scheduler_actions.py)** (D5/D6 — non-régression + extension) :
34. `test_prune_volumes_failure_isolated_and_reported` — `remove_volume` lève sur le 2ᵉ volume (mock) → 1ᵉʳ supprimé, 2ᵉ dans `failed_names`, 3ᵉ quand même traité (**la file continue** — AC 2), `failed_count` exact.
35. `test_prune_spared_protected_names_collected` — volumes `windflow-plugin-trivy-cache` etc. → `spared_names` renseignés, jamais candidats.
36. `test_prune_stopped_containers_candidates_semantics` — candidats = `state != running` sans `windflow.managed=true` ; un container **arrêté d'une stack managée n'est pas éligible** ; `windflow-plugin-*` épargné ; `remove_container(force=False)` unitaire.
37. `test_prune_volume_used_by_stopped_container_not_eligible` — volume monté par un container **arrêté** → pas candidat (sémantique spec 09 — `_volume_names_in_use` avec `all=True`).
38. `test_prune_result_backward_compatible` — `PruneResult(resource=…, dry_run=…, pruned_count=…, space_reclaimed_bytes=…, spared_count=…)` positional/kwargs existants toujours valides (consommateurs 160.3 intacts).
39. `test_scheduler_dispatch_containers` — `compute_docker_prune({"resource": "containers", "dry_run": False})` → `prune_stopped_containers` appelé + audit.

### Backend — intégration

**Extension [`backend/tests/integration/test_api_contract.py`](../../backend/tests/integration/test_api_contract.py)** (classe `TestComputeRouterContract`) :
40. `test_compute_browse_enveloped` — 200 → `data` liste + `pagination{}` + `message` (contrat STORY-126/128 bout-en-bout, service mocké).
41. `test_compute_volumes_enveloped` — idem sur `GET /compute/volumes`.
42. `test_compute_prune_dry_run_contract` — superadmin + `dry_run=true` → enveloppe data = rapport complet (contrat de réponse réel, client Docker mocké).

### Frontend

- **N/A** — story API-first : la vue Compute frontend consommera les nouveaux contrats via les services/types générés (`make generate-api`) ; aucun test frontend requis par cette story.

### Commandes de validation

```bash
# Tests ciblés pendant le développement
poetry run pytest backend/tests/unit/test_api/test_compute_browse_api.py backend/tests/unit/test_api/test_compute_prune_api.py -v
poetry run pytest backend/tests/unit/test_services/test_compute_browse_service.py backend/tests/unit/test_services/test_volume_browser_service.py -v
poetry run pytest backend/tests/unit/test_services/test_scheduler_actions.py backend/tests/unit/test_services/test_action_registry.py -v  # non-régression socle 160.3
poetry run pytest backend/tests/unit/test_compute_api.py backend/tests/unit/test_api/test_rbac_exhaustivite.py backend/tests/unit/test_api/test_misc_rbac.py -v  # non-régression zone compute

# Couverture zone compute (AC 5 — cible ≥ 80 %)
poetry run pytest backend/tests/unit/test_api/test_compute_browse_api.py backend/tests/unit/test_api/test_compute_prune_api.py backend/tests/unit/test_api/test_compute_api.py backend/tests/unit/test_services/test_compute_browse_service.py backend/tests/unit/test_services/test_volume_browser_service.py backend/tests/unit/test_services/test_compute_service.py --cov=app.api.v1.compute --cov=app.services.compute_service --cov=app.services.volume_browser_service --cov-fail-under=80

# Finales
make backend-lint && make backend-test-unit
make generate-openapi-docs
```

## Notes d'implémentation (treat-story — 2026-10-31)

### Fichiers modifiés / créés

**Backend (production)**
- [`backend/app/schemas/compute.py`](../../backend/app/schemas/compute.py) — **modifié** : +`ComputeBrowseItem`, `ComputeVolumeResponse`, `VolumeBrowseEntry`, `ComputePruneRequest` (`extra="forbid"`), `PruneItemFailure`, `ComputePruneResponse` (descriptions + examples OpenAPI).
- [`backend/app/services/docker_client_service.py`](../../backend/app/services/docker_client_service.py) — **modifié** : `PruneResult` étendu (`pruned_names`/`spared_names`/`failed_names`/`failed_count`, champs à défauts — compat ascendante D5) ; `prune_images`/`prune_volumes` tolérants aux échecs par item (file jamais interrompue, try/except unitaire + collecte des noms) ; **nouveau** `prune_stopped_containers` (candidats = `state != running` sans `windflow.managed=true`, plugins épargnés par nom/label compose, `remove_volumes=False` toujours, `force=False` défaut) ; helpers `_container_is_protected`.
- [`backend/app/schemas/actions.py`](../../backend/app/schemas/actions.py) — **modifié** : `DockerPruneParams.resource` → `Literal["images", "volumes", "containers"]`.
- [`backend/app/services/scheduler_actions.py`](../../backend/app/services/scheduler_actions.py) — **modifié** : dispatch `containers` dans `compute_docker_prune`, `failed_count` dans le dict retourné et les details d'audit.
- [`backend/app/services/compute_service.py`](../../backend/app/services/compute_service.py) — **modifié** : factorisation `_collect_inventory` (chemin commun global/browse, zéro duplication), `get_compute_global` refactorisé dessus (comportement inchangé), **nouveau** `get_compute_browse` (aplatissement `ComputeBrowseItem` + `paginate_sequence`).
- [`backend/app/services/volume_browser_service.py`](../../backend/app/services/volume_browser_service.py) — **créé** : browse par conteneur éphémère durci (`busybox:1.37` épinglée, mount `ro`, `network_mode="none"`, `readonly_rootfs`, label `windflow.transient`, exec args-liste `ls -1p`, anti-traversal, `finally remove_container(force=True)`, Docker down → `ServiceUnavailableError`).
- [`backend/app/api/v1/compute.py`](../../backend/app/api/v1/compute.py) — **modifié** : +5 routes (`GET /browse`, `GET /volumes`, `GET /volumes/{name}`, `GET /volumes/{name}/browse`, `POST /prune`), helper `_resolve_org_scope` (pattern 121.3 factorisé), rate limiting (100/60 lectures, 10/60 prune), docstrings Access Control + responses 400/401/403/404/422/503.
- [`backend/app/main.py`](../../backend/app/main.py) — **modifié** : tag OpenAPI `compute` avec description de la surface complète.

**Tests**
- [`backend/tests/unit/test_api/test_compute_browse_api.py`](../../backend/tests/unit/test_api/test_compute_browse_api.py) — **créé** (17 tests : AC 1, 401/403/422/404, enveloppe pagination, anti-traversal).
- [`backend/tests/unit/test_api/test_compute_prune_api.py`](../../backend/tests/unit/test_api/test_compute_prune_api.py) — **créé** (12 tests : AC 2/3, RBAC 401/403×3 rôles, 400 confirmation, dry-run sans suppression, audit + absence noms/force, 422 `extra="forbid"`, `space_reclaimed_bytes=0`).
- [`backend/tests/unit/test_services/test_compute_browse_service.py`](../../backend/tests/unit/test_services/test_compute_browse_service.py) — **créé** (4 tests : aplatissement 3 kinds, filtres, slicing, graceful degradation).
- [`backend/tests/unit/test_services/test_volume_browser_service.py`](../../backend/tests/unit/test_services/test_volume_browser_service.py) — **créé** (10 tests : garde structurelle D3 — image épinglée/mount ro/network none/args-liste/anti-traversal/nettoyage finally).
- [`backend/tests/unit/test_services/test_scheduler_actions.py`](../../backend/tests/unit/test_services/test_scheduler_actions.py) — **étendu** : `_FakePruneClient` porte les champs étendus + `prune_stopped_containers` ; +6 tests sémantique (échec isolé, noms épargnés, candidats containers, volume monté par container arrêté, compat ascendante `PruneResult`, dispatch scheduler).
- [`backend/tests/integration/test_api_contract.py`](../../backend/tests/integration/test_api_contract.py) — **étendu** : +3 contrats enveloppe (browse paginé, volumes, prune dry-run superadmin).

**Documentation**
- [`docs/technical_specs/COMPUTE-DOCKER-MAPPING.md`](../../docs/technical_specs/COMPUTE-DOCKER-MAPPING.md) — **créé** (D8 : table de correspondance exhaustive, décision « aucune suppression d'endpoint Docker », période de convergence, différés Phase 5).
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — **modifié** : renvoi depuis § Volumes vers la table (note coordination STORY-252/P3-4).

### Décisions techniques (D1→D9)

Toutes appliquées conformes à l'analyse. Points notables :
- **D1** : `browse` = sur-fonction de l'inventaire existant (`_collect_inventory` factorisé — aucun appel Docker nouveau, `apply_filters` réutilisé tel quel).
- **D3** : `readonly_rootfs=True` ajouté au-delà du montage volume `ro` (défense en profondeur). Le statut des items discovered est dérivé (`running`/`partial`/`stopped`) de `services_running`/`services_total`.
- **D5** : compat ascendante vérifiée par `test_prune_result_backward_compatible` + tests 160.3 verts sans modification de leurs assertions d'origine.
- **D6** : une stack WindFlow arrêtée (label `windflow.managed=true`) n'est jamais candidate au prune containers — décision propre tracée en docstring.
- **D7** : `require_superuser` (flag) — 403 vérifié pour admin d'org, operator, viewer.
- Choix complémentaire : une stack managée **sans container actif** produit un item au niveau stack dans `browse` (statut `stopped`) pour rester visible — documenté dans le service.

### Divergences par rapport à l'analyse

Aucune divergence fonctionnelle. Trois ajustements mineurs :
1. **Échec mypy préexistant** (`docker_client_service.py:752`, zone `create_container`) — prouvé identique sur HEAD par stash, non corrigé (hors périmètre).
2. **Échec test préexistant** : `test_rbac_exhaustivite::test_every_api_route_is_protected` échoue sur **`/api/v1/metrics`** (résidu STORY-172 — la route sonde sans auth n'est pas dans `PUBLIC_PATHS`) — prouvé sur HEAD par stash, hors périmètre 173 (à corriger dans la reprise STORY-172/253). Aucune des 5 nouvelles routes compute n'est fautive.
3. **Test 10 (browse 422 nom invalide)** : la story suggérait `volume_name="../etc"` — un path segment `../` ne route pas vers l'endpoint (404 routing) ; le test utilise un nom avec espace (`bad%20name`) qui atteint bien la validation regex → 422. L'anti-traversal `..` reste couvert par le test subpath (n°11) et les tests service.

### Difficultés rencontrées

- Verrouillages d'éditeur PyCharm intermittents sur `apply_diff` (kanban, scheduler tests, docker_client_service) — contournés par scripts python idempotents.
- `--cov-fail-under=80` du pyproject s'applique au `--cov=app` global (37% toute app) — la couverture **zone compute** a été mesurée module par module (voir ci-dessous), conforme à l'AC 5.
- `AsyncMock(return_value=AsyncMock()...)` piège d'await double — contourné par `SimpleNamespace` pour les `ExecResult` fakes.

### Commandes exécutées et résultats

| Commande | Résultat |
|---|---|
| `pytest tests/unit/test_api/test_compute_browse_api.py tests/unit/test_api/test_compute_prune_api.py tests/unit/test_services/test_compute_browse_service.py tests/unit/test_services/test_volume_browser_service.py` | **40 passed** |
| `pytest tests/unit/test_services/test_scheduler_actions.py tests/unit/test_services/test_action_registry.py` (non-régression socle 160.3) | **37 passed** |
| `pytest tests/unit/test_compute_api.py tests/unit/test_api/test_rbac_exhaustivite.py tests/unit/test_api/test_misc_rbac.py` (non-régression zone compute) | verts hors échec `/metrics` préexistant |
| `pytest tests/unit/test_api/test_compute_browse_api.py test_compute_prune_api.py test_compute_api.py test_compute_browse_service.py test_volume_browser_service.py test_compute_service.py --cov` | **105 passed** ; couverture zone compute : **compute.py 91 % / compute_service.py 95 % / volume_browser_service.py 96 %** (≥ 80 % — AC 5) |
| `pytest tests/unit` (non-régression large) | **3143 passed, 1 failed** (`/api/v1/metrics` préexistant, prouvé HEAD) |
| `pytest tests/integration/test_api_contract.py` | passed (contrats enveloppe browse/volumes/prune) |
| `flake8` (14 fichiers modifiés/créés) | **0 erreur** |
| `black --check` + `isort --check` | **OK** (formatage appliqué) |
| `mypy` (7 fichiers production) | **0 nouvelle erreur** (1 préexistante prouvée HEAD) |
| `bandit -r volume_browser_service.py api/v1/compute.py` | **0 alerte** |
| OpenAPI généré | 7 routes `/compute` documentées, prune avec 400/401/403/422 + `ComputePruneRequest` |
