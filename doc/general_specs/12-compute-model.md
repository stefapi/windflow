# Modèle Compute — WindFlow

Ce document décrit en détail le modèle de gestion des objets Compute dans WindFlow : containers, machines virtuelles, compositions, et leur articulation dans l'interface.

---

## 1. Taxonomie des Objets Compute

WindFlow organise tous les objets Compute selon deux axes orthogonaux : le **niveau de contrôle** (est-ce que WindFlow en est l'auteur ?) et le **type de technologie** (container ou VM).

### Axe 1 — Niveau de Contrôle

#### Stack WindFlow (managed)

WindFlow est le source of truth. Il a créé l'objet, il en connaît la configuration complète, il peut le modifier, le redémarrer, le supprimer, le sauvegarder.

Une stack WindFlow est un **environnement nommé** qui regroupe un ensemble d'objets Compute liés fonctionnellement. Elle peut contenir :

- un ou plusieurs containers Docker définis via un Compose intégré,
- une ou plusieurs releases Helm sur un cluster Kubernetes connecté,
- une ou plusieurs VMs (KVM ou LXD), provisionnées depuis un template cloud-init,
- ou un **mélange des trois** (stack mixte).

La stack définit les dépendances entre ses composants (ordre de démarrage, réseau partagé, volumes communs), les variables d'environnement globales, et éventuellement sa source Git pour le GitOps.

#### Discovered (observé, read-only)

WindFlow a détecté l'objet lors du scan d'un target, mais il ne l'a pas créé. Il peut en lire les métriques et l'état, mais ne le modifie pas sans action explicite de l'utilisateur.

Objets pouvant être discovered :

- **Containers Docker orphelins** : containers présents sur le daemon Docker mais non connus de WindFlow
- **Compositions Compose** : fichiers `docker-compose.yml` ou `compose.yaml` détectés sur le système de fichiers du target, avec leurs containers associés
- **Releases Helm** : releases déployées sur un cluster Kubernetes connecté (`helm list`)
- **VMs libvirt** : VMs présentes dans libvirt (`virsh list --all`) non créées par WindFlow
- **VMs LXC** : VMs et LXC détectés, LXD, Incus mais non créés par WindFlow

L'action **"Adopter"** permet d'importer un objet discovered dans une stack WindFlow. Un wizard guide l'utilisateur : reprise de la configuration existante, choix de préserver ou recréer les volumes et réseaux, nommage de la stack résultante.

#### Standalone (individuel, managed)

Objet créé directement depuis WindFlow, sans appartenir à une stack. WindFlow en est l'auteur et le gestionnaire, mais sans notion d'environnement groupé. Utile pour des services "one-shot", des tests rapides, ou des containers/VMs à longue durée de vie simples.

Un standalone peut être promu en stack à tout moment (l'objet rejoindra une nouvelle stack ou une stack existante).

### Axe 2 — Type de Technologie

| Type | Sous-type         | Hyperviseur / Runtime | Niveau de granularité |
|---|-------------------|-----------------------|---|
| Container | Docker standalone | Docker Engine         | Container individuel |
| Container | Podman standalone | Docker Engine         | Container individuel |
| Container | Compose           | Docker Engine         | Service dans une composition |
| Container | Helm / k8s / K3s  | Kubernetes            | Pod dans un namespace |
| VM | KVM               | libvirt / QEMU        | Instance VM |
| VM | LXD, Incus        | LXD / Incus           | Instance VM |
| VM | LXC               | Proxmox VE API        | Container système |

---

## 2. Vue Compute — Structure de l'Interface

### Navigation

La section **Compute** remplace et unifie ce qui serait autrement des sections séparées "Containers", "VMs", "Stacks". Elle est accessible depuis la sidebar principale et expose plusieurs onglets internes :

| Onglet | Contenu |
|---|---|
| **Vue globale** | Tous les objets (containers + VMs), toutes machines confondues, groupés par stack/composition puis standalones |
| **VMs** | Uniquement les VMs, avec métriques étendues et accès rapide aux consoles et snapshots |
| **Containers** | Uniquement les containers (Docker + k8s), avec la profondeur de gestion Portainer |
| **Images & ISOs** | Bibliothèque des images Docker et des images OS (qcow2 cloud-init + ISOs) |
| **Snapshots** | Vue centralisée de tous les snapshots VM, toutes machines confondues |

### Vue Globale — Principe de Regroupement

La vue globale affiche les objets Compute en trois sections ordonnées :

```
1. Stacks WindFlow
   ├── stack-a (compose · localhost) — 3/3 running
   │   ├── [container] nextcloud
   │   ├── [container] postgres
   │   └── [container] redis
   ├── stack-b (mixte VM + containers · vps-ovh) — all up
   │   ├── [VM KVM]   ubuntu-dev-vm
   │   ├── [container] postgres
   │   └── [container] redis
   └── stack-c (helm · k8s-prod) — 5/5 running

2. Discovered — non managés
   ├── monitoring (compose · vps-ovh) — observé, adoptable
   │   ├── [container] prometheus
   │   └── [container] grafana
   └── windows-legacy (VM KVM · localhost) — observé, adoptable

3. Standalone
   ├── [VM KVM]    pfsense-router · localhost · running
   ├── [VM LXC] k3s-node-1 · prox-home · running
   ├── [container]  traefik · localhost · running
   └── [container]  pihole · pi4-home · running
```

### Filtres Disponibles

La vue globale expose des filtres combinables :

- **Type** : Stacks WindFlow / Discovered / Standalone
- **Technologie** : Docker / Compose / Helm / VM KVM / LXD / LXC / Incus
- **Target** : filtrer par machine (localhost, vps-ovh, pi4-home, k8s-prod…)
- **Statut** : running / stopped / paused / exited / suspended
- **Recherche libre** : nom, image, OS

### Vue "Par Machine"

Un toggle bascule entre la vue logique (groupée par stack) et la vue physique (groupée par target/machine). En vue par machine, chaque target est une carte qui affiche :

- le résumé de ses containers et VMs (stack ou standalone)
- les métriques agrégées : CPU total, RAM totale utilisée / disponible
- l'hyperviseur et la version du daemon Docker

---

## 3. Gestion des VMs

### Cycle de Vie d'une VM

```
Template OS (cloud-init / ISO)
        │
        ▼
  Provisionnement
  (wizard WindFlow)
        │
        ▼
     stopped ──▶ running ──▶ paused / suspended
        ▲            │
        └────────────┘
             (stop)
        │
        ▼
    snapshot
        │
        ▼
   restauration
   ou suppression
```

### États d'une VM

| État | Description | Actions disponibles |
|---|---|---|
| `running` | VM démarrée, en cours d'exécution | Pause, Suspend, Stop, Console VNC, Snapshot |
| `paused` | Exécution gelée, mémoire préservée (QEMU pause) | Resume, Stop |
| `suspended` | État sauvegardé sur disque (hibernate) | Resume, Stop |
| `stopped` | VM éteinte proprement | Start, Snapshot (disque seul), Modifier config, Supprimer |
| `crashed` | Arrêt inattendu | Start (relance), Consulter logs |

### Console VNC / SPICE

La console s'ouvre dans le navigateur via noVNC (WebSocket). Elle est disponible pour toute VM en état `running` ou `paused`.

- Connexion directe sans client lourd
- Plein écran disponible
- Clipboard bidirectionnel (texte)
- La console reste accessible même si la VM n'a pas d'agent invité (contrairement au terminal SSH qui nécessite l'OS démarré et accessible)

### Provisionnement depuis un Template

1. Choisir un template OS dans la bibliothèque (Ubuntu 22.04 cloud-init, Debian 12 cloud-init, Alpine 3.19…)
2. Configurer les ressources : vCPU, RAM, taille du disque
3. Renseigner la configuration cloud-init : hostname, utilisateur, clé SSH publique, packages additionnels
4. Choisir le réseau (bridge existant ou réseau isolé)
5. WindFlow génère le `user-data`, `meta-data` et `network-config`, crée le volume qcow2 depuis le template, et démarre la VM

Le provisionnement depuis un template cloud-init prend typiquement moins de 2 minutes.

### Modification de Configuration

Une VM arrêtée peut être reconfigurée : ajout/suppression de vCPU, redimensionnement RAM, ajout de disques, modification des interfaces réseau, changement de firmware (BIOS / UEFI). Les modifications s'appliquent au redémarrage.

---

## 4. Bibliothèque d'Images OS

### Types d'Images

| Type | Format | Usage | Architecture |
|---|---|---|---|
| Template cloud-init | qcow2 | Provisionnement automatisé, déploiement rapide | amd64 + arm64 |
| ISO brute | ISO 9660 | Installation manuelle depuis un média d'installation | amd64 (principalement) |
| Template personnalisé | qcow2 | Image maison construite et sauvegardée par l'utilisateur | selon build |

### Images Officielles Maintenues par WindFlow

WindFlow maintient et met à jour les images officielles suivantes :

- **Ubuntu Server 22.04 LTS** (Jammy) — cloud-init — amd64 + arm64
- **Ubuntu Server 24.04 LTS** (Noble) — cloud-init — amd64 + arm64
- **Debian 12 Bookworm** — cloud-init — amd64 + arm64
- **Alpine Linux 3.19** — cloud-init — amd64 + arm64 (54 MB — idéal RPi)
- **Rocky Linux 9** — cloud-init — amd64
- **Home Assistant OS 12** — ISO — amd64
- **pfSense 2.7** — ISO — amd64

L'utilisateur peut importer ses propres ISOs ou images qcow2, et créer des templates personnalisés en capturant l'état d'une VM existante après configuration (sysprep / cloud-init reset).

### Relation avec les Images Docker

Les images Docker (registres OCI) et les images OS (qcow2 / ISO) sont deux registres distincts dans l'onglet **Images & ISOs**, mais dans la même section pour éviter la multiplication des entrées de navigation.

- Images Docker : pull depuis un registre (Docker Hub, ghcr.io, registre privé), listing local, détection des images dangling, nettoyage
- Images OS : stockage local sur le target, téléchargement depuis les sources officielles, vérification de signature SHA256

---

## 5. Gestion des Snapshots VM

### Concept

Un snapshot capture l'état complet d'une VM à un instant T. Selon le moment de la capture :

- **Snapshot chaud** (VM `running`) : capture mémoire + disques + état CPU. La VM continue de tourner pendant la capture (légère dégradation des performances pendant quelques secondes). Permet une restauration à l'état exact, y compris les processus en cours.
- **Snapshot froid** (VM `stopped`) : capture des disques seuls. Plus rapide, moins de données. Ne restaure pas l'état mémoire.

### Vue Snapshots

La vue **Snapshots** (onglet dans Compute) affiche l'ensemble des snapshots de toutes les VMs gérées, sur toutes les machines connectées. Pour chaque snapshot :

- nom et description
- VM source et target
- date et heure de création
- type (chaud / froid)
- taille sur disque
- actions : Restaurer, Supprimer, Créer un template depuis ce snapshot

### Arbre de Snapshots

Pour les VMs avec plusieurs snapshots, WindFlow affiche l'arbre de parenté (un snapshot peut être pris depuis un état lui-même snapshoté, créant une chaîne). La vue arbre est accessible depuis le détail d'une VM.

### Limites et Recommandations

- Les snapshots qcow2 sont des fichiers delta (COW — Copy on Write) : ils grossissent au fur et à mesure des écritures sur la VM après la capture
- WindFlow avertit si un snapshot dépasse 30 jours ou si la chaîne de snapshots dépasse 5 niveaux (impact sur les performances I/O)
- Pour une sauvegarde longue durée, utiliser le plugin Backup (Restic / Borg) qui exporte une image complète, indépendante de la chaîne COW

---

## 6. Discovery et Réconciliation

### Fonctionnement du Scan

À chaque connexion à un target (et périodiquement selon le polling configuré), WindFlow effectue un scan de découverte :

**Sur un target Docker :**
```
docker ps -a                          # containers
docker network ls                     # réseaux
docker volume ls                      # volumes
find / -name "docker-compose.yml"     # compositions (configurable)
find / -name "compose.yaml"
```

**Sur un target libvirt :**
```
virsh list --all                      # VMs
virsh pool-list --all                 # pools de stockage
```

**Sur un target Proxmox (API) :**
```
GET /api2/json/nodes/{node}/qemu      # VMs
GET /api2/json/nodes/{node}/lxc       # LXC
```

**Sur un cluster Kubernetes :**
```
kubectl get pods --all-namespaces
helm list --all-namespaces
```

### Réconciliation

WindFlow compare les objets détectés avec son état interne (base de données) :

- **Objet connu et présent** → mise à jour des métriques
- **Objet connu mais absent** → marqué `missing` (supprimé hors WindFlow)
- **Objet inconnu** → marqué `discovered`, affiché dans la section Discovered

La réconciliation est non-destructive : WindFlow ne modifie jamais un objet discovered sans action explicite de l'utilisateur.

### Wizard d'Adoption

L'adoption d'un objet discovered suit un wizard en 3 étapes :

**Étape 1 — Inventaire**
WindFlow liste les composants détectés et leur configuration actuelle (variables d'environnement, volumes, réseaux, ports exposés).

**Étape 2 — Mapping**
L'utilisateur choisit :
- le nom de la stack WindFlow à créer (ou une stack existante à laquelle rattacher l'objet)
- si les volumes existants sont préservés tels quels ou re-déclarés dans WindFlow
- si les réseaux existants sont préservés ou recréés

**Étape 3 — Validation**
WindFlow génère la définition de stack (fichier Compose ou configuration VM) correspondant à l'état actuel, l'affiche pour relecture, et l'utilisateur confirme. L'objet passe de `discovered` à `managed` sans interruption de service.

---

## 7. Actions par Type d'Objet

### Matrice des Actions Disponibles

| Action | Container standalone | Container dans stack | VM standalone | VM dans stack | Discovered |
|---|---|---|---|---|---|
| Démarrer / Arrêter | ✓ | ✓ (via stack ou individuel) | ✓ | ✓ (via stack ou individuel) | ✗ |
| Redémarrer | ✓ | ✓ | ✓ | ✓ | ✗ |
| Pause / Suspend | ✓ (Docker pause) | ✓ | ✓ (QEMU pause + hibernate) | ✓ | ✗ |
| Logs inline | ✓ | ✓ | ✗ (console VNC à la place) | ✗ | lecture seule |
| Terminal exec | ✓ | ✓ | Via console VNC ou SSH | Via console VNC ou SSH | ✗ |
| Console VNC | ✗ | ✗ | ✓ | ✓ | lecture seule |
| Snapshot | ✗ | ✗ | ✓ | ✓ | ✗ |
| Modifier config | ✓ | ✓ (éditer stack) | ✓ (VM arrêtée) | ✓ (éditer stack) | ✗ |
| Supprimer | ✓ | Via stack | ✓ | Via stack | ✗ |
| Adopter en stack | ✓ (promote) | — | ✓ (promote) | — | ✓ |
| Métriques live | ✓ | ✓ | ✓ | ✓ | ✓ (read-only) |
| Volume Browser | ✓ | ✓ | ✗ | ✗ | ✗ |

### Actions de Stack

Une stack WindFlow expose des actions globales en plus des actions par composant :

- **Démarrer la stack** : démarre tous les composants dans l'ordre de dépendance
- **Arrêter la stack** : arrête tous les composants dans l'ordre inverse
- **Redéployer la stack** : pull les nouvelles images, recrée les containers modifiés (rolling ou stop-and-start selon configuration)
- **Mettre à jour depuis Git** : pull la branche configurée et redéploie si des changements sont détectés
- **Éditer la stack** : ouvre l'éditeur de configuration (Compose YAML ou formulaire assisté)
- **Dupliquer la stack** : crée une copie de la stack avec un nouveau nom (utile pour créer un environnement staging depuis prod)
- **Archiver** : arrête la stack et la conserve en base sans la supprimer

---

## 8. Intégration dans la Sidebar

La structure de navigation principale reflète ce modèle :

```
COMPUTE
  ├── Compute          (vue unifiée — onglets Vue globale / VMs / Containers / Images & ISOs / Snapshots)
  └── Targets          (gestion des machines connectées)

STOCKAGE & RÉSEAU
  ├── Volumes          (volumes Docker + disques VM)
  ├── Networks         (réseaux Docker + bridges / VLANs pour VMs)
  └── Images           (raccourci vers l'onglet Images & ISOs de Compute)

MARKETPLACE
  ├── Marketplace      (applications one-click)
  └── Plugins          (extensions WindFlow)

ADMINISTRATION
  ├── Settings
  └── Audit
```

La section "INFRASTRUCTURE" de la sidebar actuelle est remplacée par **COMPUTE**, ce qui reflète l'unification containers + VMs et élimine l'ambiguïté entre "Containers" (la vue) et "Containers" (la technologie).

---

**Références :**
- [Vue d'Ensemble](01-overview.md) — présentation générale de WindFlow
- [Architecture Générale](03-architecture.md) — principes de conception
- [Fonctionnalités Principales](10-core-features.md) — fonctionnalités détaillées
- [Roadmap](18-roadmap.md) — plan de développement
