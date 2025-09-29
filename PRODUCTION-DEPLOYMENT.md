# Guide de Déploiement Production WindFlow

Ce guide décrit le déploiement de WindFlow en production avec le fichier `docker-compose.prod.yml`.

> **Note** : Le fichier `docker-compose-dev.yml` est utilisé pour le développement local, tandis que `docker-compose.prod.yml` est optimisé pour la production.

## 🏗️ Architecture de Production

La configuration de production inclut :

- **Reverse Proxy SSL** : Traefik avec certificats Let's Encrypt automatiques
- **Haute Disponibilité** : Réplication des services critiques (API, Workers, Frontend)
- **Sécurité Renforcée** : Headers de sécurité, réseaux isolés, authentification
- **Monitoring Complet** : Prometheus, Grafana, Loki, Promtail, Node Exporter, cAdvisor
- **Backup Automatique** : Sauvegarde PostgreSQL vers S3 avec rétention
- **Gestion des Secrets** : HashiCorp Vault pour la sécurisation des credentials
- **Logging Centralisé** : Aggregation avec Loki et Promtail
- **Resource Management** : Limites CPU/RAM et politiques de redémarrage

## 📋 Prérequis

### Serveur
- **OS** : Ubuntu 20.04+ ou CentOS 8+ recommandé
- **RAM** : Minimum 8 GB, recommandé 16 GB
- **CPU** : Minimum 4 cores, recommandé 8 cores
- **Stockage** : Minimum 100 GB SSD, recommandé 500 GB
- **Docker** : Version 24.0+ avec Docker Compose v2
- **Réseau** : Ports 80 et 443 ouverts

### DNS
- Domaine configuré pointant vers votre serveur
- Sous-domaines optionnels : `api.`, `grafana.`, `metrics.`

### Comptes Externes
- **AWS S3** : Bucket pour les backups (optionnel)
- **SMTP** : Service email pour les alertes Grafana (optionnel)

## 🚀 Installation

WindFlow propose deux méthodes d'installation : **automatique** (recommandée) et **manuelle**.

### Méthode 1 : Installation Automatique (Recommandée)

Le script `install.sh` automatise complètement l'installation de WindFlow avec détection du système d'exploitation, gestion des erreurs et configuration automatique.

#### Installation Rapide

```bash
# Installation avec les paramètres par défaut
curl -fsSL https://raw.githubusercontent.com/stefapi/windflow/main/scripts/install.sh | bash

# OU téléchargement et exécution locale
wget https://raw.githubusercontent.com/stefapi/windflow/main/scripts/install.sh
chmod +x install.sh
./install.sh
```

#### Installation Personnalisée

```bash
# Installation avec paramètres personnalisés
./install.sh --version v1.2.0 --domain windflow.example.com --install-dir /opt/windflow

# Options disponibles
./install.sh --help
```

#### Systèmes Supportés

Le script d'installation automatique supporte :
- **Ubuntu** 18.04+ / **Debian** 10+
- **CentOS** 8+ / **RHEL** 8+ / **Rocky Linux** / **AlmaLinux**
- **Fedora** 35+
- **Arch Linux** / **Manjaro**
- **Alpine Linux** 3.15+
- **openSUSE** / **SLES**

#### Ce que fait le script automatiquement

1. **Détection du système** : Identification automatique de l'OS et de l'architecture
2. **Vérification des prérequis** : Validation des ressources système (RAM, espace disque, réseau)
3. **Installation des dépendances** : Docker, Docker Compose, curl, git, openssl
4. **Téléchargement de WindFlow** : Récupération de la version spécifiée depuis GitHub
5. **Configuration sécurisée** : Génération automatique des mots de passe et clés
6. **Démarrage des services** : Lancement et vérification des conteneurs
7. **Tests d'intégrité** : Validation du fonctionnement des services

#### Logs et Dépannage

```bash
# Logs d'installation
tail -f /tmp/windflow-install.log

# Informations d'accès sauvegardées
cat /opt/windflow/passwords.txt

# État des services
docker compose ps
```

### Méthode 2 : Installation Manuelle

Pour un contrôle complet ou sur des systèmes non supportés par le script automatique.

#### 1. Préparation du Serveur

```bash
# Mise à jour du système
sudo apt update && sudo apt upgrade -y

# Installation de Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Installation de Docker Compose v2
sudo apt install docker-compose-plugin

# Création des répertoires de données
sudo mkdir -p /opt/windflow/{data,backups,logs}
sudo mkdir -p /opt/windflow/data/{postgres,redis,vault,prometheus,grafana,loki,letsencrypt,uploads}
sudo chown -R $USER:$USER /opt/windflow

# Création du réseau Traefik
docker network create traefik-public
```

#### 2. Clonage et Configuration

```bash
# Clonage du repository
git clone https://github.com/stefapi/windflow.git
cd windflow

# Configuration de l'environnement
cp .env.prod.example .env.prod
nano .env.prod  # Configurez vos variables

# Vérification des fichiers Docker Compose
ls -la docker-compose*.yml
# docker-compose-dev.yml   <- Développement
# docker-compose.prod.yml  <- Production
```

