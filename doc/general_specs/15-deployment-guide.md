# Guide de Déploiement - WindFlow

## Vue d'Ensemble

Ce guide couvre l'installation de WindFlow, du mode léger sur Raspberry Pi jusqu'à un déploiement standard sur serveur dédié. WindFlow est conçu pour être installé en moins de 5 minutes.

### Prérequis

**Système :**
- **OS** : Linux (Debian/Ubuntu, Raspberry Pi OS, Fedora, ou équivalent)
- **Architecture** : x86_64 ou ARM64
- **Docker** ≥ 20.10 + Docker Compose v2

**Pour le développement (optionnel) :**
- Python ≥ 3.11 + Poetry ≥ 1.8
- Node.js ≥ 20 + pnpm ≥ 9

### Profils d'Installation

| Profil | RAM minimum | CPU | Stockage | Machine type | Compose file |
|--------|-------------|-----|----------|--------------|--------------|
| **Léger** | 2 Go (512 Mo pour le core) | 1 core ARM | 8 Go | Raspberry Pi 4 (2 Go) | `docker-compose.light.yml` |
| **Standard** | 4 Go (1.5 Go pour le core) | 2 cores | 20 Go | RPi 4 (4 Go), mini PC, VPS | `docker-compose.yml` |
| **Développement** | 4 Go | 2 cores | 20 Go | Laptop / PC | Manuel (sans Docker) |

---

## Installation Mode Léger (Raspberry Pi)

Le mode léger utilise SQLite au lieu de PostgreSQL et un cache en mémoire au lieu de Redis. Il est conçu pour les machines avec peu de RAM.

### 1. Script d'Installation

```bash
# Télécharger et lancer l'installateur
curl -fsSL https://get.windflow.io/install.sh | bash -s -- --light

# Ou manuellement :
git clone https://github.com/windflow/windflow.git
cd windflow
./scripts/install.sh --light
```

### 2. Ce que fait le script

Le script `install.sh --light` :
1. Vérifie que Docker est installé
2. Détecte l'architecture (arm64 / amd64)
3. Génère un `SECRET_KEY` aléatoire
4. Crée le fichier `.env`
5. Lance `docker compose -f docker-compose.light.yml up -d`
6. Attend que l'API soit prête
7. Initialise la base de données (SQLite)
8. Demande la création du compte admin
9. Affiche l'URL d'accès

### 3. docker-compose.light.yml

```yaml
services:
  # API Backend
  windflow-api:
    image: windflow/api:latest
    restart: unless-stopped
    ports:
      - "8080:8000"
    environment:
      WINDFLOW_DB_MODE: light
      DATABASE_URL: "sqlite+aiosqlite:///data/windflow.db"
      SECRET_KEY: ${SECRET_KEY}
      CELERY_BROKER_URL: "filesystem://"
      CELERY_RESULT_BACKEND: "file:///data/celery-results"
      LOG_LEVEL: INFO
    volumes:
      - windflow_data:/data
      - /var/run/docker.sock:/var/run/docker.sock
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

  # Worker Celery (1 process)
  windflow-worker:
    image: windflow/worker:latest
    restart: unless-stopped
    environment:
      WINDFLOW_DB_MODE: light
      DATABASE_URL: "sqlite+aiosqlite:///data/windflow.db"
      SECRET_KEY: ${SECRET_KEY}
      CELERY_BROKER_URL: "filesystem://"
      CELERY_RESULT_BACKEND: "file:///data/celery-results"
      CELERY_CONCURRENCY: 1
    volumes:
      - windflow_data:/data
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      windflow-api:
        condition: service_healthy

  # Frontend
  windflow-frontend:
    image: windflow/frontend:latest
    restart: unless-stopped
    ports:
      - "80:80"
    environment:
      API_URL: http://windflow-api:8000
    depends_on:
      - windflow-api

volumes:
  windflow_data:
```

**Empreinte** : ~3 containers, ~500 Mo RAM total. Pas de PostgreSQL, pas de Redis.

### 4. Accès

- **Interface Web** : `http://<ip-du-raspberry>` (port 80)
- **API** : `http://<ip-du-raspberry>:8080/api/docs`
- **CLI** : `docker exec -it windflow-api windflow --help`

---

## Installation Mode Standard

Le mode standard utilise PostgreSQL et Redis. Recommandé pour les machines avec 4 Go de RAM ou plus.

### 1. Script d'Installation

```bash
# Avec le script
curl -fsSL https://get.windflow.io/install.sh | bash

# Ou manuellement :
git clone https://github.com/windflow/windflow.git
cd windflow
./scripts/install.sh
```

