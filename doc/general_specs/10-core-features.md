# Fonctionnalités Principales - WindFlow

## Vue d'Ensemble

Ce document décrit les fonctionnalités qui font partie du **core** de WindFlow — c'est-à-dire ce qui est disponible dès l'installation, sans aucun plugin. Tout ce qui n'est pas documenté ici (reverse proxy, DNS, certificats TLS, monitoring, backup, IA, workflows, mail, SSO…) est une fonctionnalité apportée par les plugins.

### Fonctionnalités Core

| # | Fonctionnalité | Description                                                      |
|---|----------------|------------------------------------------------------------------|
| 1 | Gestion des Containers | Docker/Podman/Kube : containers, compose, images, logs, terminal |
| 2 | Gestion des VMs | KVM/libvirt, LXD, Incus                                          |
| 3 | Système de Plugins | Installation, configuration, lifecycle, registre                 |
| 4 | Marketplace | Catalogue de stacks et plugins, installation one-click           |
| 5 | Stacks & Templates | Groupes de services, versioning, templates Jinja2                |
| 6 | Gestion des Targets | Machines locales et distantes (SSH), auto-discovery              |
| 7 | Volumes & Stockage | Volumes Docker, disques VM, volume browser                       |
| 8 | Réseaux | Networks Docker / Kube, isolation par environnement              |
| 9 | Authentification & RBAC | JWT, organisations, environnements, rôles                        |
| 10 | Interface Web | Dashboard, gestion visuelle, formulaires dynamiques              |
| 11 | CLI / TUI | Ligne de commande et interface terminal interactive              |

---

## 1. Gestion des Containers Docker

La gestion Docker est le cœur de WindFlow. Elle couvre l'ensemble du cycle de vie des containers et des stacks Compose.

### Containers

**Opérations :**
- Lister, créer, démarrer, arrêter, redémarrer, supprimer des containers
- Inspecter un container (configuration, ports, volumes, réseau, variables d'environnement)
- Renommer un container
- Voir les statistiques temps réel (CPU, mémoire, réseau, I/O)

**Logs :**
- Consultation des logs avec filtres (tail, since, timestamps)
- Streaming temps réel via WebSocket
- Téléchargement des logs

**Terminal interactif :**
- Shell dans un container via WebSocket (xterm.js dans le navigateur)
- Support des commandes interactives (bash, sh, etc.)
- Copier/coller, redimensionnement automatique

```python
# Exemple : API terminal WebSocket
@router.websocket("/ws/terminal/{container_id}")
async def container_terminal(websocket: WebSocket, container_id: str):
    await websocket.accept()
    container = docker_service.get_container(container_id)
    exec_instance = container.exec_run(
        "/bin/sh", stdin=True, tty=True, stream=True, socket=True
    )
    # Bidirectional streaming entre le WebSocket et le container
    await stream_bidirectional(websocket, exec_instance)
```

### Docker Compose (Stacks)

**Opérations :**
- Déployer une stack depuis un fichier docker-compose.yml
- Arrêter, redémarrer, supprimer une stack complète
- Mettre à jour une stack (pull + recreate)
- Voir l'état de tous les services d'une stack
- Logs agrégés de tous les services d'une stack

**Pipeline de déploiement :**
- Validation du fichier compose avant déploiement
- Pull des images avec barre de progression
- Déploiement séquentiel avec retry configurable
- Rollback automatique en cas d'échec (restaure l'état précédent)
- Événements de déploiement en temps réel via WebSocket

```python
class DeploymentPipeline:
    """Pipeline de déploiement avec retry et rollback."""

    async def deploy_stack(self, stack: Stack, target: Target) -> Deployment:
        deployment = await self._create_deployment(stack)
        previous_state = await self._snapshot_current_state(stack, target)

        try:
            await self._emit_event(deployment, "validating")
            await self._validate_compose(stack.compose_content)

            await self._emit_event(deployment, "pulling_images")
            await self._pull_images(stack, target)

            await self._emit_event(deployment, "deploying")
            await self._docker_compose_up(stack, target)

            await self._emit_event(deployment, "health_checking")
            await self._wait_for_healthy(stack, target, timeout=60)

            deployment.status = "success"
        except DeploymentError as e:
            await self._emit_event(deployment, "rolling_back", error=str(e))
            await self._rollback(previous_state, target)
            deployment.status = "failed"

        return deployment
```

