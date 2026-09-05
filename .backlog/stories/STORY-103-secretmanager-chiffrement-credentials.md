# STORY-103 : SecretManager AES/Fernet — chiffrement au repos des credentials cibles et env vars de stacks (P0-4)

**Statut :** DONE
**Epic Parent :** EPIC-011 — P0 : Sécurité bloquante
**Item plan :** P0-4 (rapport d'écart A6 + B3 + C12 partiel, §4/§7 critique n°1) — ampleur **L**

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que toutes les données sensibles stockées en base soient chiffrées au repos (AES-256 via Fernet, clé dérivée du `SECRET_KEY`), afin que la compromission du fichier de base de données ne révèle ni credentials d'accès aux cibles (mots de passe SSH/sudo, clés privées) ni variables d'environnement sensibles des stacks.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6.2, §14) : le modèle [`Target`](../../backend/app/models/target.py) stocke ses `credentials` en **JSON en clair** dans la base ; les variables sensibles des stacks ne sont pas non plus chiffrées. Le `SecretManager` spécifié (15-securite.md § Chiffrement des secrets) n'existe dans aucun module — c'est le **MANQUANT critique n°1** du rapport d'écart (A6). La spec est formelle : « Toutes les données sensibles stockées en base… sont chiffrées avec AES-256 via Fernet » (hosts.connection_config, stacks.env_vars_encrypted…), ce qui correspond aujourd'hui aux champs `Target.credentials` et aux variables d'environnement des stacks.

## Contexte technique

*(à remplir par analyse-story)*

Contraintes de conception posées par le plan (à respecter par l'analyse) :
- **Nouveau service** `backend/app/services/secret_manager.py` ou `core/secret_manager.py` (le plan cite `core/secret_manager.py` — arbitrage localisation à trancher par analyse-story), implémentant la classe `SecretManager` de la spec (PBKDF2HMAC, salt `windflow-secrets-v1`, 480 000 itérations, clé dérivée du `SECRET_KEY`) ;
- **Conçu sans migration de schéma** : le contenu JSON est chiffré, pas la structure (le champ reste texte) — pas de dépendance à Alembic (P1-1) ;
- **Migration par double lecture** : ancienne ligne en clair → lue puis **ré-encryptée au premier accès** ; backup de base préalable documenté ; procédure de rotation de clé maîtresse (plan §7.1) ;
- **Clé via env** : `SECRET_KEY` / variable dédiée dans [`config.py`](../../backend/app/config.py:15) — interaction avec STORY-101 (le secret dev par défaut doit devenir impossible en prod) ;
- Services écrits/lecteurs des credentials à couvrir : [`target_service.py`](../../backend/app/services/target_service.py:30), exécution distante ([`commands.py`](../../backend/app/services/commands.py:167) — `SSHCommandExecutor` consomme les credentials), rendu/déploiement des variables de stacks ([`background_tasks.py`](../../backend/app/tasks/background_tasks.py:24), [`stack_service.py`](../../backend/app/services/stack_service.py:19)) ;
- Ne jamais logger de secrets (masquage `***` déjà pratiqué par [`adoption_service.py`](../../backend/app/services/adoption_service.py:230)) ; les valeurs déchiffrées ne vivent qu'en mémoire ;
- Schéma cible : prérequis logique des entités `ssh_keys`/empreintes (06-modele-de-donnees.md) qui arriveront en P1-9 — le SecretManager est leur fondation.

## Critères d'acceptation (AC)

- [x] AC 1 : Le `SecretManager` est implémenté conforme à la spec (15-securite.md) : `SecretManager(master_key)` avec dérivation PBKDF2HMAC (salt `windflow-secrets-v1`, 480 000 itérations, SHA-256) et méthodes `encrypt(str) -> str` / `decrypt(str) -> str` — **test unitaire round-trip** : chiffre → déchiffre → valeur initiale ; texte chiffré ≠ texte clair ; échec de déchiffrement avec une mauvaise clé maîtresse lève une erreur explicite. *(validé par STORY-103.1)*
- [x] AC 2 : Toute **écriture** de `Target.credentials` (création/modification de cible) passe par le SecretManager et stocke du JSON chiffré ; toute **lecture** (déploiement, scan, health-check, exécution SSH/sudo) déchiffre à la volée — les flux existants fonctionnent à l'identique pour l'utilisateur (non-régression des déploiements et du scan, garde-fous §2.G). *(validé par STORY-103.2)*
- [x] AC 3 : Les variables d'environnement sensibles des stacks sont chiffrées au repos (équivalent `env_vars_encrypted` de la spec) et déchiffrées uniquement en mémoire au moment du rendu/déploiement — jamais écrites sur disque (`.env`/override) ni loggées ; l'API et l'UI ne renvoient jamais la valeur en clair (masquage `***` dans les réponses/aperçus). *(validé par STORY-103.3)*
- [x] AC 4 : **Migration des données existantes par double lecture** : une ligne ancienne stockée en clair est lue avec succès puis **ré-encryptée au premier accès** ; test de migration dédié (fixture avec credential clair → accès → relecture chiffrée) ; documentation de la procédure (backup préalable, rotation de clé maîtresse). *(validé par STORY-103.2)*
- [x] AC 5 : Critère de done absolu du plan : après exécution sur une base existante, **0 credential lisible en base** ; tests écrits et passants (round-trip, double lecture, non-exposition API, non-régression déploiement) — `make lint` + `make backend-test` verts ; couverture ≥ 80 % sur le nouveau module (chemin critique sécurité, viser 95 % — rules 35). *(validé par STORY-103.4)*

## Références spécification

- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) § Chiffrement des secrets → « SecretManager (référence unique) » (code de référence AES-256/Fernet, PBKDF2HMAC, salt `windflow-secrets-v1`, « ce qui est chiffré » : `stacks.env_vars_encrypted`, `hosts.connection_config`, `plugin_configs.value` si `encrypted`), § « Protection du SECRET_KEY », § Vue d'ensemble → Principes (« les secrets sont chiffrés ») ;
- [`docs/general_specs/05-stack-technologique.md`](../../docs/general_specs/05-stack-technologique.md) § Chiffrement des secrets (core) — « une seule version, salt `windflow-secrets-v1` » ;
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) § `ssh_keys` / empreintes d'hôtes (prérequis logique : la clé privée SSH est « stockée chiffrée au repos AES-256 via le SecretManager » — 15-securite.md § Clés SSH réutilisables) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §6.2 (`Target` : credentials JSON), §14.2/§14.3 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 Vague P0 — item P0-4, §2.A — item A6, §2.B — item B3, §2.C — item C12 (partiel), §7.1 (mitigations compatibilité données).