### 2. docker-compose.yml

```yaml
services:
  # Base de données PostgreSQL
  postgres:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_DB: windflow
      POSTGRES_USER: windflow
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U windflow"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Cache et Broker Redis
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 128mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # API Backend
  windflow-api:
    image: windflow/api:latest
    restart: unless-stopped
    ports:
      - "8080:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://windflow:${POSTGRES_PASSWORD}@postgres:5432/windflow
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
      LOG_LEVEL: INFO
    volumes:
      - windflow_data:/data
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

  # Worker Celery
  windflow-worker:
    image: windflow/worker:latest
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql+asyncpg://windflow:${POSTGRES_PASSWORD}@postgres:5432/windflow
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
      CELERY_CONCURRENCY: 2
    volumes:
      - windflow_data:/data
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      - postgres
      - redis

  # Frontend
  windflow-frontend:
    image: windflow/frontend:latest
    restart: unless-stopped
    ports:
      - "80:80"
    environment:
      API_URL: http://windflow-api:8000
    depends_on:
      - windflow-api

volumes:
  postgres_data:
  redis_data:
  windflow_data:

networks:
  default:
    name: windflow
```

### 3. Variables d'Environnement

Le fichier `.env` ne contient que les variables du core. Les plugins gèrent leur propre configuration via l'UI.

```bash
# .env — généré automatiquement par install.sh
SECRET_KEY=<généré automatiquement>
POSTGRES_PASSWORD=<généré automatiquement>
```

C'est tout. Pas de VAULT_TOKEN, pas d'OPENAI_API_KEY, pas de SMTP — tout ça est géré par les plugins correspondants si vous les installez.

### 4. Configuration Initiale

```bash
# Vérifier que tout tourne
docker compose ps

# Initialiser la base de données (fait automatiquement par install.sh)
docker compose exec -T windflow-api alembic upgrade head

# Créer le compte admin (fait automatiquement par install.sh)
docker compose exec -it windflow-api windflow admin create \
  --username admin \
  --email admin@example.com
# Le script demande le mot de passe de manière interactive

# Tester
curl http://localhost:8080/api/v1/health
```

### 5. Accès

- **Interface Web** : `http://<ip-du-serveur>` (port 80)
- **API** : `http://<ip-du-serveur>:8080/api/docs`
- **CLI** : `docker exec -it windflow-api windflow --help`

---

## Installation Développement

Pour contribuer au code de WindFlow ou le modifier.

### Backend

```bash
git clone https://github.com/windflow/windflow.git
cd windflow

# Installer les dépendances
poetry install --with dev

# Lancer PostgreSQL et Redis avec Docker (pour le dev)
docker compose -f docker-compose.dev-deps.yml up -d

# Configurer l'environnement
cp .env.dev.example .env

# Initialiser la base de données
poetry run alembic upgrade head

# Créer un admin
poetry run windflow admin create --username admin --email admin@localhost

# Lancer le serveur de dev
poetry run uvicorn windflow.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev   # http://localhost:5173
```

### CLI / TUI

```bash
pip install -e ./cli
windflow --help
```

### docker-compose.dev-deps.yml

Uniquement PostgreSQL et Redis pour le développement local :

```yaml
services:
  postgres:
    image: postgres:15
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: windflow
      POSTGRES_USER: windflow
      POSTGRES_PASSWORD: devpassword
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_dev_data:
```

### .env.dev.example

```bash
# Développement local
DATABASE_URL=postgresql+asyncpg://windflow:devpassword@localhost:5432/windflow
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=dev-secret-key-not-for-production
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
LOG_LEVEL=DEBUG
DEBUG=true
```

---

## Après l'Installation : Premiers Pas

Une fois WindFlow installé et le compte admin créé :

### 1. Se connecter

Ouvrir l'interface web et se connecter avec le compte admin.

### 2. Vérifier le Docker local

WindFlow détecte automatiquement le Docker Engine local. Aller dans **Targets** pour vérifier qu'il apparaît avec ses capacités.

### 3. Installer le premier plugin

Aller dans **Marketplace** et installer un plugin utile, par exemple :
- **Traefik** si vous voulez exposer des services avec un nom de domaine et du HTTPS
- **Uptime Kuma** pour surveiller la disponibilité de vos services
- **PostgreSQL Manager** si vous utilisez des containers PostgreSQL

### 4. Déployer une première stack

Aller dans **Marketplace > Stacks** et déployer une application, par exemple Gitea (serveur Git) ou Uptime Kuma. Le wizard de configuration vous guide.

