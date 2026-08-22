# Spécification fonctionnelle Dockhand — Document 0 : Chapitrage

## Objet du document

Ce document constitue le **sommaire de référence** de la spécification fonctionnelle du logiciel Dockhand. Il définit la liste des chapitres, leur périmètre et leur ordre de lecture. Il ne contient volontairement pas le contenu détaillé : chaque chapitre est rédigé dans un document dédié de la série.

## Contexte

- **Produit spécifié** : Dockhand, **interface web de gestion Docker, auto-hébergeable**, destinée à administrer des conteneurs, des stacks Compose et des hôtes Docker multiples depuis une console unique.
- **Stack technique cible** :
  - **Frontend** : SPA **Vue 3.5** construite avec **Vite** (outillage **pnpm**), routée par **Vue Router**, à l'état géré par **Pinia** ; composants d'interface **PrimeVue 4** et styles **TailwindCSS** ; éditeurs YAML/environnement **CodeMirror 6** ; terminal navigateur **xterm.js** ; graphe des réseaux éditable via **Vue Flow**.
  - **Backend** : **Python 3.13** + **FastAPI** servi par **Uvicorn** (ASGI) — un seul runtime ; WebSockets natifs **Starlette** ; flux SSE via **sse-starlette** ; planificateur **APScheduler** (AsyncIOScheduler, triggers cron) ; accès à l'API Docker Engine via **aiodocker**, avec la CLI `docker compose` invoquée en sous-processus ; tests backend **pytest**.
  - **Hôtes distants** : **remote shell** — connexion SSH sortante (**AsyncSSH**) vers l'hôte distant et exécution du CLI docker sur cet hôte ; authentification par clés SSH (ed25519 recommandé) ; aucun jeton maison ni protocole dédié.
  - **Bases de données** : **SQLite** (défaut, via aiosqlite) ou **PostgreSQL** (optionnel, via psycopg 3), bascule par `DATABASE_URL` ; accès unifié par **SQLAlchemy 2.0** (async) et **un seul jeu de migrations Alembic**.
  - **Mise à jour** : sidecar **« image updater »** remplaçant le conteneur Dockhand.
- **Modèle de licence** : BSL 1.1 (gratuit pour usage personnel/interne/éducatif ; interdit en SaaS commercial ; conversion Apache 2.0 à la Change Date). Fonctionnalités avancées (RBAC, audit, préférences par utilisateur) conditionnées à une licence Enterprise ou SMB activée par clé signée RSA.
- **Localisation** : la série documentaire réside dans `docs/spec_dockhand_reference/` (documents `00-` à `15-`).

## Principes de structuration de la spécification

- La progression suit un ordre **du général au particulier** : présentation du produit, concepts et entités transverses, puis fonctions métier détaillées, enfin sujets transverses (sécurité, administration, API, exploitation).
- Chaque chapitre correspond à un document markdown indépendant de la série `01-`, `02-`, etc.
- Les numéros de chapitre sont définitifs : un chapitre ajouté ultérieurement est suffixé (ex. `09-bis`) afin de préserver les références croisées.

## Chapitres de la spécification

### 01 — Présentation générale du produit

Présente Dockhand, son positionnement et ses objectifs fonctionnels de haut niveau : gestion visuelle et temps réel d'infrastructures Docker, orchestration de stacks Compose, multi-environnements. Décrit les utilisateurs cibles (administrateur d'homelab, équipe ops interne), les cas d'usage principaux et le modèle de distribution (image Docker auto-hébergée `python:3.13-slim`, licence BSL/éditions Free et Enterprise/SMB).

- Positionnement, objectifs et propositions de valeur
- Utilisateurs et contextes d'usage cibles
- Cas d'usage majeurs (vue d'ensemble)
- Modèle de distribution, d'édition et de licence
- Glossaire de premier niveau et références

### 02 — Architecture fonctionnelle et vue d'ensemble du système

