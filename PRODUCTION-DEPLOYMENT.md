# WindFlow Production Deployment Guide

This guide describes deploying WindFlow to production using the `docker-compose.prod.yml` file.

> **Note:** The `docker-compose-dev.yml` file is used for local development, while `docker-compose.prod.yml` is optimized for production.

## 🏗️ Production Architecture

The production setup includes:

* **SSL Reverse Proxy:** Traefik with automatic Let's Encrypt certificates
* **High Availability:** Replication of critical services (API, Workers, Frontend)
* **Hardened Security:** Security headers, isolated networks, authentication
* **Full Monitoring:** Prometheus, Grafana, Loki, Promtail, Node Exporter, cAdvisor
* **Automatic Backups:** PostgreSQL backups to S3 with retention
* **Secrets Management:** HashiCorp Vault to secure credentials
* **Centralized Logging:** Aggregation with Loki and Promtail
* **Resource Management:** CPU/RAM limits and restart policies

## 📋 Prerequisites

### Server

* **OS:** Ubuntu 20.04+ or CentOS 8+ recommended
* **RAM:** Minimum 8 GB, 16 GB recommended
* **CPU:** Minimum 4 cores, 8 cores recommended
* **Storage:** Minimum 100 GB SSD, 500 GB recommended
* **Docker:** Version 24.0+ with Docker Compose v2
* **Network:** Ports 80 and 443 open

### DNS

* Domain configured and pointing to your server
* Optional subdomains: `api.`, `grafana.`, `metrics.`

### External Accounts

* **AWS S3:** Bucket for backups (optional)
* **SMTP:** Email service for Grafana alerts (optional)

## 🚀 Installation

WindFlow offers two installation methods: **automatic** (recommended) and **manual**.

### Method 1: Automatic Installation (Recommended)

The `install.sh` script fully automates WindFlow installation with OS detection, error handling, and automatic configuration.

#### Quick Install

```bash
# Install with default parameters
curl -fsSL https://raw.githubusercontent.com/stefapi/windflow/main/scripts/install.sh | bash

# OR download and run locally
wget https://raw.githubusercontent.com/stefapi/windflow/main/scripts/install.sh
chmod +x install.sh
./install.sh
```

#### Custom Installation

```bash
# Install with custom parameters
./install.sh --version v1.2.0 --domain windflow.example.com --install-dir /opt/windflow

# Available options
./install.sh --help
```

#### Supported Systems

The automatic installer supports:

* **Ubuntu** 18.04+ / **Debian** 10+
* **CentOS** 8+ / **RHEL** 8+ / **Rocky Linux** / **AlmaLinux**
* **Fedora** 35+
* **Arch Linux** / **Manjaro**
* **Alpine Linux** 3.15+
* **openSUSE** / **SLES**

#### What the script does automatically

1. **System detection:** Automatically identifies OS and architecture
2. **Prerequisite checks:** Validates system resources (RAM, disk space, network)
3. **Dependency installation:** Docker, Docker Compose, curl, git, openssl
4. **Download WindFlow:** Fetches the specified version from GitHub
5. **Secure configuration:** Automatically generates passwords and keys
6. **Service startup:** Launches containers and performs checks
7. **Integrity tests:** Validates that services are functioning

#### Logs & Troubleshooting

```bash
# Installation logs
tail -f /tmp/windflow-install.log

# Saved access information
cat /opt/windflow/passwords.txt

# Service status
docker compose ps
```

### Method 2: Manual Installation

For full control or systems not supported by the automatic script.

#### 1. Server Preparation

```bash
# System update
sudo apt update && sudo apt upgrade -y

# Docker installation
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Docker Compose v2 installation
sudo apt install docker-compose-plugin

# Create data directories
sudo mkdir -p /opt/windflow/{data,backups,logs}
sudo mkdir -p /opt/windflow/data/{postgres,redis,vault,prometheus,grafana,loki,letsencrypt,uploads}
sudo chown -R $USER:$USER /opt/windflow

# Create Traefik network
docker network create traefik-public
```

#### 2. Cloning & Configuration

```bash
# Clone the repository
git clone https://github.com/stefapi/windflow.git
cd windflow

# Environment configuration
cp .env.prod.example .env.prod
nano .env.prod  # Configure your variables

# Check Docker Compose files
ls -la docker-compose*.yml
# docker-compose-dev.yml   <- Development
# docker-compose.prod.yml  <- Production
```

