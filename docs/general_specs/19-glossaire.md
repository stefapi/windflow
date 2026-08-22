# Chapitre 19 — Glossaire de la spécification

> **Statut** : Spec cible · **Public** : Tous · **Lié à** : [00-index.md](00-index.md), [02-familles-workloads.md](02-familles-workloads.md), [11-plugins.md](11-plugins.md)

## Vue d'ensemble

Ce glossaire recense la **terminologie canonique** de la spécification générale : concepts métier, vocabulaire technique et convention de nommage des événements. Il fait autorité : en cas de divergence entre un chapitre et ce glossaire, le glossaire prévaut et le chapitre doit être corrigé. Il ne définit pas les comportements — chaque terme renvoie au chapitre où il est spécifié. Le tableau final des alias interdits trace la correspondance entre l'ancien vocabulaire (pré-refonte) et le vocabulaire canonique.

## Concepts du modèle directeur

Le modèle à trois familles est spécifié au chapitre [02-familles-workloads.md](02-familles-workloads.md) ; ce glossaire n'en donne que les définitions de référence.

| Terme | Définition | Spécifié au |
|---|---|---|
| **Workload** | Terme générique désignant tout objet géré par WindFlow : une App, une Machine ou un Host. | [02-familles-workloads.md](02-familles-workloads.md) |
| **Famille** | L'une des trois familles distinctes du modèle : Apps, Machines, Hosts. | [02-familles-workloads.md](02-familles-workloads.md) |
| **App** | Workload *container-based* : service installé via Docker, Podman, Compose, Helm, manifests K8s, ou service systemd adopté (profil `app_native_service`). Identité : « je déploie un service ». | [02-familles-workloads.md](02-familles-workloads.md) |
| **Machine** | Workload *VM-based* : machine virtuelle avec son OS complet (KVM, LXD, Incus, LXC, VirtualBox). Identité : « je gère une machine ». Un system container (LXC/LXD mode container) est une Machine, pas une App. | [02-familles-workloads.md](02-familles-workloads.md) |
| **Host** | Substrat d'exécution (machine physique, serveur Proxmox, cluster Kubernetes, daemon Docker distant) qui héberge Apps et Machines. Un Host n'est pas déployé par WindFlow : il est **adopté**. | [02-familles-workloads.md](02-familles-workloads.md) |
| **Profil** | Sous-type technique d'un workload (ex. `docker_compose`, `vm_kvm`, `host_proxmox`). Invisible en Mode App, révélé en Mode Infra. | [02-familles-workloads.md](02-familles-workloads.md) |
| **WorkloadAdapter** | Pattern qui traduit les verbes universels d'une famille en opérations natives du profil (`AppAdapter`, `MachineAdapter`, `HostAdapter` et leurs spécialisations). | [02-familles-workloads.md](02-familles-workloads.md) |
| **Verbes universels** | Actions canoniques exposées dans l'UI par famille (ex. Apps : Ouvrir, Démarrer/Arrêter/Redémarrer, Mettre à jour, Sauvegarder, Configurer, Logs, Console). | [02-familles-workloads.md](02-familles-workloads.md) |
| **ContextualAction** | Action spécifique au profil, exposée dans le menu `[⋯ Plus]` et organisée en cinq sections (Cycle de vie, Configuration, Données, Avancé, Dangereux). | [02-familles-workloads.md](02-familles-workloads.md) |
| **Relation d'hébergement** | Chaque App et chaque Machine est hébergée par un et un seul Host à un instant donné ; exposée dans les cards, détails et filtres « Sur quel Host ? ». | [02-familles-workloads.md](02-familles-workloads.md) |
| **Migration** | Déplacement d'une App ou d'une Machine vers un autre Host (export volumes + redéploiement, live/cold migration KVM), via `[⋯ Plus]` → Avancé. | [02-familles-workloads.md](02-familles-workloads.md) |

### Profils canoniques par famille

| Famille | Profils |
|---|---|
| Apps | `docker_container`, `docker_compose`, `helm_release`, `k8s_manifest`, `app_native_service` |
| Machines | `vm_kvm`, `vm_lxd`, `vm_incus`, `vm_virtualbox`, `vm_lxc` |
| Hosts | `host_baremetal`, `host_proxmox`, `host_kubernetes`, `host_remote_docker` |

