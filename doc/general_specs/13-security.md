# Sécurité - WindFlow

## Vue d'Ensemble

WindFlow adopte une approche de sécurité pragmatique adaptée au self-hosting : protéger efficacement une petite infrastructure sans imposer une usine à gaz enterprise. Les mesures de sécurité fondamentales sont dans le core. Les fonctionnalités avancées (vulnerability scanning, 2FA, SSO, secrets management avancé) sont des plugins.

### Principes

- **Sécurisé par défaut** : Les secrets sont chiffrés, les mots de passe hashés, les tokens expirent, le rate limiting est actif — sans configuration supplémentaire.
- **Moindre privilège** : Le rôle par défaut est Viewer (lecture seule). Les permissions s'ajoutent explicitement.
- **Audit trail** : Toutes les actions modifiantes sont loggées avec l'utilisateur, l'IP, et l'horodatage.
- **Core vs Plugin** : Les mesures essentielles sont dans le core. Les mesures avancées sont des plugins installables.

### Ce qui est Core vs Plugin

| Core (toujours actif) | Plugin (optionnel) |
|---|---|
| Hashage bcrypt des mots de passe | Vulnerability scanning (Trivy) |
| Chiffrement AES-256 des secrets en base | Secrets management avancé (Vault) |
| JWT avec expiration + refresh tokens | SSO / LDAP / 2FA (Keycloak) |
| RBAC (4 rôles) | 2FA devant les services exposés (Authelia) |
| Rate limiting sur login | Scanner de configuration |
| Audit trail en base | Alerting multi-canal |
| Protection du Docker socket via RBAC | |

---

## Chiffrement des Secrets

### Secrets en Base de Données

