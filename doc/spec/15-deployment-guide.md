# Guide de Déploiement - WindFlow

## Vue d'Ensemble

Ce guide couvre l'installation et la configuration complète de WindFlow, depuis un déploiement de développement jusqu'à une architecture de production haute disponibilité.

### Prérequis Système

**Minimum (Développement) :**
- CPU : 4 cores
- RAM : 8 GB
- Stockage : 50 GB SSD
- OS : Ubuntu 20.04+ / RHEL 8+ / macOS 12+

**Recommandé (Production) :**
- CPU : 16 cores
- RAM : 32 GB
- Stockage : 200 GB SSD
- OS : Ubuntu 22.04 LTS / RHEL 9

**Logiciels Requis :**
- Docker 24.0+
- Docker Compose v2
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+

## Installation Rapide (Development)

### 1. Clone et Configuration

```bash
# Clone du repository
git clone https://github.com/windflow/windflow.git
cd windflow

# Configuration de l'environnement
cp .env.example .env
vim .env  # Configurer les variables d'environnement
```

### 2. Variables d'Environnement

```bash
# .env configuration minimale
DATABASE_URL=postgresql://windflow:password@localhost:5432/windflow
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
VAULT_URL=http://localhost:8200
VAULT_TOKEN=your-vault-token

# Configuration LLM (optionnel)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Configuration email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 3. Déploiement avec Docker Compose

```bash
# Démarrage des services
docker compose up -d

# Vérification du statut
docker compose ps
docker compose logs -f windflow-api
```

### 4. Configuration Initiale

```bash
# Initialisation de la base de données
docker compose exec windflow-api alembic upgrade head

# Création du super-administrateur
docker compose exec windflow-api python scripts/create_superuser.py \
  --username admin \
  --email admin@windflow.local \
  --password SecurePassword123!

# Test de l'installation
curl http://localhost:8000/api/v1/health
```

## Configuration Docker Compose

### docker-compose.yml Complet

```yaml
version: '3.8'

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
      - ./init-scripts:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U windflow"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Cache Redis
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # Vault pour la gestion des secrets
  vault:
    image: hashicorp/vault:1.15
    restart: unless-stopped
    ports:
      - "8200:8200"
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: ${VAULT_TOKEN}
      VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
    cap_add:
      - IPC_LOCK
    volumes:
      - vault_data:/vault/data
      - ./vault-config:/vault/config
    command: vault server -dev -dev-listen-address=0.0.0.0:8200

  # API Backend
  windflow-api:
    build:
      context: .
      dockerfile: Dockerfile.api
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://windflow:${POSTGRES_PASSWORD}@postgres:5432/windflow
      REDIS_URL: redis://redis:6379/0
      VAULT_URL: http://vault:8200
      VAULT_TOKEN: ${VAULT_TOKEN}
      SECRET_KEY: ${SECRET_KEY}
    volumes:
      - ./logs:/app/logs
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      vault:
        condition: service_started

  # Worker Celery pour les tâches asynchrones
  windflow-worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql://windflow:${POSTGRES_PASSWORD}@postgres:5432/windflow
      REDIS_URL: redis://redis:6379/0
      VAULT_URL: http://vault:8200
      VAULT_TOKEN: ${VAULT_TOKEN}
    volumes:
      - ./logs:/app/logs
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      - postgres
      - redis
      - vault

  # Frontend Vue.js
  windflow-frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    ports:
      - "3000:80"
    environment:
      API_BASE_URL: http://localhost:8000/api/v1
    depends_on:
      - windflow-api

  # Monitoring avec Prometheus
  prometheus:
    image: prom/prometheus:latest
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  # Visualisation avec Grafana
  grafana:
    image: grafana/grafana:latest
    restart: unless-stopped
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning

volumes:
  postgres_data:
  redis_data:
  vault_data:
  prometheus_data:
  grafana_data:

networks:
  default:
    name: windflow