### 5. Ajouter une machine distante (optionnel)

Si vous avez d'autres serveurs, aller dans **Targets > Ajouter** et configurer une connexion SSH. WindFlow détectera automatiquement Docker et/ou libvirt sur la machine distante.

---

## Script d'Installation Complet

```bash
#!/bin/bash
# install.sh — Script d'installation WindFlow
set -e

# --- Paramètres ---
WINDFLOW_VERSION=${WINDFLOW_VERSION:-latest}
INSTALL_DIR=${INSTALL_DIR:-/opt/windflow}
MODE="standard"

# Parse des arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --light) MODE="light" ;;
        --dir) INSTALL_DIR="$2"; shift ;;
        --version) WINDFLOW_VERSION="$2"; shift ;;
        *) echo "Option inconnue: $1"; exit 1 ;;
    esac
    shift
done

echo "========================================"
echo "  WindFlow Installer (mode: ${MODE})"
echo "========================================"
echo

# --- Vérifications ---
check_requirements() {
    echo "[1/7] Vérification des prérequis..."

    if ! command -v docker &> /dev/null; then
        echo "  ✗ Docker n'est pas installé"
        echo "  → Installer Docker : https://docs.docker.com/engine/install/"
        exit 1
    fi
    echo "  ✓ Docker $(docker --version | grep -oP '\d+\.\d+\.\d+')"

    if ! docker compose version &> /dev/null; then
        echo "  ✗ Docker Compose v2 n'est pas installé"
        exit 1
    fi
    echo "  ✓ Docker Compose $(docker compose version --short)"

    # Vérification architecture
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)  ARCH_LABEL="amd64" ;;
        aarch64) ARCH_LABEL="arm64" ;;
        *)
            echo "  ✗ Architecture non supportée: $ARCH"
            exit 1
            ;;
    esac
    echo "  ✓ Architecture: ${ARCH_LABEL}"

    # Vérification mémoire
    TOTAL_MEM_MB=$(free -m | awk '/^Mem:/{print $2}')
    if [ "$MODE" = "light" ] && [ "$TOTAL_MEM_MB" -lt 1500 ]; then
        echo "  ⚠ Mémoire faible (${TOTAL_MEM_MB} Mo) — mode léger recommandé"
    elif [ "$MODE" = "standard" ] && [ "$TOTAL_MEM_MB" -lt 3500 ]; then
        echo "  ⚠ Mémoire faible (${TOTAL_MEM_MB} Mo) — le mode léger est recommandé (--light)"
    fi
    echo "  ✓ Mémoire: ${TOTAL_MEM_MB} Mo"
    echo
}

# --- Répertoire d'installation ---
setup_directory() {
    echo "[2/7] Préparation du répertoire..."
    sudo mkdir -p "${INSTALL_DIR}"
    sudo chown "$(whoami):$(whoami)" "${INSTALL_DIR}"
    cd "${INSTALL_DIR}"
    echo "  ✓ ${INSTALL_DIR}"
    echo
}

# --- Téléchargement ---
download() {
    echo "[3/7] Téléchargement de WindFlow ${WINDFLOW_VERSION}..."
    if [ "$WINDFLOW_VERSION" = "latest" ]; then
        curl -sL https://github.com/windflow/windflow/archive/main.tar.gz | tar xz --strip-components=1
    else
        curl -sL "https://github.com/windflow/windflow/archive/v${WINDFLOW_VERSION}.tar.gz" | tar xz --strip-components=1
    fi
    echo "  ✓ Fichiers téléchargés"
    echo
}

# --- Configuration ---
configure() {
    echo "[4/7] Configuration..."

    SECRET_KEY=$(openssl rand -hex 32)

    if [ "$MODE" = "light" ]; then
        cat > .env << EOF
# WindFlow — Mode Léger
SECRET_KEY=${SECRET_KEY}
WINDFLOW_DB_MODE=light
EOF
        COMPOSE_FILE="docker-compose.light.yml"
    else
        POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
        cat > .env << EOF
# WindFlow — Mode Standard
SECRET_KEY=${SECRET_KEY}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
EOF
        COMPOSE_FILE="docker-compose.yml"
    fi

    echo "  ✓ .env généré"
    echo
}

# --- Démarrage ---
start() {
    echo "[5/7] Démarrage des services..."
    docker compose -f "${COMPOSE_FILE}" pull
    docker compose -f "${COMPOSE_FILE}" up -d

    echo "  ⏳ Attente du démarrage de l'API..."
    for i in $(seq 1 30); do
        if curl -sf http://localhost:8080/api/v1/health > /dev/null 2>&1; then
            echo "  ✓ API prête"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "  ✗ L'API n'a pas démarré dans les temps"
            echo "  → Consulter les logs : docker compose -f ${COMPOSE_FILE} logs windflow-api"
            exit 1
        fi
        sleep 2
    done
    echo
}

# --- Base de données ---
init_db() {
    echo "[6/7] Initialisation de la base de données..."
    docker compose -f "${COMPOSE_FILE}" exec -T windflow-api alembic upgrade head
    echo "  ✓ Base de données initialisée"
    echo
}

# --- Admin ---
create_admin() {
    echo "[7/7] Création du compte administrateur"
    read -rp "  Nom d'utilisateur : " ADMIN_USER
    read -rp "  Email : " ADMIN_EMAIL
    docker compose -f "${COMPOSE_FILE}" exec -it windflow-api windflow admin create \
        --username "${ADMIN_USER}" \
        --email "${ADMIN_EMAIL}"
    echo
}

# --- Résumé ---
show_summary() {
    IP=$(hostname -I | awk '{print $1}')
    echo "========================================"
    echo "  Installation terminée !"
    echo "========================================"
    echo
    echo "  Interface Web : http://${IP}"
    echo "  API Docs      : http://${IP}:8080/api/docs"
    echo "  CLI            : docker exec -it windflow-api windflow --help"
    echo
    echo "  Répertoire     : ${INSTALL_DIR}"
    echo "  Mode           : ${MODE}"
    echo "  Compose file   : ${COMPOSE_FILE}"
    echo
    echo "  Commandes utiles :"
    echo "    Logs     : docker compose -f ${COMPOSE_FILE} logs -f"
    echo "    Restart  : docker compose -f ${COMPOSE_FILE} restart"
    echo "    Stop     : docker compose -f ${COMPOSE_FILE} down"
    echo "    Update   : docker compose -f ${COMPOSE_FILE} pull && docker compose -f ${COMPOSE_FILE} up -d"
    echo
    echo "  Prochaines étapes :"
    echo "    1. Se connecter à l'interface web"
    echo "    2. Aller dans Marketplace et installer un plugin (ex: Traefik)"
    echo "    3. Déployer votre première stack"
    echo
}

# --- Main ---
check_requirements
setup_directory
download
configure
start
init_db
create_admin
show_summary
```

