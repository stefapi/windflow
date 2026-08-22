# Chapitre 13 — Principes UX

> **Statut** : Spec cible · **Public** : Développeurs frontend, designers · **Lié à** : [02-familles-workloads.md](02-familles-workloads.md), [14-ui-maquettes.md](14-ui-maquettes.md), [../technical_specs/DESIGN-SYSTEM.md](../technical_specs/DESIGN-SYSTEM.md)

## Vue d'ensemble

Ce chapitre définit les principes d'expérience utilisateur de WindFlow : synthèse de l'analyse concurrentielle (18 outils), principes fondateurs, navigation de référence (sidebars Mode App / Mode Infra), responsive, onboarding et direction esthétique. Les maquettes d'écrans complètes sont au chapitre [14-ui-maquettes.md](14-ui-maquettes.md) ; la grammaire UI par famille (squelette, action bars, onglets, menus contextuels) est définie au chapitre [02-familles-workloads.md](02-familles-workloads.md), dont ce chapitre est l'application UX. Le vocabulaire canonique est **Mode App / Mode Infra** partout.

## Analyse concurrentielle synthétique

L'analyse a couvert 18 outils répartis en 4 familles : homeserver/app stores (Umbrel, Runtipi, CasaOS, Cosmos Server, YunoHost, FreedomBox), PaaS/déploiement (Coolify, Cloudron, CapRover), infra/VMs (Proxmox VE, vSphere, Scaleway Console) et infra unifiée containers+VMs (Incus/LXD, Harvester).

Synthèse — ce que WindFlow retient et évite de chaque outil :

| Outil | Ce qu'on prend | Ce qu'on adapte ou évite |
|-------|----------------|---------------------------|
| **Umbrel** | Homepage personnalisable à widgets, app store à fiches soignées, onboarding ultra-simplifié | Cache toute la complexité Docker ; pas de VMs ni multi-Hosts |
| **Runtipi** | Page « Mes apps » avec statut inline et actions directes, app stores multiples, backup par app avant update | Ne gère que des apps Docker |
| **CasaOS** | File manager intégré (volume browser), cards avec port et bouton « Open », import de containers existants | Trop simpliste : pas de terminal, pas d'éditeur compose, pas de VMs |
| **Cosmos Server** | « Server Apps » (tout container exposé = app avec URL/TLS), monitoring intégré, bascule mode simple/admin | Monolithique — WindFlow sépare core et plugins |
| **Coolify** | Vue multi-serveurs avec métriques, déploiement depuis Git avec logs temps réel, notion unifiante de « Resources » | Dashboard vide ; 3 clics pour la config d'un service |
| **Cloudron** | Tableau apps avec domaine/statut/actions, domaines liés aux apps, backup par app, page « Activity » filtrable | Payant au-delà de 2 apps ; pas de VMs |
| **CapRover** | Simplicité des « One-Click Apps », configs modifiables post-installation | — |
| **Proxmox VE** | Arbre de navigation par hiérarchie, console VNC dans un onglet, onglets identiques VM/LXC, vue Datacenter agrégée | UI datée (ExtJS) ; pas de Docker ni app store |
| **vSphere / Scaleway** | Wizard de création par étapes, graphiques de performance, vue inventaire avec recherche | — |
| **Incus / LXD** | Principe fondamental : le type est une colonne, pas un paradigme ; mêmes commandes pour containers et VMs | Pas de Docker/Podman, pas de marketplace |
| **Harvester (SUSE)** | Abstraction « Instance » commune, même wizard pour provisionner VM ou container, métriques unifiées | — |

Le positionnement qui en résulte : l'élégance d'Umbrel, la densité de Cosmos, la transparence de Proxmox — appliquées au modèle à trois familles du chapitre 02.

## Principes fondateurs

### 1. Trois familles, une grammaire UI