```

## Déploiement Production

### Architecture Haute Disponibilité

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  # Load Balancer HAProxy
  haproxy:
    image: haproxy:2.8
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "8404:8404"  # Stats
    volumes:
      - ./haproxy/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
      - ./ssl:/etc/ssl/private:ro
    depends_on:
      - windflow-api-1
      - windflow-api-2

  # API Backend - Instance 1
  windflow-api-1:
    extends:
      file: docker-compose.yml
      service: windflow-api
    ports: []  # Pas d'exposition directe
    environment:
      INSTANCE_ID: api-1

  # API Backend - Instance 2  
  windflow-api-2:
    extends:
      file: docker-compose.yml
      service: windflow-api
    ports: []
    environment:
      INSTANCE_ID: api-2

  # PostgreSQL Primary
  postgres-primary:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_DB: windflow
      POSTGRES_USER: windflow
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_REPLICATION_USER: replicator
      POSTGRES_REPLICATION_PASSWORD: ${REPLICATION_PASSWORD}
    volumes:
      - postgres_primary_data:/var/lib/postgresql/data
      - ./postgres/primary.conf:/etc/postgresql/postgresql.conf
      - ./postgres/pg_hba.conf:/etc/postgresql/pg_hba.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf

  # PostgreSQL Standby (Read Replica)
  postgres-standby:
    image: postgres:15
    restart: unless-stopped
    environment:
      PGUSER: replicator
      POSTGRES_PASSWORD: ${REPLICATION_PASSWORD}
      POSTGRES_PRIMARY_HOST: postgres-primary
      POSTGRES_PRIMARY_PORT: 5432
    volumes:
      - postgres_standby_data:/var/lib/postgresql/data
    command: |
      bash -c "
      pg_basebackup -h postgres-primary -D /var/lib/postgresql/data -U replicator -v -P -W &&
      echo 'standby_mode = on' >> /var/lib/postgresql/data/recovery.conf &&
      echo 'primary_conninfo = \"host=postgres-primary port=5432 user=replicator\"' >> /var/lib/postgresql/data/recovery.conf &&
      postgres
      "

  # Redis Cluster
  redis-1:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "7001:7001"
    volumes:
      - redis_1_data:/data
    command: redis-server --port 7001 --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes

  redis-2:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "7002:7002"
    volumes:
      - redis_2_data:/data
    command: redis-server --port 7002 --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes

  redis-3:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "7003:7003"
    volumes:
      - redis_3_data:/data
    command: redis-server --port 7003 --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes

volumes:
  postgres_primary_data:
  postgres_standby_data:
  redis_1_data:
  redis_2_data:
  redis_3_data:
```

### Configuration HAProxy

```
# haproxy/haproxy.cfg
global
    daemon
    maxconn 4096
    log stdout local0
    
defaults
    mode http
    timeout connect 5s
    timeout client 30s
    timeout server 30s
    option httplog
    
frontend windflow_frontend
    bind *:80
    bind *:443 ssl crt /etc/ssl/private/windflow.pem
    redirect scheme https if !{ ssl_fc }
    
    # API requests
    acl is_api path_beg /api/
    use_backend windflow_api if is_api
    
    # Default to frontend
    default_backend windflow_frontend
    
backend windflow_api
    balance roundrobin
    option httpchk GET /api/v1/health
    server api-1 windflow-api-1:8000 check
    server api-2 windflow-api-2:8000 check
    
backend windflow_frontend
    balance roundrobin
    option httpchk GET /health
    server frontend-1 windflow-frontend:80 check
    
listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
```

## Configuration Kubernetes

### Namespace et ConfigMap

```yaml
# k8s/namespace.yml
apiVersion: v1
kind: Namespace
metadata:
  name: windflow
  labels:
    name: windflow

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: windflow-config
  namespace: windflow
data:
  DATABASE_URL: "postgresql://windflow:password@postgres:5432/windflow"
  REDIS_URL: "redis://redis:6379/0"
  LOG_LEVEL: "INFO"
```

### Déploiement API

