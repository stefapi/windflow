# Chapitre 15 — Sécurité

> **Statut** : Spec cible · **Public** : Administrateurs système, développeurs backend · **Lié à** : [07-authentification.md](07-authentification.md), [08-rbac-permissions.md](08-rbac-permissions.md), [11-plugins.md](11-plugins.md), [16-deploiement.md](16-deploiement.md)

## Vue d'ensemble

Ce chapitre spécifie la sécurité applicative de WindFlow : chiffrement des secrets, protection du `SECRET_KEY`, sécurité du Docker socket, sécurité réseau, audit trail, sécurité des plugins et checklists. L'approche est pragmatique et adaptée au self-hosting : protéger efficacement une petite infrastructure sans imposer une usine à gaz enterprise. Les mesures fondamentales sont dans le core ; les mesures avancées (vulnerability scanning, 2FA, SSO, secrets management avancé) sont des plugins.

### Principes

- **Sécurisé par défaut** : les secrets sont chiffrés, les mots de passe hashés, les tokens expirent, le rate limiting est actif — sans configuration supplémentaire.
- **Moindre privilège** : le rôle par défaut est Viewer (lecture seule). Les permissions s'ajoutent explicitement.
- **Audit trail** : toutes les actions modifiantes sont loggées avec l'utilisateur, l'IP et l'horodatage.
- **Core vs plugin** : les mesures essentielles sont dans le core ; les mesures avancées sont des plugins installables.

### Ce qui est core vs plugin

| Core (toujours actif) | Plugin (optionnel) |
|---|---|
| Hashage bcrypt des mots de passe | Vulnerability scanning (Trivy) |
| Chiffrement AES-256 des secrets en base | Secrets management avancé (Vault) |
| JWT avec expiration + refresh tokens | SSO / LDAP / 2FA (Keycloak) |
| RBAC (4 rôles) | 2FA devant les services exposés (Authelia) |
| Rate limiting sur login | Scanner de configuration |
| Audit trail en base | Alerting multi-canal |
| Protection du Docker socket via RBAC | |

## Chiffrement des secrets

### SecretManager (référence unique)

