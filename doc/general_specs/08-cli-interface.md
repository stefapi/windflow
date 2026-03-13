# Interface CLI/TUI - WindFlow

## Vue d'Ensemble

WindFlow propose une interface en ligne de commande (CLI) et une interface terminal interactive (TUI) comme alternatives à l'interface web. Les deux utilisent la même API REST que le frontend.

**Technologies :**
- **Typer** : Framework CLI avec auto-complétion et aide auto-générée
- **Rich** : Formatage avancé (tableaux, couleurs, barres de progression)
- **Textual** : Interface TUI interactive

### Installation

```bash
# Inclus dans WindFlow — accessible via Docker
docker exec -it windflow-api windflow --help

# Ou installation locale (pour gérer une instance distante)
pip install windflow-cli
windflow --help
```

---

## Référence des Commandes

### Auth — Authentification

```bash
# Login interactif
windflow auth login
# Username: admin
# Password: ********
# ✓ Connected to http://localhost:8080 as admin

# Login vers une instance distante
windflow auth login --url http://192.168.1.50:8080

# Login par API key
windflow auth login --api-key wf_ak_a1b2c3d4...

# Statut de la session
windflow auth status
# Instance: http://192.168.1.50:8080
# User: admin (Super Admin)
# Token expires: in 24 minutes

# Déconnexion
windflow auth logout

# Gestion des API keys
windflow auth api-key create --name "CI/CD" --expires 90d
# → wf_ak_x7y8z9... (affiché une seule fois)

windflow auth api-key list
# NAME       CREATED      EXPIRES      LAST USED
# CI/CD      2026-03-15   2026-06-13   2026-04-02

windflow auth api-key revoke --name "CI/CD"
```

### Containers — Gestion Docker

```bash
# Lister les containers
windflow containers list
windflow containers list --target my-server
windflow containers list --status running

# Exemple de sortie :
# NAME          IMAGE              STATUS    PORTS          TARGET
# nextcloud     nextcloud:28       running   8080→80        local
# postgres-1    postgres:15        running   5432→5432      local
# redis         redis:7-alpine     running   6379→6379      local
# old-app       myapp:1.0          stopped   —              local

# Détails d'un container
windflow containers inspect nextcloud

# Démarrer / Arrêter / Redémarrer
windflow containers start nextcloud
windflow containers stop nextcloud
windflow containers restart nextcloud

# Supprimer
windflow containers rm old-app
windflow containers rm old-app --force  # Force kill + remove

# Logs
windflow containers logs nextcloud
windflow containers logs nextcloud --tail 50 --follow
windflow containers logs nextcloud --since 1h

# Terminal interactif
windflow containers exec nextcloud
windflow containers exec nextcloud -- /bin/bash
windflow containers exec nextcloud -- ls -la /var/www

# Stats temps réel
windflow containers stats nextcloud
# CPU: 12.3%  MEM: 245 MB / 512 MB  NET I/O: 1.2 MB / 340 KB
```

### VMs — Machines Virtuelles

```bash
# Lister les VMs
windflow vms list
windflow vms list --target proxmox-server
windflow vms list --status running

# NAME         HYPERVISOR   STATUS    vCPU  RAM     TARGET
# ubuntu-dev   kvm          running   2     2048    local
# windows-10   proxmox      stopped   4     8192    proxmox-1

# Créer une VM
windflow vms create my-vm \
  --target local \
  --cpus 2 --memory 2048 --disk 20 \
  --iso /var/lib/libvirt/images/ubuntu-22.04.iso

# Créer avec cloud-init
windflow vms create my-vm \
  --target local \
  --cpus 2 --memory 2048 --disk 20 \
  --cloud-image ubuntu-22.04 \
  --cloud-init user-data.yml

# Démarrer / Arrêter
windflow vms start my-vm
windflow vms stop my-vm
windflow vms force-stop my-vm

# Snapshots
windflow vms snapshot create my-vm --name "before-update"
windflow vms snapshot list my-vm
windflow vms snapshot restore my-vm --name "before-update"
windflow vms snapshot delete my-vm --name "before-update"

# Supprimer
windflow vms rm my-vm
windflow vms rm my-vm --delete-disks
```

### Stacks — Docker Compose

