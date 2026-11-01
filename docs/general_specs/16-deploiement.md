# Chapitre 16 — Déploiement

> **Statut** : Spec cible · **Public** : Administrateurs système, self-hosters · **Lié à** : [04-architecture.md](04-architecture.md), [05-stack-technologique.md](05-stack-technologique.md), [15-securite.md](15-securite.md)

## Vue d'ensemble

Ce chapitre couvre l'exploitation de WindFlow : installation (mode léger sur Raspberry Pi jusqu'au mode standard sur serveur dédié), développement, premiers pas, mise à jour, sauvegarde/restauration, désinstallation et dépannage. WindFlow est conçu pour être installé en moins de 5 minutes. Les scripts d'exploitation complets (`install.sh`, `backup-windflow.sh`, `restore-windflow.sh`) sont maintenus dans le dépôt ; ce chapitre en donne les procédures et des extraits, le détail relevant de l'exploitation vit avec le code.

## Prérequis

**Système :**

- **OS** : Linux (Debian/Ubuntu, Raspberry Pi OS, Fedora, ou équivalent) ;
- **Architecture** : x86_64 ou ARM64 ;
- **Docker** ≥ 20.10 + Docker Compose v2.

**Pour le développement (optionnel) :**

- Python ≥ 3.11 + Poetry ≥ 1.8 ;
- Node.js ≥ 20 + pnpm ≥ 9.

## Profils d'installation

| Profil | RAM minimum | CPU | Stockage | Machine type | Compose file |
|--------|-------------|-----|----------|--------------|--------------|
| **Léger** | 2 Go (512 Mo pour le core) | 1 core ARM | 8 Go | Raspberry Pi 4 (2 Go) | `docker-compose.light.yml` |
| **Standard** | 4 Go (1.5 Go pour le core) | 2 cores | 20 Go | RPi 4 (4 Go), mini PC, VPS | `docker-compose.yml` |
| **Développement** | 4 Go | 2 cores | 20 Go | Laptop / PC | Manuel (sans Docker) |

Les profils de ressources et leurs empreintes sont détaillés au chapitre [04-architecture.md](04-architecture.md) (référence unique).

## Installation mode léger (Raspberry Pi)

Le mode léger utilise SQLite au lieu de PostgreSQL et un cache en mémoire au lieu de Redis (chapitre [05-stack-technologique.md](05-stack-technologique.md)).

### Procédure

```bash
# Télécharger et lancer l'installateur
curl -fsSL https://get.windflow.io/install.sh | bash -s -- --light

# Ou manuellement :
git clone https://github.com/windflow/windflow.git
cd windflow
./scripts/install.sh --light
```

Le script `install.sh --light` :

1. vérifie que Docker est installé et détecte l'architecture (arm64 / amd64) ;
2. génère un `SECRET_KEY` aléatoire et crée le fichier `.env` ;
3. lance `docker compose -f docker-compose.light.yml up -d` ;
4. attend que l'API soit prête (health check) ;
5. initialise la base SQLite (migrations Alembic) ;
6. demande la création du compte admin ;
7. affiche l'URL d'accès.

Exemple illustratif — services du mode léger :

```yaml
# docker-compose.light.yml (extrait)
services:
  windflow-api:                     # process unique : API + runtime asyncio (tâches de fond, scheduler)
    image: windflow/api:latest
    environment:
      WINDFLOW_DB_MODE: light
      DATABASE_URL: "sqlite+aiosqlite:///data/windflow.db"
    volumes:
      - windflow_data:/data
      - /var/run/docker.sock:/var/run/docker.sock
  windflow-frontend:
    image: windflow/frontend:latest
    ports:
      - "80:80"
```

**Empreinte** : ~2 containers, ~500 Mo RAM total. Pas de PostgreSQL, pas de Redis, pas de worker séparé (runtime asyncio unique — chapitre [04-architecture.md](04-architecture.md)).

## Installation mode standard

Le mode standard utilise PostgreSQL et Redis. Recommandé pour les machines avec 4 Go de RAM ou plus.

### Procédure

