# Spécifications techniques WindFlow (`docs/technical_specs/`)

> **Statut** : Index du corpus · **Refonte complète du corpus — 23/08/2026** (6 vagues : 1 socle, 2 guides stacks, 3 temps réel, 4 architecture modulaire, 5 virtualisation, 6 finition & relecture croisée)
> **Périmètre** : Point d'entrée du corpus technique : rôle et état des 8 fichiers, correspondance terminologique avec general_specs, lacunes assumées.
> **Référence de fond** : [general_specs — 00-index](../general_specs/00-index.md) · [Plan de refonte](../../PLAN-REFONTE-TECHNICAL-SPECS.md)
> **Dernière mise à jour** : 2026-08-23 — **refondu vague 6** (fin de la refonte)

## Principes du corpus

`docs/technical_specs/` décrit le **COMMENT** — le détail d'implémentation — sous la référence de fond [`docs/general_specs/`](../general_specs/00-index.md), qui fixe le **QUOI** (périmètre fonctionnel, arbitrages, vocabulaire). Concrètement :

- Aucune redite fonctionnelle : une définition fonctionnelle vit dans general_specs ; chaque fichier technique renvoie et détaille l'implémentation.
- Tout contenu décrivant du non-implémenté est marqué « ⚠️ **Non implémenté** » (proposition ou cible) — voir la convention rédactionnelle du [plan de refonte](../../PLAN-REFONTE-TECHNICAL-SPECS.md).
- La terminologie suit le glossaire canonique ([19-glossaire.md](../general_specs/19-glossaire.md)) ; la table ci-dessous fait la correspondance avec le vocabulaire historique de ce corpus.

## Matrice d'état des 8 fichiers

Les **8 fichiers sont refondus** (vagues 2-6). Chaque en-tête porte son statut détaillé et sa traçabilité vers les constats de l'audit traités.

| Fichier | Rôle | État du contenu | Refonte | Ancrages general_specs |
|---|---|---|---|---|
| [ARCHITECTURE-MODULAIRE.md](ARCHITECTURE-MODULAIRE.md) | Briques d'infrastructure optionnelles & profils compose | Partiellement implémenté — compose réels (core léger SQLite+Traefik, 5 profils), Makefile documenté ; écarts tracés (`enable-workers` sans service, script divergent, nommage `minimal`/`light`) | **Refondu (vague 4)** | [ch. 04](../general_specs/04-architecture.md), [ch. 05](../general_specs/05-stack-technologique.md), [ch. 11](../general_specs/11-plugins.md), [ch. 12](../general_specs/12-marketplace.md), [ch. 16](../general_specs/16-deploiement.md) |
| [CI-CD-GUIDE.md](CI-CD-GUIDE.md) | Runbook CI/CD (Gitea Actions + équivalent local Makefile) | Partiellement implémenté — 5 workflows réels inventoriés (`ci`, `test`, `build`, `quality-gates`, `deploy`) ; écarts tracés (ruff non branché G31, tests multi-arch manquants, `deploy-*` de `ci.yml` = notifications) | **Refondu (vague 6)** | [ch. 05](../general_specs/05-stack-technologique.md), [ch. 16](../general_specs/16-deploiement.md), [ch. 04](../general_specs/04-architecture.md) |
| [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md) | Design tokens (LA source de vérité, dérivée du code) | Implémenté — tokens vérifiés contre `theme.css`/`uno.config.ts`/`css.ts` ; écart palette ch. 13 documenté (G36, correspondance complète) | **Refondu (vague 6)** | [ch. 13](../general_specs/13-ui-principes.md), [ch. 14](../general_specs/14-ui-maquettes.md), [ch. 05](../general_specs/05-stack-technologique.md) |
| [DYNAMIC-FORMS.md](DYNAMIC-FORMS.md) | Mécanique des formulaires dynamiques (schéma → composants → payload) | Implémenté — schéma enrichi documenté, écart bornes `min`/`max` frontend tracé | **Refondu (vague 2)** | [ch. 03](../general_specs/03-modele-compute.md), [ch. 09](../general_specs/09-api.md), [ch. 11](../general_specs/11-plugins.md), [ch. 13](../general_specs/13-ui-principes.md) |
| [JINJA2-FUNCTIONS.md](JINJA2-FUNCTIONS.md) | Catalogue exhaustif des 16 fonctions Jinja2 des templates de stack | Implémenté — catalogue complet (16 fonctions), `generate_secret` et `generate_uuid_short` corrigées | **Refondu (vague 2)** | [ch. 05](../general_specs/05-stack-technologique.md), [ch. 12](../general_specs/12-marketplace.md) |
| [STACK-DEFINITIONS.md](STACK-DEFINITIONS.md) | Format YAML des stacks (schéma, validation, seeding) | Implémenté (catalogue interne) — enum `target_type`, champs requis et schéma enrichi corrigés ; écart des deux chargeurs tracé | **Refondu (vague 2)** | [ch. 03](../general_specs/03-modele-compute.md), [ch. 09](../general_specs/09-api.md), [ch. 12](../general_specs/12-marketplace.md), [ch. 19](../general_specs/19-glossaire.md) |
| [VIRTUALIZATION-SYSTEMS.md](VIRTUALIZATION-SYSTEMS.md) | Taxonomie et fiches des moteurs de virtualisation/conteneurisation | Partiellement implémenté — fiches de détection dérivées du scanner réel (scan de Host), mapping vers les adapters canoniques (cible) ; ABC monolithiques et installateurs supprimés (annexe ⚠️) | **Refondu (vague 5)** | [ch. 02](../general_specs/02-familles-workloads.md), [ch. 03](../general_specs/03-modele-compute.md), [ch. 04](../general_specs/04-architecture.md), [ch. 05](../general_specs/05-stack-technologique.md), [ch. 19](../general_specs/19-glossaire.md) |
| [WEBSOCKET-REAL-TIME.md](WEBSOCKET-REAL-TIME.md) | Spécification du temps réel (canaux, événements, protocole, composables) | Partiellement implémenté — écarts explicites (`DEPLOYMENT_PROGRESS` non émis, bus semi-canonique, protocole cible ⚠️) | **Refondu (vague 3)** | [ch. 09](../general_specs/09-api.md), [ch. 11](../general_specs/11-plugins.md), [ch. 04](../general_specs/04-architecture.md), [ch. 02](../general_specs/02-familles-workloads.md), [ch. 17](../general_specs/17-automatisation-workflows.md) |