Principe fondateur détaillé au chapitre [02-familles-workloads.md](02-familles-workloads.md) : Apps, Machines et Hosts sont distinctes dans le modèle mental, mais partagent rigoureusement la même grammaire de présentation — squelette de page, action bar canonique, onglets canoniques, menus contextuels à cinq sections. Une action universelle est toujours présente dans la barre d'action (grisée avec tooltip si `NotApplicable`) ; les actions spécifiques à un profil vivent dans le menu `[⋯ Plus ▾]`, peuplé par l'adapter. C'est là — et là seulement en Mode App — que le profil technique fuit.

### 2. Deux modes d'interface : Mode App et Mode Infra

Formalisés comme deux **niveaux de vocabulaire**, pas seulement de densité :

- **Mode App** (par défaut, suffisant pour 80 % des utilisateurs) : aucun mot « container », « compose », « helm », « VM », « namespace », « pod » hors de la section « Avancé » du menu contextuel. Écrans : Dashboard, Apps, Machines, Hosts, Marketplace, Plugins, Settings.
- **Mode Infra** (opt-in) : la même expérience App, **augmentée** — profil révélé dans le header, onglets supplémentaires (« Composants techniques », « Manifest »), section Compute par technologie (chapitre [03-modele-compute.md](03-modele-compute.md)).

Le toggle est dans la sidebar (bouton discret en bas) ; le mode est mémorisé par utilisateur. Les Viewers sont forcés en Mode App. Un **Mode Infra ciblé** existe aussi : depuis le menu `[⋯ Plus]` d'un workload, l'action `[🔧 Voir les composants techniques]` bascule cette **page seulement** en Mode Infra sans activer le toggle global.

### 3. Le workload comme vocabulaire central

Tout ce qui est déployé ou administré apparaît comme un Workload d'une des trois familles. Le terme « Workload » est interne (modèle de données, doc d'architecture) ; l'utilisateur en Mode App ne le voit jamais — il manipule des Apps, des Machines, des Hosts. Le bouton Console occupe la même position dans les trois familles, mais sa nature s'adapte : Terminal pour les Apps, VNC/SPICE pour les Machines, SSH pour les Hosts.

### 4. Dashboard type « homepage »

Inspiré d'Umbrel (widgets personnalisables) avec la densité de Runtipi (métriques système + instances running). Le dashboard est le point d'entrée unique, personnalisable avec des widgets ajoutés par les plugins (Uptime Kuma, Traefik, Restic…) et un widget natif « Dernière activité » façon Cloudron.

### 5. Marketplace-first par famille

Le point d'entrée naturel pour créer une App est la **Marketplace** (onglet Apps), pour une Machine la **Marketplace** (onglet Machine Templates) ; pour un Host, le bouton dédié `[+ Ajouter un Host]` — on adopte un substrat existant, il n'y a pas de marketplace de Hosts (chapitre [12-marketplace.md](12-marketplace.md)). L'entrée marketplace d'une App déclare plusieurs backends et WindFlow propose un mini-wizard de 2-3 questions. Pour les besoins explicites, un bouton `[+ Créer manuellement]` complète la marketplace et passe par un wizard plus complet, disponible en Mode Infra.

### 6. Actions sans navigation

Les actions courantes (start, stop, restart, console, logs, snapshot) sont accessibles **directement depuis les listes**, sans ouvrir le détail. Le détail existe pour la configuration et le troubleshooting.

## Navigation de référence

Les sidebars ci-dessous constituent la **référence unique** de navigation WindFlow, conforme au chapitre 02. La section « Plugins » est peuplée dynamiquement par les plugins installés.

### Sidebar Mode App (par défaut)