**Arbitrage backends VM** : les backends de Machines sont KVM/libvirt, LXD, Incus, VirtualBox et LXC. Proxmox n'est **pas** un backend de VM — c'est un profil de Host (`host_proxmox`) ; les VMs qu'il héberge sont des Machines standard (chapitre [02-familles-workloads.md](02-familles-workloads.md), voir aussi [../technical_specs/VIRTUALIZATION-SYSTEMS.md](../technical_specs/VIRTUALIZATION-SYSTEMS.md)).

## Les deux modes UI

| Terme | Définition | Spécifié au |
|---|---|---|
| **Mode App** | UI par défaut : vocabulaire par famille, profil technique masqué, sidebar minimale (Apps, Machines, Hosts, Marketplace, Plugins). | [02-familles-workloads.md](02-familles-workloads.md) |
| **Mode Infra** | UI augmentée : section Compute par technologie, onglets techniques (Composants techniques, Manifest, Définition libvirt XML, Moteurs installés, Scan & Diagnostics), Audit. | [02-familles-workloads.md](02-familles-workloads.md) |
| **Mode Infra ciblé** | Mode Infra activé pour une seule page workload (toggle « Voir les composants techniques »), sans bascule globale. | [02-familles-workloads.md](02-familles-workloads.md) |
| **Vue Compute** | Vue par technologie (containers, VMs, stacks, images, snapshots) exposée en Mode Infra uniquement — complément des familles, pas un remplaçant. | [03-modele-compute.md](03-modele-compute.md) |

## Objets Compute et niveaux de contrôle

Spécifiés au chapitre [03-modele-compute.md](03-modele-compute.md).