```yaml
# k8s/api-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: windflow-api
  namespace: windflow
spec:
  replicas: 3
  selector:
    matchLabels:
      app: windflow-api
  template:
    metadata:
      labels:
        app: windflow-api
    spec:
      containers:
      - name: windflow-api
        image: windflow/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: windflow-secrets
              key: database-url
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: windflow-secrets
              key: secret-key
        envFrom:
        - configMapRef:
            name: windflow-config
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          limits:
            cpu: 1000m
            memory: 2Gi
          requests:
            cpu: 500m
            memory: 1Gi

---
apiVersion: v1
kind: Service
metadata:
  name: windflow-api-service
  namespace: windflow
spec:
  selector:
    app: windflow-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

### Ingress Controller

```yaml
# k8s/ingress.yml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: windflow-ingress
  namespace: windflow
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - windflow.example.com
    secretName: windflow-tls
  rules:
  - host: windflow.example.com
    http:
      paths:
      - path: /api/
        pathType: Prefix
        backend:
          service:
            name: windflow-api-service
            port:
              number: 80
      - path: /
        pathType: Prefix
        backend:
          service:
            name: windflow-frontend-service
            port:
              number: 80
```

## Scripts d'Installation

### Script d'Installation Automatique

```bash
#!/bin/bash
# install-windflow.sh

set -e

WINDFLOW_VERSION=${1:-latest}
INSTALL_DIR=${2:-/opt/windflow}
DOMAIN=${3:-localhost}

echo "🚀 Installation de WindFlow ${WINDFLOW_VERSION}"

# Vérification des prérequis
check_requirements() {
    echo "📋 Vérification des prérequis..."
    
    command -v docker >/dev/null 2>&1 || {
        echo "❌ Docker n'est pas installé"
        exit 1
    }
    
    command -v docker compose >/dev/null 2>&1 || {
        echo "❌ Docker Compose n'est pas installé"
        exit 1
    }
    
    echo "✅ Prérequis validés"
}

# Création des répertoires
setup_directories() {
    echo "📁 Création des répertoires..."
    sudo mkdir -p ${INSTALL_DIR}
    sudo chown $(whoami):$(whoami) ${INSTALL_DIR}
    cd ${INSTALL_DIR}
}

# Téléchargement des fichiers
download_files() {
    echo "⬇️ Téléchargement des fichiers WindFlow..."
    
    if [ "$WINDFLOW_VERSION" = "latest" ]; then
        curl -L https://github.com/windflow/windflow/archive/main.tar.gz | tar xz --strip-components=1
    else
        curl -L https://github.com/windflow/windflow/archive/v${WINDFLOW_VERSION}.tar.gz | tar xz --strip-components=1
    fi
}

# Configuration de l'environnement
setup_environment() {
    echo "⚙️ Configuration de l'environnement..."
    
    # Génération des secrets
    SECRET_KEY=$(openssl rand -hex 32)
    POSTGRES_PASSWORD=$(openssl rand -base64 32)
    VAULT_TOKEN=$(openssl rand -hex 16)
    GRAFANA_PASSWORD=$(openssl rand -base64 16)
    
    # Création du fichier .env
    cat > .env << EOF
# Configuration WindFlow
DOMAIN=${DOMAIN}
SECRET_KEY=${SECRET_KEY}

# Base de données
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# Vault
VAULT_TOKEN=${VAULT_TOKEN}

# Monitoring
GRAFANA_PASSWORD=${GRAFANA_PASSWORD}

# Email (à configurer)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-password

# LLM (optionnel)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
EOF

    echo "✅ Fichier .env créé avec des secrets générés"
}

# Démarrage des services
start_services() {
    echo "🔄 Démarrage des services WindFlow..."
    
    docker compose pull
    docker compose up -d
    
    echo "⏳ Attente du démarrage des services..."
    sleep 30
    
    # Initialisation de la base de données
    docker compose exec -T windflow-api alembic upgrade head
    
    echo "✅ Services démarrés avec succès"
}