## Dépendances

- Aucune en P0 (autonome — conçu sans migration de schéma).
- **Inter-vagues (chaînes critiques du plan §5)** : STORY-103 est le prérequis de **P1-9** (SSH keys + empreintes, EPIC-012) et de **P2-3** (plugins réels, `plugin_configs` chiffré si `encrypted`, EPIC-013) ; alimente aussi P2-13 (recreate masquage secrets). Toute dérive de périmètre vers `plugin_configs` complet relève de P2-3 (C12) — hors périmètre ici.
- Cohérence à assurer avec STORY-101 (clé maîtresse via env, refus des valeurs dev en prod).

## Sous-stories

> ⚠️ Story découpée en mode proactif le 2026-09-05 par `split-story` (complexité détectée par `analyse-story` : ~11 tâches / ≥12 fichiers — seuils >5 tâches / >6 fichiers).

- [x] STORY-103.1 : SecretManager Fernet — socle config, dépendance et classe core (P0-4a) — Couvre AC 1
- [x] STORY-103.2 : Chiffrement de Target.credentials + migration double lecture (P0-4b) — Couvre AC 2, AC 4
- [x] STORY-103.3 : Env vars stacks — chiffrement au repos et masquage API (P0-4c) — Couvre AC 3
- [x] STORY-103.4 : Validation finale — 0 credential lisible, non-régression, couverture (P0-4d) — Couvre AC 5

**Ordre d'implémentation recommandé :** STORY-103.1 → STORY-103.2 → STORY-103.3 → STORY-103.4 (103.3 ne dépend que de 103.1 et peut être menée en parallèle de 103.2).

## État d'avancement technique

> ⚠️ L'avancement technique est désormais suivi dans les sous-stories individuelles.