---

## Mise à Jour

### Mise à jour standard

```bash
cd /opt/windflow

# Tirer les nouvelles images
docker compose pull

# Relancer avec les nouvelles versions
docker compose up -d

# Appliquer les migrations de base de données
docker compose exec -T windflow-api alembic upgrade head
```

### Mise à jour mode léger

```bash
cd /opt/windflow
docker compose -f docker-compose.light.yml pull
docker compose -f docker-compose.light.yml up -d
docker compose -f docker-compose.light.yml exec -T windflow-api alembic upgrade head
```

---

## Sauvegarde et Restauration

### Sauvegarde

```bash
#!/bin/bash
# backup-windflow.sh
set -e

BACKUP_DIR=${1:-/backup/windflow}
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/windflow_${DATE}.tar.gz"

mkdir -p "${BACKUP_DIR}"

echo "Sauvegarde WindFlow — ${DATE}"

# Détection du mode
if grep -q "WINDFLOW_DB_MODE=light" .env 2>/dev/null; then
    MODE="light"
    COMPOSE_FILE="docker-compose.light.yml"
else
    MODE="standard"
    COMPOSE_FILE="docker-compose.yml"
fi

# Dossier temporaire
TMP_DIR=$(mktemp -d)

# Configuration
echo "  → Configuration..."
cp .env "${TMP_DIR}/"
cp "${COMPOSE_FILE}" "${TMP_DIR}/"

# Base de données
if [ "$MODE" = "light" ]; then
    echo "  → Base SQLite..."
    docker compose -f "${COMPOSE_FILE}" exec -T windflow-api cp /data/windflow.db /tmp/windflow.db.bak
    docker compose -f "${COMPOSE_FILE}" cp windflow-api:/tmp/windflow.db.bak "${TMP_DIR}/windflow.db"
else
    echo "  → Base PostgreSQL..."
    docker compose exec -T postgres pg_dump -U windflow windflow > "${TMP_DIR}/database.sql"
fi

# Données WindFlow (plugins installés, configs)
echo "  → Données WindFlow..."
docker run --rm \
    -v windflow_windflow_data:/source:ro \
    -v "${TMP_DIR}:/backup" \
    alpine tar czf /backup/windflow_data.tar.gz -C /source .

# Compression
echo "  → Compression..."
tar czf "${BACKUP_FILE}" -C "${TMP_DIR}" .
rm -rf "${TMP_DIR}"

echo "Sauvegarde terminée : ${BACKUP_FILE}"
echo "Taille : $(du -h "${BACKUP_FILE}" | cut -f1)"
```

