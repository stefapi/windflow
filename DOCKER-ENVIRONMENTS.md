# Environnements Docker WindFlow

Ce document explique la structure des fichiers Docker Compose de WindFlow après la refactorisation.

## 📁 Structure des Fichiers

### `docker-compose.yml` (Principal)
- **Rôle** : Point d'entrée principal qui inclut la configuration de développement
- **Usage** : `docker compose up` (développement par défaut)
- **Contenu** : Documentation et redirection vers `docker-compose-dev.yml`

### `docker-compose-dev.yml` (Développement)
- **Rôle** : Configuration complète pour le développement local
- **Usage** : `docker compose -f docker-compose-dev.yml up`
- **Caractéristiques** :
  - Hot reload activé
  - Ports exposés pour debug
  - Volumes bind pour le code source
  - Services de debug (adminer, mailhog)
  - Logs verbeux
  - Aucune limite de ressources
  - Configuration Vault en mode développement

### `docker-compose.prod.yml` (Production)
- **Rôle** : Configuration optimisée pour la production
- **Usage** : `docker compose -f docker-compose.prod.yml up -d`
- **Caractéristiques** :
  - SSL/TLS avec certificats Let's Encrypt automatiques
  - Réplication des services critiques (2 répliques API/Workers/Frontend)
  - Monitoring complet (Prometheus, Grafana, Loki, Promtail)
  - Backup automatique vers S3
  - Limites de ressources strictes
  - Sécurité renforcée (headers, réseaux isolés)
  - Logging centralisé
  - Health checks complets

## 🚀 Commandes Makefile Mises à Jour

### Développement
```bash
make dev                 # Démarrer l'environnement de développement complet
make docker-dev          # Démarrer uniquement les services Docker dev
make docker-build        # Builder les images de développement
make docker-logs         # Afficher les logs de développement
make docker-stop         # Arrêter les services de développement
```

### Production
```bash
make docker-prod         # Démarrer l'environnement de production
make docker-build-prod   # Builder les images de production
make docker-logs-prod    # Afficher les logs de production
make docker-stop-prod    # Arrêter les services de production
```

## 🔄 Migration depuis l'Ancien Système

Si vous utilisiez l'ancien `docker-compose.yml` :

### Avant (Ancien)
```bash
docker compose up        # Démarrait le développement
```

### Après (Nouveau)
```bash
docker compose up        # Démarre toujours le développement (redirection)
# OU explicitement :
docker compose -f docker-compose-dev.yml up
```

### Production
```bash
# Nouvelle commande pour la production
docker compose -f docker-compose.prod.yml up -d
```

## 🎯 Avantages de cette Structure

### 1. **Séparation Claire**
- Développement et production sont complètement séparés
- Aucun risque de confusion d'environnement
- Configuration spécialisée pour chaque usage

### 2. **Facilité d'Utilisation**
- `docker compose up` fonctionne toujours pour le développement
- Pas de changement pour les développeurs existants
- Documentation claire dans chaque fichier

### 3. **Production Robuste**
- Configuration production optimisée et sécurisée
- Monitoring et backup intégrés
- Haute disponibilité avec réplication

### 4. **Maintenance Simplifiée**
- Chaque environnement a ses propres paramètres
- Mise à jour indépendante des configurations
- Tests plus faciles pour chaque environnement

## 📖 Liens vers la Documentation

- **Développement** : Voir `docker-compose-dev.yml` pour les détails
- **Production** : Voir [PRODUCTION-DEPLOYMENT.md](PRODUCTION-DEPLOYMENT.md)
- **Variables d'environnement** : Voir `.env.prod.example`
- **Commandes** : `make help` pour la liste complète

## 🔧 Dépannage

### Le fichier `docker-compose.yml` ne fonctionne plus
- Le nouveau fichier redirige vers `docker-compose-dev.yml`
- Utilisez : `docker compose -f docker-compose-dev.yml up`

### Erreur "file not found"
- Assurez-vous que `docker-compose-dev.yml` existe
- Vérifiez que vous êtes dans le bon répertoire

### Services production ne démarrent pas
- Consultez [PRODUCTION-DEPLOYMENT.md](PRODUCTION-DEPLOYMENT.md)
- Vérifiez votre fichier `.env.prod`
- Créez le réseau : `docker network create traefik-public`

---

**Version** : 1.0  
**Date** : 30/09/2025  
**Auteur** : Équipe WindFlow
