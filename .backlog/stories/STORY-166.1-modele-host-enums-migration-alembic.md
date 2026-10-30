# STORY-166.1 : Modèle `Host`, enums canoniques et migration Alembic `targets`→`hosts` (P2-4, partie modèle — STORY-166 découpée)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-166 ([ABANDONED — découpe proactive post-analyse le 2026-10-24](STORY-166-migration-target-vers-host-origin.md))
**Item plan :** P2-4 (F4 étape 2 — volet modèle de données) — ampleur **L**

> **Périmètre (découpe)** : cette sous-story reprend le **volet modèle + migration de données** de STORY-166 — modèle `Host` (table `hosts`, schéma canonique spec 06), enums canoniques (`HostProfile` 3 valeurs, `HostStatus`, `WorkloadOrigin` + colonne `hosts.origin`), **arbitrage documenté des mappings `TargetType`→`HostProfile` et `TargetStatus`→`HostStatus`**, migration Alembic `targets`→`hosts` **sans perte** (retarget des **3 FK réelles**, éclat `capabilities`→`hardware_info`+`installed_engines`, drop `targets` après validation) et stratégie d'**alias de transition** pour garder le build vert. Couvre l'**AC 1 de la mère (reformulé sur le schéma réel)**. La surface API `/hosts` est portée par [STORY-166.2](STORY-166.2-api-hosts-alias-targets-evenements.md), le renommage des services/scanners par [STORY-166.3](STORY-166.3-services-host-scanners-ws.md), `environments`/`stacks.origin`/pose métier `origin` par [STORY-166.4](STORY-166.4-origin-environments-git-url.md).

## Description

En tant qu'administrateur WindFlow, je veux que l'entité `Target` devienne `Host` au niveau du modèle de données — table `hosts` au schéma canonique spec 06 (profils à 3 valeurs, statuts canoniques, capacités éclatées `hardware_info`/`installed_engines`, axe `origin`), enums canoniques et migration Alembic de données sans perte — afin que les couches supérieures (API, services, frontend) puissent basculer sur le modèle directeur sans casser les installations existantes.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6.2, §10.3) : la table `targets` et l'enum `TargetType` (6 valeurs) divergent du modèle directeur spec 06 (`hosts`, `HostProfile` 3 valeurs, `HostStatus` canonique) ; les capacités sont stockées en colonne unique au lieu d'être éclatées.

## Contexte technique

> Extrait de l'analyse STORY-166 (2026-10-24, `analyse-story`) — volet modèle/migration, fondé sur le code réel du dépôt. Tâches détaillées à rédiger par `analyse-story` sur cette sous-story.

### État réel du code (exploration mère)

