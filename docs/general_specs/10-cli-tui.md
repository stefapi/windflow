# Chapitre 10 — CLI et TUI

> **Statut** : Spec cible · **Public** : Utilisateurs avancés, administrateurs, scripts CI · **Lié à** : [09-api.md](09-api.md), [07-authentification.md](07-authentification.md), [16-deploiement.md](16-deploiement.md)

## Vue d'ensemble

Ce chapitre est la **référence unique** de l'interface en ligne de commande (CLI) et de l'interface terminal interactive (TUI) de WindFlow. Les deux consomment la même API REST que le frontend (chapitre 09) — toute action de l'UI est donc possible en CLI et inversement. La grammaire est normalisée : groupes de ressources au **pluriel** (`windflow apps`, `windflow machines`, `windflow hosts`, `windflow plugins`), administration sous `windflow admin`, une seule forme par commande. L'authentification CLI (anciennement dispersée dans le chapitre auth) est spécifiée ici.

**Technologies** : Typer (framework CLI, auto-complétion et aide générées), Rich (tableaux, couleurs, barres de progression), Textual (TUI).

### Installation

```bash
# Inclus dans WindFlow — accessible via Docker
docker exec -it windflow-api windflow --help

# Ou installation locale (pour gérer une instance distante)
pip install windflow-cli
windflow --help
```

## Grammaire des commandes

Règles canoniques :

- **Groupes de ressources au pluriel** : `windflow apps`, `windflow machines`, `windflow hosts`, `windflow stacks`, `windflow plugins`, `windflow volumes`, `windflow images`, `windflow marketplace` — jamais au singulier.
- **Familles plutôt que technologies** : `windflow machines` (pas `vms`), `windflow hosts` (pas `targets`), `windflow apps` (pas `containers`).
- **Administration sous `windflow admin`** : utilisateurs, audit, info système.
- **Backup/restore sous `windflow admin backup`** : une seule forme (`windflow admin backup create`, `windflow admin backup restore`).
- **Sous-commandes consistentes** : `list`, `create`, `start`, `stop`, `restart`, `rm`, `logs`, `inspect`, `config`.

## Authentification CLI

### Login interactif

```bash
# Login standard (demande username et password)
windflow auth login
# Username: admin
# Password: ********
# ✓ Connected to http://localhost:8080 as admin (Super Admin)

# Login vers une instance spécifique
windflow auth login --url http://192.168.1.50:8080

# Login par API key
windflow auth login --api-key wf_ak_a1b2c3d4...
```

### Session

```bash
windflow auth status
# Instance: http://192.168.1.50:8080
# User: admin (Super Admin)
# Token expires: in 24 minutes
# Organizations: homelab (Admin), work (Viewer)

windflow auth logout
# ✓ Logged out. Credentials removed.
```

### Gestion des clés API

```bash
windflow auth api-key create --name "CI/CD" --expires 90d
# → wf_ak_x7y8z9... (affichée une seule fois)

windflow auth api-key list
# NAME       CREATED      EXPIRES      LAST USED
# CI/CD      2026-03-15   2026-06-13   2026-04-02

windflow auth api-key revoke --name "CI/CD"
```

### Stockage des tokens

Les tokens sont stockés localement dans `~/.windflow/credentials`, chiffrés avec une clé dérivée du mot de passe système de l'utilisateur (permissions 600) :

```
~/.windflow/
├── credentials          # Tokens chiffrés (permissions 600)
└── config.yml           # URL de l'instance, préférences
```

Le client CLI intercepte les réponses 401 et rafraîchit automatiquement l'access token via le refresh token stocké. Le mécanisme JWT/refresh sous-jacent est spécifié au chapitre [07-authentification.md](07-authentification.md).

## Familles de workloads

### Apps — famille Apps

