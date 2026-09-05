# STORY-101 : Garde-fou de démarrage — refus des secrets dev par défaut en production (P0-2)

**Statut :** DONE
**Epic Parent :** EPIC-011 — P0 : Sécurité bloquante
**Item plan :** P0-2 (rapport d'écart B12, §7) — ampleur **S**

## Description

En tant qu'administrateur système déployant WindFlow en production, je veux que le démarrage échoue explicitement si des secrets de développement par défaut sont encore utilisés, afin d'empêcher qu'une instance exposée tourne avec un `jwt_secret` prédictible (forgabilité des JWT) et un compte admin `changeme123` (prise de contrôle immédiate).

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §11, §14.3) : [`config.py`](../../backend/app/config.py:15) embarque un **secret JWT dev par défaut** et le seeding ([`database_seed.py`](../../backend/app/database_seed.py)) crée un admin avec le mot de passe **`changeme123`** (`Seeding` : email/username/password admin par défaut). Rien n'empêche `environment=production` de démarrer avec ces valeurs : quiconque connaît le code source peut forger des tokens valides et se connecter en admin. La spec exige l'inverse : `SECRET_KEY` « généré automatiquement par `install.sh` », « mot de passe admin suffisamment fort » (15-securite.md § Checklists de sécurité).

## Contexte technique

**Couches impactées :** Backend uniquement (config.py validateur, main.py startup, database_seed.py print) + fichiers env. Frontend/CLI non impactés.

### Constat d'exploration

1. **Divergence de nommage critique** : [.env.prod.example](../../.env.prod.example) (l.122-125) et [`env.example`](../../env.example) (l.98-99) documentent `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` / `SUPERADMIN_USERNAME`, mais [`Settings`](../../backend/app/config.py:216) lit `ADMIN_*` (`admin_email`, `admin_username`, `admin_password`). pydantic-settings ignore silencieusement `SUPERADMIN_PASSWORD` → **une installation prod conforme à la doc officielle garde le mot de passe `changeme123`**. Décision (validée) : ajouter des alias pydantic `AliasChoices("admin_password", "SUPERADMIN_PASSWORD")` etc. — les deux nommages fonctionnent, aucun breaking.
2. **Valeurs dev disséminées** : défaut code [`config.py:31`](../../backend/app/config.py) = `"dev-secret-key-change-in-production-please-use-a-long-random-string-minimum-32-characters"` ; valeur [`env.example:80`](../../env.example) = `"dev-jwt-secret-key-change-in-production"` (différente !). La liste noire doit couvrir **les deux**.
3. [`admin_password: str = "changeme123"`](../../backend/app/config.py:219) — utilisé par le seeding ([`database_seed.py:72`](../../backend/app/database_seed.py)).
4. **Print du mot de passe en clair** au seeding ([`database_seed.py:92`](../../backend/app/database_seed.py)) — violation « jamais logger de secrets » (15-securite.md) ; à corriger dans cette story (même périmètre fichier).
5. `is_production` existe déjà ([`config.py:258`](../../backend/app/config.py)) ; le lifespan ([`main.py:74-84`](../../backend/app/main.py)) fait `db.connect()` → `create_tables()` → `seed_tables()` — la validation doit s'insérer **avant** `db.connect()` (aucune exposition réseau, aucun démarrage partiel).
6. `disable_auth` ([`config.py:254`](../../backend/app/config.py), commentaire « ⚠️ DANGER : Ne JAMAIS activer en production ») : le garde-fou l'inclut (décision validée — refus de `disable_auth=true` en prod).

### Fichiers de référence (patterns)