Décrit la composition du système : SPA Vue 3.5/Vite servie en statique, application FastAPI/Uvicorn (API REST, WebSockets Starlette, SSE sse-starlette), couche de collecte Docker intégrée au backend (tâches asyncio + aiodocker), remote shell SSH (AsyncSSH) pour les hôtes distants, bases SQLite/PostgreSQL via SQLAlchemy 2.0/Alembic, sidecar « image updater ». Explique les flux majeurs entre ces composants et les Docker Engine. Introduit la carte des modules fonctionnels servant de fil conducteur aux chapitres suivants.

- Composants (SPA Vue, backend FastAPI, couche de collecte, image updater, bases de données)
- Topologie de déploiement et flux entre composants
- Connexion à Docker : socket local, socket-proxy, TCP/TLS direct, remote shell SSH
- Dualité SQLite / PostgreSQL (bascule `DATABASE_URL`) et migrations Alembic unifiées
- Carte des modules fonctionnels et correspondance avec les chapitres

### 03 — Concepts et entités métier

Définit le vocabulaire fonctionnel et le modèle de données conceptuel : environnement, conteneur, image, volume, réseau, stack, source de stack, variable d'environnement de stack, mise à jour en attente, planification, sauvegarde, destination de sauvegarde, jetons d'API, utilisateurs/rôles. Précise les relations et les cycles de vie des entités principales.

- Environnement Docker (entité pivot) et ses paramètres de connexion, dont la clé SSH du remote shell
- Conteneur, image, réseau, volume (objets Docker maniés par Dockhand)
- Stack Compose, source de stack (interne/Git), variables d'environnement, fichiers synchronisés
- Registres d'images et credentials de registre
- Mises à jour en attente (digest et semver)
- Planifications et exécutions de tâches planifiées
- Destinations et configurations de sauvegarde, snapshots
- Utilisateurs, sessions, rôles, jetons d'API
- Événements, métriques, journaux d'audit

### 04 — Environnements et connexions aux hôtes Docker

Détaille la gestion des environnements : ajout, modification, suppression, types de connexion (socket local, socket-proxy, TCP direct avec TLS optionnel, remote shell SSH), états en ligne/hors ligne, libellés et icônes, options de collecte (activité, métriques, mise en évidence des changements). Couvre la supervision de santé des connexions et le remote shell SSH (clés SSH, known_hosts, commandes docker exécutées à distance).

- Création et paramétrage d'un environnement (type de connexion, TLS, options)
- Connexions socket, socket-proxy, TCP direct et remote shell SSH
- Cycle de vie et états d'un environnement ; détection hors-ligne
- Remote shell SSH : établissement, commandes distantes, fiabilité, sécurité
- Clés SSH (ed25519 recommandé), known_hosts et périmètre d'accès
- Libellés, icônes et préférences d'affichage

### 05 — Gestion des conteneurs

Décrit la fonction centrale : inventaire temps réel des conteneurs, démarrage/arrêt/redémarrage/suppression, accès aux détails (inspection), statistiques, gestion de l'état de santé. Couvre les fonctions interactives : streaming des journaux en SSE avec filtres, terminal interactif (exec via WebSocket Starlette et xterm.js), navigateur de fichiers du conteneur (parcours, édition, téléversement, téléchargement), recreate avec fusion d'environnement/labels.

- Inventaire et supervision temps réel (statut, santé, ports, ressources)
- Cycle de vie : start, stop, restart, pause, remove, recreate
- Journaux : streaming SSE, filtres, recherche, favoris
- Terminal interactif dans le conteneur (exec, WebSocket + xterm.js)
- Navigateur de fichiers conteneur (parcours, édition, upload/download)
- Batch : opérations groupées sur plusieurs conteneurs
- Suivi des mises à jour d'image en attente (indicateur, actions)

### 06 — Stacks Compose

