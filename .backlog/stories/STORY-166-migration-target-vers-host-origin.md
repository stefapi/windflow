# STORY-166 : Migration `Target` → `Host` + axe `origin` — renommage modèle/API sur toutes les couches, profils à 3 valeurs, `environments` activés, `Stack.git_url` et auto-détection du host local (P2-4 + P2-10 — arbitrage F4 étape 2)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-4 (axes F4 étape 2, A14, C13, D2) + P2-10 (axe C8) — ampleur **XL** ⚠️ chaîne critique Alembic(120) → RBAC(121/122) → Host

## Description

En tant qu'administrateur WindFlow, je veux que l'entité `Target` devienne `Host` (modèle, API `/targets` → `/hosts`, enums, services, WebSocket, événements du bus) avec les **profils canoniques à 3 valeurs** (`host_baremetal`, `host_proxmox`, `host_remote_docker`), une colonne `origin` (`managed`/`adopted`/`external`) sur les entités pilotées, les `environments` activés (rattachement des stacks), `Stack.git_url` et l'auto-détection du host local au premier démarrage — le tout avec migration de données sans perte et alias/rétrocompatibilité API pendant la transition — afin d'aligner le code sur le modèle directeur des specs sans casser les installations existantes.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6.2, §10.3, [VIRTUALIZATION-SYSTEMS.md §6](../../docs/technical_specs/VIRTUALIZATION-SYSTEMS.md)) : le code porte `Target` (type `local|ssh|proxmox`... en réalité 6 valeurs `TargetType`), des routes `/api/v1/targets` (4 sous-modules), des services/scanners nommés `target_*` ; la spec 06 impose `hosts` (profils 3 valeurs), l'axe `origin`, `environments` (la table n'existe pas — A14), `Stack.git_url` (D2) ; l'auto-détection du host local (C8/P2-10) est absente du seed.

⚠️ **Hors périmètre explicite (arbitrage F4, à noter dans l'implémentation)** : les entités `Apps`, `Machines`, `Clusters`, le triple XOR et les verbes universels restent **hors périmètre** (Roadmap Phase 2 — « créer ces tables sans adapter de pilotage produirait des coquilles vides non testables ») ; seule l'interface `WorkloadAdapter` est posée (STORY-174). L'API `environments` reste minimale (table + rattachement stacks — le CRUD multi-env complet est hors périmètre, plan §6).

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
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

- **STORY-120** (Alembic) et **STORY-121 + STORY-122** (RBAC avant ouverture des nouveaux chemins `/hosts`) — chaîne critique du plan.
- S'appuie sur **STORY-103** (credentials chiffrés repris dans `connection_config`) et **STORY-131** (`ssh_key_id` sur Host) ; coordonnée avec **STORY-162** (événements `host.*`).
- Conditionne la suite du phasage F4 (Roadmap Phase 2) ; prépare `/compute` étendu (STORY-173 — P2-11 dépend de P2-4 pour l'entité Host).

## Sous-stories

*(section réservée — story XL, item le plus invasif de P2 avec le scheduler : `analyse-story` devra évaluer une découpe, ex. migration+modèle / API+alias / origin+environments+git_url+auto-détection ; plage réservée STORY-175-199)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