# Création du super-administrateur
create_superuser() {
    echo "👤 Création du super-administrateur..."
    
    read -p "Nom d'utilisateur admin: " ADMIN_USERNAME
    read -p "Email admin: " ADMIN_EMAIL
    read -s -p "Mot de passe admin: " ADMIN_PASSWORD
    echo
    
    docker compose exec -T windflow-api python scripts/create_superuser.py \
        --username "${ADMIN_USERNAME}" \
        --email "${ADMIN_EMAIL}" \
        --password "${ADMIN_PASSWORD}"
        
    echo "✅ Super-administrateur créé"
}

# Test de l'installation
test_installation() {
    echo "🧪 Test de l'installation..."
    
    # Test API
    if curl -f http://localhost:8000/api/v1/health >/dev/null 2>&1; then
        echo "✅ API accessible"
    else
        echo "❌ API non accessible"
        exit 1
    fi
    
    # Test Frontend
    if curl -f http://localhost:3000 >/dev/null 2>&1; then
        echo "✅ Frontend accessible"
    else
        echo "❌ Frontend non accessible"
        exit 1
    fi
}

# Affichage des informations finales
show_info() {
    echo
    echo "🎉 Installation de WindFlow terminée avec succès!"
    echo
    echo "📍 Accès aux services:"
    echo "   Frontend: http://${DOMAIN}:3000"
    echo "   API:      http://${DOMAIN}:8000"
    echo "   Grafana:  http://${DOMAIN}:3001 (admin/$(cat .env | grep GRAFANA_PASSWORD | cut -d= -f2))"
    echo
    echo "📁 Répertoire d'installation: ${INSTALL_DIR}"
    echo "📄 Configuration: ${INSTALL_DIR}/.env"
    echo
    echo "🔧 Commandes utiles:"
    echo "   Logs:     docker compose logs -f"
    echo "   Restart:  docker compose restart"
    echo "   Stop:     docker compose down"
    echo
}

# Exécution principale
main() {
    check_requirements
    setup_directories
    download_files
    setup_environment
    start_services
    create_superuser
    test_installation
    show_info
}

main "$@"
```

## Sauvegarde et Restauration

### Script de Sauvegarde

```bash
#!/bin/bash
# backup-windflow.sh

BACKUP_DIR=${1:-/backup/windflow}
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="windflow_backup_${DATE}"

echo "💾 Sauvegarde WindFlow - ${DATE}"

# Création du répertoire de sauvegarde
mkdir -p ${BACKUP_DIR}/${BACKUP_NAME}

# Sauvegarde de la base de données
echo "📊 Sauvegarde de la base de données..."
docker compose exec -T postgres pg_dump -U windflow windflow > ${BACKUP_DIR}/${BACKUP_NAME}/database.sql

# Sauvegarde des volumes
echo "💿 Sauvegarde des volumes..."
docker run --rm -v windflow_postgres_data:/data -v ${BACKUP_DIR}/${BACKUP_NAME}:/backup alpine tar czf /backup/postgres_data.tar.gz -C /data .
docker run --rm -v windflow_redis_data:/data -v ${BACKUP_DIR}/${BACKUP_NAME}:/backup alpine tar czf /backup/redis_data.tar.gz -C /data .
docker run --rm -v windflow_vault_data:/data -v ${BACKUP_DIR}/${BACKUP_NAME}:/backup alpine tar czf /backup/vault_data.tar.gz -C /data .

# Sauvegarde de la configuration
echo "⚙️ Sauvegarde de la configuration..."
cp .env ${BACKUP_DIR}/${BACKUP_NAME}/
cp docker-compose.yml ${BACKUP_DIR}/${BACKUP_NAME}/

# Compression finale
echo "🗜️ Compression de la sauvegarde..."
cd ${BACKUP_DIR}
tar czf ${BACKUP_NAME}.tar.gz ${BACKUP_NAME}/
rm -rf ${BACKUP_NAME}/

echo "✅ Sauvegarde terminée: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
```

---

**Références :**
- [Vue d'Ensemble](01-overview.md) - Contexte du projet
- [Architecture](02-architecture.md) - Architecture du système
- [Stack Technologique](03-technology-stack.md) - Technologies utilisées
- [Configuration](06-rbac-permissions.md) - Permissions et RBAC
- [Monitoring](12-monitoring.md) - Surveillance et métriques