```bash
curl -fsSL https://get.windflow.io/install.sh | bash
# Ou : ./scripts/install.sh
```

Exemple illustratif — services du mode standard :

```yaml
# docker-compose.yml (extrait)
services:
  postgres:
    image: postgres:15
    environment: { POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}" }
    volumes: [postgres_data:/var/lib/postgresql/data]
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 128mb
  windflow-api:                     # process unique : API + runtime asyncio (tâches de fond, scheduler)
    image: windflow/api:latest
    ports: ["8080:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://windflow:${POSTGRES_PASSWORD}@postgres:5432/windflow
      REDIS_URL: redis://redis:6379/0
    volumes:
      - windflow_data:/data
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
  windflow-frontend:
    image: windflow/frontend:latest
    ports: ["80:80"]
```

### Variables d'environnement

Le fichier `.env` ne contient que les variables du core ; les plugins gèrent leur propre configuration via l'UI (chapitre [11-plugins.md](11-plugins.md)).

```bash
# .env — généré automatiquement par install.sh
SECRET_KEY=<généré automatiquement>
POSTGRES_PASSWORD=<généré automatiquement>   # mode standard uniquement
```

C'est tout. Pas de `VAULT_TOKEN`, pas d'`OPENAI_API_KEY`, pas de `SMTP` — tout cela est géré par les plugins correspondants.

### Configuration initiale

```bash
# Vérifier que tout tourne
docker compose ps

# Initialiser la base (fait automatiquement par install.sh)
docker compose exec -T windflow-api alembic upgrade head

# Créer le compte admin (fait automatiquement par install.sh)
docker compose exec -it windflow-api windflow admin create \
  --username admin --email admin@example.com

# Attendre que l'API soit prête (signal canonique des orchestrateurs :
# migrations appliquées + DB + dépendances optionnelles — STORY-129)
curl -f http://localhost:8080/api/v1/system/ready

# Vérification légère (santé applicative)
curl http://localhost:8080/api/v1/system/health
```

## Installation développement

Pour contribuer au code de WindFlow.

### Backend

```bash
git clone https://github.com/windflow/windflow.git
cd windflow
poetry install --with dev

# PostgreSQL et Redis pour le dev local
docker compose -f docker-compose.dev-deps.yml up -d

cp .env.dev.example .env
poetry run alembic upgrade head
poetry run windflow admin create --username admin --email admin@localhost

# Serveur de dev
poetry run uvicorn windflow.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend et CLI

```bash
# Frontend
cd frontend
pnpm install
pnpm dev   # http://localhost:5173

# CLI / TUI
pip install -e ./cli
windflow --help
```

## Après l'installation : premiers pas

1. **Se connecter** à l'interface web avec le compte admin.
2. **Vérifier le Host local** : WindFlow détecte automatiquement le Docker Engine local — le Host `local` apparaît dans la liste Hosts avec ses moteurs détectés (chapitre [03-modele-compute.md](03-modele-compute.md)).
3. **Installer un premier plugin** depuis la Marketplace : Traefik (domaine + HTTPS), Uptime Kuma (supervision) ou PostgreSQL Manager (bases de données) — catalogue complet au chapitre [12-marketplace.md](12-marketplace.md).
4. **Déployer une première App** : Marketplace → onglet Apps → par exemple Gitea ou Nextcloud. Le wizard guide la configuration.
5. **Ajouter un Host distant (optionnel)** : Hosts → `[+ Ajouter un Host]` → connexion SSH. WindFlow détecte les moteurs et propose l'adoption des objets existants.

L'onboarding UI (wizard de premier lancement) est décrit au chapitre [13-ui-principes.md](13-ui-principes.md).

## Mise à jour

### Mode standard

```bash
cd /opt/windflow
docker compose pull
docker compose up -d
docker compose exec -T windflow-api alembic upgrade head
```

### Mode léger

```bash
cd /opt/windflow
docker compose -f docker-compose.light.yml pull
docker compose -f docker-compose.light.yml up -d
docker compose -f docker-compose.light.yml exec -T windflow-api alembic upgrade head
```

Les mises à jour de plugins se gèrent séparément (`windflow plugins update --all`, chapitre [10-cli-tui.md](10-cli-tui.md)).

## Chiffrement au repos des credentials cibles (SecretManager)

Depuis STORY-103, les credentials d'accès aux cibles (mots de passe SSH/sudo, clés privées) stockés dans la colonne `targets.credentials` sont **chiffrés au repos** (AES-256 via Fernet, clé dérivée de `SECRET_ENCRYPTION_KEY` — voir [15-securite.md](15-securite.md)). Cette section décrit la procédure opérationnelle : backup préalable, migration des données existantes et rotation de la clé maîtresse.

### Backup préalable (obligatoire avant toute mise à jour)

La migration étant progressive, un backup complet de la base **et** du fichier `.env` (qui contient la clé maîtresse) est requis avant la mise à jour :

```bash
# 1. Backup complet (base + configuration incluant la clé maîtresse)
windflow admin backup create --output /backup/windflow-pre-encryption.tar.gz

