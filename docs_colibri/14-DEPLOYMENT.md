# Déploiement Production

[← Background Processes](13-BACKGROUND-PROCESSES.md) | [Retour à l'accueil →](README.md)

## 🚀 Vue d'ensemble

Guide de déploiement de Windflow-sample en production avec Docker Compose.

## 1. Docker Compose Production

```yaml
# docker-compose.yml
version: '3.8'

services:
  Windflow-sample:
    image: Windflow-sample/Windflow-sample:latest
    container_name: Windflow-sample
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - Windflow-sample-data:/app/data
    environment:
      - DATABASE_URL=postgresql://Windflow-sample:password@postgres:5432/Windflow-sample
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - SESSION_SECRET=${SESSION_SECRET}
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    image: postgres:15-alpine
    container_name: Windflow-sample-postgres
    restart: unless-stopped
    volumes:
      - postgres-data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=Windflow-sample
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=Windflow-sample
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U Windflow-sample"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  Windflow-sample-data:
  postgres-data:
```

## 2. Variables d'environnement

```bash
# .env.production
# Base de données
DATABASE_URL=postgresql://Windflow-sample:password@postgres:5432/Windflow-sample

# Sécurité (générer avec: openssl rand -base64 32)
ENCRYPTION_KEY=your-encryption-key-here
SESSION_SECRET=your-session-secret-here

# Optionnel: OIDC
OIDC_ISSUER_URL=https://keycloak.example.com/realms/myrealm
OIDC_CLIENT_ID=Windflow-sample
OIDC_CLIENT_SECRET=your-client-secret

# Optionnel: LDAP
LDAP_URL=ldap://ldap.example.com:389
LDAP_BIND_DN=cn=admin,dc=example,dc=com
LDAP_BIND_PASSWORD=admin-password
LDAP_BASE_DN=ou=users,dc=example,dc=com
```

## 3. Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Installer dépendances système
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installer dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier l'application
COPY . .

# Créer répertoire data
RUN mkdir -p /app/data

# Exposer port
EXPOSE 3000

# Commande de démarrage
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
```

## 4. Requirements Python

```txt
# requirements.txt
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
httpx>=0.24.0
sqlalchemy[asyncio]>=2.0.0
aiosqlite>=0.19.0
asyncpg>=0.28.0
passlib[bcrypt]>=1.7.4
pyotp>=2.9.0
cryptography>=41.0.0
pyjwt>=2.8.0
authlib>=1.2.0
ldap3>=2.9.1
psutil>=5.9.0
croniter>=1.3.0
python-multipart>=0.0.6
websockets>=11.0
```

## 5. Nginx Reverse Proxy

```nginx
# nginx.conf
server {
    listen 80;
    server_name Windflow-sample.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name Windflow-sample.example.com;

    ssl_certificate /etc/letsencrypt/live/Windflow-sample.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/Windflow-sample.example.com/privkey.pem;

    client_max_body_size 100M;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 6. Health Check

```python
# routes/health.py
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}

@router.get("/api/health/db")
async def db_health(db = Depends(get_db)):
    """Database health check"""
    try:
        await db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

## 7. Backup Script

```bash
#!/bin/bash
# scripts/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# Backup database
docker exec Windflow-sample-postgres pg_dump -U Windflow-sample Windflow-sample > $BACKUP_DIR/db_$DATE.sql

# Backup data
tar -czf $BACKUP_DIR/data_$DATE.tar.gz -C /var/lib/docker/volumes/Windflow-sample-data/_data .

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

---

[← Background Processes](13-BACKGROUND-PROCESSES.md) | [Retour à l'accueil →](README.md)