Détaille la gestion des stacks Docker Compose : création depuis l'éditeur YAML (CodeMirror 6), déploiement, redéploiement, arrêt et suppression sécurisée (gardes-fous), variables d'environnement par stack, éditeur graphique de topologie (services, réseaux, volumes, secrets). Couvre la validation des fichiers Compose, le graphe de réseau éditable (Vue Flow : drag & drop des nœuds, création/suppression de nœuds et de liens, positions persistées) et les options de déploiement.

- Création et édition d'une stack (éditeur YAML, assistant, éditeur graphique)
- Déploiement, redéploiement et options (build, pull, force)
- Variables d'environnement de stack (valeurs secrètes masquées)
- Validation Compose (règles, vocabulaire, contexte effectif)
- Suppression protégée (garde-fous anti-suppression)
- Graphe de réseau éditable (Vue Flow), pile par pile
- Fichiers de stack et chemins associés sur l'hôte

### 07 — Intégration Git

Décrit le déploiement de stacks depuis des dépôts Git : credentials (none, HTTPS, SSH), dépôts et stacks Git (branche, chemin Compose, fichier .env, répertoire de contexte), synchronisation manuelle et automatique (planification), webhooks signés (formats GitHub/Gitea/Forgejo/GitLab), suivi de l'état de synchronisation (commit, statut, erreurs) et manifeste des fichiers synchronisés.

- Credentials Git (HTTPS, SSH avec passphrase)
- Dépôts Git et paramètres de synchronisation
- Stacks Git : chemins, contexte, options de déploiement (build, no-cache, repull, force)
- Synchronisation : manuelle, planifiée (cron), auto-update
- Webhooks de déploiement et vérification de signature
- État de synchronisation, historique, erreurs et fichiers synchronisés
- Sécurité (validation d'URL, isolation des chemins)

### 08 — Images, registres et gestion des mises à jour

Couvre la gestion des images : inventaire (tags, tailles, couches, usage), pull, suppression, nettoyage des images inutilisées (prune), gestion multi-instances. Décrit les registres (authentification, registre par défaut, catalogue distant) et le suivi des mises à jour d'images : détection par digest, suggestions semver pour images épinglées, mise à jour automatique planifiée avec critères (y compris critères de vulnérabilités).

- Inventaire et inspection d'images (couches, taille, conteneurs associés)
- Pull, suppression, prune d'images
- Registres : ajout, credentials, registre par défaut, catalogue
- Détection de mises à jour (digest, tags semver)
- Auto-update de conteneurs : planification, critères de vulnérabilités
- Mises à jour en attente : consultation, application, report

### 09 — Volumes, réseaux et maintenance système

Détaille la gestion des volumes et réseaux : inventaire, création, suppression, prune (avec protections), navigateur de fichiers de volume (helper `busybox:1.37.0`). Couvre la maintenance système de l'hôte Docker : informations système, usage disque, nettoyages planifiés (conteneurs/volumes/réseaux/images orphelins), helpers de volume et leur recyclage.

- Volumes : inventaire, création, suppression, prune protégé
- Navigateur de fichiers de volume
- Réseaux : inventaire, création, suppression, prune
- Informations système de l'hôte (version Docker, OS, ressources)
- Nettoyage système et planifications de maintenance
- Helpers de volume : cycle de vie, protections, purge

### 10 — Sécurité applicative : scans de vulnérabilités et secrets

Décrit les fonctions de sécurité applicative : scans d'images via Grype (`anchore/grype:v0.115.0`) et Trivy (`aquasec/trivy:0.71.2`) (conteneurs de scan réutilisables, files d'attente, cache), tableau de bord des vulnérabilités (filtrage, export). Couvre les fournisseurs de secrets externes (1Password Connect, Infisical, HashiCorp Vault, Doppler, Bitwarden, Proton, Service Account) : configuration, test de connexion, injection lors du déploiement, masquage des valeurs.

- Scans d'images : Grype, Trivy, double scanner, planification
- File de scan, cache des résultats, fraîcheur des données
- Tableau de bord vulnérabilités : vues, filtres, export
- Critères de vulnérabilités appliqués à l'auto-update
- Fournisseurs de secrets : types supportés et configuration
- Test de connexion, sondes, cache
- Injection de secrets au déploiement et masquage (clés injectées)