```bash
# Lister les stacks
windflow stacks list
windflow stacks list --target my-server --status deployed

# NAME         TARGET    STATUS     VERSION  SERVICES
# web-app      local     deployed   3        nginx, api, postgres
# monitoring   local     stopped    1        grafana, prometheus

# Créer une stack depuis un compose
windflow stacks create my-app --file docker-compose.yml --target local

# Créer depuis un template marketplace
windflow stacks create my-nextcloud --template nextcloud --target local

# Éditer le compose d'une stack (ouvre $EDITOR)
windflow stacks edit my-app

# Déployer
windflow stacks deploy my-app
windflow stacks deploy my-app --target remote-server

# Arrêter tous les services
windflow stacks stop my-app

# Rollback à la version précédente
windflow stacks rollback my-app
windflow stacks rollback my-app --version 2

# Historique des versions
windflow stacks versions my-app
# VERSION  DATE                DEPLOYED BY  STATUS
# 3        2026-04-01 14:30    admin        deployed
# 2        2026-03-28 10:15    admin        rolled_back
# 1        2026-03-25 09:00    admin        —

# Historique des déploiements
windflow stacks deployments my-app
# ID         STATUS    STARTED              DURATION  BY
# dep-abc    success   2026-04-01 14:30     45s       admin
# dep-def    failed    2026-03-30 16:00     12s       alice
# dep-ghi    success   2026-03-28 10:15     38s       admin

# Valider un compose sans déployer
windflow stacks validate my-app

# Supprimer
windflow stacks rm my-app
```

### Targets — Machines Cibles

```bash
# Lister les targets
windflow targets list

# NAME           TYPE    HOST              STATUS   DOCKER  KVM  PROXMOX
# local          local   —                 online   ✓       ✓    —
# remote-srv     ssh     192.168.1.50      online   ✓       —    —
# proxmox-1      proxmox 192.168.1.100     online   —       —    ✓

# Ajouter un target SSH
windflow targets add my-server \
  --type ssh \
  --host 192.168.1.50 \
  --user deploy \
  --key ~/.ssh/id_rsa \
  --env production

# Ajouter un target Proxmox
windflow targets add my-proxmox \
  --type proxmox \
  --host 192.168.1.100 \
  --token-id user@pam!windflow \
  --token-secret abc123... \
  --env production

# Lancer la détection des capabilities
windflow targets discover my-server
# ✓ Docker 24.0.7 detected
# ✓ Docker Compose 2.23.0 detected
# ✗ libvirt not found
# System: Debian 12, arm64, 4 cores, 4096 MB RAM, 64 GB disk

# Voir les ressources d'un target
windflow targets resources my-server
# CPU: 23% (4 cores)  RAM: 1.8 GB / 4.0 GB  DISK: 28 GB / 64 GB

# Supprimer un target
windflow targets rm my-server
```

### Plugins — Gestion des Plugins

```bash
# Lister les plugins installés
windflow plugins list

# NAME              TYPE       STATUS    VERSION  RAM
# traefik           hybrid     running   1.2.0    142 MB
# postgresql-mgr    extension  running   1.0.0    28 MB
# uptime-kuma       service    running   1.0.0    98 MB

# Installer un plugin
windflow plugins install traefik
windflow plugins install restic --registry https://my-registry.local/index.json

# Configurer un plugin
windflow plugins config traefik --set acme_email=me@example.com
windflow plugins config traefik --set dashboard_enabled=true

# Voir la config d'un plugin
windflow plugins config traefik --show

# Démarrer / Arrêter
windflow plugins start traefik
windflow plugins stop traefik

# Mettre à jour
windflow plugins update traefik
windflow plugins update --all

# Désinstaller
windflow plugins remove uptime-kuma
```

### Marketplace — Catalogue

```bash
# Parcourir le catalogue
windflow marketplace search
windflow marketplace search nextcloud
windflow marketplace search --category monitoring
windflow marketplace search --category database --arch arm64

# Voir la fiche d'un plugin/stack
windflow marketplace info traefik
# Name: Traefik
# Type: hybrid
# Category: access
# Architectures: amd64, arm64
# RAM minimum: 128 MB
# Description: Reverse proxy avec TLS automatique via Let's Encrypt
# Version: 1.2.0
# Installed: Yes (running)

# Installer directement depuis la marketplace
windflow marketplace install nextcloud

# Rafraîchir le catalogue
windflow marketplace refresh
```