Toutes les données sensibles stockées en base (mots de passe de services, tokens, clés SSH des targets, variables d'environnement des stacks) sont chiffrées avec AES-256 via Fernet. La clé de chiffrement est dérivée du `SECRET_KEY` de l'instance.

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
- `stacks.env_vars_encrypted` : variables d'environnement sensibles des stacks
- `targets.connection_config` : clés SSH, tokens Proxmox
- `plugin_configs.value` (quand `encrypted=true`) : configurations sensibles des plugins (clés API, mots de passe)
- `api_keys.key_hash` : hashé avec bcrypt (pas chiffré — on ne peut pas retrouver la clé)

### Protection du SECRET_KEY

Le `SECRET_KEY` est la clé maître de l'instance. Sa compromission compromet tous les secrets et tous les JWT.

**Recommandations :**
- Généré automatiquement par `install.sh` (64 caractères hex aléatoires)
- Stocké dans le fichier `.env` avec permissions `600`
- Ne jamais le commiter dans un dépôt Git
- Si compromis : changer le `SECRET_KEY`, re-chiffrer tous les secrets, invalider tous les tokens

### Secrets Avancés (Plugin Vault)

Pour les besoins avancés (rotation automatique, secrets dynamiques par service, audit des accès aux secrets), le plugin HashiCorp Vault est disponible. Il remplace le `SecretManager` natif par une intégration Vault complète.

---

## Authentification

Détaillé dans [05-authentication.md](05-authentication.md). Résumé des mesures de sécurité :

- **Hashage bcrypt** : Mots de passe hashés avec bcrypt (cost factor 12)
- **JWT signé HS256** : Access tokens de 30 minutes, signés avec le SECRET_KEY
- **Refresh tokens opaques** : Stockés hashés en base, 7 jours de validité
- **Rate limiting** : 5 tentatives de login par minute par IP, puis blocage 5 minutes
- **API keys** : Préfixées `wf_ak_`, hashées en base, expiration configurable

---

## RBAC

Détaillé dans [06-rbac-permissions.md](06-rbac-permissions.md). Résumé :

4 rôles hiérarchiques : **Viewer** (lecture seule) → **Operator** (actions opérationnelles) → **Admin** (gestion complète) → **Super Admin** (accès total). Permissions vérifiées sur chaque endpoint API et chaque action WebSocket.

---

## Sécurité du Docker Socket

Le Docker socket (`/var/run/docker.sock`) est le point de sécurité le plus critique de WindFlow. Quiconque a accès au socket Docker a un accès root de facto sur la machine hôte.

### Mesures de Protection

**Accès exclusif via WindFlow** : Seuls les containers `windflow-api` et `windflow-worker` montent le Docker socket. Les containers déployés par les utilisateurs n'y ont jamais accès.

**RBAC sur les opérations Docker** : Les appels à l'API Docker passent toujours par l'API WindFlow, qui vérifie les permissions RBAC avant d'exécuter. Un Viewer ne peut pas démarrer un container, même s'il connaît l'API Docker.

**Pas d'exposition réseau** : Le Docker socket n'est jamais exposé sur le réseau (pas de Docker API en TCP). Les machines distantes sont gérées via SSH.

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

### Risques Résiduels

- Un plugin **extension** (qui s'exécute dans le process core) a théoriquement accès au Docker SDK. C'est pourquoi seuls les plugins de confiance (officiels ou audités) devraient être installés.
- Un plugin **service** (qui tourne dans son propre container) n'a pas accès au socket, sauf s'il le demande explicitement dans son manifest — ce qui devrait déclencher un avertissement dans la marketplace.

---

## Sécurité Réseau

### Isolation par Environnement

Chaque environnement (dev, staging, prod) peut avoir son propre network Docker. Les containers d'un environnement ne voient pas ceux des autres par défaut.

```python
# Réseau isolé par environnement
network_name = f"windflow-{org_name}-{env_name}"
docker_client.networks.create(
    name=network_name,
    driver="bridge",
    internal=False,  # True pour bloquer l'accès Internet
)
```

### Ports Exposés

WindFlow expose par défaut :
- Port **80** : Frontend (Nginx)
- Port **8080** : API (FastAPI)

Recommandations :
- En production, placer WindFlow derrière un reverse proxy (plugin Traefik ou Caddy) pour le HTTPS
- Ne pas exposer le port 8080 directement sur Internet — le reverse proxy doit gérer le routage

### Machines Distantes (SSH)

Les connexions aux targets distants utilisent SSH avec authentification par clé. Les clés sont stockées chiffrées en base.

```python
# Connexion SSH sécurisée
async def connect_to_target(target: Target) -> SSHConnection:
    key_data = secret_manager.decrypt(target.connection_config["ssh_key"])
    pkey = paramiko.RSAKey.from_private_key(StringIO(key_data))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())  # Pas d'auto-accept
    client.connect(
        hostname=target.host,
        username=target.connection_config.get("username", "deploy"),
        pkey=pkey,
        timeout=10,
    )
    return client
```

**Recommandation** : Créer un utilisateur dédié (`deploy`) sur les machines distantes avec uniquement les permissions nécessaires (Docker, libvirt selon les besoins). Ne pas utiliser root.

---

## Audit Trail

### Ce qui est Loggé

Toute action modifiante est enregistrée dans la table `audit_logs` :

| Action | Détails loggés |
|--------|----------------|
| `user.login` | Username, IP, succès/échec |
| `user.login_failed` | Username, IP, raison |
| `user.created` | Username, email, rôle, par qui |
| `user.role_changed` | Username, ancien rôle, nouveau rôle, par qui |
| `stack.deployed` | Stack name, target, par qui |
| `stack.rollback` | Stack name, version source → cible, par qui |
| `container.started` | Container name, target, par qui |
| `container.stopped` | Container name, target, par qui |
| `vm.created` | VM name, specs, target, par qui |
| `vm.snapshot` | VM name, snapshot name, par qui |
| `plugin.installed` | Plugin name, version, par qui |
| `plugin.removed` | Plugin name, par qui |
| `target.added` | Target name, type, host, par qui |
| `target.removed` | Target name, par qui |
| `settings.changed` | Setting key, ancienne/nouvelle valeur, par qui |

### Consultation

```bash
# Via CLI
windflow admin audit --last 50
windflow admin audit --user alice --action "stack.*"
windflow admin audit --since 2026-04-01

# Via API
GET /api/v1/admin/audit?user_id=...&action=stack.deployed&since=2026-04-01
```

### Rétention

Les logs d'audit sont conservés indéfiniment en base par défaut. Sur les installations avec peu d'espace disque (RPi), une politique de rétention peut être configurée :

```bash
# Garder uniquement les 90 derniers jours
AUDIT_RETENTION_DAYS=90
```

---

## Sécurité des Plugins

### Niveaux de Confiance

| Type | Confiance requise | Risque |
|------|-------------------|--------|
| **Service plugin** | Faible — tourne dans son propre container isolé | Limité au container |
| **Extension plugin** | Élevée — s'exécute dans le process core | Accès au Docker SDK et à la base |
| **Hybrid plugin** | Élevée (partie extension) | Accès au process core |

### Vérifications à l'Installation

- **Checksum SHA-256** : Le package est vérifié contre le registre
- **Signature** (futur) : Les plugins officiels seront signés
- **Avertissements** : L'UI affiche un avertissement si un plugin demande l'accès au Docker socket ou à des ressources sensibles

### Recommandations

- N'installer que des plugins **officiels** ou provenant de sources de confiance
- Les plugins communautaires non audités ne devraient pas être installés sur des instances en production
- Vérifier les permissions demandées par un plugin avant installation (affichées dans la fiche marketplace)

---

## Sécurité via Plugins (optionnel)

### Plugin Trivy — Vulnerability Scanning

Scan des images Docker avant et après déploiement. Affiche un dashboard de vulnérabilités triées par sévérité. Peut bloquer le déploiement si des vulnérabilités critiques sont trouvées.

### Plugin Authelia — 2FA pour les Services

Ajoute une authentification 2FA (TOTP, WebAuthn) devant les services exposés via le reverse proxy. Complémentaire au plugin Traefik.

### Plugin Vault — Secrets Management Avancé

HashiCorp Vault pour la rotation automatique, les secrets dynamiques, et l'audit des accès aux secrets. Remplace le `SecretManager` natif.

### Plugin Keycloak — SSO et 2FA

SSO complet avec LDAP/AD, OIDC, SAML. Ajoute le 2FA (TOTP, WebAuthn) sur le login WindFlow lui-même.

---

## Checklist de Sécurité

### À l'Installation

- [ ] `SECRET_KEY` généré aléatoirement (fait automatiquement par `install.sh`)
- [ ] Fichier `.env` en permissions `600`
- [ ] Mot de passe admin suffisamment fort
- [ ] WindFlow pas accessible directement sur Internet sans reverse proxy HTTPS

### En Production

- [ ] Reverse proxy avec HTTPS (plugin Traefik ou Caddy)
- [ ] Utilisateurs avec le rôle minimum nécessaire
- [ ] Machines distantes avec un utilisateur SSH dédié (pas root)
- [ ] Backups réguliers (plugin Restic ou manuel)
- [ ] Mise à jour régulière de WindFlow et des plugins
- [ ] Plugin Trivy installé pour scanner les images

### Optionnel mais Recommandé

- [ ] Plugin Authelia pour 2FA devant les services exposés
- [ ] Plugin Keycloak si plusieurs utilisateurs (SSO + 2FA sur le login)
- [ ] Plugin Vault si secrets sensibles avec rotation nécessaire
- [ ] Audit trail consulté régulièrement

---

**Références :**
- [Authentification](05-authentication.md) — JWT, API keys, brute-force protection
- [RBAC et Permissions](06-rbac-permissions.md) — Rôles et matrice de permissions
- [Architecture](02-architecture.md) — Architecture de sécurité
- [Guide de Déploiement](15-deployment-guide.md) — Installation sécurisée
- [Plugins](09-plugins.md) — Plugins de sécurité (Trivy, Authelia, Vault, Keycloak)