| Terme | Définition |
|---|---|
| **Stack WindFlow** | Environnement nommé regroupant des objets Compute liés fonctionnellement (containers Compose, releases Helm, Machines, ou mélange). WindFlow en est le source of truth. |
| **Discovered** | Objet détecté lors du scan d'un Host mais non créé par WindFlow (container orphelin, composition Compose, release Helm, VM libvirt/LXD/Incus). Lecture seule tant qu'il n'est pas adopté. |
| **Standalone** | Objet créé depuis WindFlow sans appartenir à une stack. Peut être promu en stack à tout moment. |
| **Adoption** | Action qui importe un objet discovered dans le giron managé de WindFlow (wizard d'adoption) ; s'applique aussi aux services systemd devenant Apps (`app_native_service`). |
| **Discovery / réconciliation** | Scan périodique des Hosts qui détecte les objets discovered et réconcilie l'état observé avec l'état connu. |
| **Snapshot** | Capture de l'état complet d'une Machine (mémoire + disques) ; verbe canonique Machines, action contextuelle pour les Apps. |

## Plugins, marketplace et registres

Spécifiés aux chapitres [11-plugins.md](11-plugins.md) et [12-marketplace.md](12-marketplace.md).

| Terme | Définition | Spécifié au |
|---|---|---|
| **Plugin** | Brique installable qui étend WindFlow sans modifier le core. Trois types : service, extension, hybride. | [11-plugins.md](11-plugins.md) |
| **Plugin service** | Plugin qui déploie une application complète (ex. Traefik, PostgreSQL) via un manifest et des hooks. | [11-plugins.md](11-plugins.md) |
| **Plugin extension** | Plugin qui ajoute des endpoints API et des vues UI sans déployer de workload. | [11-plugins.md](11-plugins.md) |
| **Plugin hybride** | Plugin combinant les deux (ex. Uptime Kuma : application + dashboard). | [11-plugins.md](11-plugins.md) |
| **Manifest** | Descripteur YAML d'un plugin : métadonnées, compatibilité, configuration, hooks, services. | [11-plugins.md](11-plugins.md) |
| **Plugin Manager** | Service core du cycle de vie des plugins : installation, activation, mise à jour, désinstallation. | [11-plugins.md](11-plugins.md) |
| **Hook** | Fonction d'un plugin déclenchée par un événement canonique (`@on_event("stack.deployed")`) ou un point d'extension du cycle de vie. | [11-plugins.md](11-plugins.md) |
| **Registre** | Index JSON (officiel ou self-hosted) référençant les plugins installables : nom, version, compatibilité, checksums. | [12-marketplace.md](12-marketplace.md) |
| **Marketplace** | Interface d'installation en 3 onglets : Apps multi-backend, Machine Templates, Plugins. | [12-marketplace.md](12-marketplace.md) |
| **Entrée marketplace** | Fiche YAML multi-backends décrivant une App installable (compose et/ou helm) avec compatibilité et recommandations. | [12-marketplace.md](12-marketplace.md) |
| **Machine Template** | Template cloud-init d'image OS (qcow2) proposé dans l'onglet Machine Templates. | [12-marketplace.md](12-marketplace.md) |
| **Catalogue officiel** | Tableau canonique des plugins officiels (compte « 20+ »), par catégorie, au chapitre 12. | [12-marketplace.md](12-marketplace.md) |

## Événements canoniques

Le nommage suit la convention **`domaine.action_passé`** (ex. `deployment.succeeded`, jamais `deployment.success`). La **liste canonique complète** (18 événements avec données associées) est définie au chapitre [11-plugins.md](11-plugins.md) et référencée par les chapitres 04, 09 et 17 — elle n'est pas dupliquée ici. Domaines :

| Domaine | Exemples | Émis quand |
|---|---|---|
| `container.*` | `container.created`, `container.removed` | Cycle de vie d'un container |
| `stack.*` | `stack.deployed`, `stack.updated`, `stack.removed` | Cycle de vie d'une stack |
| `machine.*` | `machine.created`, `machine.stopped` | Cycle de vie d'une Machine |
| `deployment.*` | `deployment.started`, `deployment.succeeded`, `deployment.failed` | Déroulé d'un déploiement |
| `host.*` | `host.added`, `host.removed`, `host.offline` | Ajout/retrait/disponibilité d'un Host |
| `plugin.*` | `plugin.installed`, `plugin.removed` | Installation/désinstallation d'un plugin |

Ces événements alimentent le canal WebSocket `/ws/events` ([09-api.md](09-api.md)) et les triggers du scheduler ([17-automatisation-workflows.md](17-automatisation-workflows.md)).

## Identité, accès et organisation

Spécifiés aux chapitres [07-authentification.md](07-authentification.md), [08-rbac-permissions.md](08-rbac-permissions.md) et [06-modele-de-donnees.md](06-modele-de-donnees.md).

| Terme | Définition | Spécifié au |
|---|---|---|
| **Access token** | JWT de courte durée (30 min) émis à la connexion ; accepté aussi bien par l'UI, la CLI que l'API. | [07-authentification.md](07-authentification.md) |
| **Refresh token** | Chaîne opaque de longue durée (7 jours par défaut) stockée hashée en base ; sert uniquement à renouveler l'access token. | [07-authentification.md](07-authentification.md) |
| **Clé API** | Jeton longue durée préfixé `wf_ak_…` pour les intégrations programmatiques, associée à un utilisateur et à des scopes. | [07-authentification.md](07-authentification.md) |
| **RBAC** | Role-Based Access Control : 4 rôles (Viewer, Operator, Admin, Super Admin) appliqués par organisation et par famille de workload. | [08-rbac-permissions.md](08-rbac-permissions.md) |
| **Organisation** | Entité d'isolation multi-tenant regroupant utilisateurs, environnements et objets ; lien via la table `user_organizations`. | [06-modele-de-donnees.md](06-modele-de-donnees.md) |
| **Environnement** | Sous-division d'une organisation (ex. production, staging) isolant stacks et réseaux. | [06-modele-de-donnees.md](06-modele-de-donnees.md) |
| **Audit trail** | Journal immuable des actions sensibles (table `audit_logs`) : qui, quoi, quand, sur quelle ressource. | [15-securite.md](15-securite.md) |

## Exploitation et runtime

| Terme | Définition | Spécifié au |
|---|---|---|
| **Profil de déploiement** | Variante d'installation de WindFlow : léger (SQLite, sans Redis, un seul worker), standard (complet), dev. | [04-architecture.md](04-architecture.md) |
| **Scheduler** | Service core de tâches planifiées (cron) et de triggers sur événements ; les workflows avancés sont des plugins (n8n, Node-RED). | [17-automatisation-workflows.md](17-automatisation-workflows.md) |
| **Déploiement** | Exécution d'une action d'installation/mise à jour d'une stack, traçée avec version, durée et statut ; émet les événements `deployment.*`. | [09-api.md](09-api.md) |
| **Rollback** | Retour automatique à la version précédente d'une App après un échec de mise à jour. | [02-familles-workloads.md](02-familles-workloads.md) |
| **WebSocket** | Canal temps réel pour terminal, logs, console VNC, événements de déploiement et flux système (`/ws/*`, authentifié par JWT en query parameter). | [09-api.md](09-api.md), [../technical_specs/WEBSOCKET-REAL-TIME.md](../technical_specs/WEBSOCKET-REAL-TIME.md) |
| **CLI** | Interface en ligne de commande `windflow` (Typer) ; grammaire normalisée : groupes de ressources au pluriel, administration sous `windflow admin`. | [10-cli-tui.md](10-cli-tui.md) |
| **TUI** | Interface terminal interactive (`windflow tui`, Textual), même API que l'UI web. | [10-cli-tui.md](10-cli-tui.md) |
| **SecretManager** | Service core de chiffrement des secrets en base (AES, salt `windflow-secrets-v1`). | [15-securite.md](15-securite.md) |
| **Moteur (engine)** | Technologie de runtime détectée sur un Host (Docker, libvirt, Kubernetes…) via `list_engines`. | [02-familles-workloads.md](02-familles-workloads.md) |

## Alias interdits

Correspondance entre l'ancien vocabulaire (pré-refonte, encore présent dans le code hérité) et la terminologie canonique. **Les alias de la colonne de gauche ne doivent plus apparaître dans la spécification** (sauf citation historique explicite, comme dans ce tableau).

| Alias interdit / historique | Terme canonique | Note |
|---|---|---|
| Target, machine cible | **Host** | `Target` est l'ancien nom interne ; migration `targets` → `hosts` au chapitre 06 |
| VM (vocabulaire utilisateur) | **Machine** | « VM » reste correct pour désigner la technologie (VM KVM), pas l'objet |
| container (comme objet utilisateur), application, service | **App** (en Mode App) | Un container isolé est un objet Compute, vu en Mode Infra |
| type (pour un workload) | **Profil** | Le « type » d'un Host au sens ancien (`local\|ssh\|proxmox`) est remplacé par les 4 profils canoniques |
| Mode Standard, mode simple | **Mode App** | Renommage propagé dans toute la spec |
| Mode Avancé, mode admin | **Mode Infra** | Idem |
| groupe, projet | **Stack WindFlow** | Une stack est un environnement nommé d'objets Compute managés |
| orphelin, détecté | **Discovered** | Statut d'observation, pas une famille |
| individuel | **Standalone** | Objet managé hors stack |
| module, extension applicative | **Plugin** | Typé service / extension / hybride |
| app store, catalogue (pour l'UI) | **Marketplace** | Le « catalogue » est le tableau des plugins officiels au chapitre 12 |
| repository (de plugins) | **Registre** | Index JSON, officiel ou self-hosted |
| `deployment.success` | `deployment.succeeded` | Convention `action_passé`, jamais `deployment.success` |
| `target.added`, `target.offline`… | `host.added`, `host.offline`… | Domaine `host.*` ; `target.*` est l'ancien nommage |
| `/targets`, `/vms`, `/containers` en surface principale | `/hosts`, `/machines`, `/apps` | Les routes technologies deviennent `/compute/*` (Mode Infra) |
| `windflow plugin install` | `windflow plugins install` | Groupes CLI au pluriel |
| `windflow backup create` | `windflow admin backup create` | Administration sous `windflow admin` |
| libvirt + Proxmox VE comme « backends VM » du core | KVM/LXD/Incus/VirtualBox/LXC + Host `host_proxmox` | Arbitrage D1 du plan de refonte |

## Voir aussi

- [02-familles-workloads.md](02-familles-workloads.md) — modèle directeur : familles, profils, verbes, adapters
- [03-modele-compute.md](03-modele-compute.md) — taxonomie stack/discovered/standalone et adoption
- [11-plugins.md](11-plugins.md) — types de plugins et liste canonique des événements
- [00-index.md](00-index.md) — sommaire, navigation par profil et conventions de lecture
- [../technical_specs/VIRTUALIZATION-SYSTEMS.md](../technical_specs/VIRTUALIZATION-SYSTEMS.md) — taxonomie complète des moteurs de virtualisation
