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
    available_for: [cluster_kubernetes]
  - profile: docker_container
    available_for: [host_baremetal_with_docker]
    note: "Configuration minimale, pour tester"
```

Exemple illustratif — une même App déployée selon le contexte : `nextcloud` en `docker_compose` sur `nas-server`, ou en `helm_release` sur le Cluster `k3s-cluster`. L'entrée d'origine est tracée par `marketplace_entry_id` (chapitre [06-modele-de-donnees.md](06-modele-de-donnees.md)).

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

Deux plugins officiels font l'objet d'une spécification détaillée dans ce chapitre : le plugin `git` (GitOps complet — [Spécification du plugin Git (GitOps)](#spécification-du-plugin-git-gitops)) et les sources de templates externes consommées par l'onglet Apps ([Sources de templates externes (format Portainer)](#sources-de-templates-externes-format-portainer)).

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
| `trivy` | extension | Vulnerability scanning des images avant/après déploiement, dashboard de vulnérabilités, blocage optionnel des déploiements critiques (gate pre-deploy et matrice de critères : chapitre [11-plugins.md](11-plugins.md) § Hooks de déploiement) |

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
| `restic` | extension | Page « Backups », planification cron, sélection de volumes, destinations local/SFTP/S3, historique et restauration — **implémentation de référence du verbe Sauvegarder** (invariants de sûreté et taxonomie d'erreurs fermée : « Sémantique du verbe Sauvegarder », chapitre [02-familles-workloads.md](02-familles-workloads.md)) |
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
| `git` | extension | Synchronisation des stacks depuis un dépôt Git (GitHub, GitLab, Bitbucket, Gitea), webhook auto-deploy — spécification complète : [Spécification du plugin Git (GitOps)](#spécification-du-plugin-git-gitops) |
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

## Spécification du plugin Git (GitOps)

Cette section détaille le plugin `git` (extension, catégorie « Git & automatisation »). GitOps est un **rôle de plugin**, pas une capacité native du core : le core expose seulement le champ `stacks.git_url` du modèle de données (chapitre [06-modele-de-donnees.md](06-modele-de-donnees.md)). Les grands principes du système de plugins (manifest, cycle de vie, hooks) s'appliquent tels quels (chapitre [11-plugins.md](11-plugins.md)).

### Vue d'ensemble

Le plugin Git est un **producteur de stacks** : une stack Git est une stack Compose (chapitre [03-modele-compute.md](03-modele-compute.md)) dont les fichiers proviennent d'un **sous-chemin d'un dépôt Git**. La synchronisation clone (ou re-clone) le dépôt localement via la **CLI Git invoquée en sous-processus**, détecte les changements, met à jour le répertoire de déploiement de la stack, puis déclenche le déploiement standard si du contenu a changé.

- chaque stack Git possède son **propre clone** du dépôt (répertoire `DATA_DIR/git-repos/{org_name}/{stack_name}/`) — deux stacks d'un même dépôt ne partagent pas leur historique local ;
- la synchronisation **re-clône systématiquement** (clone *blobless* : commits complets, blobs à la demande) pour garantir un état propre face aux changements de branche/URL/credentials ou aux force-pushs ;
- l'état de synchronisation (`sync_status` : `pending | syncing | synced | error`, dernier commit, dernière erreur) est visible dans l'UI et exposé par l'API ;
- les déploiements suivent le pipeline standard : événements `deployment.*` et progression sur `WS /ws/deploy/{deployment_id}` (chapitre [09-api.md](09-api.md)).

### Credentials Git

Credentials réutilisables, référencés par zéro à N dépôts :

| Champ | Rôle |
|---|---|
| `name` | Nom unique d'affichage |
| `auth_type` | `none` \| `password` (HTTPS) \| `ssh` |
| `username` / `password` | Couple HTTPS (mot de passe ou jeton PAT GitHub/GitLab/Gitea) |
| `ssh_private_key` / `ssh_passphrase` | Clé privée OpenSSH + passphrase optionnelle |

**Invariants de sécurité :**

- tous les champs sensibles sont **chiffrés au repos** via le `SecretManager` du core (chapitre [15-securite.md](15-securite.md)) et **jamais retournés par l'API** — la liste n'expose que des indicateurs `has_password` / `has_ssh_key` ;
- les credentials **ne passent jamais par l'URL** : HTTPS via l'en-tête `Authorization: Basic` injecté par variables d'environnement Git (`http.extraHeader`), SSH via un fichier temporaire `0600` unique par opération référencé par `GIT_SSH_COMMAND` (`IdentitiesOnly=yes`, pas d'agent), supprimé après usage ;
- sans credential SSH, l'authentification par clé est explicitement **désactivée** — aucune clé de l'hôte WindFlow n'est utilisée.

### Stacks synchronisées

Une stack Git est créée depuis un dépôt (URL + branche, défaut `main`) ou rattachée à un dépôt existant via le champ `stacks.git_url` (chapitre [06-modele-de-donnees.md](06-modele-de-donnees.md)) :

- **chemin Compose** dans le dépôt (défaut `docker-compose.yml`) et **répertoire de contexte** optionnel (`context_dir`) pour les monorepos — le répertoire de contexte doit rester dans le clone et le Compose dans ce répertoire (erreurs explicites sinon) ;
- **fichier `.env` du dépôt** optionnel (chemin configurable) : copié tel quel, il ne reçoit jamais les secrets de WindFlow ;
- **variables d'override WindFlow** : les variables saisies dans WindFlow sont écrites dans un fichier d'override dédié `.env.windflow` superposé au déploiement (priorité de fusion : `.env` du dépôt < override WindFlow < secrets injectés par le résolveur de secrets, chapitre [15-securite.md](15-securite.md)) ;
- **déclencheurs** : manuel (`windflow stacks deploy`), planifié (cron du scheduler core, chapitre [17-automatisation-workflows.md](17-automatisation-workflows.md)) ou webhook (ci-dessous) — une synchronisation déjà en cours (`syncing`) refuse toute nouvelle demande, et les syncs planifiées/webhooks **sautent proprement** tant qu'aucun changement n'est détecté.

### Surimpression sans effacement

Le répertoire de déploiement d'une stack Git peut contenir des **données persistantes** : un Compose qui monte `./data` crée un répertoire de données vivant dans le répertoire de la stack. La synchronisation recopie donc le répertoire source du clone **par-dessus** le répertoire de la stack, **sans effacement préalable** (copie récursive filtrant `.git`) :

- les volumes et données relatifs (`./data`…) **survivent** à chaque synchronisation ;
- les fichiers modifiés localement ne sont **jamais écrasés silencieusement** : un fichier local dont le contenu diverge du dépôt est conservé et signalé dans le résumé de synchronisation ;
- seuls les fichiers disparus du dépôt sont candidats à la suppression — exclusivement via le mécanisme vérifié ci-dessous.

### Manifeste des fichiers synchronisés et suppression vérifiée

Chaque stack Git porte un **manifeste JSON** `{ "commit", "files" }` : le mapping chemin relatif → **empreinte SHA-256** de chaque fichier écrit par la dernière synchronisation réussie. C'est la **référence de propriété** : seuls les fichiers listés ont été écrits par WindFlow et sont éligibles à la suppression automatique.

À chaque synchronisation :

1. chaque fichier du clone est haché (SHA-256) ;
2. chaque entrée du manifeste **absente du nouveau clone** devient candidate à la suppression — un manifeste vide ou illisible vaut manifeste vide (**rien à supprimer**, échec fermé) ;
3. **garde de sanité** : si le parcours du clone paraît cassé (aucun fichier, ou le Compose lui-même absent), toutes les suppressions de la synchronisation sont annulées ;
4. la suppression n'a lieu qu'**après le succès de la copie en surimpression**, et seulement si l'**empreinte locale du fichier correspond encore** à celle du manifeste — toute divergence (modification locale) conserve le fichier ;
5. les fichiers porteurs (`docker-compose.yml`/`.yaml`, `compose.yml`/`.yaml`, `.env`) et les chemins non sûrs sont exclus d'office ; les répertoires devenus vides sont nettoyés par `rmdir` **non récursif**.

Les sauts sont définitifs : le pire cas est toujours « un fichier périmé survit », **jamais une perte de données**.

### Webhooks signés (auto-deploy)

Chaque stack Git peut exposer un webhook entrant de déploiement automatique. Le **secret est obligatoire** à l'activation — jamais de webhook « ouvert » :

| Source | En-tête | Vérification |
|---|---|---|
| GitHub / Gitea / Forgejo | `X-Hub-Signature-256: sha256=<hmac>` | HMAC-SHA256 du **corps brut** de la requête, clé = secret ; comparaison à temps constant |
| GitLab | `X-Gitlab-Token: <secret>` | Égalité exacte du jeton, comparaison à temps constant |

- signature invalide ou secret manquant → 401 + entrée d'audit avec motif (`invalid_signature`, `no_secret_configured`) ;
- le **rejeu est sans effet destructeur** : une requête valide re-déclenche la synchronisation, qui saute le re-déploiement si rien n'a changé (comparaison de commit + diff de répertoire).

### Garde-fous sécurité

| Risque | Mesure |
|---|---|
| Injection d'options Git via l'URL/branche | Refus des valeurs commençant par `-`, des transports `ext::`/`fd::`/`file://` et des chemins locaux ; branches de refs option-like refusées |
| Fuite de credentials en ligne de commande | HTTPS par variables d'environnement, identifiants retirés de l'URL avant clonage ; SSH par fichier temporaire `0600` unique par opération, nettoyé après usage |
| Suppression de fichiers utilisateur | Suppression conditionnée au **manifeste** (fichiers écrits par WindFlow uniquement), vérification d'**empreinte SHA-256** avant suppression, fichiers porteurs intouchables, `rmdir` non récursif |
| Données de stack détruites au re-déploiement | Copie en **surimpression sans effacement** ; overrides dans `.env.windflow` séparé du `.env` du dépôt |
| Webhook non authentifié | Secret obligatoire, HMAC-SHA256 à temps constant ou jeton, audit des échecs |
| Secrets dans les journaux | Variables journalisées **masquées** (valeurs `***`, clés seules) |

