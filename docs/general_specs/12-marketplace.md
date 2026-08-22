# Chapitre 12 — Marketplace

> **Statut** : Spec cible · **Public** : Tous · **Lié à** : [11-plugins.md](11-plugins.md), [02-familles-workloads.md](02-familles-workloads.md), [09-api.md](09-api.md)

## Vue d'ensemble

Ce chapitre spécifie la marketplace de WindFlow : structure en trois onglets (Apps multi-backend, Machine Templates, Plugins), le format **unique et complet** du registre JSON, les registres self-hosted, l'UX marketplace, et le **catalogue officiel des plugins** (compte canonique « 20+ », aligné avec [01-vision.md](01-vision.md)). Le système de plugins lui-même (manifest, lifecycle, hooks) est spécifié au chapitre [11-plugins.md](11-plugins.md).

## Structure de la marketplace

La Marketplace propose trois onglets :

```
┌─ Marketplace ────────────────────────────────────────────────┐
│                                                              │
│  [📱 Apps] [🖥️ Machine Templates] [🔌 Plugins]               │
│                                                              │
│  ── Apps ── (onglet sélectionné) ────────────────────────── │
│  Nextcloud, Gitea, Jellyfin, Home Assistant, Plex, ...       │
│  → L'utilisateur clique [Installer] → choix automatique      │
│    du backend selon les Hosts disponibles                    │
│                                                              │
│  ── Machine Templates ── (autre onglet) ──────────────────── │
│  Ubuntu 24.04, Debian 12, Alpine 3.19, Home Assistant OS,    │
│  pfSense, Rocky Linux, ...                                    │
│  → L'utilisateur clique [Créer une Machine] → wizard Machine │
│                                                              │
│  ── Plugins ── (cf. chapitre 11) ─────────────────────────── │
│  Traefik, Restic, Uptime Kuma, Trivy, Vault, ...             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Apps multi-backend

Une entrée App marketplace peut déclarer **plusieurs backends** ; WindFlow choisit le bon selon les Hosts disponibles :

```yaml
name: Nextcloud
category: cloud
backends:
  - profile: docker_compose
    available_for: [host_baremetal_with_docker, host_remote_docker]
    recommended: true
  - profile: helm_release
    available_for: [host_kubernetes]
  - profile: docker_container
    available_for: [host_baremetal_with_docker]
    note: "Configuration minimale, pour tester"
```

Exemple illustratif — une même App déployée selon le contexte : `nextcloud` en `docker_compose` sur `nas-server`, ou en `helm_release` sur le Host `k3s-cluster`. L'entrée d'origine est tracée par `marketplace_entry_id` (chapitre [06-modele-de-donnees.md](06-modele-de-donnees.md)).

Les entrées Apps du catalogue officiel couvrent notamment : Nextcloud, Immich, Photoprism (cloud) ; Gitea, Forgejo (Git) ; Jellyfin, Plex (média) ; Home Assistant (domotique) ; WordPress, Ghost (CMS) ; Baserow, NocoDB, Metabase (data) ; Plausible, Matomo (analytics) ; Mattermost, Matrix/Element (communication). Chaque template embarque un docker-compose paramétré Jinja2, un schéma de configuration (wizard), des valeurs par défaut adaptées au profil de la machine, et des labels conditionnels pour les plugins installés (ex. labels Traefik).

### Machine Templates

Les templates de Machines sont des **images OS prêtes à l'emploi** (cf. bibliothèque d'images OS, chapitre [03-modele-compute.md](03-modele-compute.md)), pas des Apps avec backends multiples :

```yaml
name: Ubuntu 24.04 LTS
category: linux
type: machine_template
image_format: qcow2
size_mb: 580
architecture: [amd64, arm64]
cloud_init: true
default_user: ubuntu
recommended_specs:
  cpu: 2
  ram_mb: 2048
  disk_gb: 20
