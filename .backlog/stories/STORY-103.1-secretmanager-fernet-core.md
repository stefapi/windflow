# STORY-103.1 : SecretManager Fernet — socle config, dépendance et classe core (P0-4a)

**Statut :** DONE
**Story Parente :** STORY-103 — SecretManager AES/Fernet — chiffrement au repos des credentials cibles et env vars de stacks (P0-4)
**Epic Parent :** EPIC-011 — P0 : Sécurité bloquante

## Description

En tant qu'administrateur sécurité de WindFlow, je veux disposer d'un `SecretManager` central conforme à la spécification de sécurité (AES-256 via Fernet, clé dérivée du `SECRET_KEY`), afin de fournir à toutes les données sensibles stockées en base un mécanisme unique de chiffrement/déchiffrement au repos.

Cette sous-story pose le **socle technique** de STORY-103 : ajout de la dépendance `cryptography` au projet, exposition de la clé maîtresse via la configuration (cohérente avec STORY-101), et implémentation de la classe `SecretManager` dans `core/`. Aucune entité métier n'est branchée ici — le branchement de `Target.credentials` fait l'objet de STORY-103.2, celui des env vars de stacks de STORY-103.3.

**Problème constaté** : le `SecretManager` spécifié (15-securite.md § Chiffrement des secrets) n'existe dans aucun module — c'est le **MANQUANT critique n°1** du rapport d'écart (A6). La dépendance `cryptography` n'est pas déclarée en direct dans [`pyproject.toml`](../../../pyproject.toml) (seulement l'extra de `python-jose`).

## Critères d'acceptation (AC)

- [x] AC 1 : Le `SecretManager` est implémenté conforme à la spec (15-securite.md) : `SecretManager(master_key)` avec dérivation PBKDF2HMAC (salt `windflow-secrets-v1`, 480 000 itérations, SHA-256) et méthodes `encrypt(str) -> str` / `decrypt(str) -> str` — **test unitaire round-trip** : chiffre → déchiffre → valeur initiale ; texte chiffré ≠ texte clair ; échec de déchiffrement avec une mauvaise clé maîtresse lève une erreur explicite.

## Contexte technique

- **Spécification de référence** : [`docs/general_specs/15-securite.md`](../../../docs/general_specs/15-securite.md) § Chiffrement des secrets → « SecretManager (référence unique) » (code de référence AES-256/Fernet, PBKDF2HMAC, salt `windflow-secrets-v1`, « une seule version » du salt cf. [`05-stack-technologique.md`](../../../docs/general_specs/05-stack-technologique.md) § Chiffrement des secrets (core)).
- **Localisation** : le plan cite `core/secret_manager.py` — arbitrée en faveur de `core/` (transversal, pas de logique métier, cohérent avec [`core/rate_limit.py`](../../../backend/app/core/rate_limit.py) pour un module de sécurité transversal).
- **Clé maîtresse** : à dériver de `jwt_secret_key` ou d'une variable dédiée dans [`config.py`](../../../backend/app/config.py:15) — **cohérence STORY-101** : la clé maîtreuse dérivée doit rester couverte par `validate_production_secrets()` ([`config.py:353`](../../../backend/app/config.py:353)) qui refuse le secret dev par défaut en production.
- **Pas de migration de schéma** : le contenu JSON est chiffré, pas la structure — aucune dépendance Alembic.
- **Sécurité** : jamais logger la clé maîtresse ni les valeurs déchiffrées ; les erreurs de déchiffrement lèvent une `WindFlowException` (cf. [`core/exceptions.py`](../../../backend/app/core/exceptions.py)), pas une exception Python brute.
- **Fondation** : ce module est le prérequis des entités `ssh_keys` (P1-9) et du chiffrement `plugin_configs` (P2-3).

## Dépendances

- Aucune (première sous-story — les sous-stories 103.2 et 103.3 en dépendent).

## Tâches d'implémentation détaillées

### Tâche 1 : Déclarer la dépendance `cryptography`
**Objectif :** Ajouter `cryptography` comme dépendance directe du projet backend (elle n'est aujourd'hui qu'un extra transitiif de python-jose) et documenter la variable d'environnement de la clé maîtresse.
**Fichiers :**
- `pyproject.toml` — Modifier — ajouter `cryptography = "^44.0.0"` (ou version compatible) dans les dépendances principales, via `poetry add cryptography`
- `env.example` — Modifier — documenter la variable de clé maîtresse (`SECRET_KEY` dédiée ou `WINDFLOW_SECRET_KEY` selon l'arbitrage de la tâche 2)
**Exigences sécurité :** aucune valeur de clé réelle dans `env.example` (placeholder explicite + commentaire invitant à générer une valeur aléatoire longue).
**Dépend de :** Aucune

### Tâche 2 : Exposer la clé maîtresse dans les settings
**Objectif :** Ajouter la configuration de la clé maîtresse dans les `Settings` Pydantic, avec valeur par défaut dérivée de `jwt_secret_key` (pas de nouvelle variable obligatoire en dev) et cohérence avec le garde-fou production de STORY-101.
**Fichiers :**
- `backend/app/config.py` — Modifier — nouveau champ settings (ex. `secret_encryption_key: str | None = None`, résolu en fallback vers `jwt_secret_key`), et étendre `validate_production_secrets()` pour couvrir la clé dérivée si une valeur dédiée est fournie
**Exigences sécurité :** la clé dérivée du secret dev par défaut doit être refusée en production par [`validate_production_secrets()`](../../../backend/app/config.py:353) (même liste `DEV_JWT_SECRET_VALUES`) ; jamais logger la clé.
**Dépend de :** Tâche 1

### Tâche 3 : Implémenter la classe `SecretManager`
**Objectif :** Créer `core/secret_manager.py` conforme à la spec : constructeur `SecretManager(master_key)`, dérivation PBKDF2HMAC (salt `windflow-secrets-v1`, 480 000 itérations, SHA-256), méthodes `encrypt(str) -> str` / `decrypt(str) -> str` basées sur Fernet (AES-256), plus un helper statique de détection de ciphertext (préfixe Fernet `gAAAA...`) pour la double lecture de STORY-103.2.
**Fichiers :**
- `backend/app/core/secret_manager.py` — Créer — classe `SecretManager` + instance unique obtenue depuis les settings (pattern de `core/rate_limit.py` si applicable)
- `backend/app/core/exceptions.py` — Modifier — si besoin, ajouter une exception dédiée (ex. `SecretDecryptionError`) héritant de `WindFlowException`
**Exigences sécurité :** erreurs de déchiffrement → exception `WindFlowException` avec message explicite sans révéler de matériel cryptographique ; dérivation faite une seule fois par instance (cache), jamais re-logger la master key.
**Dépend de :** Tâche 2

## Tests à écrire

### Backend
- `backend/tests/unit/test_core/test_secret_manager.py`
  - `test_round_trip_encrypt_decrypt` — chiffre → déchiffre → valeur initiale ; texte chiffré ≠ texte clair
  - `test_decrypt_with_wrong_master_key_raises` — mauvaise clé maîtresse → exception explicite
  - `test_ciphertext_detection` — helper de détection : préfixe `gAAAA` reconnu comme chiffré, JSON clair non reconnu
  - `test_empty_and_unicode_values` — cas limites (chaîne vide, unicode)
- `backend/tests/unit/test_config/test_production_guard.py`
  - `test_derived_secret_key_rejected_in_production` — clé maîtresse dédiée = valeur dev → violation détectée

### Commandes de validation
```bash
# Backend
poetry run pytest backend/tests/unit/test_core/test_secret_manager.py -v
make backend-lint
```

## État d'avancement technique
- [x] Tâche 1 : Déclarer la dépendance `cryptography`
- [x] Tâche 2 : Exposer la clé maîtresse dans les settings
- [x] Tâche 3 : Implémenter la classe `SecretManager`

## Notes d'implémentation

**Date :** 2026-09-05

### Fichiers modifiés/créés
- `backend/app/core/secret_manager.py` : **créé** — classe `SecretManager` (PBKDF2HMAC SHA-256, 480 000 itérations, salt `windflow-secrets-v1`, AES-256/Fernet), helper statique `is_encrypted()` (préfixe `gAAAA`), accessors `get_secret_manager()` / `reset_secret_manager()` (singleton lazy pattern `core/rate_limit.py`)
- `backend/app/core/exceptions.py` : **modifié** — ajout `SecretEncryptionError` et `SecretDecryptionError` héritant de `WindFlowException` (messages sans matériel cryptographique)
- `backend/app/config.py` : **modifié** — champ `secret_encryption_key: Optional[str]`, property `master_encryption_key` (fallback `jwt_secret_key`), extension de `validate_production_secrets()` (refus des valeurs dev de `DEV_JWT_SECRET_VALUES` pour la clé dédiée en production)
- `pyproject.toml` + `poetry.lock` : **modifiés** — `cryptography = ">=44.0.0"` en dépendance directe (46.0.2 lockée)
- `env.example` : **modifié** — documentation `SECRET_ENCRYPTION_KEY` (commentée, placeholder, instruction `openssl rand -hex 32`)
- `backend/tests/unit/test_core/test_secret_manager.py` : **créé** — 17 tests
- `backend/tests/unit/test_config/test_production_guard.py` : **modifié** — 3 tests ajoutés (clé dédiée dev refusée, clé forte acceptée, fallback couvert par garde-fou JWT)

### Décisions techniques
- **Contrainte de version `>=44.0.0`** (au lieu de `^44.0.0`) : `cryptography` 46.0.2 est déjà lockée (extra python-jose) ; `^44.0.0` (=`<45`) aurait forcé un downgrade impossible. La story autorisait « ^44.0.0 ou version compatible ».
- **Singleton lazy** : import différé de `settings` dans `get_secret_manager()` — évite la dérivation PBKDF2 coûteuse à l'import et les cycles d'import.
- **Helper `is_encrypted` en `@staticmethod`** : appelable sans instance (`SecretManager.is_encrypted(value)`) — pratique pour la double lecture STORY-103.2.
- **Garde-fou production** : vérification seulement si une valeur dédiée est fournie ; le fallback JWT est déjà couvert par la violation `JWT_SECRET_KEY` existante (pas de doublon de message).

### Divergences par rapport à l'analyse
- **Tâche 1** : `poetry add cryptography` a échoué (build `fastuuid` 0.13.5 incompatible Python 3.14 — problème préexistant étranger à cryptography, PyO3 0.22.6 ne supporte pas 3.14). Solution : édition directe de `pyproject.toml` + `poetry lock` (sans sync) — le lock préserve cryptography 46.0.2 et pyproject/lock restent cohérents. Le paquet était déjà installé dans le venv via l'extra python-jose.
- **Tâche 3** : ajout (non demandé explicitement mais dans l'esprit « instance unique » de la tâche) de `SecretEncryptionError` pour clé maîtresse vide, et de `reset_secret_manager()` pour les tests.

### Difficultés rencontrées
- Outils lint Makefile (`isort`/`black`/`flake8`/`mypy`/`bandit`) **absents du venv** (venv partiellement synchronisé — sync complet bloqué par fastuuid/Python 3.14). Validation faite avec `ruff check` + `ruff format` (équivalents) : **All checks passed**. `mypy` non exécuté — à repasser quand l'env sera réparé (`poetry install` avec Python ≤3.13).
- 41 échecs **préexistants** dans la suite unitaire (promote, stacks_archive, stacks_duplicate…) — vérifiés identiques avant/après mes changements (git stash) : aucune régression imputable à cette story.

### Tests ajoutés
- `backend/tests/unit/test_core/test_secret_manager.py` : 17 tests — couverture `secret_manager.py` **95%** (seules lignes 128-129 = branche `except Exception` de `encrypt`, defense-in-depth non atteignable)
- `backend/tests/unit/test_config/test_production_guard.py` : +3 tests — couverture `config.py` **85%**
- Validation : `pytest backend/tests/unit/test_core/ backend/tests/unit/test_config/` → **51 passed, 0 failed**
- API publique pour STORY-103.2 : `SecretManager(master_key)`, `.encrypt(str)->str`, `.decrypt(str)->str` (lève `SecretDecryptionError`), `SecretManager.is_encrypted(str)->bool`, `get_secret_manager()->SecretManager`
