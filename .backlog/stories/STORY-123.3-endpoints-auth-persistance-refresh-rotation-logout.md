# STORY-123.3 : Endpoints auth — émission persistée, `/refresh` rotatif, `/logout` révocant

**Statut :** DONE
**Story Parente :** STORY-123 — Refresh tokens révocables — table, rotation et logout invalidant (P1-3, partie refresh)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'utilisateur de WindFlow, je veux que mes actions d'authentification interagissent réellement avec les refresh tokens persistés : le login/register émet un token opaque dont le hash est stocké, le refresh **tourne** le token (usage unique + émission d'un nouveau), et le logout **révoque** — afin que la déconnexion ait un effet serveur réel et qu'un token volé soit neutralisable.

Cette sous-story applique le socle posé par STORY-123.1 (modèle/config) et STORY-123.2 (service + émission opaque) aux 4 endpoints de [`auth.py`](../../backend/app/api/v1/auth.py) : `/login`, `/register` (persistance), `/refresh` (rotation + révocation défensive), `/logout` (révocation). Les formes des réponses (`LoginResponse`/`RefreshResponse` : `{refresh_token: string}`) restent **inchangées** — STORY-126 gère le format des enveloppes.

## Critères d'acceptation (AC)

- [x] AC 3 : **Logout révocant** : `POST /auth/logout` invalide le refresh token en base ; le refresh suivant avec ce token → `401` ; **révocation globale** disponible par utilisateur (utilisée par STORY-129) ; purge des entrées expirées effective.

> **Note de découpe :** cette sous-story couvre la part **endpoints** de l'AC 3 (logout révocant + révocation globale disponible — `revoke_all_for_user` exposé par 123.2). La part « purge des entrées expirées effective » (job lifespan) est portée par STORY-123.4 — l'AC n'est cochable sur la story parente qu'après fermeture de 123.3 **et** 123.4. L'AC 2 (rotation HTTP) est démontré ici de bout en bout (démonstration portée conjointement avec 123.2 qui porte la mécanique).

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-12) — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches.

**Couches impactées :** Backend uniquement — router auth (4 endpoints), tests d'endpoints. Contrats de réponse inchangés (consommateurs frontend/CLI transparents — la découpe de STORY-123 a acté « backend seul »).

**Spécifications de référence :**
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Refresh token (flow refresh, « la déconnexion invalide le refresh token en base »), § Endpoints auth ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Authentification (`/auth/refresh`, `/auth/logout`), § Gestion des erreurs (`INVALID_OR_EXPIRED_TOKEN`).