#### 3. Variable Configuration

Edit `.env.prod` with your specific values:

```bash
# Generate secure passwords
export POSTGRES_PASSWORD=$(openssl rand -base64 32)
export REDIS_PASSWORD=$(openssl rand -base64 32)
export SECRET_KEY=$(openssl rand -hex 32)
export GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 32)
export GRAFANA_SECRET_KEY=$(openssl rand -hex 32)

# Append to .env.prod
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" >> .env.prod
echo "REDIS_PASSWORD=$REDIS_PASSWORD" >> .env.prod
echo "SECRET_KEY=$SECRET_KEY" >> .env.prod
echo "GRAFANA_ADMIN_PASSWORD=$GRAFANA_ADMIN_PASSWORD" >> .env.prod
echo "GRAFANA_SECRET_KEY=$GRAFANA_SECRET_KEY" >> .env.prod
```

#### 4. Deployment

```bash
# Build and start services
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

## 🔐 Initial Configuration

### Vault Initialization

```bash
# Connect to the Vault container
docker compose -f docker-compose.prod.yml exec vault sh

# Initialize (on first start)
vault operator init -key-shares=3 -key-threshold=2

# Save the unseal keys and the root token!
# Unseal Vault
vault operator unseal <key1>
vault operator unseal <key2>

# Authenticate with the root token
vault auth <root_token>

# Configure WindFlow secrets
vault secrets enable -path=windflow kv-v2
vault kv put windflow/database username=$POSTGRES_USER password=$POSTGRES_PASSWORD
vault kv put windflow/redis password=$REDIS_PASSWORD
vault kv put windflow/app secret_key=$SECRET_KEY
```

### Database

```bash
# Run migrations
docker compose -f docker-compose.prod.yml exec windflow-api alembic upgrade head

# Create the admin user
docker compose -f docker-compose.prod.yml exec windflow-api python -m windflow.scripts.create_admin
```

## 🔧 Service Configuration

### Traefik (Reverse Proxy)

Configuration is automatic via Docker labels. Verify that:

* SSL certificates are generated: [https://your-domain.com](https://your-domain.com)
* The Traefik dashboard is disabled in production
* HTTP-to-HTTPS redirects work

### Monitoring

Monitoring services are auto-configured:

* **Prometheus:** [https://metrics.your-domain.com](https://metrics.your-domain.com)
* **Grafana:** [https://grafana.your-domain.com](https://grafana.your-domain.com)
* **Dashboards:** Loaded automatically from `infrastructure/docker/grafana/dashboards/`

Grafana credentials: admin / (see GRAFANA_ADMIN_PASSWORD)

### Alerting

Configure Grafana alerts via SMTP:

1. Log in to Grafana
2. Go to Alerting > Notification Channels
3. Create an email channel with your SMTP configuration
4. Configure alert rules in the dashboards

## 💾 Backup & Restore

### Automatic Backup

The backup service runs automatically with the configured parameters:

```bash
# Check backups
docker compose -f docker-compose.prod.yml logs backup

# Manual backup
docker compose -f docker-compose.prod.yml exec backup /scripts/manual-backup.sh
```

### Restore

```bash
# Stop dependent services
docker compose -f docker-compose.prod.yml stop windflow-api windflow-worker

# Restore from S3
docker compose -f docker-compose.prod.yml exec backup /scripts/restore-from-s3.sh <backup-date>

# Or local restore
docker compose -f docker-compose.prod.yml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB < /backup/windflow_backup_YYYY-MM-DD.sql

# Restart services
docker compose -f docker-compose.prod.yml start windflow-api windflow-worker
```

## 📊 Monitoring & Maintenance

### Health Checks

```bash
# Check service health
curl -f https://your-domain.com/api/health
curl -f https://api.your-domain.com/health

# Container monitoring
docker compose -f docker-compose.prod.yml ps
docker stats
```

### Logs

```bash
# Application logs
docker compose -f docker-compose.prod.yml logs -f windflow-api
docker compose -f docker-compose.prod.yml logs -f windflow-worker

# Traefik logs
docker compose -f docker-compose.prod.yml logs -f traefik