# 2. Copie de sécurité du .env (contient SECRET_ENCRYPTION_KEY)
cp /opt/windflow/.env /backup/windflow-env-$(date +%Y%m%d).bak

# 3. Vérifier l'intégrité du backup (doit lister la base + la configuration)
tar -tzf /backup/windflow-pre-encryption.tar.gz
```

### Migration des données existantes (double lecture)

La migration vers le format chiffré est **progressive, sans fenêtre d'indisponibilité et sans script dédié** :

1. Au démarrage de la nouvelle version, les lignes existantes restent en clair dans la base — aucune migration bloquante n'est exécutée.
2. À la **première lecture** d'une ligne encore en clair (déploiement, scan, health-check, réponse API exposant `auth_method`/`username`/`has_sudo`), celle-ci est déchiffrée n/a — lue telle quelle, puis **ré-encryptée et re-persistance** dans la même transaction que l'opération métier.
3. Les **nouvelles écritures** (création/modification de cible) stockent directement le format chiffré.
4. La migration est donc terminée quand toutes les cibles ont été accédées au moins une fois ; les credentials vides (`{}`) restent tels quels (aucun secret à protéger).

Vérifier l'avancement (les lignes migrées contiennent un token Fernet, préfixe `gAAAA`) :

```bash
# SQLite
sqlite3 /var/lib/windflow/windflow.db \
  "SELECT COUNT(*) FROM targets WHERE credentials LIKE '%gAAAA%'"
# PostgreSQL
docker compose exec -T postgres psql -U windflow -d windflow -c \
  "SELECT COUNT(*) FROM targets WHERE credentials::text LIKE '%gAAAA%';"
```

En cas de restauration d'un backup antérieur à la migration, les lignes en clair seront migrées à nouveau au fil des accès (le mécanisme de double lecture est permanent).

### Rotation de la clé maîtresse

La rotation ré-encrypte les credentials **entièrement en mémoire**, sans jamais écrire de secret en clair sur disque. Le principe : une bascule unique (déchiffrement avec l'ancienne clé → ré-encryption avec la nouvelle) exécutée pendant que l'API est arrêtée, puis activation de la nouvelle clé.

```bash
cd /opt/windflow

# 1. Backup complet AVANT rotation (obligatoire — voir section précédente)
windflow admin backup create --output /backup/windflow-pre-rotation.tar.gz
cp .env /backup/windflow-env-pre-rotation.bak

# 2. Arrêter l'API pour éviter toute écriture concurrente pendant la bascule
docker compose stop windflow-api

# 3. Générer la nouvelle clé (en mémoire de shell, jamais écrite en clair sur disque)
OLD_KEY=$(grep '^SECRET_ENCRYPTION_KEY=' .env | cut -d= -f2)
NEW_KEY=$(openssl rand -hex 32)

# 4. Bascule one-shot : chaque credential chiffré est déchiffré avec l'ancienne
#    clé puis ré-encrypté avec la nouvelle, en mémoire du process uniquement.
#    Les lignes legacy en clair ne sont pas touchées : la double lecture les
#    migrera directement avec la nouvelle clé au premier accès.
docker compose run --rm -e OLD_KEY -e NEW_KEY windflow-api python -c "
import asyncio, json, os
from sqlalchemy import select
from app.core.secret_manager import SecretManager
from app.database import AsyncSessionLocal, db
from app.models.target import Target