## Sources de templates externes (format Portainer)

L'onglet Apps agrémente le catalogue officiel WindFlow (fiches riches : compose paramétré Jinja2, schéma de configuration wizard, multi-backends — section [Apps multi-backend](#apps-multi-backend)) avec des **catalogues communautaires au format Portainer** : la majorité de l'écosystème self-hosted publie en effet des catalogues JSON compatibles Portainer, que WindFlow sait consommer directement.

### Coexistence des deux formats

| | Fiches officielles WindFlow | Catalogues Portainer |
|---|---|---|
| **Format** | Format complet WindFlow (multi-backends, wizard, labels conditionnels) | JSON Portainer types **1** (conteneur) et **3** (stack Compose) ; les modèles Swarm type 2 sont ignorés |
| **Rédaction** | Maintenues par l'équipe WindFlow | Catalogues communautaires existants |
| **Rôle** | Entrées recommandées, intégrations plugins (Traefik, Restic…) | Longue traîne du catalogue |

Chaque entrée Portainer est **normalisée en modèle unifié** du format d'entrée Apps : titre, description, logo, catégories, type (conteneur/stack), source, ports, volumes, variables avec valeurs par défaut, politique de redémarrage, déploiement (URL + stackfile) et note du catalogue. Le déploiement suit ensuite le **wizard de création de stack standard** (formulaire prérempli : nom proposé, YAML du modèle, variables suggérées) — mêmes validations Compose et mêmes vérifications de ressources que n'importe quelle stack.