Toutes les données sensibles stockées en base (mots de passe de services, tokens, clés SSH des Hosts, variables d'environnement des stacks) sont chiffrées avec **AES-256 via Fernet**. La clé de chiffrement est dérivée du `SECRET_KEY` de l'instance. Cette version est l'unique spécification du `SecretManager`.

```python
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64

class SecretManager:
    """Chiffrement des données sensibles en base."""

    def __init__(self, master_key: str):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"windflow-secrets-v1",
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        self.fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Chiffre une valeur avant stockage en base."""
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Déchiffre une valeur lue depuis la base."""
        return self.fernet.decrypt(ciphertext.encode()).decode()
```

**Ce qui est chiffré :**

- `stacks.env_vars_encrypted` — variables d'environnement sensibles des stacks ;
- `hosts.connection_config` — clés SSH, tokens API Proxmox (serveurs isolés) ;
- `clusters.connection_config` — kubeconfigs (Clusters kubernetes), tokens API des clusters Proxmox, credentials socket/TLS Swarm ;
- `plugin_configs.value` (quand `encrypted=true`) — configurations sensibles des plugins (clés API, mots de passe) ;
- `api_keys.key_hash` et `refresh_tokens.token_hash` — hashés avec bcrypt (pas chiffrés : on ne peut pas retrouver la valeur).

### Protection du SECRET_KEY

Le `SECRET_KEY` est la clé maître de l'instance. Sa compromission compromet tous les secrets et tous les JWT.

- Généré automatiquement par `install.sh` (64 caractères hex aléatoires) ;
- stocké dans le fichier `.env` avec permissions `600` ;
- jamais commité dans un dépôt Git ;
- en cas de compromission : changer le `SECRET_KEY`, re-chiffrer tous les secrets, invalider tous les tokens.

### Secrets avancés (plugin Vault)

Pour les besoins avancés (rotation automatique, secrets dynamiques par service, audit des accès aux secrets), le plugin Vault (chapitre [12-marketplace.md](12-marketplace.md)) remplace le `SecretManager` natif par une intégration HashiCorp Vault complète.

### Résolveur de secrets (point d'extension)

Le **résolveur de secrets** est le point d'extension par lequel les plugins de gestion de secrets (Vault en premier, tout autre backend pouvant en implémenter le contrat) injectent des valeurs sensibles dans les stacks au déploiement — **sans jamais les écrire dans un fichier**. Le `SecretManager` natif reste la voie pour les simples variables chiffrées en base (`stacks.env_vars_encrypted`).

#### Contrat d'interface

Un backend résolveur implémente trois méthodes :

```python
class SecretResolver(Protocol):
    """Contrat d'un backend résolveur de secrets (plugin vault & co)."""

    def is_reference(self, value: str) -> bool:
        """Détecte si une valeur est une référence au format du backend."""

    async def resolve(self, reference: str) -> str:
        """Résout une référence unique vers la valeur du secret."""

    async def resolve_bulk(self, selector: str) -> dict[str, str]:
        """Extraction en masse : toutes les paires clé/valeur d'un sélecteur."""
```

Chaque backend déclare ses **capacités** (`supports_references`, `supports_bulk`) ; une opération non supportée lève une erreur explicite. Les échecs de résolution **individuels** (référence introuvable) sont journalisés et passent — la valeur reste littérale ; les échecs de transport/authentification font échouer le déploiement.

#### Syntaxe de référence dans les stacks

Dans les variables d'environnement des stacks, une valeur **référence** au format du backend est résolue au déploiement. Syntaxe Vault :

```
vault://chemin/vers/secret#clé
```

Exemple : `DB_PASSWORD=vault:///kv/prod/nextcloud#db_password` est remplacé par la valeur du secret `db_password` du chemin KV `kv/prod/nextcloud`. La détection de ce qui compte comme référence est propre au backend (`is_reference`).

#### Résolution au déploiement

Deux modes, appliqués au moment du déploiement (pipeline du chapitre [03-modele-compute.md](03-modele-compute.md)) :

1. **Interpolation de références** — chaque variable dont la valeur est une référence (`vault://…`) est remplacée par le secret réel ;
2. **Extraction en masse** — tous les secrets sous un sélecteur (p.ex. un chemin KV Vault) sont récupérés en paires clé/valeur et injectés comme variables.

Les valeurs résolues sont **promues secrets** et transmises à Compose par **environnement de processus**.

#### Invariants

- **Jamais écrit dans un fichier** : les valeurs résolues passent par l'environnement de processus du `docker compose up` — jamais dans le `.env`, jamais dans un override, jamais sur disque (le plugin Git applique la même règle à son fichier d'override `.env.windflow`, chapitre [12-marketplace.md](12-marketplace.md)) ;
- **masqué à l'affichage** : partout ailleurs (édition de stack, inspection de containers, journaux), la valeur apparaît comme `***` ;
- **traçabilité des clés injectées** : les **noms** des clés injectées au dernier déploiement sont tracés (jamais les valeurs) pour alimenter le masquage — y compris les clés de container liées par interpolation (un `MYSQL_PASSWORD=${db_secret}` dans le Compose masque `MYSQL_PASSWORD` si `db_secret` est un secret) ;
- **liaison conditionnée à une permission** : lier un fournisseur de secrets à une stack exige la permission **Secrets** en plus de la permission Stacks — un utilisateur « stacks seul » ne peut pas lier un coffre pour en exfiltrer les secrets via l'inspection de containers (chapitre [08-rbac-permissions.md](08-rbac-permissions.md)).

#### Garde anti-SSRF