```bash
# Lister les Apps (tous profils confondus)
windflow apps list --host nas-server --status running
# NAME          PROFILE           STATUS    VERSION   HOST
# nextcloud     docker_compose    running   28.0.4    nas-server

# Cycle de vie (verbes universels du chapitre 02)
windflow apps start nextcloud
windflow apps stop nextcloud
windflow apps restart nextcloud
windflow apps update nextcloud
windflow apps backup nextcloud

# Logs, console, détails, suppression
windflow apps logs nextcloud --tail 50 --follow
windflow apps console nextcloud -- /bin/bash
windflow apps inspect nextcloud
windflow apps rm old-test-app
```

### Machines — famille Machines

```bash
# Lister les Machines
windflow machines list --host nas-server --status running
# NAME            PROFILE   STATE      VCPU   RAM     HOST
# ubuntu-dev      vm_kvm    running    2      2048    nas-server

# Créer depuis un template marketplace (ou --iso pour une installation manuelle)
windflow machines create ubuntu-dev \
  --host nas-server \
  --template ubuntu-24.04 \
  --cpus 2 --memory 2048 --disk 20 \
  --cloud-init user-data.yml
```

Power et snapshots — vocabulaire matériel du chapitre 02 :

```bash
# Power (vocabulaire matériel)
windflow machines power-on ubuntu-dev
windflow machines power-off ubuntu-dev          # shutdown ACPI
windflow machines power-off ubuntu-dev --force  # arrêt forcé
windflow machines reboot ubuntu-dev

# Snapshots
windflow machines snapshot create ubuntu-dev --name "before-update"
windflow machines snapshot list ubuntu-dev
windflow machines snapshot restore ubuntu-dev --name "before-update"
windflow machines snapshot delete ubuntu-dev --name "before-update"

# Supprimer
windflow machines rm ubuntu-dev --delete-disks
```

### Hosts — famille Hosts

```bash
# Lister les Hosts
windflow hosts list

# NAME          PROFILE          STATUS    ENGINES
# local         host_baremetal   online    docker ✓, libvirt ✓
# nas-server    host_baremetal   online    docker ✓
# prox-home     host_proxmox     online    proxmox-api ✓
# k3s-cluster   host_kubernetes  online    k8s ✓, helm ✓

# Ajouter un Host (adoption d'un substrat)
windflow hosts add nas-server \
  --type baremetal \
  --host 192.168.1.50 \
  --user deploy \
  --key ~/.ssh/id_ed25519 \
  --key-id deploy-key \
  --env production
# (--key importe un fichier local ; --key-id référence une clé SSH
#  réutilisable enregistrée — chapitre 15)
```

Autres profils d'ajout — un par profil canonique :

```bash
windflow hosts add prox-home --type proxmox --host 192.168.1.100 \
  --token-id user@pam!windflow --token-secret abc123...
windflow hosts add k3s-cluster --type kubernetes --kubeconfig ~/.kube/config
windflow hosts add docker-remote --type remote-docker --host 192.168.1.60
```

Scan des moteurs, adoption des objets découverts, retrait du suivi :

```bash
windflow hosts scan nas-server
# ✓ Docker 24.0.7 detected
# ✓ Docker Compose 2.23.0 detected
# ✗ libvirt not found
# System: Debian 12, arm64, 4 cores, 4096 MB RAM, 64 GB disk

windflow hosts resources nas-server
windflow hosts adopt nas-server          # wizard d'adoption (chapitre 03)

# Retirer du suivi
windflow hosts rm nas-server
```

Les valeurs de `--type` correspondent aux profils canoniques : `baremetal | proxmox | kubernetes | remote-docker` (chapitre [02-familles-workloads.md](02-familles-workloads.md)).

## Compute (Mode Infra)

Les commandes `compute` exposent la vue par technologie (chapitre [03-modele-compute.md](03-modele-compute.md)) :