#### 3. Configuration des Variables

Éditez `.env.prod` avec vos valeurs spécifiques :

```bash
# Génération des mots de passe sécurisés
export POSTGRES_PASSWORD=$(openssl rand -base64 32)
export REDIS_PASSWORD=$(openssl rand -base64 32)
export SECRET_KEY=$(openssl rand -hex 32)
export GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 32)
export GRAFANA_SECRET_KEY=$(openssl rand -hex 32)

# Ajout dans .env.prod
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" >> .env.prod
echo "REDIS_PASSWORD=$REDIS_PASSWORD" >> .env.prod
echo "SECRET_KEY=$SECRET_KEY" >> .env.prod
echo "GRAFANA_ADMIN_PASSWORD=$GRAFANA_ADMIN_PASSWORD" >> .env.prod
echo "GRAFANA_SECRET_KEY=$GRAFANA_SECRET_KEY" >> .env.prod
```

#### 4. Déploiement

```bash
# Construction et démarrage des services
docker compose -f docker-compose.prod.yml up -d

# Vérification du statut
docker compose -f docker-compose.prod.yml ps

# Consultation des logs
docker compose -f docker-compose.prod.yml logs -f
```

## 🔐 Configuration Initiale

### Initialisation de Vault

```bash
# Connexion au conteneur Vault
docker compose -f docker-compose.prod.yml exec vault sh

# Initialisation (si premier démarrage)
vault operator init -key-shares=3 -key-threshold=2

# Sauvegarder les clés de descellement et le root token !
# Descellement de Vault
vault operator unseal <key1>
vault operator unseal <key2>

# Authentification avec le root token
vault auth <root_token>

# Configuration des secrets WindFlow
vault secrets enable -path=windflow kv-v2
vault kv put windflow/database username=$POSTGRES_USER password=$POSTGRES_PASSWORD
vault kv put windflow/redis password=$REDIS_PASSWORD
vault kv put windflow/app secret_key=$SECRET_KEY
```

### Base de Données

```bash
# Exécution des migrations
docker compose -f docker-compose.prod.yml exec windflow-api alembic upgrade head

# Création de l'utilisateur administrateur
docker compose -f docker-compose.prod.yml exec windflow-api python -m windflow.scripts.create_admin
```

## 🔧 Configuration des Services

### Traefik (Reverse Proxy)

Le fichier de configuration est automatique via les labels Docker. Vérifiez que :

- Les certificats SSL sont générés : https://votre-domaine.com
- Le dashboard Traefik est désactivé en production
- Les redirections HTTP vers HTTPS fonctionnent

### Monitoring

Les services de monitoring sont automatiquement configurés :

- **Prometheus** : https://metrics.votre-domaine.com
- **Grafana** : https://grafana.votre-domaine.com
- **Dashboards** : Chargés automatiquement depuis `infrastructure/docker/grafana/dashboards/`

Credentials Grafana : admin / (voir GRAFANA_ADMIN_PASSWORD)

### Alerting

Configuration des alertes Grafana via SMTP :

1. Connectez-vous à Grafana
2. Allez dans Alerting > Notification Channels
3. Créez un channel email avec votre configuration SMTP
4. Configurez les règles d'alerte dans les dashboards

## 💾 Backup et Restauration

### Backup Automatique

Le service backup s'exécute automatiquement avec les paramètres configurés :

```bash
# Vérification des backups
docker compose -f docker-compose.prod.yml logs backup

# Backup manuel
docker compose -f docker-compose.prod.yml exec backup /scripts/manual-backup.sh
```

### Restauration

```bash
# Arrêt des services dépendants
docker compose -f docker-compose.prod.yml stop windflow-api windflow-worker

# Restauration depuis S3
docker compose -f docker-compose.prod.yml exec backup /scripts/restore-from-s3.sh <backup-date>

# Ou restauration locale
docker compose -f docker-compose.prod.yml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB < /backup/windflow_backup_YYYY-MM-DD.sql

# Redémarrage des services
docker compose -f docker-compose.prod.yml start windflow-api windflow-worker
```

## 📊 Surveillance et Maintenance

### Health Checks

```bash
# Vérification de l'état des services
curl -f https://votre-domaine.com/api/health
curl -f https://api.votre-domaine.com/health

# Monitoring des conteneurs
docker compose -f docker-compose.prod.yml ps
docker stats
```

### Logs

```bash
# Logs application
docker compose -f docker-compose.prod.yml logs -f windflow-api
docker compose -f docker-compose.prod.yml logs -f windflow-worker

# Logs Traefik
docker compose -f docker-compose.prod.yml logs -f traefik

# Logs centralisés via Loki (interface Grafana)
# Explore > Loki > {container_name="windflow-api"}
```

### Mise à Jour