available_for: [host_baremetal_with_kvm, host_proxmox]
```

Le wizard de création de Machine consomme directement le template choisi.

### Plugins

Les plugins sont des extensions de WindFlow (chapitre [11-plugins.md](11-plugins.md)). Ils ne créent ni Apps ni Machines ni Hosts par eux-mêmes — ils ajoutent des fonctionnalités transversales (Traefik gère les domaines de toutes les Apps, Restic sauvegarde les volumes de toutes les Apps, etc.).

## Registre de plugins

Le registre est un **index JSON statique** hébergeable n'importe où : GitHub Pages, serveur web, ou self-hosted. Pas de base de données, pas de service complexe. Ce format est la **référence unique** (les versions courtes historiques sont obsolètes) :

```json
{
  "version": 1,
  "updated_at": "2026-06-15T10:00:00Z",
  "plugins": [
    {
      "name": "traefik",
      "display_name": "Traefik",
      "version": "1.2.0",
      "type": "hybrid",
      "category": "access",
      "description": "Reverse proxy avec TLS automatique",
      "author": "WindFlow Team",
      "license": "MIT",
      "architectures": ["linux/amd64", "linux/arm64"],
      "resources": { "ram_min_mb": 128, "cpu_min_cores": 0.5 },
      "windflow_version": ">=1.1.0",
      "download_url": "https://plugins.windflow.io/packages/traefik-1.2.0.tar.gz",
      "checksum": "sha256:a1b2c3d4e5f6...",
      "icon_url": "https://plugins.windflow.io/icons/traefik.svg",
      "homepage": "https://github.com/windflow/plugin-traefik",
      "official": true
    }
  ]
}
```

Le registre officiel est `https://plugins.windflow.io/index.json` (configuré par défaut). L'ajout de registres se fait via l'API admin (`POST /api/v1/admin/registries`, chapitre [09-api.md](09-api.md)) ou la CLI :

```bash
windflow registry list
# → https://plugins.windflow.io/index.json (officiel)

windflow registry add https://my-company.com/windflow-plugins/index.json
windflow marketplace refresh
```

### Registre self-hosted

Pour un usage interne ou en réseau isolé, il suffit de servir un fichier JSON et les packages `.tar.gz` depuis n'importe quel serveur HTTP :

```
my-registry/
├── index.json            # Catalogue
└── packages/
    ├── my-plugin-1.0.0.tar.gz
    └── another-plugin-2.1.0.tar.gz
```

```bash
# Servir avec un simple serveur HTTP
cd my-registry && python -m http.server 8000

# Ajouter dans WindFlow
windflow registry add http://192.168.1.10:8000/index.json
```

## UX marketplace

La marketplace dans l'UI agrège les entrées de tous les registres configurés et affiche :

- **Catalogue** avec catégories, recherche, filtres (architecture, officiel/communautaire) ;
- **Fiche d'une entrée** : description, captures d'écran, ressources requises, dépendances, changelog ;
- **Indicateurs de compatibilité** : ✓ compatible / ✗ architecture non supportée / ⚠ ressources insuffisantes ;
- **Bouton Installer** avec wizard de configuration (chapitre 11) ;
- **Onglet « Installés »** : plugins actifs, mises à jour disponibles.

La marketplace propose en outre une section **« Recommandés pour vous »** basée sur l'état de l'infrastructure : pas de reverse proxy détecté → recommander Traefik ; pas de backup → recommander Restic. Les maquettes d'écrans sont au chapitre [14-ui-maquettes.md](14-ui-maquettes.md).

## Catalogue officiel des plugins

Le catalogue ci-dessous est la **référence canonique** des plugins officiels — c'est lui qui fixe le compte « 20+ plugins officiels » cité au chapitre [01-vision.md](01-vision.md). Chaque fiche synthétique indique le nom, le type (service / extension / hybrid) et ce que le plugin apporte. Les détails (manifest, configuration) vivent dans chaque plugin ; les capacités IA et de sécurité sont détaillées aux chapitres [18-plugins-ia.md](18-plugins-ia.md) et [15-securite.md](15-securite.md).

### Access & routage

| Plugin | Type | Apporte |
|---|---|---|
| `traefik` | hybrid | Reverse proxy, page « Domaines & Routage », association domaine ↔ service, TLS automatique Let's Encrypt |
| `caddy` | hybrid | Alternative reverse proxy, TLS automatique, configuration simple |
| `nginx-proxy-manager` | hybrid | Reverse proxy à interface graphique pour les habitués de NPM (conflit de ports avec Traefik) |
| `authelia` | service | 2FA (TOTP, WebAuthn) devant les services exposés via le reverse proxy |

### Sécurité & SSO