### Sources intégrées et personnalisées

- WindFlow référence un ensemble de **catalogues intégrés** (curation communautaire, p.ex. les listes LinuxServer.io ou Pi-Hosted) — chaque source intégrée est **activable/désactivable** individuellement dans les réglages marketplace, avec ordre d'affichage configurable ;
- des **sources personnalisées** peuvent être ajoutées (nom + URL de catalogue JSON), modifiées, désactivées et supprimées ;
- l'agrégation ne couvre que les sources **activées** ; le catalogue consolide fiches officielles + sources actives, avec recherche et filtres (titre, catégories, source).

### Cache et garde anti-SSRF

- **Cache serveur de 1 heure par URL** : les catalogues ne sont pas re-téléchargés à chaque consultation ; le bouton « Rafraîchir » force la reprise (`windflow marketplace refresh`) ;
- **garde anti-SSRF sur l'URL de chaque source** : les cibles loopback et les adresses de métadonnées cloud sont bloquées (les plages privées/LAN restent autorisées — un catalogue interne y vit légitimement) ; les schémas sont restreints à HTTP(S).

## Voir aussi

- [11-plugins.md](11-plugins.md) — système de plugins : manifest, lifecycle, événements, guide dev
- [01-vision.md](01-vision.md) — compte canonique « 20+ plugins officiels » et métriques écosystème
- [02-familles-workloads.md](02-familles-workloads.md) — modèles consommés par la marketplace (backends, profils)
- [09-api.md](09-api.md) — endpoints `/marketplace` et `/admin/registries`
- [14-ui-maquettes.md](14-ui-maquettes.md) — maquettes des écrans marketplace et wizard d'installation
- [03-modele-compute.md](03-modele-compute.md) — pipeline de déploiement des stacks consommé par les stacks Git
- [15-securite.md](15-securite.md) — chiffrement des credentials (SecretManager) et résolveur de secrets