- [`models/target.py`](../../backend/app/models/target.py) : `Target` (table `targets`) — credentials chiffrés STORY-103 (token Fernet opaque `{"_encrypted": ...}`, double lecture + ré-encryptage au premier accès via `decrypted_credentials`), `ssh_key_id` FK SET NULL (STORY-131.1), propriétés dérivées (`auth_method`, `username`, `has_sudo`), relations vers `Deployment`, `TargetCapability`, `SSHKey`, `HostSSHFingerprint` ;
- [`enums/target.py`](../../backend/app/enums/target.py) : `TargetType` **6 valeurs** (`docker`, `docker_compose`, `docker_swarm`, `kubernetes`, `vm`, `physical`), `TargetStatus` 4 valeurs (`online`/`offline`/`error`/`maintenance`), `SSHAuthMethod`, `AccessLevel`, `CapabilityType` (~30 valeurs) ;
- [`models/target_capability.py`](../../backend/app/models/target_capability.py) : `UNIQUE(target_id, capability_type)` — table à renommer `host_capabilities` ;
- [`models/host_ssh_fingerprint.py`](../../backend/app/models/host_ssh_fingerprint.py) : `host_ssh_fingerprints.host_id` référence **déjà** `targets.id` (double nommage F3, STORY-131.1) — FK à retargeter vers `hosts.id` ;
- **FK réelles à retargeter** (⚠️ divergence n°1 de la mère : `stacks.target_id` **n'existe pas**) : [`models/deployment.py`](../../backend/app/models/deployment.py) `deployments.target_id` (l.165, CASCADE), `target_capabilities.target_id`, `host_ssh_fingerprints.host_id` — le rattachement stack→host passe par `deployments` ;
- Pattern Alembic opérationnel : 10 migrations livrées, `batch_alter_table` SQLite documenté, tests d'intégration [`backend/tests/integration/test_migrations.py`](../../backend/tests/integration/test_migrations.py) (STORY-120.3).

### Divergences héritées — à arbitrer ICI, avant tout code

1. **`stacks.target_id` n'existe pas** — l'AC 1 de la mère est reformulé dans cette sous-story sur le schéma réel (3 FK : `deployments`, `target_capabilities`, `host_ssh_fingerprints`).
2. **Mapping `TargetType` (6 valeurs) → `HostProfile` (3 valeurs) ambigu** : correspondance probable `physical`→`host_baremetal`, `docker`/`docker_compose`/`docker_swarm`→`host_remote_docker` (si distant) ou `host_baremetal` (si localhost — peut s'appuyer sur host + capacités scannées) ; **`kubernetes` n'a plus de profil** (`host_kubernetes` supprimé, spec 02) → **règle de repli à définir** ; traitement de `vm` à trancher. La **table de correspondance complète** doit être documentée dans la story et la migration **avant** implémentation.
3. **`TargetStatus` → `HostStatus`** : code `online/offline/error/maintenance` vs spec `online/offline/unreachable/scanning` — proposition : `error`→`unreachable`, `maintenance`→`offline` (à valider, documenter la table de correspondance).
4. **`TargetType` reste utilisé par les stack definitions** (`target_type` YAML, [STACK-DEFINITIONS.md](../../docs/technical_specs/STACK-DEFINITIONS.md)) — l'enum **ne doit pas être supprimé** à ce stade (incorporation F3 reportée) : conserver (déplacé ou aliasé) pour le loader.

### Décisions d'analyse applicables — arbitrages des divergences 2 et 3 (2026-10-24, `analyse-story`)

#### Table de correspondance `TargetType` (6 valeurs) → `HostProfile` (3 valeurs)

Règle en deux dimensions : la **valeur de l'enum** × le **caractère local/distant du host** (`host ∈ {localhost, 127.0.0.1}`), avec les **capacités scannées** (`target_capabilities` contient une capacité `docker` disponible) comme tie-breaker pour le repli `kubernetes`. Ces trois signaux sont évaluables en SQL pendant la migration (`CASE WHEN` + `EXISTS`) **et** en Python pur (helper testable unitairement).

| `TargetType` | host `localhost`/`127.0.0.1` | host distant |
|---|---|---|
| `docker` | `host_baremetal` | `host_remote_docker` |
| `docker_compose` | `host_baremetal` | `host_remote_docker` |
| `docker_swarm` | `host_baremetal` | `host_remote_docker` |
| `kubernetes` *(repli)* | `host_baremetal` | `host_remote_docker` **si** capacité `docker` disponible dans `target_capabilities`, sinon `host_baremetal` |
| `vm` | `host_baremetal` | `host_baremetal` |
| `physical` | `host_baremetal` | `host_baremetal` |

**Justifications (décisions d'analyse) :**

- **`kubernetes` (règle de repli)** : `host_kubernetes` est supprimé de `HostProfile` (spec 02/06 — les grappes multi-nœuds deviendront l'entité `Cluster`, Roadmap Phase 2) ; un host kubernetes **redevient un substrat individuel**. Le pilotage Docker distant étant le seul usage qui distingue `host_remote_docker` (spec 06 § « `ssh` → `host_baremetal` ou `host_remote_docker` si le Docker distant est le seul usage »), le repli est : `host_remote_docker` si la capacité scannée `docker` est disponible sur un host distant, sinon `host_baremetal`. La donnée « kubernetes » n'est **pas perdue** : elle reste dans `installed_engines` (moteurs détectés) et `extra_metadata.migrated_type` (trace de l'enum source copiée par la migration).
- **`vm`** : `HostProfile` n'a que 3 valeurs (pas de `host_vm`) ; une VM est un **substrat individuel** → `host_baremetal`. Son caractère VM reste visible via `installed_engines` (agents libvirt/qemu détectés) — modèle compute spec 03 : le profil décrit *comment on pilote*, pas *ce qu'il y a dessous*.
- **`docker*` local** : Docker sur socket local = pilotage direct d'une machine physique/virtuelle → `host_baremetal` ; `host_remote_docker` est réservé au pilotage Docker **distant** (TCP/API).

#### Table de correspondance `TargetStatus` → `HostStatus`

| `TargetStatus` | `HostStatus` | Justification |
|---|---|---|
| `online` | `online` | identique |
| `offline` | `offline` | identique |
| `error` | `unreachable` | sémantique canonique « injoignable » (spec 06 `HostStatus`) |
| `maintenance` | `offline` | pas d'équivalent canonique ; la maintenance est un choix opérateur, pas un état sondé → `offline` (proposition de la mère **validée** ici) |

`HostStatus.scanning` n'a pas d'antécédent dans `TargetStatus` ; il devient l'état posé par `mark_scan_in_progress` (comportement fonctionnel du `scan_success=None` actuel conservé, exploitation en 166.3).

#### Mapping des colonnes (schéma réel → schéma canonique, sans perte)

| `targets` | `hosts` | Règle |
|---|---|---|
| `id, name, description, host, port, credentials, ssh_key_id, extra_metadata, scan_success, os_info, access_profile, organization_id, created_at, updated_at` | idem | copie **verbatim** (credentials chiffrés jamais déchiffrés) |
| `type` | `profile` | table ci-dessus ; valeur source tracée dans `extra_metadata.migrated_type` |
| `status` | `status` | table ci-dessus |
| `scan_date` | `last_scan_at` | renommage (spec 06 `last_seen`→`last_scan_at` ; `scan_date` est le seul antécédent réel) |
| `last_check` | `last_check` | **conservée** (health-check TCP distinct du scan de capacités — aucune perte admise) |
| `platform_info` | `hardware_info` | renommage (contenu JSON inchangé) |
| *(nouveau)* | `installed_engines` | alimenté depuis `target_capabilities` (liste `{capability_type, version, is_available}` du dernier scan) |
| *(nouveau)* | `origin` | `managed` (défaut — pose métier en 166.4) |

`target_capabilities` → `host_capabilities` : copie ligne à ligne, `target_id`→`host_id`, `UNIQUE(host_id, capability_type)` recréée (`uq_host_capability_type`).

### Stratégie de transition (build vert à chaque étape)

- Créer les modules canoniques (`models/host.py`, `enums/host.py`) **avec alias de re-export** dans les anciens chemins (ex. `models/target.py` : `from app.models.host import Host as Target` — même philosophie que `LEGACY_EVENT_ALIASES` de STORY-162) : les services/API non encore renommés continuent de fonctionner sans modification ;
- ⚠️ **Clarification vs tableau de la mère** : `WorkloadOrigin` + colonne `hosts.origin` (défaut `managed`) sont créés **ici** (schéma canonique `hosts` complet) ; `stacks.origin`, la table `environments`, `hosts.environment_id` et `Stack.git_url` relèvent de [STORY-166.4](STORY-166.4-origin-environments-git-url.md) — évite deux migrations touchant `hosts` ;
- Les alias de transition seront purgés par [STORY-166.6](STORY-166.6-frontend-cli-synchronisation-hosts.md).

### Garde-fous

- La data migration **copie la colonne credentials chiffrés telle quelle** (jamais déchiffrer en migration — STORY-103) ;
- Migration testée sur **fixtures réalistes** (risque §7.1) : cibles des types réels + capacités + credentials chiffrés + deployments rattachés ;
- Backup de base préalable documenté ; drop de `targets` **après** validation de la copie ;
- Recovery orchestrateur et module Docker non touchés.

### Checklist sécurité (règle 40)

- Credentials/`connection_config` jamais déchiffrés ni loggés pendant la migration ;
- Propriété `decrypted_credentials` conservée à comportement identique (ré-encryptage au premier accès), jamais exposée dans les schémas de réponse ;
- Logs de migration sans données sensibles.

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend l'AC 1 de la mère, reformulée sur le schéma réel)* : Migration Alembic `targets`→`hosts` **sans perte** — sur fixture réaliste (cibles des types réels + capacités + credentials chiffrés + deployments rattachés), chaque `Host` a son **profil canonique correct selon la table de correspondance arbitrée** (divergence n°2, y compris règle de repli `kubernetes`), son statut mappé (n°3), ses capacités éclatées dans `hardware_info`/`installed_engines`, les **3 FK retargetées** (`deployments.host_id`, `host_capabilities.host_id`, `host_ssh_fingerprints.host_id` → `hosts.id`), et la table `targets` est supprimée après validation.
- [x] AC 2 : **Transition sans casse** — alias de compatibilité (`Target = Host`, re-exports enums) : l'API `/targets`, les services et tous les tests existants passent **sans modification** sur le modèle renommé ; `make backend-lint` + `make backend-test-all` verts.
- [x] AC 3 : **Arbitrages documentés** — tables de correspondance `TargetType`→`HostProfile` et `TargetStatus`→`HostStatus` consignées (Notes d'implémentation + doc de la migration) ; couverture ≥ 80 % sur les modules touchés.

## Références spécification

- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Host (schéma `hosts`, `installed_engines`), § Migration de `targets` vers `hosts` (stratégie 5 étapes), § Profils canoniques (`HostProfile`, `WorkloadOrigin`), § Statuts unifiés (`HostStatus`) ;
- [`02-familles-workloads.md`](../../docs/general_specs/02-familles-workloads.md) — § Arbitrage Kubernetes (`host_kubernetes` supprimé) ;
- [VIRTUALIZATION-SYSTEMS.md](../../docs/technical_specs/VIRTUALIZATION-SYSTEMS.md) §6 (enums réels, correspondance profils), [STACK-DEFINITIONS.md](../../docs/technical_specs/STACK-DEFINITIONS.md) § `target_type` ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 P2-4, §7.1 (fixtures réalistes).

## Dépendances

- **STORY-120** (Alembic) ✔ livrée — pattern `batch_alter_table` + tests d'intégration migrations ;
- **STORY-103** (credentials chiffrés) ✔ livrée — copie verbatim obligatoire ;
- **STORY-131** (ssh_keys/fingerprints) ✔ livrée — `host_ssh_fingerprints.host_id` à retargeter ;
- **Conditionne** [STORY-166.2](STORY-166.2-api-hosts-alias-targets-evenements.md), [STORY-166.3](STORY-166.3-services-host-scanners-ws.md), [STORY-166.4](STORY-166.4-origin-environments-git-url.md), [STORY-166.5](STORY-166.5-auto-detection-host-local-seed.md), [STORY-166.6](STORY-166.6-frontend-cli-synchronisation-hosts.md) — **première sous-story à traiter** ;
- Hors périmètre : table `environments` (166.4), surface API `/hosts` (166.2), renommage des services (166.3), Apps/Machines/Clusters et triple XOR (Roadmap Phase 2).
## État d'avancement technique

*(à cocher pendant `treat-story` — une case par tâche détaillée ci-dessous)*

- [x] T1. Arbitrage des mappings documenté dans la migration (docstring)
- [x] T2. `enums/host.py` + alias `enums/target.py`
- [x] T3. Helper pur `map_target_to_host_profile` / `map_target_status`
- [x] T4. `models/host.py` + alias `models/target.py`
- [x] T5. `models/host_capability.py` + alias + retarget FK `deployment.py`/`host_ssh_fingerprint.py`
- [x] T6. `models/organization.py` back_populates `hosts`
- [x] T7. Migration Alembic `1661_targets_to_hosts` (schéma + données + FK + drop)
- [x] T8. Vérification `alembic upgrade head` + `test_migrations.py` étendu

## Tâches d'implémentation détaillées

### Tâche 1 : Documenter l'arbitrage dans la migration (pré-requis)
**Objectif :** Consigner les tables de correspondance (divergences 2 et 3) comme **documentation exécutable** de la migration — source de vérité unique entre la story, la docstring de révision et les helpers Python.
**Fichiers :**
- `backend/alembic/versions/2026_10_24_1661_targets_to_hosts.py` — [Créer] — docstring d'en-tête reproduisant les tables `TargetType`→`HostProfile` et `TargetStatus`→`HostStatus` arbitrées en Contexte technique (pattern de la migration `1341_normalize_event_names` : mapping documenté in extenso)
**Dépend de :** Aucune

### Tâche 2 : Enums canoniques `enums/host.py` + alias de transition
**Objectif :** Créer `HostProfile` (`host_baremetal`/`host_proxmox`/`host_remote_docker` — valeurs spec 06 l.455-458), `HostStatus` (`online`/`offline`/`unreachable`/`scanning`), `WorkloadOrigin` (`managed`/`adopted`/`external`) ; re-exporter `SSHAuthMethod`, `AccessLevel`, `CapabilityType` (inchangés) ; garder `TargetType` **dans `enums/target.py`** (loader stack definitions + `stacks.target_type`, divergence n°4) qui devient un module de transition : définitions legacy conservées + re-exports des enums canoniques.
**Note d'analyse :** `TargetStatus` legacy a des valeurs (`error`, `maintenance`) absentes de `HostStatus` : l'alias ne peut pas être un simple `=`. Solution : `enums/target.py` garde l'intégralité des définitions legacy **et** re-exporte les enums canoniques ; le modèle `Host` n'utilise que les enums canoniques. Les dépendances legacy (`TargetStatus.ERROR` dans `target_service.mark_scan_failed` l.267, `deployment_service` l.837) continuent de compiler grâce à l'alias de transition, mais **le mapping réel est opéré par la migration** (Tâche 3) — le code legacy écrit `error`, la migration l'a déjà converti en `unreachable` : **décision d'analyse** — `mark_scan_failed` et le health-check passent à `HostStatus.UNREACHABLE`/`SCANNING` en Tâche 4 (sinon incohérence post-migration). Les autres consommateurs legacy (`deployment_service` l.837 teste `TargetStatus.ONLINE` — valeur identique dans `HostStatus`) restent fonctionnels via l'alias.
**Fichiers :**
- `backend/app/enums/host.py` — [Créer] — `HostProfile`, `HostStatus`, `WorkloadOrigin` (valeurs exactes spec 06) + re-export `SSHAuthMethod`, `AccessLevel`, `CapabilityType`
- `backend/app/enums/target.py` — [Modifier] — conserver `TargetType`, `TargetStatus`, `SSHAuthMethod`, `AccessLevel`, `CapabilityType` (compatibilité stack definitions) + ajouter re-exports canoniques (`HostProfile`, `HostStatus`, `WorkloadOrigin`) pour transition build-vert
- `backend/app/enums/__init__.py` — [Modifier] — exporter les nouveaux enums
**Dépend de :** Tâche 1

### Tâche 3 : Helpers purs de mapping (testables unitairement)
**Objectif :** Centraliser les tables de correspondance en **Python pur** (mêmes règles que le SQL de la migration — signal `type` × `host ∈ {localhost, 127.0.0.1}` × `EXISTS capacité docker disponible`) : `map_target_to_host_profile(target_type, host_address, has_docker_capability) -> HostProfile` et `map_target_status(status: TargetStatus) -> HostStatus`. Utilisés par la data migration (Tâche 7) pour les lignes complexes et testables sans DB.
**Fichiers :**
- `backend/app/helper/target_host_migration.py` — [Créer] — les deux fonctions de mapping + `LOCALHOST_ADDRESSES = {"localhost", "127.0.0.1"}` (docstrings = tables de la section Contexte technique ; aucune donnée sensible)
- `backend/tests/unit/test_helper/test_target_host_migration.py` — [Créer] — voir Tests
**Dépend de :** Tâche 2

### Tâche 4 : Modèle canonique `models/host.py` + alias `models/target.py`
**Objectif :** Créer `Host` (table `hosts`) au schéma canonique : `profile: HostProfile`, `status: HostStatus` (défaut `offline`), `hardware_info: JSON` (ex-`platform_info`), `installed_engines: JSON` (défaut `[]`), `last_scan_at` (ex-`scan_date`), `origin: WorkloadOrigin` (défaut `managed`), colonnes conservées verbatim (`host`, `port`, `credentials` + `decrypted_credentials`/`auth_method`/`username`/`has_sudo` à comportement identique — STORY-103, `ssh_key_id`, `extra_metadata`, `last_check`, `scan_success`, `os_info`, `access_profile`, `organization_id`, timestamps). Relations : `deployments` (`Host`, back_populates `host`), `capabilities` (`HostCapability`), `ssh_key`, `ssh_fingerprints`, `organization` (back_populates `hosts`). `models/target.py` devient alias : `from .host import Host as Target` + re-export `encrypt_credentials_for_storage`/`decrypt_credentials_from_storage` — zéro modification des consommateurs non encore renommés (AC 2).
**Fichiers :**
- `backend/app/models/host.py` — [Créer] — classe `Host` complète (docstrings des garde-fous STORY-103 reprises ; jamais de credentials dans `__repr__`)
- `backend/app/models/target.py` — [Modifier] — remplacer la classe par les alias de transition (`Target = Host`, re-exports fonctions chiffrement) + commentaire « purge par STORY-166.6 »
- `backend/app/models/__init__.py` — [Modifier] — exporter `Host`
- `backend/app/services/target_service.py` — [Modifier, minimal] — `mark_scan_failed` : `TargetStatus.ERROR`→`HostStatus.UNREACHABLE` ; `mark_scan_in_progress` : pose `HostStatus.SCANNING` (évite d'écrire des valeurs legacy post-migration) ; health-check `check_health` : mapper le résultat vers `HostStatus` (vérifier l.342-427 : les transitions ONLINE/OFFLINE restent identiques, ERROR→UNREACHABLE)
- `backend/app/services/target_service.py` — [Modifier] — `_build_capability_model`/`apply_scan_result` : écrire dans `HostCapability` (cf. Tâche 5) et alimenter `installed_engines` (payload `{capability_type, version, is_available}` par capacité du scan)
**Dépend de :** Tâches 2, 3

### Tâche 5 : `models/host_capability.py` + retarget des 3 FK
**Objectif :** Créer `HostCapability` (table `host_capabilities`, `UNIQUE(host_id, capability_type)` nommée `uq_host_capability_type`, colonnes identiques à `TargetCapability`, FK `hosts.id` CASCADE). Retargeter les **3 FK réelles** : `deployments.target_id`→`deployments.host_id` (l.165, CASCADE conservé), `host_ssh_fingerprints.host_id`→`hosts.id` (l.68-73 — la colonne s'appelle déjà `host_id`, seule la FK change), `host_capabilities.host_id`→`hosts.id`. `models/target_capability.py` devient alias (`TargetCapability = HostCapability`). Relations `Deployment.target`→`Deployment.host` (back_populates `host`) — vérifier `deployment_service`/`compute_service`/`container_builder` via l'alias (transition sans casse), renommage des attributs côté services reporté en 166.3.
**Fichiers :**
- `backend/app/models/host_capability.py` — [Créer] — `HostCapability` complet
- `backend/app/models/target_capability.py` — [Modifier] — alias de transition + commentaire purge 166.6
- `backend/app/models/deployment.py` — [Modifier] — `target_id`→`host_id` (l.165-170), relation `target`→`host`
- `backend/app/models/host_ssh_fingerprint.py` — [Modifier] — FK `hosts.id` (l.70) + relation vers `Host` + retrait du commentaire « arbitrage F3 » (devient obsolète)
- `backend/app/models/ssh_key.py` — [Modifier] — relation `targets`→`hosts` (back_populates) si définie côté SSHKey
- `backend/app/models/__init__.py` — [Modifier] — exporter `HostCapability`
**Dépend de :** Tâche 4

### Tâche 6 : Back_populates `Organization.hosts`
**Objectif :** Ajouter la relation `hosts` sur `Organization` (miroir de `targets` l.224-226 de l'ancien modèle) pour fermer la boucle relationship de `Host.organization`.
**Fichiers :**
- `backend/app/models/organization.py` — [Modifier] — relation `hosts: Mapped[list["Host"]]` (back_populates `organization`), remplace/adjointe à `targets`
**Dépend de :** Tâche 4

### Tâche 7 : Migration Alembic `targets`→`hosts` (schéma + données + FK + drop)
**Objectif :** Révision `1661_targets_to_hosts`, `down_revision = "1341_normalize_event_names"` (dernier head vérifié). Étapes dans **une seule révision** (SQLite → `batch_alter_table`, pattern STORY-120) : (1) créer `hosts` (schéma canonique : `profile VARCHAR(30)`, `status VARCHAR(20)`, `hardware_info JSON`, `installed_engines JSON DEFAULT '[]'`, `last_scan_at`, `origin VARCHAR(10) DEFAULT 'managed'`, colonnes verbatim) et `host_capabilities` (UNIQUE recréée) ; (2) **copie de données** : `INSERT INTO hosts SELECT ... FROM targets` avec mapping `profile` (SQL `CASE` = table d'arbitrage + helper Tâche 3 pour les lignes kubernetes complexes — lecture `target_capabilities` avant drop), `status` (CASE), `scan_date`→`last_scan_at`, `platform_info`→`hardware_info`, `credentials` **copié octet à octet** (jamais déchiffré — règle 40/STORY-103), `extra_metadata` enrichi de `migrated_type` ; (3) alimenter `installed_engines` depuis `target_capabilities` ; (4) copier `target_capabilities`→`host_capabilities` ; (5) retargeter 3 FK : recréer `deployments` FK vers `hosts` (batch: drop+create constraint, colonne renommée `host_id`), `host_ssh_fingerprints` FK recréée vers `hosts.id`, `host_capabilities` FK native ; (6) **validation** : `SELECT COUNT(*)` hosts == count targets == count host_capabilities == count target_capabilities (log INFO sans données sensibles) ; (7) `DROP TABLE targets`, `DROP TABLE target_capabilities`. Docstring : procédure de backup préalable documentée + avertissement downgrade (downgrade = restauration de backup, non reconstruit — irreversible documenté, pattern 1341).
**Fichiers :**
- `backend/alembic/versions/2026_10_24_1661_targets_to_hosts.py` — [Créer] — upgrade complet + downgrade documenté non-destructif (no-op + message backup)
**Dépend de :** Tâches 3, 4, 5

### Tâche 8 : Validation intégration migrations
**Objectif :** Étendre les tests d'intégration Alembic (pattern STORY-120.3) : fixture réaliste → `upgrade head` → assertions AC 1. Exécuter et valider `alembic upgrade head` sur base de dev + backup documenté.
**Fichiers :**
- `backend/tests/integration/test_migrations.py` — [Modifier] — nouvelle classe `TestMigration1661TargetsToHosts` (voir Tests à écrire)
**Dépend de :** Tâche 7

## Tests à écrire

### Backend

**`backend/tests/unit/test_helper/test_target_host_migration.py`** *(créer)* — mappings purs :
- `test_profile_docker_remote_maps_to_remote_docker` / `test_profile_docker_localhost_maps_to_baremetal` (idem `docker_compose`, `docker_swarm`) ;
- `test_profile_kubernetes_remote_with_docker_capability_maps_to_remote_docker` ;
- `test_profile_kubernetes_remote_without_docker_capability_falls_back_to_baremetal` ;
- `test_profile_kubernetes_localhost_maps_to_baremetal` ;
- `test_profile_vm_and_physical_always_map_to_baremetal` (localhost + distant) ;
- `test_status_error_maps_to_unreachable` / `test_status_maintenance_maps_to_offline` / `test_status_online_offline_identity`.

**`backend/tests/unit/test_models/test_host.py`** *(créer, remplace `test_target.py`)* :
- propriétés dérivées `decrypted_credentials`/`auth_method`/`username`/`has_sudo` (comportement identique STORY-103 : legacy clair → ré-encryptage au premier accès, jamais loggé) ;
- alias de transition : `from app.models.target import Target` retourne `Host` (`Target is Host`) ; `from app.models.target_capability import TargetCapability is HostCapability` ;
- defaults : `origin == managed`, `installed_engines == []`, `status == offline`, `profile` sans défaut implicite ;
- `__repr__` sans credentials/connection_config (règle 40 — absence de champs sensibles).

**`backend/tests/integration/test_migrations.py`** *(étendre — classe `TestMigration1661TargetsToHosts`)* :
- fixture réaliste : 1 target de **chaque `TargetType`** (6) dont localhost et kubernetes distant + capacités (dont `docker` disponible sur le kubernetes) + credentials chiffrés (`encrypt_credentials_for_storage`) + 1 deployment rattaché + 1 fingerprint ;
- après `upgrade head` : chaque host a le **profil attendu selon la table d'arbitrage** (notamment kubernetes distant + docker → `host_remote_docker`, kubernetes sans docker → `host_baremetal`) ;
- statuts mappés : `error`→`unreachable`, `maintenance`→`offline` ;
- capacités éclatées : lignes `host_capabilities` présentes + `installed_engines` alimenté + `hardware_info` == ancien `platform_info` ;
- 3 FK retargetées : `deployments.host_id` → `hosts.id` (données préservées), `host_ssh_fingerprints.host_id` → `hosts.id`, `host_capabilities.host_id` → `hosts.id` ;
- `targets` et `target_capabilities` **absentes** du schéma post-upgrade ;
- credentials identiques **octet à octet** avant/après (jamais déchiffrés pendant la migration — assertion sur le JSON brut) ;
- `extra_metadata.migrated_type` trace l'enum source.

**Non-régression (AC 2 — sans modification)** : `make backend-test-unit` + `make backend-test-integration` verts sur l'ensemble existant (API `/targets`, services, WS, seed — via alias).

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_helper/test_target_host_migration.py backend/tests/unit/test_models/test_host.py -v
poetry run pytest backend/tests/integration/test_migrations.py -v
make backend-test-all
make backend-lint
```

## Notes d'implémentation

### Fichiers créés
- `backend/app/enums/host.py` — enums canoniques (`HostProfile`, `HostStatus`, `WorkloadOrigin`) + **définitions des enums d'accès** (`SSHAuthMethod`, `AccessLevel`, `CapabilityType`) déplacées ici (home canonique) ;
- `backend/app/helper/target_host_migration.py` — helpers purs `map_target_to_host_profile` / `map_target_status` + `_coerce_enum_member` (normalisation **nom ou valeur** — les bases legacy persistent les noms `'ONLINE'`/`'DOCKER'`, baseline sans `values_callable`) ;
- `backend/app/models/host.py` — modèle `Host` canonique (synonyms `scan_date`/`platform_info`, hybrid property `type` avec table d'arbitrage et trace `migrated_type`) ;
- `backend/app/models/host_capability.py` — `HostCapability` + synonym `target_id` ;
- `backend/alembic/versions/2026_10_24_1661_targets_to_hosts.py` — migration `1661` (docstring d'arbitrage, schéma + data + FK + validation par comptage + drop, **défensive** : no-op si `hosts` déjà présente) ;
- `backend/tests/unit/test_helper/test_target_host_migration.py` — 28 tests mappings ;
- `backend/tests/unit/test_models/test_host.py` — 17 tests modèle (alias, defaults, hybrid type, synonyms, sécurité `__repr__`, non-régression STORY-103).

### Fichiers modifiés
- `backend/app/enums/target.py` — module de transition : définitions legacy conservées + re-exports canoniques (import unidirectionnel target→host) ;
- `backend/app/models/target.py` / `target_capability.py` — alias de transition (`Target = Host`, `TargetCapability = HostCapability`) + re-exports ;
- `backend/app/models/deployment.py` — `host_id` + FK `hosts.id` + synonyms `target_id`/`target` ; `host_ssh_fingerprint.py` — FK `hosts.id` + synonym `target` ; `organization.py` (`hosts` + synonym `targets`) ; `ssh_key.py` (`hosts` + synonym `targets`) ; `models/__init__.py` (exports `Host`/`HostCapability`) ;
- `backend/app/services/target_service.py` — bascule `HostStatus` (`mark_scan_in_progress`→SCANNING, `mark_scan_failed`/`check_health`→UNREACHABLE), `installed_engines` alimenté dans `apply_scan_result`, profil posé après construction dans `create` ;
- `backend/app/services/deployment_service.py` — écriture statut `HostStatus.ONLINE` post-déploiement ;
- `backend/app/schemas/target.py` — `status: HostStatus` (TargetUpdate/Response/HealthCheck) ;
- `backend/alembic/versions/2026_10_16_1311_ssh_keys_and_fingerprints.py` — **défensive** : table cible `hosts`/`targets` résolue par inspection (round-trips), offline-safe ;
- Tests adaptés : `tests/integration/test_migrations.py` (classe `TestMigration1661TargetsToHosts` 6 tests + EXPECTED_TABLES + helper), `tests/integration/test_secret_encryption.py` (SQL `hosts`), `tests/unit/test_alembic_config.py`, `test_database.py`, `test_migrations_131.py` (upgrade ciblé `1311_ssh_keys`), `test_services/test_target_health_check.py` (UNREACHABLE).

### Décisions techniques
1. **Direction d'import inversée vs analyse** : `enums/host.py` importé par `enums/target.py` (l'inverse tel que rédigé initialement dans la story créait un **cycle d'import cassant le build** — constaté à la reprise). Les enums d'accès restent identiques, seule leur localisation change.
2. **Normalisation nom-ou-valeur dans les helpers** : la baseline Alembic persiste les **noms** de membres (`'ONLINE'`), le nouveau modèle les **valeurs** (`'online'`, `values_callable`) — la migration lit les deux formes (découverte d'implémentation, non prévue par l'analyse).
3. **Migration défensive** : no-op journalisé si `targets` absente (base déjà canonique — simulation `create_all` des tests), `RuntimeError` si `hosts` ET `targets` coexistent (état incohérent, abort avant écriture) ; en mode no-op la FK de `host_ssh_fingerprints` est retargetée si la 1311 l'a recréée vers `targets`.
4. **Retarget fingerprints par rename/copy** : la FK 1311 est anonyme inline en SQLite (non adressable par `drop_constraint`) — rebuild déterministe par `rename_table` + copie SQL + drop ; l'index `idx_host_ssh_fp_host` est droppé avant le rename (il suit la table en SQLite).
5. **Colonnes enum en `sa.Enum` avec valeurs canoniques** (pas VARCHAR) : alignement exact avec les modèles — `alembic check` reste sans diff après migration (vérifié par test).
6. **`HostCapability.target_id` synonym** : `target_service` écrit `target_id` (non renommé — périmètre 166.3), le synonym assure la transition.
7. **downgrade 1661 = no-op documenté** (pattern 1341, irreversible) ; en conséquence le test `downgrade base` complet s'exécute depuis `1341` (limite documentée dans le test).

### Divergences par rapport à l'analyse
- **Enums d'accés déplacés** dans `enums/host.py` (définitions) au lieu d'être re-exportés depuis `enums/target.py` (cycle d'import — cf. décision 1) ;
- **`TargetResponse.status` basculé vers `HostStatus`** : l'analyse ne le prévoyait pas, mais le schéma legacy aurait rejeté `unreachable` (422) après migration — bascule nécessaire à l'AC 2 ;
- **`deployment_service` l.847** : l'analyse supposait que l'alias suffisait (`TargetStatus.ONLINE` ≡ `HostStatus.ONLINE`) — faux, ce sont des enums distincts (comparaison `==` inter-classes toujours False) : bascule directe effectuée ;
- **1311 rendue défensive** (table cible résolue dynamiquement) : non prévu par l'analyse, requis pour les round-trips downgrade/upgrade des tests existants et le mode offline (`--sql`).

### Difficultés rencontrées
- Cycle d'import enums (build cassé à la reprise) — résolu par inversion de la direction d'import ;
- `sa.inspect()` indisponible sur `MockConnection` en mode offline — helper offline-safe avec défaut `targets` ;
- Defaults SQLAlchemy au flush (pas à la construction) — tests defaults adaptés avec session in-memory + flush ;
- 3 fichiers de tests legacy simulant des bases via `create_all` sur les modèles courants : adaptations ciblées (helpers table-variable, upgrades ciblés par révision, SQL `hosts`).

### Validation
- Tests ciblés : `pytest tests/unit/test_helper/test_target_host_migration.py tests/unit/test_models/test_host.py -v` → **53 passed** ; `pytest tests/integration/test_migrations.py -v` → **41 passed, 1 skipped** (PostgreSQL hors CI locale) ;
- Non-régression : `pytest tests/unit` → **2486 passed** ; `pytest tests/integration` → **206 passed / 1 failed** (`test_deployments_api.py::test_delete_deployment` — **préexistant sur main, vérifié par `git stash`**, hors périmètre 166.1) ;
- Lint : isort + black + flake8 **0 erreur** sur tout le périmètre modifié ; mypy **0 erreur** sur les fichiers de la story (les erreurs restantes du repo sont préexistantes : jwt/docker_client/background_tasks) ; bandit : 1 faux positif B105 (`PASSWORD = "password"` — valeur d'enum de méthode d'auth, même pattern que l'existant) ;
- Couverture modules touchés : `helper/target_host_migration.py` 100 %, `enums/host.py` 100 %, `models/host.py` 88 %, `models/host_capability.py` 100 % ;
- Schéma : `alembic upgrade head` + `alembic check` verts sur base vierge (FK `deployments`/`host_ssh_fingerprints` → `hosts.id` vérifiées par PRAGMA) ;
- Backup préalable documenté en tête de la migration (procédure SQLite/PostgreSQL).

### Points d'attention pour STORY-166.3
- `target_service` écrit toujours via les synonyms `scan_date`/`platform_info`/`target_id` (HostCapability) — le renommage 166.3 devra basculer vers les noms canoniques puis purger les synonyms (166.6) ;
- `mark_scan_in_progress` pose désormais `HostStatus.SCANNING` — l'exploitation WS/scan (166.3) peut s'appuyer sur ce statut ;
- le hybrid `Host.type` (echo API legacy) sera remplacé par la surface `/hosts` (166.2) — ne pas l'étendre ;
- `deployment_service` l.847 écrit `HostStatus.ONLINE` directement (à reloger dans le service renommé).
