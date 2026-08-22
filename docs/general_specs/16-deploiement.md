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
  windflow-api:
    image: windflow/api:latest
    environment:
      WINDFLOW_DB_MODE: light
      DATABASE_URL: "sqlite+aiosqlite:///data/windflow.db"
      CELERY_BROKER_URL: "filesystem://"
    volumes:
      - windflow_data:/data
      - /var/run/docker.sock:/var/run/docker.sock
  windflow-worker:
    image: windflow/worker:latest
    environment:
      CELERY_CONCURRENCY: 1        # 1 worker en mode léger
  windflow-frontend:
    image: windflow/frontend:latest
    ports:
      - "80:80"
```

**Empreinte** : ~3 containers, ~500 Mo RAM total. Pas de PostgreSQL, pas de Redis.

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
  windflow-api:
    image: windflow/api:latest
    ports: ["8080:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://windflow:${POSTGRES_PASSWORD}@postgres:5432/windflow
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
    volumes:
      - windflow_data:/data
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
  windflow-worker:
    image: windflow/worker:latest        # CELERY_CONCURRENCY: 2
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

# Tester
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

## Voir aussi

- [04-architecture.md](04-architecture.md) — profils de déploiement et empreintes (référence unique)
- [05-stack-technologique.md](05-stack-technologique.md) — stack technique derrière chaque profil
- [15-securite.md](15-securite.md) — checklist d'installation sécurisée
- [10-cli-tui.md](10-cli-tui.md) — commandes `admin backup` et `admin info`
- [12-marketplace.md](12-marketplace.md) — plugins à installer en premier