```bash
# Containers individuels
windflow compute containers list --host nas-server
windflow compute containers logs nextcloud-php
windflow compute containers exec nextcloud-php -- ls -la /var/www

# Instances VM
windflow compute vms list
windflow compute vms stop windows-legacy

# Stacks
windflow stacks list
windflow stacks create my-app --file docker-compose.yml --host nas-server
windflow stacks create my-nextcloud --template nextcloud
windflow stacks deploy my-app
windflow stacks rollback my-app --version 2
windflow stacks versions my-app
windflow stacks validate my-app
windflow stacks rm my-app

# Snapshots consolidés
windflow compute snapshots list --host nas-server
```

## Plugins et marketplace

### Plugins

```bash
# Lister les plugins installés
windflow plugins list

# NAME              TYPE       STATUS    VERSION  RAM
# traefik           hybrid     running   1.2.0    142 MB
# postgresql-mgr    extension  running   1.0.0    28 MB
# uptime-kuma       service    running   1.0.0    98 MB

# Installer / configurer
windflow plugins install traefik
windflow plugins install restic --registry https://my-registry.local/index.json
windflow plugins config traefik --set acme_email=me@example.com
windflow plugins config traefik --show

# Cycle de vie
windflow plugins start traefik
windflow plugins stop traefik
windflow plugins update traefik
windflow plugins update --all
windflow plugins remove uptime-kuma

# Développement
windflow plugins create my-plugin --type extension
windflow plugins dev-install ./my-plugin
windflow plugins logs my-plugin
windflow plugins pack ./my-plugin
```

### Marketplace

```bash
# Parcourir et chercher
windflow marketplace search
windflow marketplace search nextcloud
windflow marketplace search --category monitoring --arch arm64

# Fiche d'une entrée
windflow marketplace info traefik
# Name: Traefik — Type: hybrid — Category: access
# Architectures: amd64, arm64 — RAM minimum: 128 MB
# Version: 1.2.0 — Installed: Yes (running)

# Installer directement / rafraîchir
windflow marketplace install nextcloud
windflow marketplace refresh

# Registres (chapitre 12)
windflow registry list
windflow registry add https://my-company.com/windflow-plugins/index.json
```

## Stockage et réseau

```bash
# Volumes
windflow volumes list --host nas-server
windflow volumes prune
windflow volumes browse nextcloud_data --path /config
windflow volumes download nextcloud_data /config/config.php ./config.php
windflow volumes upload nextcloud_data ./custom.conf /config/custom.conf

# Images Docker
windflow images list
windflow images pull postgres:15
windflow images prune
```

Le volume browser et le pruning suivent les mêmes capacités que l'UI (chapitre [14-ui-maquettes.md](14-ui-maquettes.md) et [`../user-guide/`](../user-guide)).

## Organisations, environnements et administration

### Organisations et environnements

```bash
windflow orgs list
windflow orgs create --name "homelab" --description "Mon homelab"

windflow envs list --org homelab
windflow envs create --org homelab --name production --type production
windflow envs create --org homelab --name dev --type development
```

### Administration

```bash
# Utilisateurs (détail RBAC : chapitre 08)
windflow admin user list
windflow admin user create --username alice --email alice@example.com --org homelab --role operator
windflow admin user role --username alice --org homelab --role admin
windflow admin user remove --username alice --org homelab

# Journal d'audit
windflow admin audit --last 50
windflow admin audit --user alice --action "stack.*"
windflow admin audit --since 2026-04-01

# Backup / restore (forme unique)
windflow admin backup create --output /backup/windflow-20260401.tar.gz
windflow admin backup restore --input /backup/windflow-20260401.tar.gz

# Infos système
windflow admin info
# WindFlow v1.1.0 — Mode: standard (PostgreSQL + Redis)
# Architecture: arm64 — Uptime: 15 days, 3 hours
# Plugins: 3 installed, 3 running — Hosts: 2 (2 online)
```

Les procédures complètes de backup/restore sont au chapitre [16-deploiement.md](16-deploiement.md) ; les actions auditées au chapitre [15-securite.md](15-securite.md).