# Centralized logs via Loki (Grafana UI)
# Explore > Loki > {container_name="windflow-api"}
```

### Upgrades

#### Using the Installation Script (Recommended)

```bash
# Automatic upgrade to the latest version
./install.sh --update

# Upgrade to a specific version
./install.sh --update --version v1.3.0

# The script automatically performs:
# - Backup of existing data
# - Download of the new version
# - Preservation of configuration (.env)
# - Service restart
# - Post-upgrade validation
```

#### Manual Upgrade

```bash
# Backup before upgrading
docker compose -f docker-compose.prod.yml exec backup /scripts/manual-backup.sh

# Backup configuration
cp .env .env.backup

# Update code
git pull origin main

# Rebuild and redeploy
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

# Database migrations
docker compose -f docker-compose.prod.yml exec windflow-api alembic upgrade head
```

#### Rollback if Needed

```bash
# With the script (if automatic backup available)
./install.sh --restore-backup

# Manual method
git checkout v1.2.0  # previous version
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

## 🛡️ Security

### Security Checklist

* [ ] Unique, complex passwords (32+ characters)
* [ ] Valid Let's Encrypt SSL certificates
* [ ] Vault properly configured and unsealed
* [ ] Isolated Docker networks (internal backend)
* [ ] Security headers configured via Traefik
* [ ] Encrypted backups to S3
* [ ] Logs free of sensitive data
* [ ] Prometheus protected by basic auth
* [ ] Grafana with a strong password
* [ ] Non-essential ports closed

### Server Hardening

```bash
# UFW firewall
sudo ufw enable
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS

# Fail2ban for SSH
sudo apt install fail2ban
sudo systemctl enable fail2ban

# Disable root user
sudo passwd -l root

# Automatic security updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
```

## 🔧 Troubleshooting

### Automatic Installation Issues

**install.sh script fails:**

```bash
# Check installation logs
tail -f /tmp/windflow-install.log

# Run with debug enabled
bash -x ./install.sh --domain your-domain.com

# Check prerequisites
# - Network connectivity
ping -c 1 github.com

# - User permissions
groups $USER | grep docker

# - Available disk space
df -h /opt
```

**Unsupported operating system:**

```bash
# Verify OS detection
cat /etc/os-release
uname -a

# Manually install dependencies
# See "Manual Installation" section below
```

**Docker issues with the script:**

```bash
# Verify Docker installation
docker --version
docker compose version

# Test Docker functionality
docker run --rm hello-world

# Manually add user to docker group if needed
sudo usermod -aG docker $USER
newgrp docker
```

**Download failure:**

```bash
# Manual download test
curl -I https://github.com/stefapi/windflow/archive/main.tar.gz

# Use a proxy if needed
export https_proxy=http://proxy:port
./install.sh
```

### Post-Installation Issues

**Services won't start:**

```bash
# Check resources
df -h
free -h
docker system df

# Clean up if needed
docker system prune -a

# Review generated passwords
cat /opt/windflow/passwords.txt
```

**SSL certificates:**

```bash
# Check Traefik
docker compose -f docker-compose.prod.yml logs traefik | grep -i acme

# Manual Let's Encrypt test
curl -I https://your-domain.com
```

**Database:**

```bash
# PostgreSQL connection
docker compose -f docker-compose.prod.yml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB

# Check connections
docker compose -f docker-compose.prod.yml exec postgres pg_stat_activity
```

**Performance:**

```bash
# Real-time monitoring
docker stats
htop

# Prometheus metrics
curl http://localhost:9090/metrics | grep windflow
```

## 📞 Support

For help:

1. **Documentation:** See the [main README](README.md)
2. **Issues:** Open an issue on the GitHub repository
3. **Logs:** Collect relevant logs before requesting help
4. **Monitoring:** Check Grafana for system metrics

## 📝 Scheduled Maintenance

### Daily Tasks

* Verify automatic backups
* Review Grafana alerts
* Monitor performance metrics

### Weekly Tasks

* Clean up old logs
* Verify SSL certificates
* Test backup restore

### Monthly Tasks

* Update dependencies
* Audit security logs
* Review retention policies

---

**Version:** 1.0
**Last updated:** 09/30/2025
**Author:** WindFlow Team