#### Avec le Script d'Installation (Recommandé)

```bash
# Mise à jour automatique vers la dernière version
./install.sh --update

# Mise à jour vers une version spécifique
./install.sh --update --version v1.3.0

# Le script effectue automatiquement :
# - Sauvegarde des données existantes
# - Téléchargement de la nouvelle version
# - Préservation de la configuration (.env)
# - Redémarrage des services
# - Validation post-mise à jour
```

#### Mise à Jour Manuelle

```bash
# Sauvegarde avant mise à jour
docker compose -f docker-compose.prod.yml exec backup /scripts/manual-backup.sh

# Sauvegarde de la configuration
cp .env .env.backup

# Mise à jour du code
git pull origin main

# Reconstruction et redéploiement
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

# Migrations base de données
docker compose -f docker-compose.prod.yml exec windflow-api alembic upgrade head
```

#### Rollback en cas de problème

```bash
# Avec le script (si sauvegarde automatique disponible)
./install.sh --restore-backup

# Méthode manuelle
git checkout v1.2.0  # version précédente
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

## 🛡️ Sécurité

### Checklist Sécurité

- [ ] Mots de passe uniques et complexes (32+ caractères)
- [ ] Certificats SSL Let's Encrypt valides
- [ ] Vault correctement configuré et descellé
- [ ] Réseaux Docker isolés (backend internal)
- [ ] Headers de sécurité configurés via Traefik
- [ ] Backups chiffrés vers S3
- [ ] Logs sans données sensibles
- [ ] Prometheus protégé par basic auth
- [ ] Grafana avec mot de passe fort
- [ ] Ports non-essentiels fermés

### Hardening Serveur

```bash
# Firewall UFW
sudo ufw enable
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS

# Fail2ban pour SSH
sudo apt install fail2ban
sudo systemctl enable fail2ban

# Désactivation de l'utilisateur root
sudo passwd -l root

# Mise à jour automatique des paquets de sécurité
sudo apt install unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
```

## 🔧 Dépannage

### Problèmes d'Installation Automatique

**Script install.sh échoue :**
```bash
# Vérification des logs d'installation
tail -f /tmp/windflow-install.log

# Exécution avec debug activé
bash -x ./install.sh --domain votre-domaine.com

# Vérification des prérequis
# - Connectivité réseau
ping -c 1 github.com

# - Permissions utilisateur
groups $USER | grep docker

# - Espace disque disponible
df -h /opt
```

**Système d'exploitation non supporté :**
```bash
# Vérification de la détection d'OS
cat /etc/os-release
uname -a

# Installation manuelle des dépendances
# Voir section "Installation Manuelle" ci-dessous
```

**Problèmes Docker avec le script :**
```bash
# Vérification de l'installation Docker
docker --version
docker compose version

# Test de fonctionnalité Docker
docker run --rm hello-world

# Ajout manuel au groupe docker si nécessaire
sudo usermod -aG docker $USER
newgrp docker
```

**Échec de téléchargement :**
```bash
# Test manuel de téléchargement
curl -I https://github.com/stefapi/windflow/archive/main.tar.gz

# Utilisation d'un proxy si nécessaire
export https_proxy=http://proxy:port
./install.sh
```

### Problèmes Post-Installation

**Services qui ne démarrent pas :**
```bash
# Vérification des ressources
df -h
free -h
docker system df

# Nettoyage si nécessaire
docker system prune -a

# Consultation des mots de passe générés
cat /opt/windflow/passwords.txt
```

**Certificats SSL :**
```bash
# Vérification Traefik
docker compose -f docker-compose.prod.yml logs traefik | grep -i acme

# Test manuel Let's Encrypt
curl -I https://votre-domaine.com
```

**Base de données :**
```bash
# Connexion PostgreSQL
docker compose -f docker-compose.prod.yml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB

# Vérification des connexions
docker compose -f docker-compose.prod.yml exec postgres pg_stat_activity
```

**Performance :**
```bash
# Monitoring en temps réel
docker stats
htop

# Métriques Prometheus
curl http://localhost:9090/metrics | grep windflow
```

## 📞 Support

Pour obtenir de l'aide :

1. **Documentation** : Consultez le [README principal](README.md)
2. **Issues** : Ouvrez une issue sur le repository GitHub
3. **Logs** : Collectez les logs pertinents avant de demander de l'aide
4. **Monitoring** : Vérifiez Grafana pour les métriques système

## 📝 Maintenance Programmée

### Tâches Quotidiennes
- Vérification des backups automatiques
- Consultation des alertes Grafana
- Monitoring des métriques de performance

### Tâches Hebdomadaires
- Nettoyage des logs anciens
- Vérification des certificats SSL
- Test de restauration backup

### Tâches Mensuelles
- Mise à jour des dépendances
- Audit des logs de sécurité
- Révision des politiques de rétention

---

**Version** : 1.0  
**Dernière mise à jour** : 30/09/2025  
**Auteur** : Équipe WindFlow