**Fichiers de référence (patterns vérifiés) :**
- [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py) — `/login` (~l. 56), `/refresh` (~l. 288, décode le refresh JWT actuel), `/logout` (~l. 391/466, stateless aujourd'hui), `/register` (~l. 548) ;
- Service à consommer → `backend/app/services/refresh_token_service.py` (posé par STORY-123.2 : `create`/`rotate`/`revoke`/`revoke_all_for_user`) ;
- Émission → `backend/app/auth/jwt.py` `create_token_pair()` (adapté par 123.2 : refresh opaque, persistance à la charge de l'appelant) ;
- Mode dev sans auth → `settings.disable_auth` / auto-login ([`backend/tests/unit/test_auth/test_dev_mode.py`](../../backend/tests/unit/test_auth/test_dev_mode.py)) — cf. arbitrage n°3 ;
- Liste blanche routes publiques → [`backend/tests/unit/test_api/test_rbac_exhaustivite.py`](../../backend/tests/unit/test_api/test_rbac_exhaustivite.py) (login/refresh/logout/register déjà blanchies — **aucun changement de garde attendu** ; `/logout` porte `get_current_active_user` s'il est actuellement protégé, sinon le laisser public best-effort comme acté par STORY-122.7) ;
- Fixtures : `db_session`, `test_user`, `authenticated_client`, `client` ([`backend/tests/conftest.py`](../../backend/tests/conftest.py)).

**Décisions d'analyse :**
- **Contrats inchangés :** `/login`, `/register`, `/refresh` retournent les mêmes formes (`{access_token, refresh_token, token_type, ...}`) — le refresh vaut désormais une chaîne opaque plus longue, c'est le seul delta consommateur (transparent : champ string) ;
- **`/refresh` :** reçoit `{refresh_token}` (body actuel), appelle `RefreshTokenService.rotate()` → refus `401 INVALID_OR_EXPIRED_TOKEN` si inconnu/expiré/consommé (la révocation défensive de la famille est déclenchée par le service, 123.2) ; vérification **utilisateur actif** conservée (AC 2 : « cohérence conservée avec les vérifications actuelles ») ;
- **`/logout` :** cf. arbitrage n°2 ci-dessous ;
- **Auto-login dev :** cf. arbitrage n°3 ci-dessous ;
- **Rate limiting :** `/login` et `/refresh` restent sur les limiters existants (aucun changement de périmètre).

## ⚠️ Points d'arbitrage à traiter dans cette sous-story

**Arbitrage n°2 — `/logout` ne reçoit pas le refresh token (frontend appelle sans body) :**
- **Constat :** le frontend appelle `/logout` sans body → le serveur ne connaît pas le token à révoquer ;
- **Option A (recommandée par l'analyse) :** `/logout` (authentifié par `get_current_active_user`) applique `revoke_all_for_user(current_user.id)` — **révocation globale** : conforme à l'AC 3 (« révocation globale disponible par utilisateur »), zéro impact frontend, sémantique « je me déconnecte de partout » acceptable pour un logout sans body ;
- **Option B :** étendre le body de `/logout` avec `refresh_token` optionnel → révocation ciblée si fournie, globale sinon — mais impact frontend (appel à modifier) hors périmètre « backend seul » de STORY-123 ;
- **Impact :** consigner le choix dans les Notes d'implémentation ; si Option B partielle (body optionnel), documenter la non-régression (appel sans body continue de fonctionner).

**Arbitrage n°3 — Mode dev `disable_auth` :**
- L'auto-login du mode dev (superadmin implicite) doit **aussi persister la ligne `refresh_tokens`** pour ne pas casser le flux refresh/logout en dev — couvrir par un test dédié ([`test_dev_mode.py`](../../backend/tests/unit/test_auth/test_dev_mode.py)).

**Exigences sécurité identifiées (Phase 2.6 de l'analyse) :**
- **Auth :** `/login` et `/refresh` sans auth (rate-limited existants) ; `/logout` avec `get_current_active_user` (en place — sinon le laisser public best-effort conformément à la liste blanche STORY-122.7) ;
- **Isolation :** le lookup par hash (service 123.2) garantit qu'un refresh ne résout que son user ; `/logout` ne révoque que les tokens de l'utilisateur authentifié (`current_user.id`, jamais un id client fourni) ;
- **Validation :** `refresh_token` non vide, longueur max bornée (validation Pydantic côté schéma de requête — cohérente avec la borne du service 123.2) ;
- **Exposition :** formes `LoginResponse`/`RefreshResponse` inchangées (STORY-126 = format) ; **jamais de token en clair dans les logs** (log info sans valeur de token) ;
- **Audit :** log info à la révocation/logout (user_id, pas de token) ; audit formel reporté à STORY-125.

## Dépendances

- STORY-123.2 (service + émission opaque) — **prérequis** (elle-même dépend de 123.1).
- Bloque : STORY-123.4 (tests transverses sur les endpoints finaux).
- STORY-129 (`PUT /auth/password`) consommera `revoke_all_for_user` — aucune action ici, s'assurer seulement que la méthode reste exposée.

## Périmètre indicatif (répartition des tâches identifiées par l'analyse de STORY-123)

| # | Tâche (issue de l'analyse STORY-123) | Périmètre de cette sous-story |
|---|--------------------------------------|-------------------------------|
| T5 | `/login` + `/register` persistance | ✅ Complet |
| T6 | `/refresh` rotation + révocation famille | ✅ Complet |
| T7 | `/logout` révocant | ✅ Complet |
| T1-T4 | Modèle/migration/config (123.1), service/jwt (123.2) | ❌ Prérequis |
| T8 | Job de purge lifespan | ❌ STORY-123.4 |
| T9 | Tests endpoints → ici ; transverses/purge → 123.4 | 🔶 Partie endpoints |

**Hors périmètre :** enveloppes de réponse (STORY-126) ; audit formel (STORY-125) ; `PUT /auth/password` et sa révocation (STORY-129) ; job de purge (123.4).

## Tâches d'implémentation détaillées

### Tâche 1 : `/login` et `/register` persistent le refresh token
**Objectif :** Toute émission d'un token pair au login (username/email — non-régression) et au register (avec auto-login le cas échéant) crée la ligne `refresh_tokens` via le service.
**Fichiers :**
- `backend/app/api/v1/auth.py` — Modifier — Dans `/login` : après validation des credentials, `token_pair = create_token_pair(...)` puis `await RefreshTokenService.create(db, user.id, token_pair.refresh_token)` avant de répondre (forme de réponse inchangée). Dans `/register` : idem sur le flux qui émet des tokens (auto-login register le cas échéant). Dans l'**auto-login du mode dev** (`disable_auth`) : idem — persister la ligne (arbitrage n°3).
**Exigences sécurité :** Ne jamais logger la valeur claire du token émis ; login username ET email non régressés (garde-fou epic §2.G).
**Dépend de :** STORY-123.2 (Tâches 1-2)

### Tâche 2 : `/refresh` rotatif avec révocation défensive
**Objectif :** Remplacer le décodage JWT du refresh par la rotation via service : usage unique, nouveau token émis, refus 401 sur consommé/révoqué/inconnu/expiré, utilisateur actif vérifié.
**Fichiers :**
- `backend/app/api/v1/auth.py` — Modifier — `/refresh` : valider le body (`refresh_token` non vide, longueur bornée — schéma de requête) ; `line, new_plain = await RefreshTokenService.rotate(db, body.refresh_token)` ; sur refus → `401` code `INVALID_OR_EXPIRED_TOKEN` (spec 09) avec révocation défensive déjà appliquée par le service ; vérifier **utilisateur actif** (charger le user de la ligne — inactif → 401) ; émettre l'access JWT (15 min) + retourner le nouveau refresh (forme `RefreshResponse` inchangée).
**Exigences sécurité :** 401 générique sans révéler si le token a existé (message `INVALID_OR_EXPIRED_TOKEN`) ; jamais de token dans les logs.
**Dépend de :** Tâche 1 (aucune — mais même fichier ; STORY-123.2 requis)

### Tâche 3 : `/logout` révocant
**Objectif :** Rendre le logout stateful : invalider le(s) refresh token(s) en base selon l'arbitrage n°2.
**Fichiers :**
- `backend/app/api/v1/auth.py` — Modifier — `/logout` : appliquer l'**Option A** de l'arbitrage n°2 par défaut : `await RefreshTokenService.revoke_all_for_user(db, current_user.id)` (si `/logout` est public best-effort, résoudre l'utilisateur via l'access token si présent, sinon 200 sans action — conserver le code 200 actuel, non-régression). Log info (user_id, nombre de tokens révoqués, pas de token). Si l'Option B est retenue lors de l'implémentation : body optionnel `{refresh_token?}` → `revoke()` ciblé sinon `revoke_all_for_user()` — documenter la décision.
**Exigences sécurité :** Ne révoquer que les tokens de l'utilisateur authentifié ; idempotence (logout double = 200).
**Dépend de :** Tâche 2 (même fichier ; service 123.2 requis)

### Tâche 4 : Tests d'endpoints (login/refresh/logout/register)
**Objectif :** Couvrir les 4 endpoints modifiés : persistance au login, rotation HTTP complète, logout révocant, non-régression des contrats et du mode dev.
**Fichiers :**
- `backend/tests/unit/test_api/test_auth_refresh_rotation.py` — Créer — Détail en section « Tests à écrire ».
- `backend/tests/unit/test_auth/test_dev_mode.py` — Modifier — Ajouter le cas auto-login → ligne `refresh_tokens` persistée (arbitrage n°3).
**Exigences sécurité :** Les tests 401 (token inconnu/expiré/consommé) sont les tests sécurité obligatoires de cette couche (rules 40).
**Dépend de :** Tâches 1-3

## Tests à écrire

### Backend — unitaires (endpoints)
- `backend/tests/unit/test_api/test_auth_refresh_rotation.py`
  - `test_login_persists_refresh_token_hash` — après `/login` : une ligne `refresh_tokens` existe, contient le **hash** (pas la valeur claire) (AC 1 démo)
  - `test_login_response_contract_unchanged` — forme `LoginResponse` inchangée, refresh = string opaque (AC 4, part non-régression)
  - `test_register_persists_refresh_token` — idem au `/register` (si émission de tokens)
  - `test_refresh_rotates_token` — refresh → nouveau couple émis ; **l'ancien** refresh re-soumis → 401 `INVALID_OR_EXPIRED_TOKEN` (AC 2 démo HTTP)
  - `test_refresh_unknown_token_returns_401` — token inconnu → 401
  - `test_refresh_expired_token_returns_401` — ligne expirée → 401
  - `test_refresh_reuse_revokes_family` — rotation puis réutilisation de l'ancien → 401 **et** tokens de l'utilisateur tous révoqués (nouveau inclus) — révocation défensive
  - `test_refresh_inactive_user_returns_401` — utilisateur désactivé → 401 (cohérence vérifications actuelles)
  - `test_refresh_empty_or_oversized_body_returns_422` — body invalide → 422 (validation Pydantic)
  - `test_logout_revokes_refresh_tokens` — login → logout → refresh avec le token → 401 (AC 3 démo)
  - `test_logout_idempotent_returns_200` — double logout → 200
  - `test_logout_does_not_revoke_other_users` — logout de A n'invalide pas les tokens de B (isolation)
- `backend/tests/unit/test_auth/test_dev_mode.py`
  - auto-login dev → ligne persistée ; flux refresh fonctionne en `disable_auth`

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_api/test_auth_refresh_rotation.py backend/tests/unit/test_auth/test_dev_mode.py -v
poetry run pytest backend/tests/unit/test_api/test_rbac_exhaustivite.py -v   # liste blanche inchangée
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : `/login` + `/register` + auto-login dev persistent la ligne hashée
- [x] Tâche 2 : `/refresh` rotatif (401 consommé/révoqué/inconnu/expiré, user actif)
- [x] Tâche 3 : `/logout` révocant (arbitrage n°2 appliqué)
- [x] Tâche 4 : Tests endpoints + dev mode

## Notes d'implémentation

**Date :** 2026-09-13

### Arbitrage n°2 (/logout) — décision : Option A

Logout **révocant global** : `revoke_all_for_user(current_user.id)` sur
l'utilisateur résolu par `get_current_active_user` (jamais un id client).
L'access token du user est requis (garde en place), le code 200 est
conservé (non-régression `test_logout_200`), l'idempotence est assurée
(un second logout révoque 0 token). Sémantique « déconnexion de
partout » — conforme à l'AC 3, zéro impact frontend (appel sans body).

### Arbitrage n°3 (disable_auth) — application

La persistance est posée dans le **bloc commun** de `/login` (après
`create_token_pair`) : elle couvre donc ipso facto l'auto-login dev
(username/password vides → superadmin). Couvert par
`test_dev_auto_login_persists_refresh_token` (voir divergence n°2).

### Divergences par rapport à l'analyse

1. **`/refresh` : comparaison username/is_superuser supprimée.** Le
   refresh opaque ne porte plus de claims (123.2) — la vérification
   « données du token ↔ user » n'a plus de sens ; remplacée par la
   vérification **utilisateur actif** (conservée, AC 2) + révocation
   défensive du token fraîchement émis si le compte est inactif.
2. **Test dev mode par appel direct du handler.** FastAPI 0.141.1
   filtre les champs form **vides** comme manquants (422, vérifié sur
   app minimale — comportement framework préexistant) : le chemin
   auto-login n'est pas atteignable par HTTP de test. Le test
   construit un `OAuth2PasswordRequestForm` vide et appelle
   `login()` directement ; la partie refresh reste via HTTP (200 réel).
3. **Message 401 `/refresh` unifié.** Les trois messages distincts
   (`Invalid refresh token`, `User not found or inactive`, `Token data
   mismatch`) sont remplacés par le générique spec 09
   `INVALID_OR_EXPIRED_TOKEN` (anti-oracle, exigence sécurité de la
   story : « 401 générique sans révéler si le token a existé ») ;
   OpenAPI documenté en conséquence.

### Décisions techniques

- **Access token émis via `create_access_token()` seul** dans
  `/refresh` (le refresh neuf vient de `rotate()` — éviter
  `create_token_pair` qui générerait un 2e token orphelin) ;
- **Défense utilisateur inactif** : `revoke_all_for_user` sur la ligne
  fraîchement rotée avant le 401 (aucune ligne active ne survit à un
  compte désactivé) ;
- **`RefreshTokenRequest` borné** (`min_length=1`, `max_length=512`,
  cohérent avec `MAX_TOKEN_LENGTH` du service) → 422 avant tout hash
  Argon2 (anti-DoS) ;
- **Retrait complet du shim `decode_refresh_token()`** (prévu par cette
  story) : `jwt.py` ne contient plus que l'émission/validation access +
  refresh opaque ; les 3 tests du shim retirés de `test_jwt_claims.py`.

### Tests ajoutés

- `backend/tests/unit/test_api/test_auth_refresh_rotation.py` :
  12 tests (les 12 prescrits : persistance login/register + contrat,
  rotation + rejeu 401, inconnu/expiré/inactif/422, logout révocant/
  idempotent/isolation inter-utilisateurs). Tous passent.
- `backend/tests/unit/test_auth/test_dev_mode.py` : +1 test
  auto-login dev (persistance hash + flux refresh 200 en disable_auth).
- `backend/tests/unit/test_auth/test_jwt_claims.py` : -3 tests du shim
  déprécié (fonction retirée), 11 restants passent.

### Validation

- `pytest tests/unit/test_api/test_auth_refresh_rotation.py
  tests/unit/test_auth/test_dev_mode.py` → **17 passed**
- Non-régression ciblée (RBAC exhaustivité, jwt_claims, isolation,
  matrice consolidée, service, intégration auth_api) → **102 passed**
- `pytest tests/unit/ --timeout=120` → **1424 passed, 0 failed**
  (1 *error* teardown flaky préexistant `test_ws_auth.py` — documenté
  123.2, passe isolément ; hors périmètre)
- Couverture (limite préexistante : le tracing ne suit pas les handlers
  ASGI dans ce setup — vérifié sur `users.py` non modifié, même
  comportement) : `jwt.py` **93%**, `refresh_token_service.py` **98%** ;
  les lignes endpoints de `auth.py` exécutées par les tests passants
  apparaissent « missing » (artefact), couverture réelle des chemins
  modifiés démontrée par les 17 tests dédiés verts.
- `black` + `isort` : appliqués (2 fichiers reformatés) puis tests
  re-passés (29 passed) ; `flake8` : 0 erreur ; `bandit -ll` : rien à
  signaler ; `mypy` : 0 erreur nouvelle (seule l'absence de stub
  `jose` préexistante, documentée 123.2).
- Venv `.venv-test` (divergence documentée 123.2 : venv Poetry racine
  incomplet).

### Fichiers modifiés/créés

- `backend/app/api/v1/auth.py` — modifié (T1-T3 : persistance
  login/register, `/refresh` rotatif, `/logout` révocant, doc OpenAPI)
- `backend/app/schemas/user.py` — modifié (`RefreshTokenRequest` borné)
- `backend/app/auth/jwt.py` — modifié (retrait shim
  `decode_refresh_token`)
- `backend/tests/unit/test_api/test_auth_refresh_rotation.py` — créé
- `backend/tests/unit/test_auth/test_dev_mode.py` — modifié (+1 test)
- `backend/tests/unit/test_auth/test_jwt_claims.py` — modifié (-3 tests
  shim)
