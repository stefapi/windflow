# BUG-012 : `helper/security.py` bcrypt orphelin — purger le helper et la dépendance transitionnelle

**Statut :** DONE
**Gravité :** Mineur

> Constaté lors de la revue finale de conformité (STORY-254.3, 2026-11-07) ; signalement n°1 de STORY-252, jamais traité.

## Reproduction
1. `grep -rn "from.*helper.security import\|helper\.security" backend/app --include="*.py"` → **0 consommateur**
2. Lire [`backend/app/helper/security.py`](../../backend/app/helper/security.py) : hash bcrypt non utilisé (Argon2id effectif via services auth, STORY-130.1)

## Comportement attendu
Le retrait de `bcrypt` « post-migration » était planifié (STORY-130.1/250 : « dépendance bcrypt ajoutée en transition (lecture seule), retrait post-migration ») : une fois la migration Argon2id achevée et sans consommateur, le helper et la dépendance `bcrypt ^4.0.0` doivent disparaître.

## Comportement actuel
- [`helper/security.py`](../../backend/app/helper/security.py) : code mort (0 import) ;
- `bcrypt` toujours déclaré dans [`pyproject.toml`](../../pyproject.toml) (transition « lecture seule » — plus rien ne lit).

## Résolution

Corrigé le 2026-11-07 (cycle NEW → CONFIRMED → IN_PROGRESS → REVIEW → DONE parcouru lors de la session de correction).

### Préreuve de fin de migration

Vérification des bases existantes avant purge : les 3 DB du dépôt (`data/windflow/windflow.db`, `dev/data/windflow.db`, `backend/data/windflow/windflow.db`) contiennent **0 hash bcrypt** (`SELECT SUM(hashed_password LIKE '$2b$%')` = 0 — 100 % `$argon2`). La migration Argon2id (STORY-130.1, upgrade paresseux au login) est donc achevée sur toutes les instances connues : la condition « retrait post-migration » est remplie.

### Correctifs appliqués

- **Suppression** de `backend/app/helper/security.py` (0 importeur vérifié sur backend/cli/frontend/docs hors backlog) ;
- [`pyproject.toml`](../../pyproject.toml) : retrait du pin direct `bcrypt = "^4.0.0"` (transition passlib — ligne d'origine du bug) + retrait de l'override mypy `bcrypt` + `poetry lock` régénéré ;
- **Découverte lors de la validation** (non prévue par le contrat) : `bcrypt` est aussi une dépendance **runtime d'`asyncssh`** (KDF `bcrypt_pbkdf` des clés OpenSSH chiffrées, `asyncssh/public_key.py`) que celui-ci ne déclare pas strictement — le retrait complet du package cassait `POST /ssh-keys/generate` (test `test_ssh_keys.py::test_no_secret_in_responses_nor_logs` FAILED). **Arbitrage** : le pin direct est remplacé par `asyncssh = {version = "^2.14.0", extras = ["bcrypt"]}` (bcrypt 5.0.0 dans le lock via l'extra officiel) — la dépendance transitionnelle « lecture hashes legacy » disparaît, la dépendance légitime d'asyncssh est déclarée proprement ;
- [`backend/app/services/user_service.py`](../../backend/app/services/user_service.py) : `pwd_context = CryptContext(schemes=["argon2"])` — retrait du schème `"bcrypt"` (double lecture) et docstrings alignées (lecture Argon2id seule, échec silencieux sur schème inconnu maintenu — arbitrage n°9) ;
- [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py) : docstrings OpenAPI login/`PUT /auth/password` alignées (plus de « double read at login » ni mention d'upgrade bcrypt automatique) + commentaire l.1153 mis à jour ;
- **Tests réécrits** pour refléter le contrat post-purge (résidu bcrypt = schème inconnu → 401 générique / `(False, None)` sans re-hash) :
  - [`backend/tests/unit/test_services/test_user_service.py`](../../backend/tests/unit/test_services/test_user_service.py) — fixtures bcrypt générées via passlib remplacées par une constante `$2b$…` (plus de dépendance au package) ;
  - [`backend/tests/unit/test_api/test_auth_login_hash_upgrade.py`](../../backend/tests/unit/test_api/test_auth_login_hash_upgrade.py) — login nominal Argon2id + rejet générique du résidu bcrypt ;
  - [`backend/tests/integration/test_password_hash_migration.py`](../../backend/tests/integration/test_password_hash_migration.py) — flux complet Argon2id + résidu bcrypt rejeté hash inchangé.

**Contrat résultant** : un éventuel hash bcrypt résiduel en base ne peut plus se connecter (échec silencieux → 401 générique anti-énumération, hash jamais modifié) — le compte doit être réinitialisé. Ce comportement est couvert par les tests ci-dessus.

### Vérification

- `grep -rn "bcrypt" backend/app pyproject.toml` → 0 hit hors commentaires historiques tracés (user_service BUG-012, auth.py « legacy read path removed ») et hors pin asyncssh justifié — écran du contrat adapté : **plus aucun code applicatif n'importe bcrypt** (`grep "^import bcrypt\|^from bcrypt" backend/app cli` → 0 hit), seul `asyncssh` (tiers) le consomme ;
- `poetry lock` : bcrypt 5.0.0 présent **uniquement** via l'extra asyncssh (plus de pin direct transitionnel) ;
- **Suite unitaire complète** : `poetry run pytest tests/unit` → **3255 passed** (y compris ssh_keys — le cas FAILED sans bcrypt a été diagnostiqué et résolu par l'extra) ;
- Suites ciblées (user_service, login hash upgrade, intégration migration, auth_refresh_security, auth_api, password_flow) → tous verts (32 + 4 + 86 + 4 passed) ;
- `pwd_context.schemes()` → `('argon2',)` ; `black`/`isort` conformes sur tous les fichiers modifiés.