```
┌──────────────────────────┐
│  🌀 WindFlow              │
│                          │
│  🏠  Dashboard           │
│                          │
│  ── Workloads ──         │
│  📱  Apps                │
│  🖥️  Machines           │
│  🖧  Hosts               │
│                          │
│  🏪  Marketplace         │
│  🔌  Plugins             │
│                          │
│  ── Plugins ──           │  ← Ajouté dynamiquement
│  🌍  Domaines            │  ← (Plugin Traefik)
│  📈  Monitoring          │  ← (Plugin Uptime Kuma)
│  💾  Backups             │  ← (Plugin Restic)
│  🤖  Assistant IA        │  ← (Plugin Ollama/LiteLLM)
│                          │
│  ⚙️  Settings            │
│                          │
│  ─────────────────────── │
│  [🔧 Mode Infra]         │  ← Toggle
│  🟢 nas-server (x86_64)  │
│  👤 admin                │
└──────────────────────────┘
```

### Sidebar Mode Infra (toggle activé)

```
┌──────────────────────────┐
│  🌀 WindFlow              │
│                          │
│  🏠  Dashboard           │
│                          │
│  ── Workloads ──         │
│  📱  Apps                │  ← profil révélé dans le header
│  🖥️  Machines           │
│  🖧  Hosts               │
│                          │
│  🏪  Marketplace         │
│  🔌  Plugins             │
│                          │
│  ── Compute (technique) ─│  ← Mode Infra uniquement
│  ⚡  Compute             │  ← chapitre 03
│  📚  Stacks              │
│  💾  Volumes             │
│  🌐  Networks            │
│  🖼️  Images              │
│  📸  Snapshots           │
│                          │
│  ── Plugins ──           │
│  🌍  Domaines            │
│  📈  Monitoring          │
│  💾  Backups             │
│  🤖  Assistant IA        │
│                          │
│  ⚙️  Settings            │
│  📋  Audit               │
│                          │
│  ─────────────────────── │
│  [📱 Mode App]           │  ← Toggle retour
└──────────────────────────┘
```

**Rationale** : un self-hoster débutant qui veut installer Nextcloud et Jellyfin ne devrait jamais voir « Containers », « Networks » ou « Images ». Un admin qui veut debug un container qui crashe a besoin de tout. Le Mode App reste honnête sur les problèmes (statut `degraded`, badge `⚠`) sans forcer la connaissance technique ; le Mode Infra (global ou ciblé) ouvre l'accès au détail.

## Responsive et mobile

### Tablette (768-1024 px)

- Sidebar rétractée en icônes (labels au survol) ;
- Dashboard : widgets en 2 colonnes au lieu de 3 ;
- listes de familles : une card par ligne (plus de place pour les actions).

### Mobile (< 768 px)

Inspiré de l'approche Umbrel (dock en bas) :

```
┌─────────────────────────┐
│ 🌀 WindFlow    🔔  👤   │
├─────────────────────────┤
│  CPU 38%  RAM 1.2/4 GB  │
│  5 apps running         │
│ ┌─────────────────────┐ │
│ │ ☁️ Nextcloud  🟢    │ │
│ │ cloud.example.com   │ │
│ │ [Ouvrir] [⋯]        │ │
│ └─────────────────────┘ │
├─────────────────────────┤
│ 🏠  📱  🏪  🔌  ⚙️      │
└─────────────────────────┘
```

- **Dock fixe en bas** avec les 5 sections principales ;
- cards simplifiées : bouton « Ouvrir » (action principale) et menu `[⋯]` pour le reste ;
- console VNC et terminal non accessibles sur mobile (écran trop petit) ;
- volume browser en lecture seule sur mobile.

## Onboarding (premier lancement)

Wizard en 4 étapes inspiré d'Umbrel et Cosmos : **Compte → Machine → Première app → Terminé**.

L'étape « Machine » détecte le hardware (architecture, RAM, stockage, moteurs Docker/KVM disponibles) et recommande un profil de déploiement (chapitre [04-architecture.md](04-architecture.md)) :