À noter : `windflow admin user create` suppose une instance **fonctionnelle et authentifiée**. Pour un scénario d'instance verrouillée (admin oublié, refresh tokens expirés), les commandes `windflow admin recovery *` s'exécutent via `docker exec` sans authentification — voir « Récupération d'urgence » au chapitre [16-deploiement.md](16-deploiement.md).

## Interface TUI

Le TUI est une interface terminal interactive lancée avec `windflow tui` : vue graphique des ressources avec navigation clavier, utilisable via SSH sur des machines sans interface graphique.

### Écran principal

```
┌─ WindFlow ─────────────────────────────────────────────────┐
│ Host: nas-server (amd64) | 3 Apps running | 2 Machines    │
├──────────────────────────┬─────────────────────────────────┤
│ Resources                │ Details                         │
│                          │                                 │
│ ▸ Apps (3/5)             │ nextcloud                       │
│   ▸ nextcloud   ● run    │ Profile: docker_compose         │
│     postgres    ● run    │ Status: running (3 days)        │
│     old-app     ○ stop   │ Ports: 8080 → 80                │
│                          │ CPU: 5.2%  RAM: 234 MB          │
│ ▸ Machines (2)           │ Network: windflow-prod          │
│   ▸ ubuntu-dev  ● run    │                                 │
│                          │ [s]tart [p] sto[p] [r]estart    │
│ ▸ Stacks (2)             │ [l]ogs  [c]onsole [i]nspect     │
│   ▸ web-app    deployed  │                                 │
│     monitoring stopped   │                                 │
├──────────────────────────┴─────────────────────────────────┤
│ ↑↓ Navigate  Enter Select  h Host  m Marketplace  q Quit   │
└────────────────────────────────────────────────────────────┘
```

### Raccourcis clavier

```
Navigation : ↑/↓ liste · ←/→ panneau · Enter sélection · Esc retour
Actions    : s start · p stop · r restart · l logs · c console · i inspect · d deploy · x supprimer
Global     : Tab cycle Apps/Machines/Stacks · h changer de Host · m marketplace · / rechercher · ? aide · q quitter
```

Le TUI suit le vocabulaire des familles (Apps, Machines, Hosts) et expose les mêmes verbes universels que l'UI web (chapitre [02-familles-workloads.md](02-familles-workloads.md)).

## Configuration CLI

### Fichier de configuration

```yaml
# ~/.windflow/config.yml
url: "http://192.168.1.50:8080"    # URL de l'instance WindFlow
output: table                       # table, json, yaml
color: true                         # Activer les couleurs
pager: true                         # Pager pour les longues sorties
```

### Variables d'environnement

```bash
export WINDFLOW_URL="http://192.168.1.50:8080"
export WINDFLOW_API_KEY="wf_ak_a1b2c3d4..."    # Auth par API key
export WINDFLOW_OUTPUT="json"                    # Format de sortie
```

Priorité : arguments CLI > variables d'environnement > fichier de configuration.

### Auto-complétion

```bash
windflow --install-completion bash   # ou zsh, fish
```

### Format de sortie

```bash
# Tableau (défaut, lisible)
windflow apps list

# JSON / YAML (pour scripts et automatisation)
windflow apps list --output json
windflow apps list --output yaml

# Noms seuls (pour piping)
windflow apps list --quiet

# Utilisation dans un script
for app in $(windflow apps list --quiet --status stopped); do
    windflow apps rm "$app"
done
```

## Voir aussi

- [09-api.md](09-api.md) — API REST consommée par la CLI et le TUI
- [07-authentification.md](07-authentification.md) — mécanisme JWT/refresh et clés API
- [02-familles-workloads.md](02-familles-workloads.md) — familles et verbes universels reflétés par la grammaire CLI
- [12-marketplace.md](12-marketplace.md) — commandes marketplace et registres
- [16-deploiement.md](16-deploiement.md) — procédures d'exploitation associées