Les coordonnées du backend sont contrôlées : **loopback et IP de métadonnées cloud bloquées**, LAN autorisé (un coffre auto-hébergé y vit légitimement) ; les sélecteurs de chemin sont assainis (pas de traversée `..`).

## Authentification et RBAC — synthèse

Résumé des mesures ; le détail est dans les chapitres dédiés :

- **Authentification** (chapitre [07-authentification.md](07-authentification.md)) : bcrypt (cost 12), JWT HS256 de 30 min, refresh tokens opaques de 7 jours, clés API `wf_ak_` hashées, rate limiting 5 tentatives/minute par IP puis blocage 5 minutes.
- **RBAC** (chapitre [08-rbac-permissions.md](08-rbac-permissions.md)) : 4 rôles hiérarchiques Viewer → Operator → Admin → Super Admin, permissions vérifiées sur chaque endpoint API et chaque action WebSocket.

## Sécurité du Docker socket

Le Docker socket (`/var/run/docker.sock`) est le point de sécurité le plus critique de WindFlow : quiconque y a accès a un accès root de fait sur la machine hôte.

### Mesures de protection

**Accès exclusif via WindFlow** — seuls les containers `windflow-api` et `windflow-worker` montent le Docker socket. Les containers déployés par les utilisateurs n'y ont jamais accès.

**RBAC sur les opérations Docker** — les appels à l'API Docker passent toujours par l'API WindFlow, qui vérifie les permissions RBAC avant d'exécuter. Un Viewer ne peut pas démarrer un container, même s'il connaît l'API Docker.

**Pas d'exposition réseau** — le Docker socket n'est jamais exposé sur le réseau (pas d'API Docker en TCP). Les machines distantes sont gérées via SSH (profil `host_remote_docker`).

```yaml
# docker-compose.yml — seuls les services core montent le socket
services:
  windflow-api:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro  # Lecture seule quand possible
  windflow-worker:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

### Risques résiduels

- Un plugin **extension** (exécuté dans le process core) a théoriquement accès au Docker SDK — d'où la règle de n'installer que des plugins de confiance (voir [Sécurité des plugins](#sécurité-des-plugins)).
- Un plugin **service** (dans son propre container) n'a pas accès au socket, sauf demande explicite dans son manifest — ce qui déclenche un avertissement dans la marketplace.

## Sécurité réseau

### Isolation par environnement

Chaque environnement (dev, staging, prod) a son propre network Docker. Les containers d'un environnement ne voient pas ceux des autres par défaut.

```python
# Réseau isolé par environnement
network_name = f"windflow-{org_name}-{env_name}"
docker_client.networks.create(
    name=network_name,
    driver="bridge",
    internal=False,  # True pour bloquer l'accès Internet
)
```

### Ports exposés

WindFlow expose par défaut le port **80** (frontend Nginx) et le port **8080** (API FastAPI). Recommandations :

- en production, placer WindFlow derrière un reverse proxy (plugin Traefik ou Caddy) pour le HTTPS ;
- ne pas exposer le port 8080 directement sur Internet — le reverse proxy doit gérer le routage.

### Hosts distants (SSH)

Les connexions aux Hosts distants utilisent SSH avec authentification par clé. La clé est une **entité réutilisable** `ssh_keys` (section ci-dessous) référencée par le Host — la partie privée est stockée chiffrée en base (déchiffrée via le `SecretManager` uniquement en mémoire, pour l'établissement des sessions).

```python
# Connexion SSH sécurisée
async def connect_to_host(host: Host) -> SSHConnection:
    key = await ssh_keys.get(host.ssh_key_id)          # entité réutilisable
    key_data = secret_manager.decrypt(key.private_key_encrypted)
    pkey = paramiko.Ed25519Key.from_private_key(StringIO(key_data))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())  # Pas d'auto-accept
    client.connect(
        hostname=host.address,
        username=host.connection_config.get("username", "deploy"),
        pkey=pkey,
        timeout=10,
    )
    return client
