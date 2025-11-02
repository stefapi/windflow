# WindFlow Docker Environments

This document explains the structure of WindFlow’s Docker Compose files after the refactor.

## 📁 File Structure

### `docker-compose.yml` (Main)

* **Role:** Main entry point that includes the development configuration
* **Usage:** `docker compose up` (development by default)
* **Contents:** Documentation and redirection to `docker-compose-dev.yml`

### `docker-compose-dev.yml` (Development)

* **Role:** Full configuration for local development
* **Usage:** `docker compose -f docker-compose-dev.yml up`
* **Features:**

  * Hot reload enabled
  * Ports exposed for debugging
  * Bind mounts for source code
  * Debug services (Adminer, MailHog)
  * Verbose logs
  * No resource limits
  * Vault configured in development mode

### `docker-compose.prod.yml` (Production)

* **Role:** Configuration optimized for production
* **Usage:** `docker compose -f docker-compose.prod.yml up -d`
* **Features:**

  * SSL/TLS with automatic Let’s Encrypt certificates
  * Replication of critical services (2 replicas for API/Workers/Frontend)
  * Full monitoring (Prometheus, Grafana, Loki, Promtail)
  * Automatic backups to S3
  * Strict resource limits
  * Hardened security (headers, isolated networks)
  * Centralized logging
  * Comprehensive health checks

## 🚀 Updated Makefile Commands

### Development

```bash
make dev                 # Start the full development environment
make docker-dev          # Start Docker dev services only
make docker-build        # Build development images
make docker-logs         # Show development logs
make docker-stop         # Stop development services
```

### Production

```bash
make docker-prod         # Start the production environment
make docker-build-prod   # Build production images
make docker-logs-prod    # Show production logs
make docker-stop-prod    # Stop production services
```

## 🔄 Migration from the Old System

If you used the old `docker-compose.yml`:

### Before (Old)

```bash
docker compose up        # Started development
```

### After (New)

```bash
docker compose up        # Still starts development (redirected)
# OR explicitly:
docker compose -f docker-compose-dev.yml up
```

### Production

```bash
# New command for production
docker compose -f docker-compose.prod.yml up -d
```

## 🎯 Benefits of This Structure

### 1. **Clear Separation**

* Development and production are completely separated
* No risk of environment confusion
* Configuration tailored to each use case

### 2. **Ease of Use**

* `docker compose up` always works for development
* No changes for existing developers
* Clear documentation in each file

### 3. **Robust Production**

* Optimized and secured production configuration
* Built-in monitoring and backups
* High availability with replication

### 4. **Simplified Maintenance**

* Each environment has its own settings
* Independent configuration updates
* Easier testing per environment

## 📖 Documentation Links

* **Development:** See `docker-compose-dev.yml` for details
* **Production:** See [PRODUCTION-DEPLOYMENT.md](PRODUCTION-DEPLOYMENT.md)
* **Environment variables:** See `.env.prod.example`
* **Commands:** Run `make help` for the full list

## 🔧 Troubleshooting

### The `docker-compose.yml` file no longer works

* The new file redirects to `docker-compose-dev.yml`
* Use: `docker compose -f docker-compose-dev.yml up`

### “file not found” error

* Make sure `docker-compose-dev.yml` exists
* Verify you’re in the correct directory

### Production services won’t start

* See [PRODUCTION-DEPLOYMENT.md](PRODUCTION-DEPLOYMENT.md)
* Check your `.env.prod` file
* Create the network: `docker network create traefik-public`

---

**Version:** 1.0
**Date:** 09/30/2025
**Author:** WindFlow Team