**Progression :** 4/4 sous-stories terminées
- [x] STORY-103.1 : SecretManager Fernet — socle config, dépendance et classe core
- [x] STORY-103.2 : Chiffrement de Target.credentials + migration double lecture
- [x] STORY-103.3 : Env vars stacks — chiffrement au repos et masquage API
- [x] STORY-103.4 : Validation finale — 0 credential lisible, non-régression, couverture

## Tâches d'implémentation détaillées

> ⚠️ Cette story a été découpée en sous-stories avant implémentation (complexité détectée par analyse-story).
> Toutes les tâches ont été redistribuées dans les sous-stories listées ci-dessus.
> Consulter chaque sous-story pour les tâches détaillées.

## Tests à écrire

> ⚠️ Les tests sont désormais définis dans les sous-stories individuelles.

## Notes d'implémentation

> Clôture administrative de la story parente le 2026-09-05 — l'implémentation détaillée est consignée dans les notes de chaque sous-story.

### Sous-stories (4/4 DONE)

- **STORY-103.1 (DONE)** : `SecretManager` Fernet implémenté dans `backend/app/core/secret_manager.py` (PBKDF2HMAC, salt `windflow-secrets-v1`, 480 000 itérations, SHA-256, clé dérivée du `SECRET_KEY`) avec dépendance `cryptography` déclarée — 95 % de couverture sur le module (51 tests ciblés passés).
- **STORY-103.2 (DONE)** : `Target.credentials` chiffré à l'écriture + migration par double lecture (ligne clair legacy lue puis ré-encryptée au premier accès) — 100 % de couverture sur `models/target.py` (20 tests ajoutés).
- **STORY-103.3 (DONE)** : env vars des stacks chiffrées au repos dans les snapshots de déploiement, déchiffrement en mémoire seule au rendu, masquage `***` dans l'API — 100 % de couverture sur `models/deployment.py` + `schemas/deployment.py` (29 tests ajoutés).
- **STORY-103.4 (DONE)** : validation finale transverse — verdict **CONFORME** (voir ci-dessous).

### Fichiers principaux créés/modifiés

- `backend/app/core/secret_manager.py` — créé (classe `SecretManager`)
- `backend/app/core/exceptions.py`, `backend/app/config.py` — exception dédiée + config de la clé maîtresse
- `backend/app/models/target.py`, `backend/app/services/target_service.py`, `backend/app/services/target_scanner_service.py` — chiffrement des credentials + double lecture
- `backend/app/models/deployment.py`, `backend/app/services/deployment_service.py`, `backend/app/services/deployment_orchestrator.py`, `backend/app/schemas/deployment.py` — chiffrement des env vars + masquage API
- `backend/app/tasks/background_tasks.py` — rendu/déploiement avec valeurs déchiffrées en mémoire uniquement
- `env.example`, `pyproject.toml` — variable d'environnement de la clé maîtresse + dépendance `cryptography`
- `docs/general_specs/16-deploiement.md` — procédure documentée (backup préalable, migration double lecture, rotation de clé maîtresse) ; spec de référence : `docs/general_specs/15-securite.md`
- Tests : `backend/tests/unit/test_core/test_secret_manager.py`, `backend/tests/unit/test_models/test_target.py`, `backend/tests/unit/test_models/test_deployment.py`, `backend/tests/unit/test_schemas/test_deployment.py`, `backend/tests/integration/test_secret_encryption.py` (entre autres)

### Validation finale (STORY-103.4) — verdict CONFORME

- **0 credential lisible en base** après migration (inspection SQL brute : aucun secret en clair, idempotence vérifiée)
- **API masquée** : env vars renvoyées en `***` sur tous les endpoints exposés ; `GET targets` sans credentials
- **Aucun secret dans les logs**
- Non-régression des déploiements et du scan (garde-fous §2.G préservés)

### Recommandations résiduelles

- Isoler la config de test de `DISABLE_AUTH` (éviter la fuite de settings entre suites de tests)
- Repasser `mypy` + `bandit` sur l'ensemble (une partie de la validation a été exécutée hors venv principal)
- Planifier la rotation de la clé maîtresse (procédure documentée dans `docs/general_specs/16-deploiement.md`, à opérationnaliser)
- Réparer le venv Python 3.14 (environnement de test local cassé)
