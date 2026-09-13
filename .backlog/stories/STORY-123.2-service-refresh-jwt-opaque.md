# STORY-123.2 : `RefreshTokenService` et refresh token opaque dans `jwt.py`

**Statut :** DONE
**Story Parente :** STORY-123 — Refresh tokens révocables — table, rotation et logout invalidant (P1-3, partie refresh)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'utilisateur de WindFlow, je veux que le refresh token émis soit une **chaîne opaque** (pas un JWT) générée cryptographiquement, et que toute la logique de cycle de vie (création par hash, vérification, **rotation à chaque usage avec révocation défensive de la famille**, révocation unitaire et globale, purge) soit centralisée dans un service testable, afin que les endpoints auth (STORY-123.3) ne fassent qu'orchestrer sans logique métier.

Cette sous-story ne modifie **aucun endpoint** : elle transforme [`jwt.py`](../../backend/app/auth/jwt.py) (le refresh devient opaque, l'access reste un JWT 15 min — durée code actuelle, plus sûre que la spec, arbitrage F5) et pose le service consommé par STORY-123.3 (endpoints) et STORY-123.4 (purge).

## Critères d'acceptation (AC)

- [x] AC 2 : **Rotation** : `POST /auth/refresh` accepte le refresh courant une seule fois et en émet un nouveau (l'ancien invalidé) ; un refresh révoqué/expiré/consommé → `401` ; cohérence conservée avec les vérifications actuelles (utilisateur actif).

> **Note de découpe :** cette sous-story couvre la part **mécanique** de l'AC 2 (rotation + invalidation au niveau service et émission opaque). La démonstration HTTP de bout en bout (`POST /auth/refresh` → 401 sur token consommé) est portée par STORY-123.3 — l'AC n'est cochable sur la story parente qu'après fermeture de 123.2 **et** 123.3.

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-12) — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches.

**Couches impactées :** Backend uniquement — `auth/jwt.py`, nouveau service, tests backend. **Aucun endpoint modifié** dans cette sous-story ; les contrats des endpoints (formes `LoginResponse`/`RefreshResponse`) restent inchangés (STORY-126 = format).

**Spécifications de référence :**
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Refresh token (opaque, hash en base, flow refresh, rotation), § Validation des tokens ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Gestion des erreurs (`INVALID_OR_EXPIRED_TOKEN`).

**Fichiers de référence (patterns vérifiés) :**
- [`backend/app/auth/jwt.py`](../../backend/app/auth/jwt.py) — `create_token_pair()` / `decode_access_token()` / `decode_refresh_token()` : `create_token_pair` devient émetteur du token opaque ; `decode_refresh_token` est **rendu obsolète** (remplacé par le lookup par hash du service — vérifier ses consommateurs résiduels avant retrait) ;
- Pattern service statique async → [`backend/app/services/user_organization_service.py`](../../backend/app/services/user_organization_service.py) ;
- Contexte de hash mots de passe (objet de l'arbitrage n°1 tranché en STORY-123.1) → `pwd_context` Argon2 dans `backend/app/auth/` ;
- Modèle `RefreshToken` + settings `refresh_token_expire_days` → posés par STORY-123.1 (`models/refresh_token.py`, `config.py`) ;
- Tests JWT à adapter → [`backend/tests/unit/test_auth/test_jwt_claims.py`](../../backend/tests/unit/test_auth/test_jwt_claims.py) ;
- Fixtures : `db_session`, `test_user` ([`backend/tests/conftest.py`](../../backend/tests/conftest.py)).

**Décisions d'analyse :**
- **Génération opaque :** `secrets.token_urlsafe(64)` (~86 caractères base64url, entropie 512 bits) — recommandation OWASP pour les refresh tokens opaques ; préfixe de version optionnel (ex. `wf_rt_`) pour diagnostic visuel, sans exiger de format pour les consommateurs (contrat `{refresh_token: string}` inchangé) ;
- **Durée :** `settings.refresh_token_expire_days` (7 j par défaut, STORY-123.1) — supprime toute constante 7 j résiduelle côté `jwt.py` ;
- **Access token inchangé :** JWT 15 min, `decode_access_token()` intact — l'arbitrage F5 (spec corrigée en P3/STORY-252) acte que le code est plus sûr que la spec ;
- **Rotation atomique :** `rotate()` marque l'ancienne ligne (`revoked_at`) **et** crée la nouvelle dans la même transaction session — un refresh déjà `revoked_at` non nul = token **consommé** → refus + **révocation défensive de la famille** (tous les tokens de l'utilisateur, recommandation analysis §rotation) ;
- **Lookup par hash uniquement :** `verify()` hashe le token soumis et cherche par `token_hash` — un refresh ne résout que son user, jamais l'inverse ;
- **`decode_refresh_token()`** : supprimée ou réduite à un déprecated shim selon ses consommateurs — l'unique consommateur légitime est `/auth/refresh` (réécrit en 123.3).

## ⚠️ Points d'arbitrage hérités / dépendances d'arbitrage

**Arbitrage n°1 (bcrypt vs Argon2) — tranché en STORY-123.1 :** cette sous-story **consomme** la décision (fonction de hash du `token_hash` = `pwd_context` Argon2 si Option A retenue). Ne pas re-trancher ici — appliquer et, si un blocage survient, documenter la divergence dans les Notes d'implémentation.

**Exigences sécurité identifiées (Phase 2.6 de l'analyse) :**
- **Isolation :** lookup par hash — un refresh ne résout que son utilisateur ; réutilisation d'un token révoqué → refus **+ révocation défensive de la famille** ;
- **Validation :** le token soumis à `verify()` est validé non vide et **longueur max bornée** (ex. ≤ 512 caractères) avant tout hash — anti-DoS du hash (le hash d'une chaîne énorme coûte cher) ;
- **Exposition :** **jamais de token en clair dans les logs** (logger uniquement `user_id`, ids de lignes, codes) ; aucune méthode du service ne retourne la valeur claire d'un token existant ;
- **Audit :** log info sans valeur de token à la rotation/révocation (audit formel reporté à STORY-125).

## Dépendances

- STORY-123.1 (modèle + migration + config) — **prérequis**.
- Bloque : STORY-123.3, STORY-123.4.

## Périmètre indicatif (répartition des tâches identifiées par l'analyse de STORY-123)

| # | Tâche (issue de l'analyse STORY-123) | Périmètre de cette sous-story |
|---|--------------------------------------|-------------------------------|
| T3 | Service (hash/rotation/révocations/purge) | ✅ Complet |
| T4 | `jwt.py` token opaque | ✅ Complet |
| T5-T7 | Endpoints `/login` `/refresh` `/logout` | ❌ STORY-123.3 |
| T8 | Job de purge lifespan | ❌ STORY-123.4 (consomme `purge_expired`) |
| T9 | Tests service/jwt → ici ; endpoint/transverses → 123.3/123.4 | 🔶 Partie service + adaptation `test_jwt_claims.py` |

**Hors périmètre :** endpoints et persistance au login (123.3) ; job lifespan et tests transverses (123.4) ; schémas Pydantic des réponses (formes inchangées — STORY-126).

## Tâches d'implémentation détaillées

### Tâche 1 : Refresh token opaque dans `jwt.py`
**Objectif :** Faire émettre par `create_token_pair()` un refresh token opaque (au lieu d'un JWT 7 j) tout en laissant l'access JWT 15 min intact, et retirer la fabrication JWT du refresh.
**Fichiers :**
- `backend/app/auth/jwt.py` — Modifier —
  - Ajouter `generate_refresh_token() -> str` : `secrets.token_urlsafe(64)` (préfixe optionnel `wf_rt_`) ;
  - `create_token_pair(...)`: le refresh vaut désormais `generate_refresh_token()` — **la persistance de son hash est du ressort de l'appelant** (123.3) : changer la signature pour retourner la valeur claire (ou introduire `create_token_pair_opaque`) tout en documentant l'obligation de persister le hash immédiatement ;
  - Supprimer/reléguer `decode_refresh_token()` (vérifier les consommateurs par recherche globale ; l'unique consommateur légitime est `/auth/refresh`, réécrit en 123.3) ; conserver `decode_access_token()` inchangé ;
  - Supprimer toute constante `REFRESH_TOKEN_EXPIRE_*` JWT résiduelle (la durée vit côté service/setting 123.1).
- `backend/tests/unit/test_auth/test_jwt_claims.py` — Modifier — Adapter les assertions : le refresh n'est **pas** un JWT (pas de structure à 3 segments, pas de décodage possible) ; l'access conserve ses claims.
**Exigences sécurité :** Entropie ≥ 512 bits (`token_urlsafe(64)`) ; aucune donnée sensible dans les logs de `jwt.py`.
**Dépend de :** Aucune (au sein de cette sous-story)

### Tâche 2 : `RefreshTokenService` — création, vérification, rotation, révocations
**Objectif :** Poser le service complet du cycle de vie des refresh tokens (pattern service statique async), avec rotation atomique et révocation défensive de la famille.
**Fichiers :**
- `backend/app/services/refresh_token_service.py` — Créer — Classe/méthodes (pattern : `user_organization_service.py`) :
  - `async create(db, user_id, token_plain) -> RefreshToken` — hashe le token (fonction issue de l'arbitrage n°1 — `pwd_context` si Option A), stocke `token_hash` + `expires_at = now + settings.refresh_token_expire_days`, **ne logge jamais la valeur claire** ;
  - `async verify(db, token_plain) -> RefreshToken` — validations préalables (non vide, longueur ≤ 512), hash, lookup par `token_hash` ; refus si introuvable, `expires_at` dépassé ou `revoked_at` non nul (token consommé → déclencher la révocation défensive, cf. `rotate`) ;
  - `async rotate(db, token_plain) -> tuple[RefreshToken, str]` — atomique en une transaction session : refus + **révocation défensive de la famille** (`revoke_all_for_user`) si `revoked_at` non nul ou expiré ; sinon marque `revoked_at`, génère un nouveau token opaque, crée sa ligne, retourne (nouvelle ligne, valeur claire) ;
  - `async revoke(db, token_plain) -> bool` — marque `revoked_at` sur la ligne résolue par hash (idempotent) ;
  - `async revoke_all_for_user(db, user_id) -> int` — révocation globale (consommée par `/logout` selon l'arbitrage n°2 et par STORY-129 changement de mot de passe) ;
  - `async purge_expired(db) -> int` — suppression des lignes expirées **ou révoquées** au-delà d'une rétention courte (implémentation consommée par le job 123.4).
- `backend/app/services/__init__.py` — Modifier — Si le pattern du module l'exige (vérifier l'existant), exporter `RefreshTokenService` selon les conventions.
**Exigences sécurité :** Isolation par hash (un token ne résout que son user) ; borne de longueur anti-DoS avant hash ; révocation défensive de la famille sur réutilisation ; logs sans valeur de token (user_id + ids de lignes seulement).
**Dépend de :** Tâche 1 (émission opaque), STORY-123.1 (modèle + setting)

### Tâche 3 : Tests unitaires du service et de l'émission opaque
**Objectif :** Couvrir le cycle de vie complet au niveau service (création/verify/rotate/révocations/purge) et l'opacité du refresh émis.
**Fichiers :**
- `backend/tests/unit/test_services/test_refresh_token_service.py` — Créer — Fixtures `db_session`, `test_user`. Détail en section « Tests à écrire ».
**Exigences sécurité :** Les tests de rotation/réutilisation/révocation défensive **sont** les tests sécurité de cette couche (rules 40).
**Dépend de :** Tâche 2

## Tests à écrire

### Backend — unitaires (service)
- `backend/tests/unit/test_services/test_refresh_token_service.py`
  - `test_create_stores_hash_not_plaintext` — la ligne contient le hash, jamais la valeur claire (AC 4, part hash)
  - `test_verify_resolves_by_hash_only` — token valide → ligne + user attendus
  - `test_verify_rejects_unknown_token` — token inconnu → refus (401 sémantique)
  - `test_verify_rejects_expired` — ligne expirée → refus
  - `test_verify_rejects_oversized_token` — token > 512 caractères → refus avant hash (anti-DoS)
  - `test_rotate_returns_new_token_and_revokes_old` — rotation : ancien `revoked_at` non nul, nouvelle ligne active (AC 2, part mécanique)
  - `test_rotate_reused_revoked_token_revokes_family` — réutilisation d'un consommé → refus **et** tous les tokens de l'utilisateur révoqués
  - `test_revoke_is_idempotent` — double révocation sans erreur
  - `test_revoke_all_for_user_revokes_every_token` — révocation globale (prérequis STORY-129)
  - `test_purge_expired_removes_expired_and_revoked` — purge des expirées (+ révoquées selon rétention)

### Backend — unitaires (jwt)
- `backend/tests/unit/test_auth/test_jwt_claims.py` (adaptation)
  - le refresh émis n'est pas décodable comme JWT ; l'access conserve claims/durée 15 min

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_services/test_refresh_token_service.py backend/tests/unit/test_auth/test_jwt_claims.py -v
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : `jwt.py` — émission opaque (`generate_refresh_token`, `create_token_pair` adapté, retrait `decode_refresh_token`)
- [x] Tâche 2 : `RefreshTokenService` (create/verify/rotate + famille/révocations/purge)
- [x] Tâche 3 : Tests service + adaptation `test_jwt_claims.py`

## Notes d'implémentation

**Date :** 2026-09-13

### Réconciliation (run interrompu)

Un run précédent avait déjà posé la Tâche 1 (`jwt.py` opaque) et l'essentiel
de la Tâche 2 (service). Inventaire à la reprise :

- **Conforme, conservé** : `generate_refresh_token()` (CSPRNG 512 bits,
  préfixe `wf_rt_`), `create_token_pair()` retournant la valeur claire avec
  docstring d'obligation de persistance, shim déprécié
  `decode_refresh_token()` (consommateur legacy unique :
  `POST /auth/refresh`, réécrit par 123.3), service complet
  create/verify/rotate/revoke/revoke_all/purge, export
  `services/__init__.py`.
- **Corrigé (non-conformité rules 30)** : `InvalidRefreshTokenError`
  héritait de `Exception` brute → déplacée dans
  `core/exceptions.py` héritant de `WindFlowException` (ré-exportée par le
  service pour les appelants 123.3).
- **Corrigé (mypy)** : `result.rowcount` sur `Result[Any]` → `cast(CursorResult, ...)`
  sur les 3 UPDATE/DELETE bulk.
- **Complété (Tâche 3)** : réécriture de `test_jwt_claims.py` (l'ImportError
  `create_refresh_token` cassait la collection du fichier ET bloquait la
  suite unitaire complète — confirmé résolu : 1414 tests passent) et création
  de `test_refresh_token_service.py`.

### Arbitrage n°1 (hash) — application

Conformément à la décision STORY-123.1 : hash **Argon2** via le `pwd_context`
passlib existant (zéro dépendance nouvelle). Contrainte technique du lookup
par hash : le sel Argon2 est **dérivé du token** (HMAC-SHA256 de
`jwt_secret_key` sur le token, tronqué à 16 octets) pour garantir un hash
**déterministe** (requis par `WHERE token_hash = :h`) tout en dépendant du
secret serveur — une fuite isolée de la base ne permet pas de forger des
hashes valides pour un autre déploiement.

### Divergences par rapport à l'analyse

- **Tâche 1, « supprimer/reléguer `decode_refresh_token` »** : choix du shim
  déprécié (DeprecationWarning + rejet des tokens opaques) plutôt que
  suppression pure — l'unique consommateur légitime (`auth.py:417`) doit
  rester fonctionnel jusqu'à la réécriture de 123.3, sinon `POST /auth/refresh`
  lèverait une ImportError en production entre 123.2 et 123.3. Le retrait
  complet est explicitement porté par 123.3.
- **Tâche 2, `InvalidRefreshTokenError`** : définie dans
  `core/exceptions.py` (rules 30 : exceptions héritant de `WindFlowException`,
  jamais d'exception brute dans les services) plutôt que dans le fichier du
  service — ré-exportée par commodité.

### Tests ajoutés

- `backend/tests/unit/test_services/test_refresh_token_service.py` :
  17 tests (les 10 prescrits + 7 compléments : durée depuis settings, refus
  token vide ×2, expired rotate sans effet de bord, revoke unknown → False,
  revoke_all idempotent, purge table vide, conformité WindFlowException).
  Couverture service : **98%**.
- `backend/tests/unit/test_auth/test_jwt_claims.py` : réécrit — 14 tests
  (claims access 121.3 préservés, opacité structurelle du refresh : pas de
  segments JWT/entropie ≥512 bits/préfixe/unicité, paire access-JWT +
  refresh-opaque, shim déprécié : warning émis + opaque rejeté + legacy JWT
  décodable pendant la migration). Couverture `jwt.py` : **92%**.

### Difficultés rencontrées

- **Blocage full-suite (rapporté au lancement)** : l'ImportError
  `create_refresh_token` dans `test_jwt_claims.py` corrompait la session de
  tests pytest et laissait la suite pendre indéfiniment. Résolu par la
  réécriture du fichier — `backend/tests/unit/` passe intégralement
  (1414 passed, ~47s, `--timeout=120` en garde-fou).
- **`MissingGreenlet` dans les tests service** : `revoke_all_for_user`
  expire volontairement les objets en session (bulk UPDATE) — l'accès
  paresseux d'attribut après coup déclenche de l'IO synchrone interdite.
  Contournement test : capture des ids avant la révocation bulk.
- **Flaky teardown WebSocket** (`test_ws_auth.py`, teardown `TestClient`
  qui pend occasionnellement) : démontré préexistant et indépendant de la
  story (test passant isolément, erreur reproductible sans les changements).
  Hors périmètre — à traiter séparément si récurrent.

### Fichiers modifiés/créés

- `backend/app/auth/jwt.py` — modifié (émission opaque, shim déprécié ; run
  interrompu, reformaté black)
- `backend/app/core/exceptions.py` — modifié (`InvalidRefreshTokenError`)
- `backend/app/services/refresh_token_service.py` — modifié (import
  `core.exceptions`, `cast(CursorResult)` mypy, format)
- `backend/app/services/__init__.py` — export `RefreshTokenService` (run
  interrompu, vérifié)
- `backend/tests/unit/test_auth/test_jwt_claims.py` — réécrit
- `backend/tests/unit/test_services/test_refresh_token_service.py` — créé

### Validation

- `pytest tests/unit/test_services/test_refresh_token_service.py
  tests/unit/test_auth/test_jwt_claims.py` → **34 passed**
- `pytest tests/unit/ --timeout=120` → **1414 passed** (0 failed)
- Couverture nouveaux fichiers : service 98%, jwt 92% (≥ 80% DoD)
- `black` + `isort` + `flake8` : OK sur les fichiers de la story
- `mypy` : 0 erreur sur les fichiers de la story (5 erreurs préexistantes
  hors périmètre : stubs yaml/jose, docker_client_service)
- `bandit -ll` : rien à signaler
- Commandes lancées avec le venv `.venv-test` (divergence documentée :
  venv Poetry racine incomplet)