### 11 — Sauvegardes et restauration (bêta)

Décrit le sous-système de sauvegarde reposant sur restic : destinations (dépôt restic, mot de passe chiffré, variables d'environnement, politiques), configurations de sauvegarde (conteneur ou stack, volumes ciblés, arrêt avant sauvegarde, planification, rétention, options), exécution et suivi des jobs, snapshots (parcours, diff, restauration partielle ou complète), maintenance des dépôts (prune, check, verify), sécurité et cloisonnement par instance/environnement.

- Destinations restic : paramètres, chiffrement, test de connexion
- Configurations de sauvegarde : cibles, volumes, planification, rétention
- Exécutions : suivi, annulation, statuts, code d'erreurs
- Snapshots : liste, parcours de fichiers, diff, métadonnées
- Restauration : prévisualisation, restauration sélective, redéploiement de stack
- Maintenance de dépôt : prune, check, verify, auto-unlock
- Sécurité : balisage par instance, portée environnement (Enterprise)
- Statut bêta : activation par variable d'environnement

### 12 — Authentification, utilisateurs et contrôle d'accès (RBAC)

Décrit l'authentification : comptes locaux (Argon2id via argon2-cffi), SSO via OIDC multiple (authlib), LDAP/AD (ldap3), MFA TOTP avec codes de secours (pyotp), sessions (cookies HttpOnly, expiration), mode authentification désactivée. Puis le contrôle d'accès : rôles et permissions par domaine fonctionnel, portée par environnement, mappings de rôles depuis OIDC/LDAP, différences Free vs Enterprise, jetons d'API personnels, commandes d'administration des accès en urgence.

- Comptes locaux : création, mot de passe (Argon2id), profil, avatar
- SSO OIDC : fournisseurs multiples, découverte, claims, mappings de rôles
- LDAP/AD : configuration, filtres, groupes, TLS
- MFA : TOTP, codes de secours, activation par utilisateur
- Sessions : cookies, expiration, révocation, purge
- Rôles et permissions : structure, rôles système, portée environnement
- Free vs Enterprise : périmètre effectif des droits
- Jetons d'API : création, usage, expiration, préfixe
- Procédures d'urgence : create-admin, reset-password, disable-auth, list-users

### 13 — Observabilité : tableaux de bord, activité, audit, événements et notifications

Couvre l'observabilité fonctionnelle : tableau de bord personnalisable (tuiles d'environnement, vues), flux d'activité des conteneurs, journal d'audit (Enterprise), journalisation des événements de stack, collecte des métriques (CPU/mémoire/disque via la couche de collecte intégrée au backend, historique), export Prometheus (`prometheus-client`), et le système de notifications multi-canaux (SMTP via aiosmtplib, Discord, Slack, Telegram, Gotify, ntfy, Bark, Signal, Apprise, Pushover, webhook générique, workflows GitHub, Zabbix, Mattermost — assurés par la bibliothèque Python `apprise`) avec routage par type d'événement et par environnement.

- Tableau de bord : tuiles, disposition, préférences, filtres par libellé
- Activité des conteneurs : flux temps réel, filtres, surlignage des changements
- Journal d'audit : contenu, consultation, portée (Enterprise)
- Événements de stack et historique
- Métriques : collecte intégrée (tâches asyncio), stockage, historique, fraîcheur
- Export Prometheus / endpoint de métriques
- Notifications : canaux supportés, configuration, test
- Routage des notifications par type d'événement et par environnement
- Masquage par label de conteneur

### 14 — Automatisation : planificateur, modèles et API

Décrit l'automatisation : planificateur unifié (APScheduler — AsyncIOScheduler, triggers cron) couvrant auto-update de conteneurs, synchronisation Git, prune d'images, sauvegardes, maintenance de dépôts, nettoyages système (exécutions, événements, helpers, cache scanner), fuseau horaire (fuseaux IANA via `zoneinfo`). Couvre la bibliothèque de modèles de stacks (sources de templates compatibles Portainer, sources personnalisées) et l'API REST documentée par OpenAPI 3.0 générée nativement par FastAPI (activation, jetons, surface de l'API, viewer Scalar).

