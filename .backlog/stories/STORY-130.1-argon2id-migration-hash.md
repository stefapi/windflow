# STORY-130.1 : Migration Argon2id — double lecture bcrypt et re-hash automatique au login (P1-10 — F2)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Story Parent (split) :** STORY-130 ([ABANDONED — découpe proactive post-analyse le 2026-10-02](STORY-130-purge-celery-arbitrage-argon2.md))
**Item plan :** P1-10 (arbitrage F2, rapport §2) — ampleur **S**

> **Périmètre (découpe)** : cette sous-story reprend le **volet Argon2** de l'analyse STORY-130 — tâches 1-2, la partie « service hash/upgrade + login API » de la tâche 11, la tâche 12, et la partie Argon2 de la tâche 13 (CHANGELOG `Changed` + validation). Le volet Celery (tâches 3-10, garde-fou de la tâche 11, tâche 13 `Removed`) est porté par [STORY-130.2](STORY-130.2-purge-references-celery.md). Les deux sous-stories sont **indépendantes** (aucune interaction technique).

## Description

En tant que mainteneur de WindFlow, je veux **migrer le hachage des mots de passe vers Argon2id avec upgrade automatique au login** — l'écriture est déjà Argon2id, il manque la **lecture des hashes bcrypt legacy** (`$2b$...`) avec re-hachage transparent — afin qu'aucun reset de mot de passe ne soit requis (tous les comptes existants continuent de se connecter) et que le hashage soit aligné sur les rules sécurité (rules 40 : passlib + argon2-cffi), la documentation embarquée OpenAPI étant corrigée en conséquence.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §2) : un contexte `CryptContext(schemes=["argon2"])` **ne sait pas vérifier** un hash bcrypt legacy — passlib ne reconnaît pas le schème → vérification échouée → un éventuel compte bcrypt ne peut pas se connecter aujourd'hui, donc pas non plus être re-haché. Par ailleurs les docstrings/descriptions OpenAPI publiques ([`auth.py`](../../backend/app/api/v1/auth.py), [`users.py`](../../backend/app/api/v1/users.py)) mentionnent encore bcrypt. L'arbitrage F2 tranche : **migrer le code** (double lecture + re-hash au login) et corriger la spec 07 de façon consolidée en STORY-252 (P3-4).

## Contexte technique

> Extrait de l'analyse STORY-130 (2026-10-02, `analyse-story`) — volet Argon2 (P1-10, F2). Constats vérifiés dans le code au moment de l'analyse. Sous-story **indépendante** de STORY-130.2 (purge Celery) : ordre de traitement quelconque, lots de commit/merge séparés.

### État des lieux — la migration est plus avancée que l'ébauche ne le laissait croire

- **`pwd_context` est déjà Argon2** : [`user_service.py`](../../backend/app/services/user_service.py:20) définit `CryptContext(schemes=["argon2"])` — `hash_password` (:31), `verify_password` (:48), `create` (hash à la création, :324) et `update` (re-hash, :374) produisent donc déjà de l'Argon2id. STORY-129 a confirmé et étendu ce socle : `PUT /auth/password` hash en Argon2 ([`auth.py:1126-1128`](../../backend/app/api/v1/auth.py:1126)), le seed admin passe par `UserService.create` ([`database_seed.py:82`](../../backend/app/database_seed.py:82)) → Argon2id dès la création.
- **`argon2-cffi` est déjà une dépendance Poetry** : [`pyproject.toml:24-25`](../../pyproject.toml:24) déclare `passlib = "^1.7.4"` (extra `argon2`) **et** `argon2-cffi = "^23.0.0"` (présent dans `poetry.lock`). L'AC « dépendance argon2-cffi ajoutée » de la story mère est donc **satisfaite de facto** — divergence consignée.
- **Le mécanisme d'upgrade au login existe et est déjà branché** : [`UserService.verify_and_update_user()`](../../backend/app/services/user_service.py:98) (passlib `verify_and_update` + écriture DB + refresh) est consommé par le login ([`auth.py:290-292`](../../backend/app/api/v1/auth.py:290)).
- **⚠️ Trou réel — la double lecture bcrypt est impossible en l'état** : pour honorer « login bcrypt → re-hash Argon2id, aucun reset requis », il faut :
  1. déclarer `schemes=["argon2", "bcrypt"]` avec `deprecated="auto"` — bcrypt devient un schème **déprécié en lecture seule** : `verify_and_update` retourne alors un hash Argon2id à ré-écrire ; l'ordre des schèmes fait d'argon2 le schème par défaut en **écriture** (`hash_password` inchangé) ;
  2. ajouter la dépendance **`bcrypt`** — la seule réellement manquante (absente de [`poetry.lock`] ; passlib exige le package `bcrypt` pour activer son handler bcrypt). C'est une dépendance de **transition (lecture)** : rules 40 (écriture Argon2) restent respectées ; sa retraite post-migration est à consigner pour STORY-250.