- Validateur de configuration pur → à créer dans `config.py` (pattern : méthodes helper existantes `is_production`, `build_csp_header` — fonctions simples, testables sans app)
- Tests unitaires settings → pattern : [`test_dev_mode.py`](../../backend/tests/unit/test_auth/test_dev_mode.py) (patch de `settings`, asserts sur exceptions)
- Refus au startup → `RuntimeError` levée dans le `lifespan` avant toute connexion (pas d'exception custom nécessaire — échec de démarrage uvicorn natif)

**Exigences sécurité identifiées :**
- Auth : non applicable (garde-fou de démarrage, avant toute exposition)
- Validation : liste noire prod — `jwt_secret_key` ∈ {défaut code, valeur env.example dev}, `admin_password` = `changeme123` ou longueur < 16, `disable_auth` = true
- Exposition : message d'erreur nommant les **variables** (jamais leurs valeurs) ; suppression du print du mot de passe au seeding
- Audit : log CRITICAL au refus avec procédure de correction ; aucune valeur sensible dans les logs

### Décisions de conception (validées par l'utilisateur)

- **Alias pydantic** `AliasChoices` pour accepter `SUPERADMIN_*` ET `ADMIN_*` — non-breaking, aligne code et docs
- **Garde-fou étendu** : inclut `disable_auth=true` interdit en production (renforcement au-delà du strict B12, justifié par le commentaire DANGER du code)
- **Fonction pure** `validate_production_secrets(settings) -> list[str]` (retourne les violations) + wrapper levant `RuntimeError` — séparable pour tests unitaires sans lever l'app
- En dev/test (`environment` ≠ production) : aucun contrôle, comportement inchangé (AC 3)

Points d'appui existants :
- `Settings` pydantic-settings avec propriété `is_production` / champ `environment` ([`config.py`](../../backend/app/config.py:15)) ;
- Lifespan startup : `db.connect()` + `create_tables()` + `seed_tables()` puis init rate limiter ([`main.py`](../../backend/app/main.py:59)) — la validation doit intervenir **avant** toute exposition réseau ;
- Fichiers env à maintenir cohérents : `env.example` (critère de done du plan), `.env.prod.example` ;
- Mode dev (`environment` ≠ production) : comportement inchangé, aucun blocage.

## Critères d'acceptation (AC)

- [x] AC 1 : Au démarrage avec `environment=production`, si `jwt_secret` garde sa valeur dev par défaut **ou** si le seeding admin utiliserait le mot de passe `changeme123`, l'application **refuse de démarrer** : exception au startup avec un message explicite nommant la/les variable(s) concernée(s) et la marche à suivre (aucun démarrage partiel, aucune exposition de l'API). ✅ `enforce_production_secrets()` appelé en tête du lifespan ([main.py](../../backend/app/main.py)) AVANT `db.connect()` → `RuntimeError` listant variables + procédures ; tests `test_startup_fails_*`.
- [x] AC 2 : Le même démarrage avec des secrets forts (`jwt_secret` défini, mot de passe admin défini via env) fonctionne normalement en production — pas de faux positif bloquant les installations légitimes. ✅ `test_startup_succeeds_in_production_with_strong_secrets` ; alias `SUPERADMIN_*` fonctionnels (`test_superadmin_alias_accepted`) + non-breaking `ADMIN_*` (`test_admin_naming_still_works`) ; 892 tests unitaires verts.
- [x] AC 3 : Les environnements de développement/test ne sont pas impactés : valeurs par défaut toujours acceptées dès que `environment` ≠ production. ✅ `validate_production_secrets` retourne `[]` hors prod ; tests `test_dev_environment_unaffected_by_guard`, `test_test_environment_unaffected_by_guard`.
- [x] AC 4 : [`env.example`](../../env.example) documente les variables concernées et le comportement de blocage en production (critère de done du plan : « doc `env.example` à jour ») ; `.env.prod.example` vérifié cohérent. ✅ Garde-fou documenté sur `JWT_SECRET_KEY`, `DISABLE_AUTH`, `SUPERADMIN_PASSWORD` dans les 2 fichiers + alias documentés + ligne checklist.
- [x] AC 5 : Tests écrits et passants : `test_startup_fails_in_production_with_default_jwt_secret`, `test_startup_fails_in_production_with_default_admin_password`, `test_startup_fails_lists_all_offending_secrets`, `test_startup_succeeds_in_production_with_strong_secrets`, `test_dev_environment_unaffected_by_guard` — `make lint` + `make backend-test` verts. ✅ 13/13 tests dans [`test_production_guard.py`](../../backend/tests/unit/test_config/test_production_guard.py) (les 5 exigés nommément + 8 complémentaires) ; flake8/black/isort verts ; suite complète 892/892.

## Références spécification

- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) § Checklists de sécurité → « À l'installation » (`SECRET_KEY` généré aléatoirement, mot de passe admin suffisamment fort) et § Chiffrement des secrets → « Protection du SECRET_KEY » (jamais commité, compromission = compromission de tous les JWT) ;
- [`docs/general_specs/16-deploiement.md`](../../docs/general_specs/16-deploiement.md) § Installation — `install.sh` génère un `SECRET_KEY` aléatoire et crée le `.env` (le garde-fou couvre les installations hors `install.sh`) ;
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) § Access token (JWT) — signature HS256 avec le `SECRET_KEY` de l'instance, § Configuration — `SECRET_KEY` généré automatiquement ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §11 (Configuration : « Secret (valeur dev par défaut) », seeding `changeme123`), §14.3 (« Secrets dev par défaut ») ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 Vague P0 — item P0-2, §2.B — item B12.