> Corrections tracées par vague dans le [plan de refonte](../../PLAN-REFONTE-TECHNICAL-SPECS.md) (vague 2 : X2-X5, R1-R3, C1-C4, G10-G15, G28-G30 ; vague 3 : X6-X8, R4-R7, G16-G20, G38, A7 ; vague 4 : X1, X9, X10, A5-A8, C5-C6, G21-G27, L1, L2, L7 ; vague 5 : A1-A4, G1-G9, L3-L6 ; vague 6 : G31-G37, R9, R10, P4). Relecture croisée finale effectuée en vague 6 : zéro lien cassé, terminologie conforme, renvois inter-fichiers vérifiés.
>
> **Écarts restants tracés pour la Roadmap** (côté code ou general_specs, hors périmètre doc) : G18 (`core/events.py` semi-canonique), G31 (migration ruff), G33 (matrice de tests multi-arch), G36 (alignement palette ch. 13), G39 (URL registre plugins).

## Correspondance terminologique

Le vocabulaire canonique et les alias interdits sont définis par [19-glossaire.md](../general_specs/19-glossaire.md). Les identifiants du code historique restent cités entre backticks avec leur correspondance ; correspondance (reprise de l'audit §4.9) :

| Terme historique (technical_specs) | Terme canonique general_specs |
|---|---|
| target, machine cible | **Host** |
| VM (pour l'objet) | **Machine** (« VM » reste correct pour la technologie) |
| `target_type` ; valeurs `lxd`, `kvm` | **profil** — Apps : `docker_container`… ; Machines : `vm_kvm`, `vm_lxd`… (`vm` aujourd'hui dans le code) |
| deployment (ressource créée via `POST /deployments` + `target_id`) | **App** — `POST /apps` + `host_id`/`machine_id`/`cluster_id` (triple XOR) ; « déploiement » = exécution d'une action |
| `/api/v1/targets…` | `/api/v1/hosts…` (+ `/clusters` pour les grappes) |
| extension (optionnelle) | **Plugin** (types service / extension / hybride) |
| « plugin » WebSocket (interne) | module de broadcast interne — ≠ Plugin marketplace |
| GROUPE VMs / CONTAINERS / ORCHESTRATION | familles **Apps / Machines / Hosts** + entité **Cluster** |
| Containers Système (« VMs légères ») | famille **Machines** (`vm_lxc`, `vm_lxd` mode container, `vm_incus`) |
| core minimal (PostgreSQL+Redis+Nginx) | profils de déploiement **léger** (SQLite, sans Redis) / **standard** |
| `docker-compose.minimal.yml` | `docker-compose.light.yml` |
| `DEPLOYMENT_STATUS_CHANGED` (SCREAMING_SNAKE) | `deployment.started` / `deployment.succeeded` / `deployment.failed` |
| topic `deployment_logs_{id}` sur `/ws` | canal dédié `/ws/logs/{app_id}` (et `/ws/deploy/{deployment_id}`) |
| « marketplace de stacks » (stacks_definitions) | catalogue de stacks interne (Marketplace = 3 onglets) |
| scanner / scan d'une cible | scan du **Host** (`POST /hosts/{id}/scan`), discovery/réconciliation |

## Lacunes assumées

Certains socles techniques ne sont couverts **que** côté general_specs — aucune spec technique dédiée n'existe dans ce corpus (constat G40 de l'audit ; les noms des 8 fichiers sont conservés) :

- **Plugins & registre** (manifest, hooks lifecycle, `/plugins`, `/registry`) → [ch. 11 Plugins](../general_specs/11-plugins.md), [ch. 12 Marketplace](../general_specs/12-marketplace.md)
- **Compute / Mode Infra** (`/compute/*`, discovery, adoption) → [ch. 03 Modèle compute](../general_specs/03-modele-compute.md)
- **Scheduler / schedules & workflows** → [ch. 17 Automatisation & workflows](../general_specs/17-automatisation-workflows.md)

La création de spécifications techniques dédiées à ces surfaces est recommandée (backlog / Roadmap), hors périmètre de la refonte en cours.

## Voir aussi

- [general_specs — index](../general_specs/00-index.md) et [README general_specs](../general_specs/README.md) — référence de fond (le QUOI)
- [19-glossaire.md](../general_specs/19-glossaire.md) — terminologie canonique et alias interdits
- [AUDIT-TECHNICAL-SPECS.md](AUDIT-TECHNICAL-SPECS.md) — 🗄️ rapport d'audit historique (22/08/2026), conservé comme trace de traçabilité des décisions
- [PLAN-REFONTE-TECHNICAL-SPECS.md](../../PLAN-REFONTE-TECHNICAL-SPECS.md) — plan de refonte, source de vérité de la restructuration en 6 vagues