```

**Recommandation** : créer un utilisateur dédié (`deploy`) sur les Hosts distants avec uniquement les permissions nécessaires (Docker, libvirt selon les besoins). Ne pas utiliser root.

#### Clés SSH réutilisables

Les clés SSH sont des entités **partagées par plusieurs Hosts** (évite une clé par Host dans `hosts.connection_config`) :

- **Génération** côté serveur (UI admin ou CLI), algorithme **ed25519 recommandé** ; l'**import** d'une clé existante (avec ou sans passphrase) est également possible ;
- la **clé privée est affichée/importable une seule fois** à la création, puis stockée **chiffrée au repos** (AES-256 via le `SecretManager`) — seule l'empreinte et la clé publique restent consultables (pour déploiement dans l'`authorized_keys` de l'hôte distant) ;
- **Suppression** refusée si des Hosts l'utilisent encore (ou avec déréférencement explicite) — jamais de suppression silencieuse.

Schéma et contraintes de l'entité : chapitre [06-modele-de-donnees.md](06-modele-de-donnees.md) § `ssh_keys`.

#### Empreintes d'hôtes (known_hosts) et anti-MITM

Chaque Host distant porte son entrée **known_hosts** (empreinte attendue du serveur SSH, table `host_ssh_fingerprints` — chapitre [06-modele-de-donnees.md](06-modele-de-donnees.md)) :

- **première connexion** : l'empreinte est présentée à l'administrateur pour **acceptation explicite** ; le test de connexion ne l'ajoute **jamais** silencieusement à known_hosts ;
- **divergence d'empreinte** : la connexion est **bloquée** avec un message explicite (hôte reconfiguré ou tentative d'usurpation / MITM) — l'administrateur doit réaccepter délibérément la nouvelle empreinte.

#### Compteur d'échecs et backoff anti-tempête

- les **échecs d'authentification SSH sont comptés par hôte cible** avec refroidissement progressif (protection contre les tentatives répétées) ; un succès efface l'historique d'échecs ;
- **anti-tempête de reconnexion** : les tentatives de réétablissement de session sont limitées par une fenêtre glissante avec refroidissement progressif (**30 s → 60 s → 120 s → 300 s**) par Host ; une session **stable pendant 5 minutes** réinitialise le compteur.

## Audit trail

### Ce qui est loggé

Toute action modifiante est enregistrée dans la table `audit_logs` (schéma au chapitre [06-modele-de-donnees.md](06-modele-de-donnees.md)) :

| Action | Détails loggés |
|--------|----------------|
| `user.login` / `user.login_failed` | Username, IP, succès/échec, raison |
| `user.created` / `user.role_changed` | Username, email, rôles, par qui |
| `stack.deployed` / `stack.rollback` | Stack, Host, versions, par qui |
| `container.started` / `container.stopped` | Container, Host, par qui |
| `machine.created` / `machine.snapshot` | Machine, specs/snapshot, par qui |
| `plugin.installed` / `plugin.removed` | Plugin, version, par qui |
| `host.added` / `host.removed` | Host, profil, par qui |
| `settings.changed` | Clé, ancienne/nouvelle valeur, par qui |

### Consultation

```bash
# Via CLI
windflow admin audit --last 50
windflow admin audit --user alice --action "stack.*"
windflow admin audit --since 2026-04-01