## Dépendances

- Aucune (item autonome de la vague P0).

## Sous-stories

*(section réservée — STORY-101 ampleur S, découpage non prévu)*

## État d'avancement technique

- [x] Tâche 1 : Validateur `validate_production_secrets()` dans config.py
- [x] Tâche 2 : Câblage startup main.py + alias SUPERADMIN_* + correction print seeding
- [x] Tâche 3 : Documentation env.example et .env.prod.example
- [x] Tâche 4 : Tests du garde-fou (5 familles AC 5 + alias + disable_auth)
- [x] Tests unitaires backend
- [x] Build & lint OK

## Notes d'implémentation

**Date :** 2026-09-05

### Fichiers modifiés/créés

- `backend/app/config.py` — Ajout de `DEV_JWT_SECRET_VALUES` (les 2 valeurs dev connues), `DEV_ADMIN_PASSWORD`, `MIN_ADMIN_PASSWORD_LENGTH=16`, `validate_production_secrets()` (fonction pure) et `enforce_production_secrets()` (log CRITICAL + RuntimeError) ; alias `AliasChoices` sur les 4 champs admin (`SUPERADMIN_*` acceptés en plus de `ADMIN_*`)
- `backend/app/main.py` — `enforce_production_secrets(settings)` en tête du lifespan, avant `db.connect()` et avant la bannière de démarrage
- `backend/app/database_seed.py` — print du mot de passe remplacé par un message sans valeur
- `env.example` — garde-fou documenté (JWT_SECRET_KEY, DISABLE_AUTH, SUPERADMIN_PASSWORD) + alias mentionnés
- `.env.prod.example` — garde-fou documenté sur les 3 variables + alias + ligne ajoutée à la checklist finale
- `backend/tests/unit/test_config/__init__.py` — créé
- `backend/tests/unit/test_config/test_production_guard.py` — créé : 13 tests

### Décisions techniques

- Garde-fou = 2 fonctions séparées : `validate` (pure, testable) / `enforce` (log + raise) — pattern cohérent avec la story
- Alias `AliasChoices` plutôt que renommage : non-breaking, `.env.prod.example` (qui documente `SUPERADMIN_*`) devient fonctionnel
- Refus inclut `disable_auth=true` en prod (renforcement validé) et longueur minimale 16 caractères
- Message d'erreur : noms de variables + procédures uniquement (`test_no_secret_value_in_error_message` vérifie l'absence de valeur)
- Isolation des tests via `Settings(_env_file=None, **kwargs)` — évite toute pollution par le `.env` local

### Divergences par rapport à l'analyse

- Aucune divergence fonctionnelle. Test de borne : mot de passe initialement 17 caractères au lieu de 16 (coquille), corrigé en `Exact16CharsPwd!`.
- Environnement : validations via venv de secours `.venv-test` (Python 3.11/uv), venv Poetry racine cassé — même situation que STORY-100, commandes Makefile restent la référence CI.

### Difficultés rencontrées

- Aucune difficulté bloquante.

### Tests ajoutés

- `backend/tests/unit/test_config/test_production_guard.py` : 13/13 passants — couvre les 5 tests AC 5, la valeur dev de env.example, le mot de passe court, disable_auth, les alias SUPERADMIN/ADMIN, la borne 16 caractères, et l'absence de valeur de secret dans les messages
- Non-régression : suite unitaire complète **892 passés / 0 échec** ; flake8 + black + isort verts sur les 4 fichiers Python touchés

## Tâches d'implémentation détaillées