### Restauration

```bash
#!/bin/bash
# restore-windflow.sh
set -e

BACKUP_FILE=$1
if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <fichier-backup.tar.gz>"
    exit 1
fi

echo "Restauration WindFlow depuis ${BACKUP_FILE}"

# Arrêter WindFlow
echo "  → Arrêt des services..."
docker compose down 2>/dev/null || true
docker compose -f docker-compose.light.yml down 2>/dev/null || true

# Extraction
TMP_DIR=$(mktemp -d)
tar xzf "${BACKUP_FILE}" -C "${TMP_DIR}"

# Restaurer la configuration
echo "  → Restauration de la configuration..."
cp "${TMP_DIR}/.env" .
if [ -f "${TMP_DIR}/docker-compose.light.yml" ]; then
    COMPOSE_FILE="docker-compose.light.yml"
else
    COMPOSE_FILE="docker-compose.yml"
fi

# Démarrer les services de base
echo "  → Démarrage des services..."
docker compose -f "${COMPOSE_FILE}" up -d

# Attendre que les services soient prêts
sleep 10

# Restaurer la base de données
if [ -f "${TMP_DIR}/windflow.db" ]; then
    echo "  → Restauration base SQLite..."
    docker compose -f "${COMPOSE_FILE}" cp "${TMP_DIR}/windflow.db" windflow-api:/data/windflow.db
elif [ -f "${TMP_DIR}/database.sql" ]; then
    echo "  → Restauration base PostgreSQL..."
    docker compose exec -T postgres psql -U windflow windflow < "${TMP_DIR}/database.sql"
fi

# Restaurer les données
if [ -f "${TMP_DIR}/windflow_data.tar.gz" ]; then
    echo "  → Restauration des données..."
    docker run --rm \
        -v windflow_windflow_data:/target \
        -v "${TMP_DIR}:/backup:ro" \
        alpine sh -c "cd /target && tar xzf /backup/windflow_data.tar.gz"
fi

# Redémarrer pour appliquer
docker compose -f "${COMPOSE_FILE}" restart

rm -rf "${TMP_DIR}"
echo "Restauration terminée."
```

---

## Désinstallation

```bash
cd /opt/windflow

# Arrêter et supprimer les containers et volumes
docker compose down -v
# ou
docker compose -f docker-compose.light.yml down -v

# Supprimer les fichiers
sudo rm -rf /opt/windflow
```

---

## Dépannage

### L'API ne démarre pas

```bash
# Vérifier les logs
docker compose logs windflow-api

# Causes fréquentes :
# - PostgreSQL pas prêt → vérifier "docker compose logs postgres"
# - Port 8080 déjà utilisé → changer le port dans docker-compose.yml
# - Pas assez de RAM → passer en mode léger (--light)
```

### Pas assez de mémoire sur Raspberry Pi

```bash
# Vérifier la mémoire disponible
free -m

# Si < 1 Go libre, utiliser le mode léger
docker compose down
docker compose -f docker-compose.light.yml up -d

# Optionnel : augmenter le swap
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### Les images ne se téléchargent pas (ARM)

```bash
# Vérifier que les images multi-arch sont disponibles
docker manifest inspect windflow/api:latest

# Si erreur, vérifier l'architecture
uname -m  # Doit afficher aarch64 (ARM64) ou x86_64

# Forcer le pull pour la bonne plateforme
docker pull --platform linux/arm64 windflow/api:latest
```

### Réinitialiser WindFlow

```bash
# Supprimer les volumes (perd toutes les données)
docker compose down -v
docker compose up -d
docker compose exec -T windflow-api alembic upgrade head

# Recréer un admin
docker compose exec -it windflow-api windflow admin create \
  --username admin --email admin@example.com
```

---

**Références :**
- [Vue d'Ensemble](01-overview.md) - Vision du projet
- [Architecture](02-architecture.md) - Architecture et système de plugins
- [Stack Technologique](03-technology-stack.md) - Technologies utilisées
- [Fonctionnalités Principales](10-core-features.md) - Fonctionnalités core
- [RBAC & Permissions](06-rbac-permissions.md) - Permissions et rôles