### Images

- Lister les images locales
- Pull une image depuis un registry (Docker Hub, registries privés)
- Supprimer des images
- Prune des images non utilisées (libérer de l'espace — important sur RPi)
- Inspecter une image (layers, taille, tags)

### Docker sur Machine Distante

Les mêmes opérations fonctionnent sur des Docker Engines distants via SSH. Pas besoin d'exposer l'API Docker sur le réseau.

```python
# Le target définit le mode de connexion
# Local : unix:///var/run/docker.sock
# Distant : ssh://user@192.168.1.50
docker_client = docker.DockerClient(base_url=target.docker_url)
```

---

## 2. Gestion des Machines Virtuelles

WindFlow gère les VMs via les hyperviseurs disponibles sur la machine cible. Le support est détecté automatiquement.

### KVM / QEMU (via libvirt) ou LXD / Incus

**Opérations VM :**
- Créer une VM (CPU, mémoire, disque, réseau, ISO/cloud-init)
- Démarrer, arrêter, redémarrer, forcer l'arrêt
- Suspendre et reprendre
- Supprimer une VM et ses disques

**Snapshots :**
- Créer un snapshot (état complet : mémoire + disque)
- Lister les snapshots d'une VM
- Restaurer un snapshot
- Supprimer un snapshot

**Clones :**
- Cloner une VM existante (full clone ou linked clone)

**Console :**
- Console VNC/SPICE intégrée au navigateur (noVNC)
- Console Terminal intégrée
- Pas de client lourd nécessaire

```python
# Exemple : création d'une VM KVM
@router.post("/api/v1/vms")
async def create_vm(config: VMCreateRequest, target: Target = Depends(get_target)):
    vm_service = get_vm_service(target)  # LibvirtService
    vm_id = await vm_service.create_vm(
        name=config.name,
        vcpus=config.vcpus,
        memory_mb=config.memory_mb,
        disk_size_gb=config.disk_size_gb,
        iso_path=config.iso_path,
        cloud_init=config.cloud_init,
    )
    return {"id": vm_id, "status": "created"}
```

**Disques :**
- Créer, redimensionner, supprimer des disques virtuels
- Formats supportés : qcow2, raw
- Conversion entre formats
- Snapshots de disques indépendants

**Images et ISOs :**
- Gestion d'une bibliothèque d'ISOs et d'images cloud
- Upload d'ISOs depuis l'UI
- Support cloud-init pour le provisionnement automatique

---

## 3. Système de Plugins

Le système de plugins est le mécanisme fondamental d'extensibilité de WindFlow. Il permet d'ajouter des fonctionnalités sans modifier le core.

### Trois Types de Plugins

**Service Plugin** — Déploie une stack Docker préconfigurée avec un wizard de configuration. L'utilisateur n'a pas besoin d'écrire de docker-compose.yml. Exemple : installer Uptime Kuma en un clic.

**Extension Plugin** — Ajoute des capacités au core (endpoints API, pages UI, réactions aux événements) sans déployer de nouveau container. Exemple : le plugin PostgreSQL détecte les containers `postgres` et ajoute des actions (créer une DB, un user, backup) dans l'interface.

**Hybrid Plugin** — Combine les deux : déploie un service ET étend le core. Exemple : le plugin Traefik déploie le container Traefik et s'intègre à l'UI pour permettre l'association domaine ↔ service.

### Installation et Gestion

**Depuis l'UI :**
- Page "Plugins" avec la liste des plugins installés
- Statut, version, consommation de ressources
- Actions : configurer, activer, désactiver, mettre à jour, désinstaller

**Depuis la CLI :**
```bash
windflow plugin install traefik
windflow plugin list
windflow plugin update traefik
windflow plugin remove traefik
windflow plugin config traefik --set acme_email=user@example.com
```

### Vérifications Automatiques

Avant d'installer un plugin, le Plugin Manager vérifie :

- **Architecture** : le plugin supporte-t-il l'architecture de la machine (arm64/amd64) ?
- **Ressources** : la machine a-t-elle assez de RAM et CPU disponibles ?
- **Dépendances** : les plugins requis sont-ils installés ? Y a-t-il des conflits ?
- **Intégrité** : le checksum du package correspond-il au registre ?

Si une vérification échoue, l'installation est refusée avec un message explicatif.

### Configuration Dynamique

Chaque plugin déclare ses paramètres de configuration dans son manifest. WindFlow génère automatiquement un formulaire dans l'UI à partir de cette déclaration :

```yaml
# Extrait du manifest d'un plugin
config:
  - key: acme_email
    label: "Email pour Let's Encrypt"
    type: string
    required: true
  - key: dashboard_enabled
    label: "Activer le dashboard"
    type: boolean
    default: true
  - key: log_level
    label: "Niveau de logs"
    type: select
    options: ["debug", "info", "warn", "error"]
    default: "info"
```

L'utilisateur remplit le formulaire, et les valeurs sont injectées dans le plugin via variables d'environnement ou fichier de configuration.

### Hooks et Événements

Les extension/hybrid plugins peuvent réagir aux événements du core :

```python
# Exemple : hook du plugin Traefik qui auto-configure le routage
class TraefikHooks:
    async def on_stack_deployed(self, event: StackDeployedEvent):
        """Appelé quand une stack est déployée."""
        for service in event.stack.services:
            if service.labels.get("windflow.domain"):
                domain = service.labels["windflow.domain"]
                await self.traefik_api.add_route(
                    domain=domain,
                    service_url=f"http://{service.container_name}:{service.port}",
                    auto_tls=True,
                )

    async def on_stack_removed(self, event: StackRemovedEvent):
        """Appelé quand une stack est supprimée."""
        await self.traefik_api.remove_routes_for_stack(event.stack.id)
```

### Exemples de Plugins Concrets

**Plugin PostgreSQL (extension)** — Détecte tout container basé sur l'image `postgres`. Ajoute dans l'UI de WindFlow :
- Bouton "Créer une base de données" avec formulaire (nom, encoding, owner)
- Bouton "Créer un utilisateur" avec gestion des permissions
- Vue des bases existantes, tailles, connexions actives
- Export/import SQL

**Plugin Traefik (hybrid)** — Déploie Traefik + s'intègre au core :
- Page "Domaines & Routage" dans le menu WindFlow
- Association domaine ↔ service en un clic
- Certificats Let's Encrypt automatiques (HTTP ou DNS challenge)
- Dashboard Traefik accessible depuis WindFlow

**Plugin Restic (extension)** — Ajoute des fonctions de backup :
- Page "Backups" avec planification (cron)
- Sélection des volumes à sauvegarder
- Destinations : disque local, SFTP, S3 (via plugin MinIO)
- Historique et restauration

---

## 4. Marketplace

La marketplace est le catalogue intégré à WindFlow pour découvrir et installer des stacks et des plugins.

### Catalogue

- Navigation par catégories (reverse proxy, bases de données, monitoring, média, collaboration…)
- Recherche par nom, description, tags
- Filtres : compatible avec mon architecture, ressources suffisantes, plugins officiels / communautaires

### Fiche Plugin/Stack

Chaque entrée du catalogue affiche :
- Nom, description, icône, captures d'écran
- Version, auteur, licence
- Architectures supportées (arm64, amd64)
- Ressources requises (RAM, CPU)
- Dépendances (autres plugins nécessaires)
- Notes d'installation et changelog

### Installation One-Click

1. L'utilisateur clique "Installer"
2. Le Plugin Manager vérifie la compatibilité
3. Si le plugin a des paramètres de configuration, un wizard s'affiche
4. L'installation se lance (téléchargement, déploiement, configuration)
5. Le plugin apparaît dans la liste "Plugins installés"

### Stacks Préconfigurées

La marketplace propose aussi des stacks d'applications complètes (pas des plugins, juste des docker-compose.yml avec wizard) :

- **Cloud personnel** : Nextcloud, Immich, Photoprism
- **Git** : Gitea, Forgejo
- **Média** : Jellyfin, Plex
- **Communication** : Mattermost, Matrix/Element
- **Domotique** : Home Assistant
- **CMS** : WordPress, Ghost
- **Data** : Baserow, NocoDB, Metabase
- **Analytics** : Plausible, Matomo

Chaque stack template inclut :
- Un docker-compose.yml paramétré avec Jinja2
- Un schéma de configuration (génère le wizard)
- Des valeurs par défaut adaptées au profil de la machine
- Des labels pour l'intégration avec les plugins installés (ex: labels Traefik si le plugin Traefik est présent)

---

## 5. Stacks & Templates

### Gestion des Stacks

Une stack dans WindFlow est un groupe de services Docker déployés ensemble (équivalent d'un projet Docker Compose).

**Opérations :**
- Créer une stack depuis un docker-compose.yml écrit manuellement
- Créer depuis un template de la marketplace
- Créer depuis un dépôt Git (avec plugin Git)
- Éditer le compose dans l'éditeur YAML intégré à l'UI
- Versioning : chaque modification crée une nouvelle version
- Rollback vers une version précédente
- Variables d'environnement par stack, avec chiffrement des valeurs sensibles

### Templates Jinja2

Les templates de stacks utilisent Jinja2 pour la paramétrisation :

```yaml
# Template paramétré
version: "3.8"
services:
  app:
    image: {{ app_image }}:{{ app_version | default('latest') }}
    ports:
      - "{{ app_port | default('8080') }}:8080"
    environment:
      DATABASE_URL: postgresql://{{ db_user }}:{{ db_password }}@db:5432/{{ db_name }}
    {% if traefik_enabled %}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.{{ stack_name }}.rule=Host(`{{ domain }}`)"
    {% endif %}

  db:
    image: postgres:15
    volumes:
      - db_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: {{ db_name }}
      POSTGRES_USER: {{ db_user }}
      POSTGRES_PASSWORD: {{ db_password }}

volumes:
  db_data:
```

Les variables sont renseignées via le wizard de configuration ou la CLI :

```bash
windflow stack create my-app \
  --template web-app-postgresql \
  --set app_image=myapp --set app_port=3000 \
  --set db_name=mydb --set db_user=admin --set db_password=secret
```

### Formulaires Dynamiques

Chaque template peut déclarer un schéma de configuration (Pydantic/JSON Schema) qui génère automatiquement un formulaire dans l'UI :

```yaml
# Schéma de configuration du template
config_schema:
  - key: app_image
    label: "Image de l'application"
    type: string
    required: true
  - key: app_port
    label: "Port exposé"
    type: integer
    default: 8080
  - key: db_password
    label: "Mot de passe PostgreSQL"
    type: password
    required: true
    generate: true  # Propose de générer un mot de passe aléatoire
  - key: domain
    label: "Nom de domaine (optionnel)"
    type: string
    required: false
    visible_if: traefik_installed  # Affiché seulement si le plugin Traefik est installé
```

---

## 6. Gestion des Targets (Machines Cibles)

### Types de Targets

**Local** — La machine sur laquelle WindFlow est installé. Docker et/ou libvirt sont détectés automatiquement.

**SSH** — Une machine distante accessible via SSH. WindFlow détecte automatiquement ce qui est disponible (Docker, libvirt, LXD) sur la machine distante.

### Discovery Automatique

Quand un target est ajouté, WindFlow détecte ses capacités :

```python
class TargetDiscovery:
    async def discover(self, target: Target) -> dict:
        """Détecte les capacités d'une machine cible."""
        capabilities = {}

        # Docker disponible ?
        if await self._check_docker(target):
            capabilities["docker"] = {
                "version": await self._get_docker_version(target),
                "containers": await self._count_containers(target),
            }

        # libvirt disponible ?
        if await self._check_libvirt(target):
            capabilities["libvirt"] = {
                "hypervisor": await self._get_hypervisor_type(target),
                "vms": await self._count_vms(target),
            }

        # LXD API disponible ?
        if await self._check_LXD(target):
            capabilities["LXD"] = {
                "version": await self._get_LXD_version(target),
                "nodes": await self._list_nodes(target),
            }

        # Ressources système
        capabilities["system"] = {
            "arch": await self._get_arch(target),       # amd64, arm64
            "cpu_cores": await self._get_cpu_count(target),
            "memory_mb": await self._get_memory(target),
            "disk_gb": await self._get_disk_space(target),
            "os": await self._get_os_info(target),
        }

        return capabilities
```

### Vue Consolidée

Le dashboard affiche une vue globale de tous les targets avec :
- État de la connexion (en ligne / hors ligne)
- Ressources utilisées vs disponibles (CPU, RAM, disque)
- Nombre de containers et VMs par machine
- Alertes (machine pleine, connexion perdue)

### Monitoring Basique

Le core fournit un monitoring basique des targets :
- CPU, mémoire, disque, réseau (collecté via SSH ou agent)
- Historique court (dernières 24h en base)
- Alertes simples (seuils configurables)

Pour un monitoring avancé (dashboards, historique long, alerting multi-canal), les plugins Netdata, Uptime Kuma ou Prometheus + Grafana sont recommandés.

---

## 7. Volumes & Stockage

### Volumes Docker

**Opérations :**
- Lister les volumes avec taille et containers associés
- Créer et supprimer des volumes
- Identifier et nettoyer les volumes orphelins (important sur RPi pour libérer de l'espace)

### Volume Browser

Un file browser intégré à l'UI permet de naviguer dans le contenu des volumes sans accès SSH :

- **Arborescence** : navigation dans les dossiers
- **Preview** : affichage de fichiers texte, logs, images
- **Édition** : modification de fichiers de configuration directement depuis le navigateur
- **Upload/Download** : envoyer ou récupérer des fichiers
- **Permissions** : affichage des permissions fichiers

Le volume browser fonctionne en montant temporairement le volume dans un container utilitaire léger.

### Disques VM

Pour les machines virtuelles gérées par WindFlow :

- Créer, redimensionner, supprimer des disques virtuels
- Formats : qcow2, raw (KVM), vdi (VirtualBox), vmdk (VMware)
- Conversion entre formats (`qemu-img convert`)
- Snapshots de disques

---

## 8. Réseaux Docker

### Gestion des Networks

- Lister les networks avec containers connectés
- Créer des networks (bridge, overlay, macvlan)
- Supprimer des networks
- Connecter/déconnecter un container d'un network
- Inspecter un network (subnet, gateway, IPAM)

### Isolation par Environnement

Chaque environnement (dev, staging, prod) peut avoir son propre network Docker isolé. Les containers d'un environnement ne voient pas ceux des autres par défaut.

```python
class NetworkIsolation:
    async def create_environment_network(self, environment: Environment) -> str:
        """Crée un network Docker isolé pour un environnement."""
        network_name = f"windflow-{environment.organization.name}-{environment.name}"
        network = self.docker.networks.create(
            name=network_name,
            driver="bridge",
            labels={
                "windflow.environment": environment.id,
                "windflow.organization": environment.organization.id,
            },
        )
        return network.id
```

Les stacks déployées dans un environnement sont automatiquement connectées au network de cet environnement.

---

## 9. Authentification & RBAC

### Authentification

- **JWT** avec access token (courte durée) + refresh token (longue durée)
- Hashage des mots de passe (bcrypt)
- Protection brute-force (rate limiting sur `/auth/login`)
- Pas de dépendance externe — fonctionne out of the box
- SSO disponible via le plugin Keycloak (LDAP/AD, OIDC, SAML)

### Organisations et Environnements

- Un utilisateur appartient à une ou plusieurs **organisations**
- Chaque organisation contient des **environnements** (dev, staging, prod, ou noms libres)
- Les targets, stacks et ressources sont scopés par environnement

### RBAC (Role-Based Access Control)

Rôles par défaut :

| Rôle | Containers | VMs | Stacks | Plugins | Targets | Users |
|------|-----------|-----|--------|---------|---------|-------|
| **Viewer** | Lire | Lire | Lire | Lire | Lire | — |
| **Operator** | Lire, Déployer | Lire, Démarrer/Arrêter | Lire, Déployer | Lire | Lire | — |
| **Admin** | Tout | Tout | Tout | Installer/Supprimer | Ajouter/Supprimer | Gérer |
| **Super Admin** | Tout | Tout | Tout | Tout | Tout | Tout (toutes orgs) |

Les permissions sont attribuées par organisation. Un utilisateur peut être Admin dans une organisation et Viewer dans une autre.

---

## 10. Interface Web

### Dashboard

Page d'accueil avec une vue d'ensemble de l'infrastructure :

- Nombre de containers (running / stopped / total)
- Nombre de VMs (running / stopped / total)
- Ressources système (CPU, RAM, disque) par target
- Derniers déploiements (statut, date, durée)
- Alertes actives
- Widgets des plugins installés (ex : statut Uptime Kuma, routes Traefik)

### Pages Principales

- **Containers** : liste, actions, logs, terminal, stats
- **VMs** : liste, actions, console VNC, snapshots
- **Stacks** : liste, déploiement, éditeur YAML, historique versions
- **Targets** : machines connectées, ressources, capabilities
- **Marketplace** : catalogue, recherche, installation
- **Plugins** : plugins installés, configuration, statut
- **Settings** : organisations, environnements, utilisateurs, RBAC

### Fonctionnalités UI Transversales

- **Notifications temps réel** : événements de déploiement, alertes, installations de plugins
- **Éditeur YAML** avec coloration syntaxique et validation
- **Formulaires dynamiques** générés depuis les schémas Pydantic des stacks et plugins
- **Responsive** : utilisable sur tablette et mobile (lecture et actions simples)
- **Thème sombre / clair**

---

## 11. CLI / TUI

### CLI (Rich + Typer)

Interface en ligne de commande pour l'automatisation et les scripts :

```bash
# Containers
windflow containers list
windflow containers logs my-app --tail 50 --follow
windflow containers exec my-app -- /bin/sh

# VMs
windflow vms list
windflow vms create my-vm --cpus 2 --memory 2048 --disk 20
windflow vms snapshot my-vm --name before-update

# Stacks
windflow stacks deploy my-stack
windflow stacks deploy my-stack --target remote-server
windflow stacks rollback my-stack --version 3

# Plugins
windflow plugin install traefik
windflow plugin list
windflow plugin config traefik --set acme_email=me@example.com

# Marketplace
windflow marketplace search nextcloud
windflow marketplace install nextcloud

# Targets
windflow targets add my-server --type ssh --host 192.168.1.50 --user deploy
windflow targets discover my-server

# Backup core
windflow backup create --output /backup/windflow.tar.gz
windflow backup restore --input /backup/windflow.tar.gz
```

### TUI (Textual)

Interface terminal interactive pour la gestion quotidienne :

- Vue tabulaire des containers et VMs avec actions clavier
- Navigation entre targets
- Logs en streaming
- Raccourcis clavier pour les actions courantes (deploy, restart, stop)
- Fonctionne via SSH sur des machines sans interface graphique

---

## Ce que les Plugins Ajoutent (exemples)

Pour clarifier la frontière core/plugins, voici ce que les plugins les plus courants ajoutent à WindFlow :

| Plugin | Ce qu'il ajoute |
|--------|-----------------|
| **Traefik** | Page "Domaines", association domaine ↔ service, TLS automatique |
| **PostgreSQL** | Boutons "Créer DB/User" sur les containers postgres, vue des bases |
| **Uptime Kuma** | Widget dashboard avec statut des services, page monitoring |
| **Restic** | Page "Backups", planification, sélection de volumes, restauration |
| **Pi-hole** | Page "DNS", gestion des enregistrements, stats adblock |
| **Authelia** | 2FA devant les services exposés, page de configuration |
| **Ollama + LiteLLM** | Chat assistant dans l'UI, génération de docker-compose, diagnostic |
| **n8n** | Page "Workflows", triggers sur événements WindFlow |
| **Keycloak** | SSO, intégration LDAP/AD, remplacement de l'auth JWT native |

Chaque plugin est documenté individuellement. Voir la [documentation plugins](plugin-development.md) pour créer vos propres plugins.

---

**Références :**
- [Vue d'Ensemble](01-overview.md) - Vision et contexte
- [Architecture](02-architecture.md) - Architecture et système de plugins
- [Stack Technologique](03-technology-stack.md) - Technologies utilisées
- [LLM Integration](17-llm-integration.md) - Plugin IA (Ollama, LiteLLM)
- [Roadmap](18-roadmap.md) - Plan de développement