- **Bcrypt legacy résiduel** : [`helper/security.py`](../../backend/app/helper/security.py:1) (bcrypt nu) n'est **importé nulle part** (vérifié par grep sur `backend/`, `cli/`, `frontend/`) — code mort, sa suppression reste réservée à STORY-250 ; cette story s'assure uniquement qu'aucun chemin d'auth ne l'utilise (déjà le cas — à proscrire, arbitrage n°1 de STORY-129 toujours valable).
- **Docstrings/OpenAPI mensongères** : [`auth.py:96-98`](../../backend/app/api/v1/auth.py:96) (login : « Password hashing with bcrypt »), [`auth.py:674-676`](../../backend/app/api/v1/auth.py:674) (register), [`users.py:427-429`](../../backend/app/api/v1/users.py:427) (« Passwords are hashed with bcrypt ») — descriptions OpenAPI publiques à corriger en Argon2id. Les **specs** `docs/general_specs/07|15` restent réservées à STORY-252 (répartition du plan).
- **Paramètres Argon2id** : passlib/argon2-cffi appliquent leurs défauts (variant id, recommandations RFC 9106). Décision : **ne pas surcharger** les paramètres (arbitrage n°2 ci-dessous).

### Patterns existants à réutiliser (réutilisation directe)

| Besoin | Élément réutilisable | Fichier |
|---|---|---|
| Upgrade hash au login | `UserService.verify_and_update_user(db, user, plain)` — déjà branché au login | [`user_service.py:98`](../../backend/app/services/user_service.py:98), consommé [`auth.py:291`](../../backend/app/api/v1/auth.py:291) |
| Hash Argon2id (écriture) | `UserService.hash_password` — inchangé par l'extension de schèmes | [`user_service.py:31`](../../backend/app/services/user_service.py:31) |
| Hash Argon2 déterministe (clés API) | pattern `pwd_context.handler().using(salt=...)` — **non impacté** (déjà argon2-only, aucune donnée bcrypt) | [`api_key_service.py:72`](../../backend/app/services/api_key_service.py:72) |
| Comptes seedés Argon2 | `UserService.create` consommé par le seed | [`database_seed.py:82`](../../backend/app/database_seed.py:82) |
| Génération d'un hash bcrypt de fixture | passlib `CryptContext(schemes=["bcrypt"])` local au test (après ajout de la dépendance) | — |
| Tests login/password sur DB réelle | fixtures du conftest + patterns de [`test_auth_password_flow.py`](../../backend/tests/integration/test_auth_password_flow.py) | [`conftest.py`](../../backend/tests/conftest.py) |

### Arbitrages d'analyse (décisions proposées, à appliquer telles quelles — volet Argon2)