# Via API
GET /api/v1/admin/audit?user_id=...&action=stack.deployed&since=2026-04-01
```

Dans l'UI, l'écran Activité (chapitre [14-ui-maquettes.md](14-ui-maquettes.md)) présente le journal avec filtres et actions directes.

### Rétention

Les logs d'audit sont conservés indéfiniment en base par défaut. Sur les installations avec peu d'espace disque (RPi), une politique de rétention peut être configurée :

```bash
# Garder uniquement les 90 derniers jours
AUDIT_RETENTION_DAYS=90
```

## Sécurité des plugins

### Niveaux de confiance

| Type | Confiance requise | Risque |
|------|-------------------|--------|
| **Service plugin** | Faible — tourne dans son propre container isolé | Limité au container |
| **Extension plugin** | Élevée — s'exécute dans le process core | Accès au Docker SDK et à la base |
| **Hybrid plugin** | Élevée (partie extension) | Accès au process core |

### Vérifications à l'installation

- **Checksum SHA-256** : le package est vérifié contre le registre ; l'installation est refusée en cas d'écart ;
- **Signature** (évolutif) : les plugins officiels seront signés ;
- **Avertissements** : l'UI affiche un avertissement si un plugin demande l'accès au Docker socket ou à des ressources sensibles.

### Recommandations

- n'installer que des plugins **officiels** (catalogue du chapitre [12-marketplace.md](12-marketplace.md)) ou provenant de sources de confiance ;
- ne pas installer de plugins communautaires non audités sur des instances en production ;
- vérifier les permissions demandées par un plugin avant installation (affichées dans sa fiche marketplace).

Les mécanismes techniques (isolation, intégrité, chiffrement des secrets plugin, RBAC sur les routes injectées) sont spécifiés au chapitre [11-plugins.md](11-plugins.md).

## Sécurité via plugins (optionnel)

- **Plugin Trivy** — scan des images Docker avant et après déploiement, dashboard de vulnérabilités par sévérité, blocage optionnel des déploiements critiques via la gate pre-deploy (chapitre [11-plugins.md](11-plugins.md) § Hooks de déploiement).
- **Plugin Authelia** — 2FA (TOTP, WebAuthn) devant les services exposés via le reverse proxy. Complémentaire au plugin Traefik.
- **Plugin Vault** — HashiCorp Vault pour la rotation automatique, les secrets dynamiques et l'audit des accès. Remplace le `SecretManager` natif — implémente le contrat [Résolveur de secrets](#résolveur-de-secrets-point-dextension).
- **Plugin Keycloak** — SSO complet (LDAP/AD, OIDC, SAML) et 2FA sur le login WindFlow lui-même (chapitre [07-authentification.md](07-authentification.md)).

## Checklists de sécurité

### À l'installation

- [ ] `SECRET_KEY` généré aléatoirement (automatique via `install.sh`)
- [ ] Fichier `.env` en permissions `600`
- [ ] Mot de passe admin suffisamment fort
- [ ] WindFlow pas accessible directement sur Internet sans reverse proxy HTTPS

### En production

- [ ] Reverse proxy avec HTTPS (plugin Traefik ou Caddy)
- [ ] Utilisateurs avec le rôle minimum nécessaire
- [ ] Hosts distants avec un utilisateur SSH dédié (pas root)
- [ ] Empreintes des Hosts distants validées explicitement à la première connexion (known_hosts)
- [ ] Backups réguliers (plugin Restic ou procédure du chapitre [16-deploiement.md](16-deploiement.md))
- [ ] Mise à jour régulière de WindFlow et des plugins
- [ ] Plugin Trivy installé pour scanner les images

### Optionnel mais recommandé

- [ ] Plugin Authelia pour la 2FA devant les services exposés
- [ ] Plugin Keycloak si plusieurs utilisateurs (SSO + 2FA sur le login)
- [ ] Plugin Vault si secrets sensibles avec rotation nécessaire
- [ ] Audit trail consulté régulièrement

## Voir aussi

- [07-authentification.md](07-authentification.md) — JWT, clés API, protection brute-force
- [08-rbac-permissions.md](08-rbac-permissions.md) — rôles et matrice de permissions
- [11-plugins.md](11-plugins.md) — sécurité technique du système de plugins
- [16-deploiement.md](16-deploiement.md) — installation sécurisée et backup/restore
- [12-marketplace.md](12-marketplace.md) — plugins de sécurité du catalogue officiel
