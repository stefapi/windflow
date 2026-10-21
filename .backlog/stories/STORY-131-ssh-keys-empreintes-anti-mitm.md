# STORY-131 : [ABANDONED] SSH réutilisables + empreintes hôtes + anti-MITM (TOFU + confirmation) (P1-9)

**Statut :** ABANDONED
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-9 (axe A7, rapports §4/§7) — ampleur **L**

> *Story ajoutée à la vague P1 pour couvrir l'intégralité du plan (P1-1 à P1-11) : la mission initiale listait 11 stories sans cet item ; conservée ici conformément au plan §4.*

> **Note d'abandon (2026-10-16)** : story **découpée proactivement post-analyse** (`split-story`) en trois sous-stories autonomes, l'ampleur L (modèles + migrations + service/API + helper runtime TOFU sur 5 sites SSH) dépassant le périmètre d'une seule implémentation :
> - [STORY-131.1](STORY-131.1-modeles-migrations-ssh-keys.md) — Modèles & migrations (`ssh_keys`, `host_ssh_fingerprints`, FK `targets.ssh_key_id`, data migration crypto tolérante R1) ;
> - [STORY-131.2](STORY-131.2-service-api-gestion-cles-ssh.md) — Schémas API, service et router de gestion des clés/empreintes ;
> - [STORY-131.3](STORY-131.3-anti-mitm-tofu-runtime.md) — Helper TOFU runtime et intégration aux 5 sites SSH.
>
> L'analyse complète (phase A/B/C, patterns, risques R1-R3, arbitrage F3) est reportée dans les sections « Contexte technique » des sous-stories. Cette story est conservée pour l'historique.

## Description

En tant qu'administrateur de cibles distantes WindFlow, je veux des **clés SSH réutilisables** (entité `ssh_keys` partagée par N cibles, clé privée chiffrée au repos) et des **empreintes d'hôtes** (table `host_ssh_fingerprints`, politique TOFU avec acceptation explicite et blocage en cas de divergence), afin de supprimer les credentials SSH en clair dans `connection_config` et de me protéger contre les attaques MITM sur les connexions aux Hosts.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §4, §7, §14) : les credentials cibles sont stockés en **JSON en clair** dans `Target.connection_config` (chiffrement posé par STORY-103/EPIC-011) ; il n'existe ni entité `ssh_keys`, ni empreintes known_hosts, ni politique anti-MITM. La spec 15 exige : première connexion → empreinte présentée pour acceptation explicite (jamais d'ajout silencieux) ; divergence → connexion bloquée avec message explicite.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- Schémas cibles spec 06 : `ssh_keys (id, name UNIQUE, key_type DEFAULT 'ssh-ed25519', public_key, private_key_encrypted, fingerprint, last_used_at, created_at)` + index fingerprint ; `host_ssh_fingerprints (id, host_id FK, …)` + index host — détail exact des colonnes à lire en analyse (spec 06 § Entités d'accès distant) ;
- **Chiffrement** : `private_key_encrypted` via le SecretManager (STORY-103) ; clé privée affichée **une seule fois** (génération) ; empreinte + clé publique consultables (déploiement `authorized_keys`) ; suppression refusée si des Hosts référencent encore la clé (ou déréférencement explicite) ;
- **Génération/import** : génération côté serveur (ed25519 recommandé) ou import (avec/sans passphrase) — spec 15 § Clés SSH réutilisables ;
- Cibles actuelles : les credentials `Target.connection_config` passent par une `ssh_keys` référencée (profils à accès SSH) — migration des données : extraction des clés existantes chiffrées (post-STORY-103) vers l'entité, FK `ssh_key_id` ;
- **Anti-MITM** : première connexion → empreinte présentée (événement/écran de confirmation) ; le test de connexion ne l'ajoute **jamais** silencieusement ; divergence d'empreinte → déploiement **bloqué** + événement de confirmation (re-acceptation délibérée) ;
- Intégration : [`target_service.py`](../../backend/app/services/target_service.py:30), [`commands.py`](../../backend/app/services/commands.py:167) — **flux `commands.py` inchangé côté appelants** (critère de done) ; le client SSH existant (asyncssh) doit appliquer la vérification d'empreinte (pas d'auto-accept) ;
- Recommandations associées spec 15 (utilisateur dédié `deploy`, compteur d'échecs/backoff) : le backoff anti-tempête peut être reporté (non bloquant pour cette story — à trancher en analyse) ;
- Endpoints API de gestion des clés (CRUD `ssh_keys` + confirmation d'empreinte) à exposer selon spec 09 (surface hôtes) — protégés `require_role("admin")`+ (STORY-122) ;
- STORY-164 (EPIC-013, canal WS `ssh`) dépend de cette story.

## Critères d'acceptation (AC)

- [ ] AC 1 : Les tables `ssh_keys` et `host_ssh_fingerprints` existent via migration Alembic (STORY-120) conformément aux schémas spec 06 ; les cibles à accès SSH référencent une clé via FK ; migration des credentials existants sans perte (clés privées chiffrées via STORY-103, jamais en clair).
- [ ] AC 2 : **Réutilisabilité** : une même clé est référençable par N cibles (test) ; génération serveur (ed25519) et import fonctionnels ; clé privée affichée une seule fois ; suppression refusée si des Hosts l'utilisent (ou déréférencement explicite) — jamais de suppression silencieuse.
- [ ] AC 3 : **Anti-MITM** : empreinte **inconnue** → déploiement bloqué + événement de confirmation émis (acceptation explicite requise ; le test de connexion n'ajoute jamais silencieusement) ; empreinte **divergente** → connexion bloquée avec message explicite et ré-acceptation délibérée ; vérification appliquée sur toutes les sessions SSH (asyncssh).
- [ ] AC 4 : Le flux [`commands.py`](../../backend/app/services/commands.py:167) est **inchangé côté appelants** (test de non-régression des commandes existantes) ; endpoints de gestion protégés (`401`/`403` selon RBAC STORY-122) ; aucun secret/cla privée dans les réponses API ni les logs.
- [ ] AC 5 : `make lint` + `make backend-test` verts ; couverture ≥ 80 % sur les modules touchés.

## Références spécification

- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité réseau → Hosts distants (SSH) : clés réutilisables (génération/import, affichage unique, suppression contrôlée), empreintes known_hosts et anti-MITM (TOFU, divergence bloquée), compteur d'échecs/backoff ;
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités d'accès distant (SSH) : `SSHKey` et `HostSSHFingerprint` (schémas SQL, relations) ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — surface d'exposition des hôtes et des clés (à confronter à la surface réelle `/targets/*` existante — arbitrage F3/double nommage en P2) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §4 (credentials JSON en clair sur `Target`), §7 (critique SSH), §14 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-9 (dépend de P1-1 et P0-4), §2.A A7, §3 F4 étape 1, §5 chaîne critique n°2.

## Dépendances

- **STORY-120** (migrations des tables) ; **STORY-103** (EPIC-011 — SecretManager avant ssh_keys : chiffrement des clés privées) ; s'appuie sur STORY-122 pour la protection RBAC des endpoints de gestion.
- Est un prérequis de : STORY-164 (EPIC-013 — canal WS `ssh`).

## Sous-stories

*(section réservée — ampleur L : `analyse-story` pourra découper (ex. modèle+migration / gestion clés / empreintes+anti-MITM / intégration cibles) ; plage réservée STORY-132-159)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