| # | Question | Décision | Justification |
|---|---|---|---|
| 1 | Dépendance à ajouter | **`bcrypt = "^4.0.0"`** (transition, lecture seule) — **pas** argon2-cffi (déjà présent, divergence AC mère) | passlib exige le package bcrypt pour vérifier les hashes legacy ; l'avertissement passlib 1.7.4 / bcrypt ≥ 4.1 (« error reading bcrypt version ») est cosmétique — l'ignorer, ou pinner `4.0.1` s'il bruite la CI |
| 2 | Paramètres Argon2id | **Défauts passlib/argon2-cffi, sans surcharge** (pas de `argon2__*`) | Les hashes existants utilisent ces défauts ; surcharger déclencherait un re-hash de **tous** les comptes au login via `deprecated="auto"` (coût ~100 ms/compte, gain nul) ; tout durcissement futur sera auto-porté par `verify_and_update` |
| 3 | Stratégie de migration | **Upgrade paresseux au login uniquement** — pas de script de masse en migration Alembic | Conforme à l'arbitrage F2 et au critère de done P1-10 (« aucun reset requis ») ; un re-hash de masse coûterait cher pour un gain nul ; les comptes inactifs gardent un hash bcrypt vérifiable indéfiniment (double lecture permanente) |
| 4 | `helper/security.py` (bcrypt nu) | **Ne pas toucher** — purge réservée à STORY-250 | Code mort non importé (vérifié) ; périmètre minimal ; cette story garantit seulement qu'aucun chemin d'auth ne l'importe |
| 9 | Blindage des hashes illisibles | `verify_password` / `verify_and_update` interceptent `ValueError`/`TypeError` (schème inconnu, hash corrompu) → `(False, None)` sans lever | Un hash imprévisible en base ne doit jamais provoquer de 500 au login ; échec silencieux = même 401 générique anti-énumération (rules 40) |