### Volumes — Gestion des Volumes

```bash
# Lister les volumes
windflow volumes list
windflow volumes list --target local

# NAME                    DRIVER  SIZE     USED BY
# nextcloud_data          local   2.1 GB   nextcloud
# postgres_data           local   890 MB   postgres-1
# orphan_volume           local   45 MB    —

# Nettoyer les volumes orphelins
windflow volumes prune
# Will remove 1 orphan volume(s) (45 MB). Continue? [y/N]

# Naviguer dans un volume (file browser CLI)
windflow volumes browse nextcloud_data
windflow volumes browse nextcloud_data --path /config

# Télécharger un fichier depuis un volume
windflow volumes download nextcloud_data /config/config.php ./config.php

# Uploader un fichier dans un volume
windflow volumes upload nextcloud_data ./custom.conf /config/custom.conf
```

### Images — Images Docker

```bash
# Lister les images
windflow images list
windflow images list --target local

# Pull une image
windflow images pull postgres:15
windflow images pull --target remote-server postgres:15

# Nettoyer les images non utilisées
windflow images prune
# Will remove 5 unused image(s) (1.2 GB). Continue? [y/N]
```

### Organizations & Environments

```bash
# Organisations
windflow orgs list
windflow orgs create --name "homelab" --description "Mon homelab"

# Environnements
windflow envs list --org homelab
windflow envs create --org homelab --name production --type production
windflow envs create --org homelab --name dev --type development
```

### Admin — Administration

```bash
# Gestion des utilisateurs
windflow admin user list
windflow admin user create --username alice --email alice@example.com --org homelab --role operator
windflow admin user role --username alice --org homelab --role admin
windflow admin user remove --username alice --org homelab

# Journal d'audit
windflow admin audit --last 50
windflow admin audit --user alice --action "stack.*"
windflow admin audit --since 2026-04-01

# Backup / Restore
windflow admin backup --output /backup/windflow-$(date +%Y%m%d).tar.gz
windflow admin restore --input /backup/windflow-20260401.tar.gz

# Infos système
windflow admin info
# WindFlow v1.1.0
# Mode: standard (PostgreSQL + Redis)
# Architecture: arm64
# Uptime: 15 days, 3 hours
# Plugins: 3 installed, 3 running
# Targets: 2 (1 online, 1 offline)
```

---

## Interface TUI

Le TUI est une interface terminal interactive lancée avec `windflow tui`. Elle offre une vue graphique des ressources avec navigation clavier.

### Lancement

```bash
windflow tui
```

### Écran Principal

```
┌─ WindFlow ─────────────────────────────────────────────────┐
│ Target: local (arm64) | 2 containers running | 1 VM       │
├──────────────────────────┬─────────────────────────────────┤
│ Resources                │ Details                         │
│                          │                                 │
│ ▸ Containers (2/3)       │ nextcloud                       │
│   ▸ nextcloud   ● run    │ Image: nextcloud:28             │
│     postgres-1  ● run    │ Status: running (3 days)        │
│     old-app     ○ stop   │ Ports: 8080 → 80               │
│                          │ CPU: 5.2%  RAM: 234 MB          │
│ ▸ VMs (1/1)              │ Network: windflow-prod          │
│   ▸ ubuntu-dev  ● run    │                                 │
│                          │ [s]tart [p]sto[p] [r]estart     │
│ ▸ Stacks (2)             │ [l]ogs  [t]erminal [i]nspect    │
│   ▸ web-app    deployed  │                                 │
│     monitoring stopped   │                                 │
│                          │                                 │
├──────────────────────────┴─────────────────────────────────┤
│ ↑↓ Navigate  Enter Select  t Target  m Marketplace  q Quit │
└────────────────────────────────────────────────────────────┘
```

### Raccourcis Clavier

```
Navigation :
  ↑/↓         Naviguer dans la liste
  ←/→         Changer de panneau
  Enter       Sélectionner / Développer
  Esc         Retour / Fermer

Actions :
  s           Démarrer (container / VM / stack)
  p           Arrêter
  r           Redémarrer
  l           Voir les logs (streaming)
  t           Terminal interactif
  i           Inspecter (détails complets)
  d           Déployer (stack)
  x           Supprimer

Navigation globale :
  Tab         Basculer entre Containers / VMs / Stacks
  t           Changer de target
  m           Ouvrir la marketplace
  P           Voir les plugins installés
  /           Rechercher
  ?           Aide
  q           Quitter
```