async def rotate():
    old = SecretManager(os.environ['OLD_KEY'])
    new = SecretManager(os.environ['NEW_KEY'])
    await db.connect()
    async with AsyncSessionLocal() as session:
        targets = (await session.execute(select(Target))).scalars().all()
        for t in targets:
            token = (t.credentials or {}).get('_encrypted')
            if token and SecretManager.is_encrypted(token):
                plain = json.loads(old.decrypt(token))
                t.credentials = {'_encrypted': new.encrypt(json.dumps(plain))}
        await session.commit()
asyncio.run(rotate())
"

# 5. Activer la nouvelle clé et redémarrer
sed -i "s|^SECRET_ENCRYPTION_KEY=.*|SECRET_ENCRYPTION_KEY=${NEW_KEY}|" .env
docker compose up -d
unset OLD_KEY NEW_KEY
```

> **Note :** le snippet ci-dessus est un exemple représentatif — la commande exacte d'un script `scripts/rotate-master-key.sh` livré avec l'installation prime sur ce extrait.

**Points d'attention :**
- Ne perdez **jamais** l'ancienne clé avant d'avoir vérifié la bascule (étape 4) — sinon les credentials deviennent indéchiffrables (`SecretDecryptionError` à l'accès).
- La procédure ne nécessite à aucun moment d'écrire un secret en clair sur disque : la bascule se fait en mémoire du process.
- Les credentials indéchiffrables (clé perdue) rendent la cible inutilisable pour SSH/scan : il faut ressaisir les credentials via l'API/UI.

## Sauvegarde et restauration

### Sauvegarde via la CLI (grammaire normalisée)

```bash
# Backup core — export de la base et des fichiers de configuration
windflow admin backup create --output /backup/windflow-20260401.tar.gz

# Backup d'App (volumes, values, config) — verbe universel du chapitre 02
windflow apps backup nextcloud
```

Le backup core embarque : le fichier `.env`, le compose file actif, un dump de la base (copie SQLite ou `pg_dump` selon le mode), et les données WindFlow (plugins installés, configurations) depuis le volume `windflow_data`.

### Contenu du script `backup-windflow.sh`

Le script du dépôt automatise la même procédure. Exemple illustratif — cœur du script :

```bash
#!/bin/bash
# backup-windflow.sh (extrait)
set -e
BACKUP_DIR=${1:-/backup/windflow}
DATE=$(date +%Y%m%d_%H%M%S)
TMP_DIR=$(mktemp -d)

# Configuration
cp .env "${TMP_DIR}/"

# Base de données — selon le mode détecté
if grep -q "WINDFLOW_DB_MODE=light" .env; then
    docker compose -f docker-compose.light.yml cp \
        windflow-api:/data/windflow.db "${TMP_DIR}/windflow.db"
else
    docker compose exec -T postgres pg_dump -U windflow windflow \
        > "${TMP_DIR}/database.sql"
fi

# Données WindFlow (volume windflow_data)
docker run --rm -v windflow_windflow_data:/source:ro \
    -v "${TMP_DIR}:/backup" alpine \
    tar czf /backup/windflow_data.tar.gz -C /source .

tar czf "${BACKUP_DIR}/windflow_${DATE}.tar.gz" -C "${TMP_DIR}" .
echo "Sauvegarde terminée : ${BACKUP_DIR}/windflow_${DATE}.tar.gz"
```

### Restauration

```bash
# Via la CLI (grammaire normalisée)
windflow admin backup restore --input /backup/windflow-20260401.tar.gz
```

Le script `restore-windflow.sh` du dépôt enchaîne : arrêt des services → extraction de l'archive → restauration du `.env` et du compose file → `up -d` des services de base → restauration de la base (copie SQLite ou `psql`) → restauration du volume `windflow_data` → redémarrage.

### Backups applicatifs avancés

Pour des backups avancés (volumes applicatifs, planification cron, destinations offsite S3/SFTP, rétention), installer le plugin Restic ou Borg (chapitre [12-marketplace.md](12-marketplace.md)). Les snapshots de Machines ne sont pas des backups longue durée (chapitre [03-modele-compute.md](03-modele-compute.md)).

## Désinstallation

```bash
cd /opt/windflow

