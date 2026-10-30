# STORY-166 : [ABANDONED] Migration `Target` → `Host` + axe `origin` — renommage modèle/API sur toutes les couches, profils à 3 valeurs, `environments` activés, `Stack.git_url` et auto-détection du host local (P2-4 + P2-10 — arbitrage F4 étape 2)

**Statut :** ABANDONED
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-4 (axes F4 étape 2, A14, C13, D2) + P2-10 (axe C8) — ampleur **XL** ⚠️ chaîne critique Alembic(120) → RBAC(121/122) → Host

> **Note de clôture — découpe `split-story` (2026-10-24, mode proactif)** : cette story a été **découpée à l'issue de la phase d'analyse** (`analyse-story`), qui a conclu à une **complexité excessive** (ampleur XL confirmée : **6 domaines hétérogènes**, ~45 fichiers touchés, 40+ tâches estimées, migration de données destructive multi-tables avec credentials chiffrés, mapping d'enums ambigu — verdict §Sous-stories ci-dessous). Conformément au pipeline (règles 01 §5.1, étape 2b), elle est refermée `ABANDONED` selon le pattern STORY-160/164/131 (Règle d'Or : fichier conservé pour l'historique) et **remplacée sans perte d'information** par 6 sous-stories autonomes :
>
> - [STORY-166.1](STORY-166.1-modele-host-enums-migration-alembic.md) — Modèle `Host`, enums canoniques (`HostProfile`/`HostStatus`/`WorkloadOrigin`), **arbitrage mappings TargetType/TargetStatus**, migration Alembic `targets`→`hosts` sans perte (3 FK réelles) + alias de transition (couvre l'AC 1 reformulé)
> - [STORY-166.2](STORY-166.2-api-hosts-alias-targets-evenements.md) — Surface API `/api/v1/hosts/*` spec 09 + alias `/targets` avec header `Deprecation` + émission réelle `host.*` (couvre l'AC 2 et la partie événements de l'AC 5)
> - [STORY-166.3](STORY-166.3-services-host-scanners-ws.md) — Renommage services/scanners/parsers/access_profile + WS + consommateurs, non-régression payloads (~20 parseurs, garde-fou §2.G) (couvre la partie scan de l'AC 3 et la partie non-régression de l'AC 5)
> - [STORY-166.4](STORY-166.4-origin-environments-git-url.md) — Pose métier axe `origin` (`hosts`+`stacks`, adoption → `adopted`), table `environments`, `stacks.environment_id`/`hosts.environment_id`, `Stack.git_url` (couvre la partie origin de l'AC 3 et la partie environments/git_url de l'AC 4)
> - [STORY-166.5](STORY-166.5-auto-detection-host-local-seed.md) — Auto-détection du host local : setting désactivable + alignement du seed existant (divergence n°5) (couvre la partie auto-détection de l'AC 4)
> - [STORY-166.6](STORY-166.6-frontend-cli-synchronisation-hosts.md) — Synchronisation frontend (`hostsApi`/store/vues/navigation) + CLI + purge des références `target` résiduelles (couvre la partie frontend/CLI de l'AC 5)
>
> Le contexte technique, les 6 divergences, les dépendances vérifiées et les jalons de tests documentés ci-dessous ont été **intégralement répartis** dans ces sous-stories — **se reporter à elles pour le détail d'implémentation** (tâches ordonnées via `analyse-story` puis exécution `treat-story`). Ordre recommandé : **166.1 → 166.2/166.3 (ordre libre) → 166.4 → 166.5 → 166.6 en dernier** (purge).

## Description

En tant qu'administrateur WindFlow, je veux que l'entité `Target` devienne `Host` (modèle, API `/targets` → `/hosts`, enums, services, WebSocket, événements du bus) avec les **profils canoniques à 3 valeurs** (`host_baremetal`, `host_proxmox`, `host_remote_docker`), une colonne `origin` (`managed`/`adopted`/`external`) sur les entités pilotées, les `environments` activés (rattachement des stacks), `Stack.git_url` et l'auto-détection du host local au premier démarrage — le tout avec migration de données sans perte et alias/rétrocompatibilité API pendant la transition — afin d'aligner le code sur le modèle directeur des specs sans casser les installations existantes.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6.2, §10.3, [VIRTUALIZATION-SYSTEMS.md §6](../../docs/technical_specs/VIRTUALIZATION-SYSTEMS.md)) : le code porte `Target` (type `local|ssh|proxmox`... en réalité 6 valeurs `TargetType`), des routes `/api/v1/targets` (4 sous-modules), des services/scanners nommés `target_*` ; la spec 06 impose `hosts` (profils 3 valeurs), l'axe `origin`, `environments` (la table n'existe pas — A14), `Stack.git_url` (D2) ; l'auto-détection du host local (C8/P2-10) est absente du seed.

⚠️ **Hors périmètre explicite (arbitrage F4, à noter dans l'implémentation)** : les entités `Apps`, `Machines`, `Clusters`, le triple XOR et les verbes universels restent **hors périmètre** (Roadmap Phase 2 — « créer ces tables sans adapter de pilotage produirait des coquilles vides non testables ») ; seule l'interface `WorkloadAdapter` est posée (STORY-174). L'API `environments` reste minimale (table + rattachement stacks — le CRUD multi-env complet est hors périmètre, plan §6).

## Contexte technique

> **Analyse réalisée (analyse-story, 2026-10-24) — verdict : découpe recommandée via `split-story` (mode proactif).** L'exploration constate un périmètre de **~35 fichiers backend + ~10 frontend/CLI** réparti sur 6 domaines hétérogènes, une migration de données destructive multi-tables et un mapping d'enums ambigu. Les sections « Tâches d'implémentation détaillées » et « Tests à écrire » ne sont donc **pas remplies au niveau de cette story** — elles le seront dans les sous-stories créées par `split-story` (proposition en § Sous-stories). Le statut reste `TODO`.

### Inventaire du code réel (exploration)

**Modèles & enums**
- [`models/target.py`](../../backend/app/models/target.py) : `Target` (table `targets`) — credentials chiffrés STORY-103.2 (token Fernet opaque `{"_encrypted": ...}`, double lecture + ré-encryptage au premier accès via `decrypted_credentials`), `ssh_key_id` FK SET NULL (STORY-131.1), propriétés dérivées (`auth_method`, `username`, `has_sudo`), relations vers `Deployment`, `TargetCapability`, `SSHKey`, `HostSSHFingerprint` ;
- [`enums/target.py:10`](../../backend/app/enums/target.py:10) : `TargetType` **6 valeurs** (`docker`, `docker_compose`, `docker_swarm`, `kubernetes`, `vm`, `physical`), `TargetStatus` 4 valeurs (`online`/`offline`/`error`/`maintenance`), `SSHAuthMethod`, `AccessLevel`, `CapabilityType` (~30 valeurs) ;
- [`models/target_capability.py`](../../backend/app/models/target_capability.py) : `UNIQUE(target_id, capability_type)` ;
- [`models/host_ssh_fingerprint.py`](../../backend/app/models/host_ssh_fingerprint.py) : `host_ssh_fingerprints.host_id` référence **déjà** `targets.id` (double nommage F3, STORY-131.1) — FK à retargeter ;
- **Aucune table `environments`** en base (aucun modèle Environment) — à créer entièrement ici (STORY-121 ne l'a pas posée, vérifié).

**FK réelles à migrer (⚠️ divergence avec la description — voir ci-dessous)**
- [`models/deployment.py:165`](../../backend/app/models/deployment.py:165) : `deployments.target_id` → FK `targets.id` (CASCADE) — c'est la seule FK « cible » d'une entité pilotée ;
- [`models/stack.py`](../../backend/app/models/stack.py) : **pas de colonne `target_id`/`host_id`** — le rattachement stack→host passe par `deployments` ;
- [`models/target_capability.py`](../../backend/app/models/target_capability.py) : `target_capabilities.target_id` — troisième FK à retargeter.

**Surface API**
- [`api/v1/targets/`](../../backend/app/api/v1/targets) : 7 fichiers — `crud.py` (934 lignes), `capabilities.py`, `connectivity.py`, `fingerprints.py`, `scanning.py`, `helpers.py`, agrégés dans `__init__.py` ; montage dans [`api/v1/__init__.py:38`](../../backend/app/api/v1/__init__.py:38) (`prefix="/targets"`) ;
- RBAC **déjà systématique** : `require_viewer` (lecture), `require_operator` (connectivité), `require_admin` (gestion/scan/fingerprints) depuis [`auth/rbac.py`](../../backend/app/auth/rbac.py) — pattern à conserver sur `/hosts` (la story mentionne `require_role` : le pattern code réel est `require_*` par rôle) ;
- Enveloppes/pagination STORY-128 déjà en place (`PaginatedResponse` + `build_meta`), rate limiting `conditional_rate_limiter` sur tous les endpoints, isolation organisationnelle via `_get_target_for_org` ;
- Événement `target.deleted` émis dans [`crud.py:910`](../../backend/app/api/v1/targets/crud.py:910) — point d'émission à basculer vers `host.removed`.

**Schémas** : [`schemas/target.py`](../../backend/app/schemas/target.py) (`TargetCreate/TargetResponse/TargetUpdate`, **`HostReachabilityRequest/Response` déjà préfixés « Host »** — renommage partiellement amorcé), `target_capability.py`, `target_scan.py`.

**Services** : [`target_service.py`](../../backend/app/services/target_service.py), [`target_scanner_service.py:75`](../../backend/app/services/target_scanner_service.py:75) (`scan_localhost`/`scan_remote`/`scan_and_update_target`), [`target_scan_parsers.py`](../../backend/app/services/target_scan_parsers.py) (~20 parseurs + `build_capabilities_payload`), [`target_access_profile.py`](../../backend/app/services/target_access_profile.py) ; consommateurs : `deployment_service`, `deployment_orchestrator`, `compute_service`, [`container_classifier.py:26`](../../backend/app/services/container_classifier.py:26) (`LOCAL_TARGET_ID = "local"` placeholder, pas une ligne en base), `adoption_service`, `terminal_service`, `ssh_connection`.

**WebSocket** : [`websocket/host_access.py`](../../backend/app/websocket/host_access.py) (STORY-164.2 — **déjà nommé « host »** : `resolve_host_and_check_access` résout `Target` + isolation org), consommé par `ssh_session.py` et `journal.py` → renommage interne limité.

**Événements bus (STORY-162 déjà livrée)** : [`core/events.py:167`](../../backend/app/core/events.py:167) — `host.added`/`host.removed`/`host.offline` **déjà canoniques**, `LEGACY_EVENT_ALIASES` mappe `target.*` → `host.*` et `resolve_event_name()` est consommé par le scheduler : l'infrastructure de transition est posée, il manque uniquement l'**émission réelle** `host.*` côté CRUD hosts.

**Seed / auto-détection** : [`database_seed.py:123`](../../backend/app/database_seed.py:123) `_create_localhost_target` **existe déjà** (scan via `TargetScannerService.scan_localhost()`, création, `apply_scan_result` avec capacités persistées) — reste : **setting de désactivation** (aucun dans [`config.py`](../../backend/app/config.py) aujourd'hui), profil canonique `host_baremetal`, trace d'origine.

**Frontend/CLI**
- [`services/api.ts:142`](../../frontend/src/services/api.ts:142) : `targetsApi` (11 méthodes) ; [`stores/targets.ts`](../../frontend/src/stores/targets.ts) : store complet + health polling + pagination STORY-128 ; types dans `types/api.ts` ;
- Vues/composants touchés : `views/Targets.vue`, `DeploymentDetail.vue` (lien `/targets`), `Dashboard.vue`, [`useSidebarNav.ts:72`](../../frontend/src/composables/useSidebarNav.ts:72) (path `/targets`), `SidebarNav.vue`, `ResourceMetricsWidget.vue` ;
- CLI : pas de commandes targets dédiées — seul [`cli/tests/test_client_envelope.py`](../../cli/tests/test_client_envelope.py) consomme `/targets` comme URL générique de test.

**Tests existants à migrer/étendre** : `test_api/test_targets_rbac.py`, `test_targets_crud_ssh_key_ref.py`, `test_targets_fingerprints.py`, `test_test_connection_tofu.py` ; `test_services/test_target_service.py`, `test_target_scanner_service.py`, `test_target_health_check.py`, `test_adoption_service.py` ; `test_models/test_target.py`, `test_host_ssh_fingerprint.py` ; `integration/test_migrations.py`, `test_api_contract.py`, `test_openapi.py`, `test_api_pagination.py` ; `test_websocket/test_ws_journal.py`, `test_ws_ssh_session.py`.

### Divergences & ambiguïtés (documentées, à arbitrer lors de la découpe)

1. **`stacks.target_id` n'existe pas** (description + AC 1) : la FK réelle est `deployments.target_id` ; le « rattachement des stacks » de la spec passe par le déploiement. La découpe doit reformuler l'AC 1 sur le schéma réel (3 FK à retargeter : `deployments`, `target_capabilities`, `host_ssh_fingerprints`).
2. **Mapping `TargetType` (6 valeurs) → `HostProfile` (3 valeurs) ambigu** : la stratégie spec 06 décrit `local`→`host_baremetal`, `ssh`→`host_baremetal`|`host_remote_docker`, `proxmox`→`host_proxmox` — or le code n'a **ni** `local`, **ni** `ssh`, **ni** `proxmox`, mais `docker*`/`kubernetes`/`vm`/`physical`. Correspondance probable : `physical`→`host_baremetal`, `docker`/`docker_compose`/`docker_swarm`→`host_remote_docker` (si distant) ou `host_baremetal` (si localhost) — **arbitrage explicite requis** (peut s'appuyer sur host + capacités scannées) ; `kubernetes` n'a plus de profil (host_kubernetes supprimé, spec 02) → règle de repli à définir.
3. **`TargetStatus` vs `HostStatus`** : code `online/offline/error/maintenance` vs spec `online/offline/unreachable/scanning` — mapping à définir (`error`→`unreachable` ? `maintenance`→ conservé ?).
4. **[`adoption_service.py`](../../backend/app/services/adoption_service.py) ne pose pas `origin=adopted`** (contrairement à la ligne de contexte de cette story) : l'adoption pose aujourd'hui `tags=["adopted", ...]` et `target_id=LOCAL_TARGET_ID` — l'axe `origin` est **entièrement à créer** (enum + colonnes + pose à l'adoption).
5. **Auto-détection déjà partiellement livrée** (seed) : la sous-story correspondante est plus petite qu'annoncé par P2-10/C8 — setting off + profil canonique + origin.
6. **Alias schémas** : `HostReachabilityRequest/Response` déjà préfixés Host — prévoir `HostCreateRequest/HostResponse` (spec 09) comme noms cibles côté schemas.

### Éléments fournis à la création de la story (réutilisation / contraintes)
- **Migration spec 06 § Migration de `targets` vers `hosts`** (stratégie en 5 étapes) : création de `hosts` (schéma canonique : `profile`, `status` online/offline/unreachable/scanning, `environment_id`, `ssh_key_id`, `hardware_info`, `installed_engines`, `last_scan_at`...) ; copie des lignes avec correspondance de profils : `local` → `host_baremetal`, `ssh` → `host_baremetal` (accès SSH) **ou** `host_remote_docker` (si le Docker distant est le seul usage), `proxmox` → `host_proxmox` ; reprise des colonnes : `capabilities` → `hardware_info` + `installed_engines` (éclaté), `connection_config` conservé (chiffré via STORY-103), `last_seen` → `last_scan_at` ; FK `stacks.target_id` → `stacks.host_id` ; suppression de `targets` **après validation** ;
- **Profils 3 valeurs** (enum `HostProfile` spec 06) ; l'actuel `TargetType` 6 valeurs sert au `target_type` des stacks definitions — la correspondance `target_type` YAML ↔ profils canoniques est documentée (STACK-DEFINITIONS § target_type) : le champ stack definition reste tel quel à ce stade (incorporation F3) ;
- **Axe `origin`** (spec 03 § Matrice « profil × origine », enum `WorkloadOrigin`) : colonne sur les entités pilotées — au minimum `hosts`/`stacks` à ce stade du code réel ; [`adoption_service.py:230`](../../backend/app/services/adoption_service.py:230) pose `origin=adopted` lors de l'adoption (P2-4 : « adoption marque origin=adopted ») ;
- **`environments`** (A14) : table canonique spec 06 (id, name, type, organization_id FK, configuration, is_active — `UNIQUE(organization_id, name)`), posée en P1 par STORY-121 si couverte, sinon ici ; rattachement stacks : `stacks.environment_id` ;
- **`Stack.git_url`** (D2) : simple champ optionnel (URL dépôt Git) — **le GitOps complet est hors périmètre** (plugin Git, Roadmap) ; `env_vars_encrypted` déjà couvert par STORY-103 ;
- **Auto-détection du host local** (P2-10/C8) : au premier démarrage, créer le host local avec capacités scannées (réutiliser [`target_scanner_service.py:70`](../../backend/app/services/target_scanner_service.py:70)), désactivable par setting ;
- **Double nommage API** : `/api/v1/hosts/*` devient la surface canonique (spec 09 § Famille Hosts : list/create/detail/scan/metrics/services + WS `/ws/ssh`, `/ws/journal` de STORY-164) ; `/api/v1/targets/*` reste en **alias avec header de dépréciation** pendant la transition (plan §3 F3) — RBAC requis sur les nouveaux chemins (règle : RBAC avant ouverture de nouveaux endpoints) ;
- **Couches à renommer** : modèles (`Target`→`Host`, `TargetCapability`), schemas, routers [`api/v1/targets/`](../../backend/app/api/v1/targets), services `target_service`/`target_scanner_service`/`target_scan_parsers`/`target_access_profile`, enums [`enums/target.py:10`](../../backend/app/enums/target.py:10), WS, événements bus `target.*` → `host.*` (STORY-162), frontend/CLI consommateurs à synchroniser ;
- **Garde-fou §2.G majeur** : le scan de cibles (~20 parseurs, SocketProbe 7 familles, profils d'accès) doit être **branché sur Host sans casser les payloads** — renommage/wrapping, pas réécriture ;
- Garde-fous : module Docker intact ; recovery orchestrateur conservé ; OpenAPI multi-interfaces maintenu (routes `/hosts` documentées, alias déprécié visible) ;
- Risque §7.1 : migration de données testée sur **fixtures réalistes** ; backup de base préalable documenté.

## Critères d'acceptation (AC)

- [ ] AC 1 : Migration Alembic `targets` → `hosts` **sans perte** : test sur fixture réaliste (cibles des 3 types + capacités + credentials chiffrés + stacks rattachées) → après migration, chaque Host a son profil canonique correct (`local`→`host_baremetal`, `ssh`→`host_baremetal`/`host_remote_docker`, `proxmox`→`host_proxmox`), ses capacités éclatées dans `hardware_info`/`installed_engines`, ses stacks re-rattachées via `host_id`, et la table `targets` est supprimée après validation.
- [ ] AC 2 : La surface API canonique `/api/v1/hosts/*` est exposée conformément à la spec 09 (liste filtrable, création, détail hardware/moteurs/statut, scan, health-check, capacités, test-reachability/test-connection) avec **RBAC** (`require_role` — lecture viewer+, gestion admin+) et enveloppes/pagination (STORY-126/128) ; `/api/v1/targets/*` répond en **alias avec header `Deprecation`** et note OpenAPI — aucun consommateur cassé (tests de contrat sur les deux chemins).
- [ ] AC 3 : L'axe `origin` est en place : colonne `origin` (`managed|adopted|external`, défaut pertinent) sur les entités concernées ; l'**adoption marque `origin=adopted`** (test : adoption d'un conteneur découvert → stack/host marqués `adopted`) ; le scan de cibles branché sur Host fonctionne à l'identique (payloads non cassés — tests de non-régression des ~20 parseurs/profils d'accès existants).
- [ ] AC 4 : `environments` activés : table canonique + rattachement des stacks (`stacks.environment_id`), un host appartient à un environnement ; `Stack.git_url` optionnel persisté ; **auto-détection** : premier démarrage → host local présent avec capacités scannées, désactivable par setting (test avec setting off → aucun host créé).
- [ ] AC 5 : Les événements bus sont émis en `host.*` (création/suppression/offline — via STORY-162 ou double émission) ; non-régression globale (module Docker, déploiements, WS existants, CLI/frontend synchronisés) ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — **§ Host — substrat d'exécution** (schéma `hosts`, `installed_engines`), § Migration de `targets` vers `hosts` (stratégie 5 étapes), § Profils canoniques (`HostProfile` 3 valeurs, `WorkloadOrigin`), § Environment (schéma), § Statuts unifiés (`HostStatus`) ;
- [`02-familles-workloads.md`](../../docs/general_specs/02-familles-workloads.md) — § Famille Hosts (substrat, adoption, verbes SSH/journalctl/packages), § Arbitrage Kubernetes (`host_kubernetes` supprimé) ;
- [`03-modele-compute.md`](../../docs/general_specs/03-modele-compute.md) — § Axe origine managed/adopted/external (matrice canonique), § Détection de l'origine par runtime (labels WindFlow) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Famille Hosts — `/api/v1/hosts/` (endpoints complets, `HostCreateRequest`/`HostResponse`) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Hosts distants SSH (clés réutilisables `hosts.ssh_key_id`, empreintes) ;
- [VIRTUALIZATION-SYSTEMS.md](../../docs/technical_specs/VIRTUALIZATION-SYSTEMS.md) — §6 (enums réels, scanner pipeline, correspondance profils), [STACK-DEFINITIONS.md](../../docs/technical_specs/STACK-DEFINITIONS.md) — § `target_type` (correspondance vers profils canoniques) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-4 + P2-10, §3 F3/F4 (étape 2), §2.A A14, §2.C C8/C13, §2.D D2, §5 chaîne critique n°1, §7.1 (fixtures réalistes, double nommage) ;
- [`backend_status.md`](../../docs/backend_status.md) — §3.4 (router targets), §6.2 (modèle Target), §10.3 (enums), §5 (services target_*).

## Dépendances

- **STORY-120** (Alembic) et **STORY-121 + STORY-122** (RBAC avant ouverture des nouveaux chemins `/hosts`) — chaîne critique du plan. ✔ Vérifié : pattern `require_viewer/operator/admin` systématique sur `/targets`, infra Alembic opérationnelle (10 migrations livrées, pattern `batch_alter_table` SQLite documenté).
- **STORY-103** (credentials chiffrés) — ✔ livré : `Target.credentials` au format Fernet opaque ; la data migration devra **copier la colonne telle quelle** (jamais de déchiffrement en migration).
- **STORY-131** (`ssh_key_id` + fingerprints) — ✔ livré : `host_ssh_fingerprints.host_id` référence `targets.id`, FK à retargeter vers `hosts.id`.
- **STORY-162** (bus canonique) — ✔ livrée : noms `host.*` canoniques + alias legacy + `resolve_event_name()` déjà en place ; cette story n'a plus qu'à **émettre réellement** les événements côté CRUD hosts.
- **STORY-164** (WS SSH/journal) — ✔ livré : `websocket/host_access.py` résout déjà la `Target` — impact renommage WS limité.
- **Environnements** : aucune table `environments` posée par STORY-121 (vérifié) — création à la charge de cette story.
- **STORY-160/161** (scheduler) : la surcharge fuseau par Host (colonne timezone) est renvoyée à cette story par 160.x — arbitrer dans la découpe : ajouter la colonne ici ou tracer un renvoi explicite (non bloquant pour 160).
- Conditionne la suite du phasage F4 (Roadmap Phase 2) ; prépare `/compute` étendu (STORY-173 — P2-11 dépend de P2-4 pour l'entité Host).
- **Hors périmètre confirmé** : Apps/Machines/Clusters (F4 étape 3), GitOps complet (plugin Git), CRUD multi-env complet.

## Sous-stories

**⚠️ Verdict analyse-story (2026-10-24) : découpe recommandée — exécutée le même jour (`split-story` mode proactif) : voir la note de clôture en tête de fichier ; cette story est `ABANDONED`, remplacée par STORY-166.1 → 166.6.**

**Justification :**
- **6 domaines hétérogènes** (modèle+migration / API+alias / services+scanners+WS / origin / environments+git_url / auto-détection+frontend+CLI) — très au-delà de ~10 tâches homogènes (estimé **40+ tâches**, ~45 fichiers touchés backend+frontend+tests) ;
- **Migration de données destructive multi-tables** (création `hosts`, copie, éclat capacités, retarget 3 FK, drop `targets`) avec credentials chiffrés — risque §7.1 maximal, mérite isolation + fixtures dédiées ;
- **Mapping `TargetType`→`HostProfile` ambigu** (divergence n°2 du Contexte technique) — arbitrage préalable nécessaire, plus sûr dans une sous-story dédiée ;
- Non-régression à garantir sur ~20 parseurs + WS + module Docker + ~15 fichiers de tests existants — périmètre de validation trop large pour une seule story.

**Découpe exécutée** (numérotation `STORY-166.x`, convention STORY-131/160/164 — fichiers créés dans `.backlog/stories/`) :

| Sous-story | Périmètre | Sortie clé |
|---|---|---|
166.1 | Modèle `Host` + enums canoniques (`HostProfile` 3 valeurs, `HostStatus`, `WorkloadOrigin`) + **arbitrage mapping TargetType/TargetStatus** + migration Alembic `targets`→`hosts` (création, copie avec mapping profils, éclat `capabilities`→`hardware_info`+`installed_engines`, retarget des 3 FK, drop `targets` après validation, fixtures réalistes) | Schéma canonique + data migration testée sans perte |
| 166.2 | Surface API `/api/v1/hosts/*` (spec 09 : liste filtrable, création, détail hardware/moteurs/statut, scan, health-check, capacités, test-reachability/test-connection) + alias `/targets` avec header `Deprecation` + note OpenAPI + émission réelle `host.*` (création/suppression/offline) | Contrats validés sur les 2 chemins, aucun consommateur cassé |
| 166.3 | Renommage services (`target_service`→`host_service`, scanner, parsers, access_profile) + WebSocket `host_access` + consommateurs (deployment, compute, adoption, terminal) — **non-régression payloads des ~20 parseurs et profils d'accès** | Scan identique branché sur Host |
| 166.4 | Axe `origin` (enum + colonnes `hosts`/`stacks` + adoption marque `adopted`) + table `environments` (`UNIQUE(organization_id, name)`) + `stacks.environment_id` + `hosts.environment_id` + `Stack.git_url` optionnel | Origin + environments actifs, git_url persisté |
| 166.5 | Auto-détection : setting désactivable (`config.py`) + alignement du seed existant (profil `host_baremetal`, trace d'origine) | Host local détecté au 1er démarrage, désactivable |
| 166.6 | Frontend (store/services/types/vues `/targets`→`/hosts`) + CLI (tests envelope) + types partagés + purge références résiduelles | Consommateurs synchronisés |

Chaque sous-story recevra ses propres « Tâches d'implémentation détaillées » et « Tests à écrire » via `analyse-story` (les jalons ci-dessus ont été répartis dans les fichiers respectifs). Le tableau ci-dessus correspond aux fichiers créés : 166.1 (modèle+migration), 166.2 (API+alias+événements), 166.3 (services+scanners+WS), 166.4 (origin+environments+git_url), 166.5 (auto-détection), 166.6 (frontend+CLI+purge) — avec une clarification : `hosts.origin` (enum+colonne) est créé en **166.1**, la pose métier `origin` et `stacks.origin` en **166.4**.

## État d'avancement technique

*(analyse-story réalisée le 2026-10-24, découpe `split-story` exécutée le même jour — aucune implémentation à ce niveau ; le suivi se fait dans les sous-stories STORY-166.1 → 166.6)*

## Tâches d'implémentation détaillées

**Non remplies volontairement** — verdict découpe (`split-story` mode proactif exécuté). Les tâches détaillées (fichier par fichier, avec exigences sécurité RBAC/validation Pydantic/exclusion champs sensibles/logs sans données sensibles intégrées) seront rédigées par `analyse-story` dans chaque sous-story 166.1 → 166.6. Le périmètre par sous-story est esquissé dans le tableau § Sous-stories.

## Tests à écrire

**Non remplis volontairement** — reportés aux sous-stories après découpe exécutée (patterns rules 35 : `backend/tests/unit/...`, sécurité 401/403/422/404 + isolation organisationnelle + absence de champs sensibles obligatoires). Jalons identifiés lors de l'exploration, répartis dans les sous-stories :

- **166.1** : migration sur fixtures réalistes (AC 1 : cibles des types réels + capacités + credentials chiffrés + deployments rattachés → Hosts avec profils corrects, capacités éclatées, FK re-rattachées, `targets` droppée) — extension `integration/test_migrations.py` ;
- **166.2** : contrats `/hosts` + alias `/targets` (header `Deprecation`), RBAC viewer/admin, 422/404, isolation organisationnelle, pagination, émissions `host.*` (pattern `test_canonical_event_emitters.py`) ;
- **166.3** : non-régression ~20 parseurs + `target_access_profile` + WS (`test_ws_journal.py`, `test_ws_ssh_session.py`) ;
- **166.4** : adoption → `origin=adopted` ; `UNIQUE(organization_id, name)` sur environments ; `Stack.git_url` persisté ; rattachement `stacks.environment_id` ;
- **166.5** : seed off → aucun host créé ; seed on → host local présent avec capacités scannées ;
- **166.6** : store/services frontend (`frontend/tests/unit/...`), tests CLI envelope sur `/hosts`.

## Notes d'implémentation

*(story refermée sans implémentation — découpe `split-story` proactive le 2026-10-24 : 6 sous-stories créées, aucune ligne de code modifiée ; se reporter aux sous-stories pour l'exécution.)*