### Écran Logs

```
┌─ Logs: nextcloud ─────────────────────────────────────────┐
│ 2026-04-01 14:30:01 [INFO] Apache started                  │
│ 2026-04-01 14:30:02 [INFO] Nextcloud ready                 │
│ 2026-04-01 14:31:15 [INFO] GET /status.php 200             │
│ 2026-04-01 14:31:16 [INFO] GET /apps/dashboard/ 200        │
│ 2026-04-01 14:32:00 [WARN] Slow query detected (2.1s)      │
│ ▌                                                          │
├────────────────────────────────────────────────────────────┤
│ f Follow  /Search  ↑↓ Scroll  Esc Back                     │
└────────────────────────────────────────────────────────────┘
```

### Implémentation

```python
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Tree, Static, DataTable, Log

class WindFlowTUI(App):
    """Interface TUI principale."""

    CSS_PATH = "windflow.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("t", "change_target", "Target"),
        ("m", "marketplace", "Marketplace"),
        ("tab", "cycle_view", "Cycle"),
        ("/", "search", "Search"),
        ("?", "help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Horizontal(
            Vertical(
                Tree("Resources", id="resource-tree"),
                id="left-panel",
            ),
            Vertical(
                Static("Select a resource", id="details"),
                id="right-panel",
            ),
        )
        yield Footer()

    async def on_mount(self):
        tree = self.query_one("#resource-tree", Tree)
        await self._populate_tree(tree)

    async def _populate_tree(self, tree: Tree):
        """Charge les containers, VMs et stacks dans l'arbre."""
        containers = await self.api.get("/containers")
        vms = await self.api.get("/vms")
        stacks = await self.api.get("/stacks")

        c_node = tree.root.add("Containers", expand=True)
        for c in containers:
            status = "●" if c["status"] == "running" else "○"
            c_node.add_leaf(f"{status} {c['name']}", data={"type": "container", "id": c["id"]})

        v_node = tree.root.add("VMs", expand=True)
        for v in vms:
            status = "●" if v["status"] == "running" else "○"
            v_node.add_leaf(f"{status} {v['name']}", data={"type": "vm", "id": v["id"]})

        s_node = tree.root.add("Stacks", expand=True)
        for s in stacks:
            s_node.add_leaf(f"{s['name']} [{s['status']}]", data={"type": "stack", "id": s["id"]})
```

---

## Configuration CLI

### Fichier de Configuration

```yaml
# ~/.windflow/config.yml
url: "http://192.168.1.50:8080"    # URL de l'instance WindFlow
output: table                       # table, json, yaml
color: true                         # Activer les couleurs
pager: true                         # Utiliser un pager pour les longues sorties
```

### Variables d'Environnement

```bash
export WINDFLOW_URL="http://192.168.1.50:8080"
export WINDFLOW_API_KEY="wf_ak_a1b2c3d4..."    # Auth par API key
export WINDFLOW_OUTPUT="json"                    # Format de sortie
```

Les variables d'environnement ont priorité sur le fichier de configuration. Les arguments CLI ont priorité sur tout.

### Auto-Complétion

```bash
# Bash
windflow --install-completion bash

# Zsh
windflow --install-completion zsh

# Fish
windflow --install-completion fish
```

### Format de Sortie

```bash
# Tableau (défaut, lisible)
windflow containers list

# JSON (pour scripts et automatisation)
windflow containers list --output json

# YAML
windflow containers list --output yaml

# Juste les noms (pour piping)
windflow containers list --quiet
# nextcloud
# postgres-1
# redis

# Utilisation dans un script
for c in $(windflow containers list --quiet --status stopped); do
    windflow containers rm "$c"
done
```

---

**Références :**
- [API Design](07-api-design.md) — API consommée par la CLI
- [Authentification](05-authentication.md) — Auth CLI et API keys
- [Fonctionnalités Principales](10-core-features.md) — Fonctionnalités accessibles via CLI
- [Guide de Déploiement](15-deployment-guide.md) — Installation
