# Chapitre 00 — Index de la spécification générale

> **Statut** : Spec cible · **Public** : Tous · **Lié à** : tous les chapitres ci-dessous, [../Roadmap.md](../Roadmap.md)

**Version de la documentation :** 3.2 (refonte, vague 3 — finalisation) · **Dernière mise à jour :** Août 2026 · **Projet :** WindFlow — gestionnaire d'infrastructure self-hosted

## Vue d'ensemble

Cet index est le point d'entrée de la spécification générale de WindFlow : sommaire des chapitres, tableau des fonctionnalités core, navigation par profil de lecteur et conventions de lecture. Il ne spécifie aucun comportement par lui-même.

## Convention de lecture

- **Spec cible** : `general_specs` décrit la vision produit cible de WindFlow, en avance sur l'implémentation réelle. Les écarts avec le code sont attendus et tracés par [../Roadmap.md](../Roadmap.md).
- **QUOI vs COMMENT** : la spec générale décrit les comportements, contrats et périmètres (le QUOI). Le détail d'implémentation (schémas de code, procédures, protocoles) vit dans [`../technical_specs/`](../technical_specs) ; les parcours utilisateurs pas à pas dans [`../user-guide/`](../user-guide).
- **Modèle directeur** : toute la spec est écrite dans le paradigme des trois familles (Apps, Machines, Hosts) défini au chapitre [02-familles-workloads.md](02-familles-workloads.md). Le terme *target* est un alias historique de Host ; les anciens libellés « Mode Standard / Mode Avancé » correspondent à Mode App / Mode Infra.
- **Gabarit** : chaque chapitre suit le même gabarit (bloc `Statut · Public · Lié à`, vue d'ensemble, sections, « Voir aussi ») et vise 200 à 600 lignes.
- **Liens** : tous les liens sont relatifs et vérifiés.
- **Terminologie** : le glossaire canonique (définitions et alias interdits) est au chapitre [19-glossaire.md](19-glossaire.md) ; il prévaut en cas de divergence.

## Sommaire

### Fondations (vague 1 — publiée)

| Chapitre | Périmètre |
|---|---|
| [01-vision.md](01-vision.md) | Vision, objectifs, proposition de valeur, cas d'usage, différenciateurs, métriques de succès, standards |
| [02-familles-workloads.md](02-familles-workloads.md) | **Modèle directeur** : familles Apps/Machines/Hosts, grammaire UI, verbes universels, WorkloadAdapter, Mode App/Mode Infra |
| [04-architecture.md](04-architecture.md) | Monolithe modulaire, frontière core/plugins, profils de déploiement, services core, résilience, performance |
| [06-modele-de-donnees.md](06-modele-de-donnees.md) | Schéma unifié : comptes/organisations, entités App/Machine/Host, stacks/déploiements, plugins, audit ; migration `targets` → `hosts` |
| [09-api.md](09-api.md) | API unifiée : `/apps`, `/machines`, `/hosts` en surface principale, `/compute/*` en Mode Infra, endpoints transverses, WebSocket, erreurs, rate limiting |

### Chapitres fonctionnels (vague 2 — publiée)

| Chapitre | Périmètre |
|---|---|
| [03-modele-compute.md](03-modele-compute.md) | Taxonomie stack/discovered/standalone, **matrice canonique profil × origine (managed/adopted/external)**, vue Compute (Mode Infra), adoption, snapshots, bibliothèque d'images OS |
| [05-stack-technologique.md](05-stack-technologique.md) | Choix techniques, backends VM (adapters), dépendances, CI Gitea Actions, correspondance spec ↔ technical_specs |
| [07-authentification.md](07-authentification.md) | JWT, refresh tokens, clés API, brute-force, SSO via plugin Keycloak |
| [08-rbac-permissions.md](08-rbac-permissions.md) | 4 rôles, matrice complète des permissions, RBAC par famille, gestion des utilisateurs, audit des permissions |
| [10-cli-tui.md](10-cli-tui.md) | Référence CLI/TUI unique, grammaire normalisée (groupes au pluriel, `windflow admin backup`) |
| [11-plugins.md](11-plugins.md) | Système de plugins : manifest, Plugin Manager, **liste canonique des événements**, hooks, extension API/UI, guide dev |
| [12-marketplace.md](12-marketplace.md) | Marketplace 3 onglets, registres, **catalogue officiel des plugins** (compte canonique 20+) |
| [13-ui-principes.md](13-ui-principes.md) | Principes UX, analyse concurrentielle synthétique, navigation (sidebars Mode App/Infra), direction esthétique |
| [14-ui-maquettes.md](14-ui-maquettes.md) | Les 19 écrans maquettés (familles, marketplace, Hosts, adoption, console, plugins, activité) |
| [15-securite.md](15-securite.md) | SecretManager, Docker socket, réseau, audit trail, sécurité des plugins, checklists |
| [16-deploiement.md](16-deploiement.md) | Installation léger/standard/dev, mise à jour, sauvegarde/restauration, dépannage |
| [17-automatisation-workflows.md](17-automatisation-workflows.md) | Scheduler core + workflows en plugins (arbitrage D2 : n8n/Node-RED, pas de moteur intégré) |
| [18-plugins-ia.md](18-plugins-ia.md) | Plugins IA Ollama/LiteLLM : génération de compose, diagnostic, chat assistant |

### Transversal (vague 3 — publiée)

| Chapitre | Périmètre |
|---|---|
| [19-glossaire.md](19-glossaire.md) | Terminologie canonique de la spec : concepts métier, événements, vocabulaire technique, **tableau des alias interdits** (ancien terme → terme canonique) |

## Fonctionnalités core

Ce tableau récapitule les fonctionnalités disponibles dès l'installation, sans aucun plugin. Tout le reste (reverse proxy, DNS, certificats TLS, monitoring, backup, IA, workflows, mail, SSO…) est apporté par des plugins (chapitre [11-plugins.md](11-plugins.md) ; frontière détaillée au chapitre [04-architecture.md](04-architecture.md)).

| # | Fonctionnalité | Description |
|---|----------------|--------------|
| 1 | Gestion des Apps | Docker/Podman/K8s : containers, compose, images, logs, terminal |
| 2 | Gestion des Machines | VMs KVM/libvirt, LXD, Incus, VirtualBox ; snapshots, consoles |
| 3 | Gestion des Hosts | Substrats baremetal/Proxmox/Kubernetes/remote-docker, moteurs détectés |
| 4 | Système de Plugins | Installation, configuration, lifecycle, registre |
| 5 | Marketplace | Catalogue Apps + Machine Templates + Plugins, installation one-click |
| 6 | Stacks & Templates | Groupes de services, versioning, templates Jinja2 |
| 7 | Volumes & Stockage | Volumes Docker, disques Machines, volume browser |
| 8 | Réseaux | Networks Docker/K8s, isolation par environnement |
| 9 | Authentification & RBAC | JWT, organisations, environnements, rôles |
| 10 | Interface Web | Dashboard Mode App/Mode Infra, formulaires dynamiques |
| 11 | CLI / TUI | Ligne de commande et interface terminal interactive |

## Navigation par profil

### Self-hoster / utilisateur

1. [01-vision.md](01-vision.md) — comprendre WindFlow et son positionnement.
2. [02-familles-workloads.md](02-familles-workloads.md) — le modèle mental Apps/Machines/Hosts.
3. [16-deploiement.md](16-deploiement.md) — installer WindFlow.
4. [12-marketplace.md](12-marketplace.md) — choisir quoi installer.
5. [`../user-guide/`](../user-guide) — guides pas à pas (stacks, adoption, compute).

### Développeur backend

1. [04-architecture.md](04-architecture.md) — comment WindFlow est construit.
2. [06-modele-de-donnees.md](06-modele-de-donnees.md) — tables et relations.
3. [09-api.md](09-api.md) — endpoints et conventions.
4. [05-stack-technologique.md](05-stack-technologique.md) — technologies et dépendances.
5. [07-authentification.md](07-authentification.md) et [15-securite.md](15-securite.md) — auth et sécurité.

### Développeur de plugins

1. [11-plugins.md](11-plugins.md) — manifest, lifecycle, hooks, guide de développement.
2. [09-api.md](09-api.md) — comment les plugins étendent l'API.
3. [`../technical_specs/ARCHITECTURE-MODULAIRE.md`](../technical_specs/ARCHITECTURE-MODULAIRE.md) — architecture modulaire détaillée.
4. [12-marketplace.md](12-marketplace.md) — registres et publication.
5. [02-familles-workloads.md](02-familles-workloads.md) — le modèle que les plugins enrichissent.

### Administrateur système

1. [16-deploiement.md](16-deploiement.md) — installation et configuration.
2. [15-securite.md](15-securite.md) — checklist et bonnes pratiques.
3. [08-rbac-permissions.md](08-rbac-permissions.md) — gestion des accès.
4. [10-cli-tui.md](10-cli-tui.md) — administration en ligne de commande.
5. [../Roadmap.md](../Roadmap.md) — feuille de route produit.

## Documentation liée hors `general_specs/`

- [`../technical_specs/`](../technical_specs) — spécifications techniques détaillées : WebSocket temps réel, architecture modulaire, systèmes de virtualisation, design system, CI/CD, fonctions Jinja2, définitions de stacks.
- [`../user-guide/`](../user-guide) — guides utilisateur : containers, stacks, adoption, compute, volumes, réseaux, images, infos système.
- [../Roadmap.md](../Roadmap.md) — feuille de route produit : épic, stories et priorités d'implémentation.

## Voir aussi

- [02-familles-workloads.md](02-familles-workloads.md) — chapitre fondateur à lire en premier
- [04-architecture.md](04-architecture.md) — vue d'ensemble technique
- [11-plugins.md](11-plugins.md) — extensibilité et liste canonique des événements
- [19-glossaire.md](19-glossaire.md) — terminologie canonique et alias interdits
- [../Roadmap.md](../Roadmap.md) — feuille de route produit