# Arrêter et supprimer les containers et volumes
docker compose down -v          # ou : docker compose -f docker-compose.light.yml down -v

# Supprimer les fichiers
sudo rm -rf /opt/windflow
```

## Dépannage

### L'API ne démarre pas

```bash
docker compose logs windflow-api

# Causes fréquentes :
# - PostgreSQL pas prêt → vérifier "docker compose logs postgres"
# - Port 8080 déjà utilisé → changer le port dans docker-compose.yml
# - Pas assez de RAM → passer en mode léger (--light)
```

### Pas assez de mémoire sur Raspberry Pi

```bash
free -m
# Si < 1 Go libre, utiliser le mode léger
docker compose down
docker compose -f docker-compose.light.yml up -d

# Optionnel : augmenter le swap (Raspberry Pi OS)
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
sudo dphys-swapfile setup && sudo dphys-swapfile swapon
```

### Les images ne se téléchargent pas (ARM)

```bash
# Vérifier que les images multi-arch sont disponibles
docker manifest inspect windflow/api:latest

# Forcer le pull pour la bonne plateforme
uname -m   # doit afficher aarch64 (ARM64) ou x86_64
docker pull --platform linux/arm64 windflow/api:latest
```

### Réinitialiser WindFlow

```bash
# Supprime toutes les données
docker compose down -v
docker compose up -d
docker compose exec -T windflow-api alembic upgrade head
docker compose exec -it windflow-api windflow admin create \
  --username admin --email admin@example.com
```

### Récupération d'urgence (instance verrouillée)

Scénarios couverts : compte admin oublié, mot de passe admin perdu, tous les refresh tokens expirés, unique Super Admin exclu par erreur. Les commandes d'urgence s'exécutent via `docker exec` **directement dans le container `windflow-api`**, sans passer par l'API authentifiée — elles opèrent sur la base en direct et inscrivent chaque opération au journal d'audit (chapitre [15-securite.md](15-securite.md)). En mode léger, préfixer avec `-f docker-compose.light.yml`.

```bash
# Lister les utilisateurs (aucune authentification requise)
docker compose exec -T windflow-api windflow admin recovery list-users

# Créer un admin de secours (mot de passe généré, affiché une seule fois)
docker compose exec -it windflow-api windflow admin recovery create-admin \
  --username rescue --email rescue@example.com

# Réinitialiser le mot de passe d'un utilisateur
docker compose exec -it windflow-api windflow admin recovery reset-password \
  --username admin

# Révoquer toutes les sessions et refresh tokens d'un utilisateur
docker compose exec -T windflow-api windflow admin recovery clear-sessions \
  --username admin
```

Règles de sûreté :

- `create-admin` **ajoute** un compte de secours, il ne remplace ni ne rétrograde jamais un Super Admin existant — la protection du dernier Super Admin reste applicable (chapitre [08-rbac-permissions.md](08-rbac-permissions.md)) ;
- chaque commande affiche un résumé de l'opération (compte ciblé, action, horodatage) et le journalise ;
- ces commandes nécessitent un accès shell à la machine hôte : leur sécurité est celle de l'hôte (SSH/sudo), pas celle de WindFlow — à utiliser en dernier recours, pas en routine d'administration.

## Voir aussi

- [04-architecture.md](04-architecture.md) — profils de déploiement et empreintes (référence unique)
- [05-stack-technologique.md](05-stack-technologique.md) — stack technique derrière chaque profil
- [15-securite.md](15-securite.md) — checklist d'installation sécurisée
- [10-cli-tui.md](10-cli-tui.md) — commandes `admin backup` et `admin info`
- [12-marketplace.md](12-marketplace.md) — plugins à installer en premier