```
┌─────────────────────────────────────────────────────────────┐
│                     🌀 Bienvenue sur WindFlow                │
│                                                             │
│         ○─────────●─────────○─────────○                     │
│        Compte    Machine   Première   Terminé               │
│                            app                              │
│                                                             │
│         Étape 2 — Votre machine                             │
│                                                             │
│         WindFlow a détecté :                                │
│         🖥️  Raspberry Pi 4 (arm64)                          │
│         💾  4 GB RAM • 64 GB stockage                       │
│         🐳  Docker 24.0.7 ✅                                │
│         ⚡  KVM/libvirt ✅                                  │
│                                                             │
│         Profil recommandé : Standard                        │
│         (PostgreSQL + Redis, ~1.5 GB RAM)                   │
│                                                             │
│                              [Continuer →]                  │
└─────────────────────────────────────────────────────────────┘
```

L'étape suivante propose d'installer un premier plugin (Traefik recommandé) et une première App (Nextcloud, Gitea ou Jellyfin au choix). Ce wizard d'onboarding exploite la même détection de moteurs que le scan des Hosts (chapitre [03-modele-compute.md](03-modele-compute.md)).

## Direction esthétique

### Inspiration visuelle

Le design se positionne entre **Umbrel** (élégance, polish) et **Proxmox/Cosmos** (densité d'information, fonctionnalité) :

- **Élégance d'Umbrel** : coins arrondis, espacement généreux, animations subtiles, wallpaper optionnel ;
- **Densité de Cosmos** : métriques inline, actions accessibles, pas de perte d'espace ;
- **Transparence de Proxmox** : montrer ce qui se passe (containers, réseaux, volumes), pas le cacher.

### Typographie

- **UI / corps** : Inter — lisible, technique, open source, large support de langues ;
- **Code / logs / terminal** : JetBrains Mono — ligatures, lisible en petite taille ;
- **Titres d'apps** : Inter Semi-Bold — pas besoin d'une display font pour un outil technique.

### Palette thème sombre (par défaut)

```
Fond principal     #0c0e14    (noir profond, comme un terminal moderne)
Fond carte/card    #151821    (léger relief)
Fond hover         #1c1f2b    (feedback subtil)
Bordures           #252838    (séparation douce)
Texte principal    #e2e5f0    (blanc cassé, confortable)
Texte secondaire   #7c8098    (gris moyen pour les métadonnées)
Accent bleu        #4f8ff7    (actions, liens, sélections)
Succès             #34d399    (vert menthe)
Erreur             #f87171    (rouge doux)
Warning            #fbbf24    (ambre)
Info               #60a5fa    (bleu clair)
```

### Palette thème clair

```
Fond principal     #f8f9fc
Fond carte/card    #ffffff
Bordures           #e5e7eb
Texte principal    #1f2937
Texte secondaire   #6b7280
Accent bleu        #3b82f6
```

### Composants clés

- **Cards** : `border-radius: 12px`, `padding: 20px`, bordure subtile, ombre douce 1px uniquement ;
- **Boutons d'action** : icône + texte pour les actions principales, icône seule pour les actions inline ;
- **Status dots** : 🟢 running (vert pulsant subtil), 🔴 stopped (rouge statique), 🟡 deploying (jaune clignotant) ;
- **Barres de progression** : coins arrondis, dégradé subtil du bleu accent vers le bleu clair ;
- **Toast notifications** : en haut à droite, auto-dismiss 5 s, empilables.

Les tokens complets et les composants détaillés sont dans [../technical_specs/DESIGN-SYSTEM.md](../technical_specs/DESIGN-SYSTEM.md).

## Voir aussi

- [02-familles-workloads.md](02-familles-workloads.md) — grammaire UI par famille dont ce chapitre est l'application
- [14-ui-maquettes.md](14-ui-maquettes.md) — les 19 écrans maquettés
- [03-modele-compute.md](03-modele-compute.md) — vue Compute révélée en Mode Infra
- [12-marketplace.md](12-marketplace.md) — structure 3 onglets derrière l'écran Marketplace
- [../technical_specs/DESIGN-SYSTEM.md](../technical_specs/DESIGN-SYSTEM.md) — design system détaillé