| Plugin | Type | Apporte |
|---|---|---|
| `keycloak` | hybrid | SSO complet (LDAP/AD, OIDC, SAML), 2FA sur le login WindFlow, mapping des rôles (chapitre 07) |
| `vault` | extension | HashiCorp Vault : rotation automatique, secrets dynamiques, audit des accès (remplace le SecretManager natif, chapitre 15) |
| `trivy` | extension | Vulnerability scanning des images avant/après déploiement, dashboard de vulnérabilités, blocage optionnel des déploiements critiques |

### Bases de données

| Plugin | Type | Apporte |
|---|---|---|
| `postgresql-manager` | extension | Détection des containers `postgres`, boutons « Créer une DB / un utilisateur / Backup SQL », vue des bases |
| `redis-manager` | extension | Détection des containers `redis`, monitoring des instances, gestion des clés |
| `mongodb-manager` | extension | Détection des containers `mongodb`, gestion des bases et utilisateurs |

### Monitoring & observabilité

| Plugin | Type | Apporte |
|---|---|---|
| `uptime-kuma` | service | Container Uptime Kuma + widget dashboard de disponibilité des services |
| `netdata` | service | Métriques système temps réel par Host, détection d'anomalies |
| `prometheus` | hybrid | Stack Prometheus + Grafana préconfigurée, alerting, historique long |
| `grafana` | service | Dashboards visualisation (utilisé seul ou avec Prometheus) |

### Backup

| Plugin | Type | Apporte |
|---|---|---|
| `restic` | extension | Page « Backups », planification cron, sélection de volumes, destinations local/SFTP/S3, historique et restauration |
| `borg` | extension | Alternative backup, dépôts chiffrés BorgBackup, planification et restauration |

### DNS & réseau

| Plugin | Type | Apporte |
|---|---|---|
| `pi-hole` | hybrid | Page « DNS », gestion des enregistrements, statistiques adblock |
| `cloudflare-dns` | extension | Gestion des enregistrements DNS Cloudflare, DNS challenge pour Let's Encrypt |
| `coredns` | hybrid | DNS interne pour les environnements WindFlow |

### Git & automatisation

| Plugin | Type | Apporte |
|---|---|---|
| `gitea` | service | Container Gitea (serveur Git) déployé en un clic |
| `git` | extension | Synchronisation des stacks depuis un dépôt Git (GitHub, GitLab, Bitbucket, Gitea), webhook auto-deploy |
| `n8n` | hybrid | Workflows d'automatisation visuels avec triggers sur les événements WindFlow (chapitre 17) |
| `node-red` | hybrid | Workflows alternatifs orientés IoT, triggers sur les événements WindFlow (chapitre 17) |

### Mail

| Plugin | Type | Apporte |
|---|---|---|
| `mailu` | service | Suite mail complète (SMTP/IMAP/Webmail) déployée et gérée |
| `stalwart` | service | Serveur mail moderne tout-en-un (SMTP/IMAP/JMAP) |

### IA

| Plugin | Type | Apporte |
|---|---|---|
| `ollama` | hybrid | LLM local, chat assistant, génération de compose, diagnostic (chapitre 18) |
| `litellm` | hybrid | Proxy multi-provider vers les APIs cloud OpenAI/Anthropic/… (chapitre 18) |

### Messagerie

| Plugin | Type | Apporte |
|---|---|---|
| `mattermost` | service | Chat d'équipe self-hosted déployé en un clic |

**Compte canonique : 28 plugins officiels**, arrondi en communication produit à « 20+ plugins officiels » (chapitre [01-vision.md](01-vision.md)). Ce tableau fait autorité en cas de divergence de comptage ; toute addition ou suppression de plugin officiel se reflète ici.

## Voir aussi

- [11-plugins.md](11-plugins.md) — système de plugins : manifest, lifecycle, événements, guide dev
- [01-vision.md](01-vision.md) — compte canonique « 20+ plugins officiels » et métriques écosystème
- [02-familles-workloads.md](02-familles-workloads.md) — modèles consommés par la marketplace (backends, profils)
- [09-api.md](09-api.md) — endpoints `/marketplace` et `/admin/registries`
- [14-ui-maquettes.md](14-ui-maquettes.md) — maquettes des écrans marketplace et wizard d'installation