- Planificateur unifié : types de tâches, cycles de vie des jobs
- Exécutions planifiées : statuts, journaux, historique, rétention
- Fuseaux horaires et planifications par environnement
- Bibliothèque de modèles : sources intégrées, ajout de sources, déploiement depuis un modèle
- API REST : activation des docs, authentification par jeton, périmètre
- Spécification OpenAPI et viewer intégré
- Webhooks entrants (Git, sauvegardes) et signatures

### 15 — Administration, exploitation et cycle de vie de l'application

Regroupe les fonctions d'administration transverses : réglages généraux et préférences (thème, police, colonnes de grilles, sidebar), réglages par environnement (onglets activité/mises à jour/sauvegardes, types d'événements), gestion de licence (activation, expiration, notifications), auto-mise à jour de Dockhand (sidecar « image updater »), endpoints de santé et diagnostic, pages légales générées, journal des modifications, opérations d'urgence sur base de données (sauvegarde/restauration/réinitialisation), configuration au démarrage (variables d'environnement, `docker-entrypoint.sh` PUID/PGID, HTTPS natif, HSTS).

- Réglages généraux et préférences utilisateur (thème, disposition, grilles)
- Réglages par environnement et types d'événements collectés
- Gestion de licence : activation, désactivation, alertes d'expiration
- Auto-mise à jour de l'application (sidecar, remplacement de conteneur)
- Santé et diagnostic : endpoints de santé, debug, dépendances
- Changelog et pages légales générées
- Outils d'urgence base de données (backup, restore, reset, sessions)
- Configuration au démarrage : variables d'environnement, HTTPS/HSTS, feature flags

## Ordre de lecture recommandé

```mermaid
flowchart LR
    C01[01 Présentation générale] --> C02[02 Architecture fonctionnelle]
    C02 --> C03[03 Concepts et entités]
    C03 --> C04[04 Environnements]
    C04 --> C05[05 Conteneurs]
    C04 --> C06[06 Stacks Compose]
    C06 --> C07[07 Intégration Git]
    C04 --> C08[08 Images et registres]
    C04 --> C09[09 Volumes réseaux maintenance]
    C08 --> C10[10 Sécurité applicative]
    C06 --> C11[11 Sauvegardes]
    C03 --> C12[12 Authentification et RBAC]
    C04 --> C13[13 Observabilité et notifications]
    C13 --> C14[14 Automatisation modèles API]
    C02 --> C15[15 Administration et exploitation]
```

1. **Fondations (01 → 03)** : compréhension du produit, de son architecture et de son vocabulaire.
2. **Fonctions métier (04 → 11)** : les grandes fonctions au gré d'une lecture recommandée — environnements d'abord, puis conteneurs et stacks (cœurs du produit), intégrations (Git, registres), ressources (volumes/réseaux), sécurité applicative et sauvegardes.
3. **Transverse (12 → 15)** : sécurité des accès, observabilité, automatisation, administration et exploitation.

## Règles de rédaction

- Chaque chapitre est un document distinct nommé `NN-titre.md` dans `docs/spec_dockhand_reference/`.
- Chaque chapitre commence par un rappel du contexte, du périmètre et des prérequis de lecture.
- Les descriptions fonctionnels s'appuient sur des **descriptions architecturales** (services, couches, modules), sans référence à du code source : la spécification décrit le produit cible, pas son implémentation fichier par fichier.
- Les comportements spécifiques à une édition (Free / SMB / Enterprise) sont explicitement signalés.
- Les fonctionnalités gated par feature flag (sauvegardes bêta, docs API) sont signalées comme telles.
- L'outillage de référence est **pnpm** pour la construction du frontend et **pytest** pour les tests du backend.