### Tâche 1 : Validateur `validate_production_secrets()` dans config.py
**Objectif :** Créer une fonction pure qui collecte toutes les violations de secrets dev en environnement production (retourne une liste de messages), testable unitairement sans lever l'application.
**Fichiers :**
- `backend/app/config.py` — Modifier — Ajouter au niveau module (après l'instanciation `settings = Settings()`) :
  1. Constante `DEV_JWT_SECRET_VALUES: frozenset[str]` contenant les deux valeurs dev connues : `"dev-secret-key-change-in-production-please-use-a-long-random-string-minimum-32-characters"` (défaut code l.31) et `"dev-jwt-secret-key-change-in-production"` (valeur env.example l.80).
  2. Constante `MIN_ADMIN_PASSWORD_LENGTH: int = 16`.
  3. `def validate_production_secrets(config: Settings) -> list[str]` — retourne une liste de messages de violation (vide = OK). Contrôles **uniquement si `config.is_production`** :
     - `config.jwt_secret_key in DEV_JWT_SECRET_VALUES` → message nommant `JWT_SECRET_KEY` avec marche à suivre (`openssl rand -hex 32`) ;
     - `config.admin_password == "changeme123"` OU `len(config.admin_password) < MIN_ADMIN_PASSWORD_LENGTH` → message nommant `ADMIN_PASSWORD`/`SUPERADMIN_PASSWORD` (les deux alias) ;
     - `config.disable_auth is True` → message nommant `DISABLE_AUTH` (« ne jamais activer en production »).
     Chaque message liste la variable, la raison et la procédure — **jamais la valeur du secret**. Hors production : retour `[]` inconditionnel (AC 3).
  4. Wrapper `def enforce_production_secrets(config: Settings) -> None` : appelle le validateur, si violations → log CRITICAL (logger dédié, sans valeurs) + `RuntimeError` avec le message consolidé « Refus de démarrage : N secret(s) de développement détecté(s) en production — [liste des variables + procédures] ».
**Exigences sécurité :** Messages = noms de variables + procédures uniquement ; aucune valeur de secret dans les messages ni les logs.
**Dépend de :** Aucune

### Tâche 2 : Câblage startup + alias SUPERADMIN_* + correction print seeding
**Objectif :** Brancher le garde-fou au lifespan **avant** `db.connect()` (aucun démarrage partiel), accepter les variables `SUPERADMIN_*` documentées (alias pydantic non-breaking), et supprimer l'affichage du mot de passe au seeding.
**Fichiers :**
- `backend/app/main.py` — Modifier — Dans le `lifespan` (l.60), insérer **en tout premier** (avant `db.connect()` l.81 et avant tout log de bannière) : `enforce_production_secrets(settings)` (import depuis `.config`). En cas d'échec, uvicorn ne démarre pas — comportement attendu AC 1. Ajouter un import `enforce_production_secrets`.
- `backend/app/config.py` — Modifier — Sur les 4 champs admin (l.217-220) : ajouter `validation_alias=AliasChoices("admin_email", "SUPERADMIN_EMAIL")` etc. (migrer `admin_username`, `admin_password`, `admin_full_name`, `admin_email` vers la forme `Field(validation_alias=AliasChoices(...), default=...)` ; importer `AliasChoices` depuis `pydantic`). Conserver les valeurs par défaut actuelles — non-breaking pour les installs `ADMIN_*`.
- `backend/app/database_seed.py` — Modifier — Remplacer la ligne 92 `print(f"  - Mot de passe par défaut: {settings.admin_password}")` par un avertissement **sans valeur** : `print("  - Mot de passe admin: configuré via ADMIN_PASSWORD/SUPERADMIN_PASSWORD")`. Conserver l'avertissement l.93.
**Exigences sécurité :** Garde-fou exécuté avant toute exposition réseau ; aucun secret dans les logs/stdout.
**Dépend de :** Tâche 1

### Tâche 3 : Documentation env.example et .env.prod.example
**Objectif :** Documenter le comportement de blocage et les variables concernées (critère de done du plan), avec nommage cohérent entre les deux fichiers.
**Fichiers :**
- `env.example` — Modifier — (1) Section JWT (l.79-81) : ajouter sous `JWT_SECRET_KEY` un commentaire « ⛔ En production (ENVIRONMENT=production), le démarrage est REFUSÉ si cette clé garde une valeur de développement — générez `openssl rand -hex 32` » ; (2) section superadmin (l.98-99) : préciser que `SUPERADMIN_PASSWORD` (alias `ADMIN_PASSWORD`) doit faire ≥ 16 caractères et ≠ `changeme123` en production, sinon démarrage refusé ; (3) section DISABLE_AUTH (si présente) : avertir du refus en production.
- `.env.prod.example` — Modifier — Vérifier/renforcer les commentaires : (1) l.101 `JWT_SECRET_KEY` — mentionner le garde-fou ; (2) l.125 `SUPERADMIN_PASSWORD` — mentionner ≥ 16 caractères, `changeme123` interdit, garde-fou au démarrage ; (3) l.484-487 checklist — ajouter une ligne « [ ] Le garde-fou de démarrage est passé ( ENVIRONMENT=production + secrets forts) ». Les nommages `SUPERADMIN_*` existants deviennent fonctionnels grâce à la Tâche 2 (alias).
**Exigences sécurité :** Documentation uniquement — aucune valeur réelle.
**Dépend de :** Tâche 2 (pour cohérence des alias documentés)

### Tâche 4 : Tests du garde-fou
**Objectif :** Couvrir les 5 familles de tests exigées par l'AC 5 + les cas alias et disable_auth — tests unitaires purs sur `validate_production_secrets` / `enforce_production_secrets` (pas d'app FastAPI nécessaire).
**Fichiers :**
- `backend/tests/unit/test_config/__init__.py` — Créer — Package vide (convention des autres packages de tests).
- `backend/tests/unit/test_config/test_production_guard.py` — Créer — (pattern : [`test_dev_mode.py`](../../backend/tests/unit/test_auth/test_dev_mode.py)) — construire des `Settings(environment="production", ...)` ciblés via kwargs/monkeypatch env (attention : pydantic-settings lit l'env — utiliser la construction par kwargs `Settings(_env_file=None, environment="production", jwt_secret_key=...)` pour isolation). Voir section Tests.
**Exigences sécurité :** Aucune valeur de secret réelle dans les tests (valeurs factices locales).
**Dépend de :** Tâches 1, 2

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md` — sécurité : `.clinerules/40-security.md`
> Outil : tests unitaires purs — instancier `Settings(_env_file=None, ...)` par kwargs pour isoler de l'environnement.

### Unitaires Backend — `backend/tests/unit/test_config/test_production_guard.py`

Classe `TestValidateProductionSecrets` :
- `test_startup_fails_in_production_with_default_jwt_secret` — **AC 5** : prod + `jwt_secret_key` = défaut code → `enforce_production_secrets` lève `RuntimeError` mentionnant `JWT_SECRET_KEY`
- `test_startup_fails_in_production_with_env_example_jwt_secret` — variante : valeur dev de env.example (`dev-jwt-secret-key-change-in-production`) → également refusée
- `test_startup_fails_in_production_with_default_admin_password` — **AC 5** : prod + `admin_password="changeme123"` → RuntimeError mentionnant `ADMIN_PASSWORD`/`SUPERADMIN_PASSWORD`
- `test_startup_fails_with_short_admin_password` — prod + mot de passe de 10 caractères non-default → refus (longueur < 16)
- `test_startup_fails_lists_all_offending_secrets` — **AC 5** : prod + jwt défaut + changeme123 + disable_auth=True → le message liste les **3** variables
- `test_startup_fails_with_disable_auth_in_production` — prod + `disable_auth=True` (autres secrets forts) → refus mentionnant `DISABLE_AUTH`
- `test_startup_succeeds_in_production_with_strong_secrets` — **AC 5 / AC 2** : prod + jwt fort + admin_password 20+ chars → `validate_production_secrets` retourne `[]`, `enforce` ne lève pas
- `test_dev_environment_unaffected_by_guard` — **AC 5 / AC 3** : `environment="development"` + tous les défauts dev → `[]` (aucun contrôle)
- `test_test_environment_unaffected_by_guard` — `environment="test"` + défauts → `[]`
- `test_no_secret_value_in_error_message` — **sécurité** : l'exception levée avec jwt défaut ne contient **pas** la valeur du secret (assert sur message)
- `test_superadmin_alias_accepted` — **AC 2** : `Settings(_env_file=None, environment="production", _env_overrides...)` ou monkeypatch env `SUPERADMIN_PASSWORD=UnMotDePasseTresFort123` → `settings.admin_password` prend la valeur (alias fonctionnel)
- `test_admin_naming_still_works` — non-breaking : env `ADMIN_PASSWORD=...` continue de fonctionner
- `test_min_password_boundary_16_chars` — limite : exactement 16 caractères → accepté

### Commandes de validation
```bash
# Backend (voir Makefile)
cd backend && poetry run pytest tests/unit/test_config/test_production_guard.py -v --tb=short
make backend-lint
make backend-test-unit
```