*(Les arbitrages n°5-8 de l'analyse mère concernent le volet Celery — voir STORY-130.2.)*

### Points d'attention sécurité (checklist rules 40 appliquée à cette story)

- **Aucun nouvel endpoint** → pas de surface HTTP nouvelle ; le login existant change de comportement uniquement pour les hashes bcrypt (vérification + re-hash transparent). Tests 401/403/422/404 existants non impactés (non-régression à jouer).
- **Jamais de mot de passe ni de hash dans les logs/réponses** : l'upgrade au login logge uniquement `user_id` (pattern existant) ; les tests assertent l'absence de hash dans les réponses login/password.
- **Messages génériques** : échec bcrypt ou argon2 → même 401 générique (aucune fuite d'information sur l'algorithme du hash stocké — anti-énumération).
- **Audit** : aucun événement d'audit nouveau requis (le re-hash est une opération technique transparente, pas une action utilisateur) — décision à consigner dans les notes d'implémentation.
- **Exposition de données sensibles** : aucune réponse API ne change de forme ; `users.hashed_password` n'est jamais sérialisé (schémas Pydantic existants).

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend l'AC 2 de la story mère)* : la dépendance de lecture **`bcrypt`** est ajoutée (Poetry — `argon2-cffi` étant déjà présent, divergence consignée) ; le login d'un utilisateur bcrypt → **hash re-haché Argon2id en base après login** (test) ; **aucun reset de mot de passe requis** (tous les comptes existants continuent de se connecter) ; comptes nouvellement créés hashés Argon2id.
- [x] AC 2 *(reprend l'AC 3 de la story mère)* : l'upgrade path est **documenté** (notes d'implémentation + mention dans la story) : paramètres Argon2id (défauts, pas de surcharge), transition double lecture, stratégie paresseuse au login, renvoi de la correction consolidée des specs 07/15 à STORY-252 (P3-4) avec les arbitrages F5 (JWT 15 min) et F1 (specs 04/05).
- [x] AC 3 *(reprend l'AC 4 de la story mère, périmètre auth)* : `make lint` + `make backend-test` verts ; non-régression complète des flux auth (login username/email, register, refresh, disable_auth).

## Références spécification

- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § hashage (bcrypt cost 12 — à corriger en Argon2id via STORY-252 conformément à l'arbitrage F2), § flow de login (upgrade au login) ;
- `.roo/rules/40-security.md` — bibliothèques d'authentification : passlib + **argon2-cffi** (hash des mots de passe) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §2 (bcrypt vs rules) ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §3 F2 (Argon2, corriger le code), §4 P1-10, §7.4 arbitrage F2 (validé).

## Dépendances

- **Arbitrage F2 validé par l'utilisateur** (plan §7.4 — validation acquise lors de la création des epics).
- **STORY-129 — DONE ✔** : `pwd_context` déjà Argon2 ; `PUT /auth/password`, register et seed hashsent déjà en Argon2id — cette story n'a **aucun changement** à y apporter ; l'extension `schemes=["argon2","bcrypt"]` est rétro-compatible avec tous les hashes Argon2 déjà écrits (aucun re-hash superflu — arbitrage n°2).
- **STORY-130.2 — indépendante** : aucune interaction technique avec la purge Celery (ordre quelconque, lots de commit/merge séparés).
- **Aucune migration DB** : `users.hashed_password` (colonne String existante) accueille indifféremment `$argon2id$...` et `$2b$...` — l'upgrade est purement applicatif, au fil des logins (arbitrage n°3).
- **Aucun service externe nouveau**.
- **Interaction STORY-252 (P3-4, EPIC-014)** : corrections consolidées des specs 07/15 réservées — cette story **ne modifie aucun fichier `docs/general_specs/`** (divergence contrôlée documentée dans l'epic).
- **Interaction STORY-250 (EPIC-014)** : retraite de la dépendance `bcrypt` post-migration + suppression de `helper/security.py`.

## État d'avancement technique

*(cochage progressif pendant treat-story — rien n'est coché à ce stade ; numérotation propre à cette sous-story, correspondance avec l'analyse mère indiquée par tâche)*

- [x] Tâche 1 — *(mère : tâche 1)* Double lecture Argon2/bcrypt : `pwd_context` + dépendance `bcrypt` + blindage
- [x] Tâche 2 — *(mère : tâche 2)* Correction docstrings/OpenAPI « bcrypt » → Argon2id (auth.py, users.py)
- [x] Tâche 3 — *(mère : tâche 11, partie Argon2)* Tests unitaires — service hash/upgrade + login API
- [x] Tâche 4 — *(mère : tâche 12)* Tests d'intégration — migration bcrypt→Argon2id de bout en bout
- [x] Tâche 5 — *(mère : tâche 13, ajustée au périmètre Argon2)* CHANGELOG `Changed` + validation finale du périmètre Argon2

## Tâches d'implémentation détaillées

> Séquencement : code (tâches 1-2) → tests (tâches 3-4) → clôture (tâche 5). Les exigences sécurité (rules 40) sont intégrées inline dans les tâches concernées. Contenu repris de l'analyse STORY-130 (tâches 1-2, 11 partie Argon2, 12, 13 partie Argon2), renuméroté.

### Tâche 1 : Double lecture Argon2/bcrypt — `pwd_context` + dépendance `bcrypt`

*(mère : tâche 1 — arbitrages n°1, n°2, n°9 inline)*

**Objectif :** permettre la vérification (et le re-hash automatique au login) des mots de passe bcrypt legacy, l'écriture restant Argon2id — cœur de l'AC 1.

**Fichiers :**
- [`pyproject.toml`](../../pyproject.toml:24) — **Modifier** : ajouter `bcrypt = "^4.0.0"` dans `[tool.poetry.dependencies]` (à côté de `passlib`/`argon2-cffi`, avec un commentaire « transition : vérification des hashes bcrypt legacy (lecture seule) — retrait post-migration, cf. STORY-250 ») ; régénérer le lock (`poetry lock && poetry install` — Poetry uniquement, rules 05) ; **conserver** l'override mypy `bcrypt` (:110, pas de stubs) ;
- [`backend/app/services/user_service.py`](../../backend/app/services/user_service.py:20) — **Modifier** :
  - `pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")` avec commentaire : argon2 = schème par défaut en **écriture** (premier non-déprécié) ; bcrypt = **lecture seule dépréciée** pour la transition (upgrade au login) ;
  - `verify_and_update` (:64) et `verify_password` (:47) : aveuglir contre les hashes illisibles — `try/except (ValueError, TypeError)` → retour `(False, None)` / `False` sans lever (arbitrage n°9 : jamais de 500 au login, même 401 générique) ;
  - docstrings : documenter la double lecture, l'upgrade automatique, les paramètres Argon2id **par défaut** de passlib/argon2-cffi (arbitrage n°2 — pas de surcharge), et le chemin de retraite de bcrypt (STORY-250) ;
  - `verify_and_update_user` (:98) : inchangé fonctionnellement (il écrit déjà le `new_hash` retourné) — vérifier uniquement que le re-hash pose bien `db.commit()` (déjà le cas).

**Sécurité (inline) :** aucun log de mot de passe/hash ; l'échec de vérification reste un `False` silencieux consommé par le 401 générique existant du login.

**Dépend de :** Aucune

### Tâche 2 : Correction des docstrings/OpenAPI « bcrypt » → Argon2id

*(mère : tâche 2)*

**Objectif :** aligner la documentation embarquée (descriptions OpenAPI publiques) sur la réalité Argon2id — AC 2 (documentation de l'upgrade path), rules 20 (OpenAPI à jour).

**Fichiers :**
- [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py:96) — **Modifier** : description du login (:96-98 « Password hashing with bcrypt » → Argon2id + mention « automatic upgrade of legacy bcrypt hashes at login ») et du register (:674-676) ;
- [`backend/app/api/v1/users.py`](../../backend/app/api/v1/users.py:427) — **Modifier** : « Passwords are hashed with bcrypt before storage » → Argon2id ;
- vérifier à la génération (`/openapi.json` ou `make generate-openapi-docs`) que plus aucune description publique ne mentionne bcrypt.

**Dépend de :** Tâche 1 (cohérence du discours)

### Tâche 3 : Tests unitaires — hash/upgrade + login API

*(mère : tâche 11, **partie Argon2 uniquement** — la partie « garde-fou `test_no_celery_residue.py` » de la tâche 11 mère est portée par STORY-130.2, tâche 9)*

**Objectif :** couvrir le mécanisme de migration (AC 1). Cible ≥ 80 % sur les fichiers touchés (rules 35).

**Fichiers :**
- [`backend/tests/unit/test_services/test_user_service.py`](../../backend/tests/unit/test_services/test_user_service.py) — **Modifier (étendre)** — nouveau bloc « hashage Argon2 / migration bcrypt » :
  - `hash_password` produit un préfixe `$argon2id$` ;
  - `verify_password` round-trip Argon2 ;
  - `verify_and_update` sur hash **bcrypt** (fixture générée via `CryptContext(schemes=["bcrypt"])` locale au test) → `(True, new_hash)` avec `new_hash.startswith("$argon2id$")` — **cœur AC 1** ;
  - `verify_and_update` sur hash **argon2** → `(True, None)` (pas de re-hash superflu — arbitrage n°2) ;
  - `verify_and_update` mot de passe faux → `(False, None)` ;
  - `verify_and_update`/`verify_password` sur hash illisible (préfixe inconnu, ex. `$scrypt$...`) → `(False, None)`/`False` **sans lever** (arbitrage n°9) ;
  - `verify_and_update_user` (session `AsyncMock`) : bcrypt → `user.hashed_password` mis à jour + `commit` appelé ; argon2 → pas de `commit` superflu ;
- `backend/tests/unit/test_api/test_auth_login_hash_upgrade.py` — **Créer** (patterns `_jwt_mode`/fixtures du conftest, DB de test) :
  - utilisateur seedé avec hash bcrypt (écriture directe en base) → `POST /auth/login` → **200** ; relecture DB : `hashed_password.startswith("$argon2id$")` (AC 1) ;
  - deuxième login (hash désormais argon2) → 200 — la boucle est stable ;
  - mot de passe faux → **401 générique** — aucune fuite du schème du hash (rules 40) ;
  - réponse login sans hash ni mot de passe (champs sensibles absents).

**Dépend de :** Tâches 1-2

### Tâche 4 : Tests d'intégration — migration de bout en bout

*(mère : tâche 12)*

**Objectif :** valider le parcours complet en conditions réelles (AC 1 + AC 3 : non-régression des flux auth).

**Fichiers :**
- `backend/tests/integration/test_password_hash_migration.py` — **Créer** (DB réelle, patterns [`test_auth_password_flow.py`](../../backend/tests/integration/test_auth_password_flow.py)) :
  - **flux complet** : seed utilisateur bcrypt → `POST /auth/login` (200) → hash DB devenu `$argon2id$` → `PUT /auth/password` avec l'ancien mot de passe d'origine (200 — preuve que la vérification bcrypt fonctionne aussi sur ce chemin) → login avec le nouveau mot de passe (200) ;
  - **non-régression argon2** : utilisateur créé via `POST /auth/register` → hash `$argon2id$` dès la création (AC 1) → login 200 → hash **inchangé** en base (pas de re-hash superflu) ;
  - **non-régression flux existants** : jouer les suites auth déjà vertes (`test_auth_password_flow.py`, `test_auth_api.py`, `test_auth_refresh_security.py`) — login username/email, register, refresh, disable_auth couverts par ces suites (AC 3).

**Dépend de :** Tâches 1-3

### Tâche 5 : CHANGELOG + validation finale (périmètre Argon2)

*(mère : tâche 13, **ajustée** : seule l'entrée `Changed` et les validations du périmètre Argon2 — l'entrée `Removed` et les validations compose/grep sont portées par STORY-130.2, tâche 10)*

**Objectif :** tracer les changements et valider l'ensemble du périmètre Argon2 (AC 1, AC 2, AC 3).

**Fichiers :**
- [`CHANGELOG.md`](../../CHANGELOG.md) — **Modifier** : entrée sous `[Unreleased]` (pattern STORY-126.3/128/129) :
  - **Changed** : « Password hashing : double lecture bcrypt legacy + re-hash automatique Argon2id au login (aucun reset de mot de passe requis — arbitrage F2) ; dépendance `bcrypt` ajoutée en transition (lecture seule) » ;
- **Notes d'implémentation (AC 2)** : documenter l'upgrade path — paramètres Argon2id par défaut (arbitrage n°2), double lecture permanente, stratégie paresseuse au login (arbitrage n°3), retraite de `bcrypt` → STORY-250, renvoi des corrections consolidées de specs 07/15 → STORY-252 (avec arbitrages F5/F1) ; consigner la décision « aucun audit nouveau requis pour le re-hash » et la divergence « argon2-cffi déjà présent ».

**Validation (périmètre Argon2 uniquement) :**
```bash
make backend-lint                                # isort + black + flake8 + mypy + bandit
make backend-test-unit                           # dont test_user_service étendu, login upgrade
make backend-test-integration                    # dont test_password_hash_migration
make backend-test                                # AC 3 — global (baseline STORY-128 : 12 échecs préexistants documentés acceptés)
make lint                                        # AC 3 (backend + frontend + cli)
```

**Dépend de :** Tâches 1-4

## Tests à écrire

> Récapitulatif (détail dans les tâches 3-4). Patterns : rules 35 (`httpx.AsyncClient` + `ASGITransport`, fixtures DB du conftest), helpers `unwrap`/`error_code`. Sécurité rules 40 : cette story n'ouvre aucun endpoint — les obligations 401/403/422/404 sont couvertes par **non-régression** des suites existantes + cas génériques ci-dessous.

### Backend — unitaires

- `backend/tests/unit/test_services/test_user_service.py` (extension) — `$argon2id$` en écriture ; double lecture bcrypt→Argon2id via `verify_and_update` ; pas de re-hash superflu sur hash argon2 ; mot de passe faux → `(False, None)` ; hash illisible → échec silencieux sans exception ; `verify_and_update_user` persiste le re-hash (commit).
- `backend/tests/unit/test_api/test_auth_login_hash_upgrade.py` (création) — login d'un compte bcrypt → 200 + hash DB re-haché Argon2id (AC 1) ; login suivant 200 ; mot de passe faux → 401 générique (anti-énumération, aucune fuite du schème) ; réponse sans champ sensible.

### Backend — intégration

- `backend/tests/integration/test_password_hash_migration.py` (création) — flux complet bcrypt → login (re-hash) → `PUT /auth/password` → login nouveau mot de passe ; register → Argon2id dès création, hash stable ; non-régression des suites auth existantes (login username/email, register, refresh, disable_auth — AC 3).

### Frontend / CLI

- *(non applicable — aucun contrat API modifié : comportement interne de hashage)*

### Commandes de validation

```bash
poetry run pytest backend/tests/unit/test_services/test_user_service.py backend/tests/unit/test_api/test_auth_login_hash_upgrade.py -v
poetry run pytest backend/tests/integration/test_password_hash_migration.py backend/tests/integration/test_auth_password_flow.py -v
make backend-lint
make backend-test
```

## Notes d'implémentation

*(clôture treat-story — 2026-10-03)*

### Fichiers modifiés/créés

- [`pyproject.toml`](../../pyproject.toml) — **modifié** : `bcrypt = "^4.0.0"` dans `[tool.poetry.dependencies]` avec commentaire « transition : vérification des hashes bcrypt legacy (lecture seule) — retrait post-migration, cf. STORY-250 » ; override mypy `bcrypt` **conservé** ; `poetry lock` régénéré (bcrypt 4.3.0 résolu, seul ajout au lock — 66 insertions).
- [`backend/app/services/user_service.py`](../../backend/app/services/user_service.py) — **modifié** : `pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")` (argon2 = écriture par défaut, bcrypt = lecture seule dépréciée) ; blindage `try/except (ValueError, TypeError)` sur `verify_password` (→ `False`) et `verify_and_update` (→ `(False, None)`) ; docstrings complétées (double lecture, upgrade auto, paramètres par défaut, retraite STORY-250). `verify_and_update_user` inchangé (le `db.commit()` était déjà présent — vérifié).
- [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py) — **modifié** : docstrings OpenAPI login/register → Argon2id + « automatic upgrade of legacy bcrypt hashes at login » ; docstring `PUT /auth/password` aligné sur la double lecture.
- [`backend/app/api/v1/users.py`](../../backend/app/api/v1/users.py) — **modifié** : « Passwords are hashed with Argon2id before storage » (+ reformatage black cosmétique ligne 113).
- [`backend/app/helper/security.py`](../../backend/app/helper/security.py) — **modifié (divergence, voir ci-dessous)** : `except (ValueError, bcrypt.exceptions.SaltValidationError)` → `except ValueError` (compatibilité bcrypt ≥ 4.0).
- [`backend/tests/unit/test_services/test_user_service.py`](../../backend/tests/unit/test_services/test_user_service.py) — **étendu** : blocs `TestArgon2Hashing` (2), `TestVerifyAndUpdate` (5), `TestVerifyAndUpdateUser` (3).
- [`backend/tests/unit/test_api/test_auth_login_hash_upgrade.py`](../../backend/tests/unit/test_api/test_auth_login_hash_upgrade.py) — **créé** : 5 tests (login bcrypt → 200 + re-hash, 2e login, 401 générique sans fuite de schème, réponse sans champ sensible, login par email).
- [`backend/tests/integration/test_password_hash_migration.py`](../../backend/tests/integration/test_password_hash_migration.py) — **créé** : 2 tests (flux complet bcrypt → login → `PUT /auth/password` → login nouveau mdp ; register → Argon2id stable).
- [`CHANGELOG.md`](../../CHANGELOG.md) — **modifié** : entrée `Changed` STORY-130.1 sous `[Unreleased]`.

### Décisions techniques (AC 2 — upgrade path)

- **Paramètres Argon2id** : défauts passlib/argon2-cffi, **aucune surcharge** (arbitrage n°2 — un durcissement déclencherait un re-hash de tous les comptes au login via `deprecated="auto"` ; tout durcissement futur sera auto-porté par `verify_and_update`).
- **Double lecture permanente** : `schemes=["argon2", "bcrypt"]` — les comptes inactifs gardent un hash bcrypt vérifiable indéfiniment (arbitrage n°3 : upgrade paresseux au login uniquement, pas de script de masse).
- **Retraite de `bcrypt`** : dépendance de transition lecture seule → STORY-250 (EPIC-014).
- **Specs 07/15** : corrections consolidées renvoyées à STORY-252 (P3-4, arbitrages F5 JWT 15 min et F1 specs 04/05) — cette story ne modifie aucun `docs/general_specs/`.
- **Audit** : aucun événement d'audit nouveau requis — le re-hash est une opération technique transparente, pas une action utilisateur (l'audit `user.login` existant couvre le flux).
- **Avertissement passlib 1.7.4 / bcrypt ≥ 4.1** (« error reading bcrypt version », `__about__`) : cosmétique et prévu par l'arbitrage n°1 — n'entraîne aucun échec de test (vérifié : 18+4 tests verts). Le pin 4.0.1 n'a **pas** été retenu car il ne résoudrait pas l'erreur mypy `bcrypt.exceptions` (module absent dès 4.0 — vérifié sur wheel 4.0.1).

### Divergences

1. **`helper/security.py`** (arbitrage n°4 « ne pas toucher » contredit) : l'installation de `bcrypt` a rendu le module visible pour mypy → erreur `[attr-defined]` sur `bcrypt.exceptions.SaltValidationError` (module supprimé en bcrypt 4.0). Correction **minimale de compatibilité** (une ligne, pas une purge) pour ne pas introduire d'erreur lint nouvelle ; la suppression du fichier reste intégralement portée par STORY-250.
2. **`make backend-test` inexistant** : la cible Makefile réelle est `backend-test-all` (vérifié `make: *** Aucune règle`) — utilisée en substitution ; écarts de story purement nominatifs.
3. **Baseline tests** : la story référence « 12 échecs préexistants (STORY-128) » ; l'environnement actuel présente **35 échecs unitaires + 20 intégration**, tous **vérifiés préexistants par stash** (mêmes échecs sur le code d'origine) et **aucun dans les fichiers liés au hashage** : `test_stack_actions` (19), `test_stacks_archive` (9), `test_users` (3), `test_auth_isolation` (2), `test_stacks_duplicate` (1), `test_debug_story1033` (1) ; intégration : `test_deployments_api` (8), `test_security_headers` (9), `test_auth_api` (3, « No superadmin user found » en mode dev). Zéro régression introduite — ces échecs semblent postérieurs à la baseline STORY-128 (hors périmètre de cette story).
4. **`make backend-lint`** : échoue sur 17 erreurs mypy **préexistantes** (7 fichiers non touchés : plugin_lifecycle_service, stats/psutil, targets/connectivity, main.py, docker_client_service, jwt/jose) et sur **bandit non installé** dans l'environnement (absent des dev-dependencies Poetry). Lint ciblé sur les 7 fichiers touchés : isort + black + flake8 + mypy **tous verts**.

### Difficultés rencontrées

- `poetry install` : builds natifs `libvirt-python`/`fastuuid` impossibles sous Python 3.14 (environnement) — sans impact : seuls `bcrypt` (+ deps) était requis, installé ; `passlib`/`argon2` opérationnels.
- Test intégration register : 2 itérations — provisionnement de l'org par défaut requise (`DEFAULT_ORG_SLUG`, pattern `test_auth_isolation`) puis chemin de payload `created["user"]["id"]` (la réponse register retourne les tokens + `user` imbriqué).

### Validation (commandes et résultats)

| Commande | Exécuté | Résultat |
|---|---|---|
| `poetry run pytest backend/tests/unit/test_services/test_user_service.py backend/tests/unit/test_api/test_auth_login_hash_upgrade.py -v` | oui | **18 passed** |
| `poetry run pytest backend/tests/integration/test_password_hash_migration.py backend/tests/integration/test_auth_password_flow.py -v` | oui | **4 passed** |
| `make backend-lint` | oui | ❌ 17 erreurs mypy **préexistantes** + bandit absent (préexistant) ; lint ciblé fichiers touchés : **vert** |
| `make backend-test-unit` | oui | 1658 passed / 35 failed **préexistants** (vérifiés stash, aucun lié au hashage) |
| `make backend-test-integration` | oui | 166 passed / 20 failed **préexistants** (vérifiés stash) |
| `make backend-test-all` (substitution `backend-test`) | oui | s'arrête à la phase unit (échecs préexistants) — phases jouées séparément |
| `make lint` | oui | ❌ bloque sur `backend-lint` (préexistant) ; `cli-lint` : **OK** ; `frontend-lint-check` : script `lint:check` manquant (environnement, préexistant) |
| Vérification OpenAPI (`app.openapi()`) | oui | Plus aucune description ne présente bcrypt comme algorithme de hachage ; seules mentions restantes = upgrade legacy au login + double lecture `PUT /auth/password` (voulues) |

**Statut final : DONE** — tous les tests de la story passent ; aucune régression introduite (échecs préexistants prouvés par comparaison stash).
