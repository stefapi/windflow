# STORY-123 : Refresh tokens révocables — table, rotation et logout invalidant (P1-3, partie refresh)

**Statut :** TODO
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-3 partie refresh (axes A4 + B6, rapport §2) — ampleur **M** (partie refresh de l'item L)

## Description

En tant qu'utilisateur de WindFlow, je veux que mes refresh tokens soient des chaînes opaques stockées hashées en base, révocables (rotation à chaque usage, invalidation au logout, révocation globale par utilisateur), afin qu'une fuite de token puisse être neutralisée côté serveur et que la déconnexion ait un effet réel.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §2, §7.6, §14) : le refresh token est un **JWT de 7 jours** sans table dédiée ni blacklist ; [`POST /auth/logout`](../../backend/app/api/v1/auth.py:391) est **stateless** — « le client supprime les tokens, pas de blacklist serveur » — si bien que logout et révocation sont impossibles. La spec exige un token **opaque** (pas un JWT) dont le hash est stocké en `refresh_tokens`, dont la déconnexion « invalide le refresh token en base ».

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- Schéma cible spec 06 : `refresh_tokens (id, user_id FK CASCADE, token_hash VARCHAR(255), expires_at, created_at)` + index `user_id` et `expires_at` ;
- [`jwt.py`](../../backend/app/auth/jwt.py:16) : `create_token_pair()` / `decode_access_token()` / `decode_refresh_token()` — le refresh devient opaque, l'access reste JWT 15 min (durée code actuelle, plus sûre que la spec — arbitrage F5 : spec corrigée en P3) ;
- [`auth.py`](../../backend/app/api/v1/auth.py:27) : `/login` (doit créer la ligne en base, hash stocké), `/refresh` (retrouve l'entrée par **comparaison de hash**, vérifie utilisateur actif + expiration, émet un nouvel access, **rotation** : l'ancien refresh est invalidé et un nouveau peut être émis), `/logout` (devient révocant) ;
- Rotation et réutilisation : un refresh token déjà consommé/révoqué doit être refusé (`401` `INVALID_OR_EXPIRED_TOKEN`) ; en cas de tentative de réutilisation d'un token révoqué, révocation défensive de la famille (tous les tokens de l'utilisateur) recommandée ;
- Hashage : bcrypt (jamais la valeur en clair en base) ;
- Nettoyage : purge des entrées expirées (peut s'appuyer sur la tâche de cleanup existante ou un job asyncio simple — STORY-130 purge Celery) ;
- STORY-129 (`PUT /auth/password`) dépend de la révocation globale (« révoquer tous les refresh tokens de l'utilisateur ») exposée ici.

## Critères d'acceptation (AC)

- [ ] AC 1 : La table `refresh_tokens` existe via migration Alembic (STORY-120) conformément au schéma spec 06 ; le refresh token émis au login est **opaque** (pas un JWT), seul son **hash** est stocké en base ; durée 7 jours configurable (`REFRESH_TOKEN_EXPIRE_DAYS`).
- [ ] AC 2 : **Rotation** : `POST /auth/refresh` accepte le refresh courant une seule fois et en émet un nouveau (l'ancien invalidé) ; un refresh révoqué/expiré/consommé → `401` ; cohérence conservée avec les vérifications actuelles (utilisateur actif).
- [ ] AC 3 : **Logout révocant** : `POST /auth/logout` invalide le refresh token en base ; le refresh suivant avec ce token → `401` ; **révocation globale** disponible par utilisateur (utilisée par STORY-129) ; purge des entrées expirées effective.
- [ ] AC 4 : Tests de sécurité : `401` sur refresh avec token inconnu/invalide/révoqué ; non-régression login/refresh/logout (codes et bodies actuels hors enveloppe — STORY-126 gère le format) ; hash bcrypt en base vérifié (jamais la valeur brute) ; `make lint` + `make backend-test` verts.

## Références spécification

- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Refresh token (opaque, hash en base, flow refresh, « la déconnexion invalide le refresh token en base »), § Validation des tokens, § Configuration (`REFRESH_TOKEN_EXPIRE_DAYS`) ;
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités auth et audit → `RefreshToken` (schéma SQL) ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Authentification (`/auth/refresh`, `/auth/logout`), § Gestion des erreurs (`INVALID_OR_EXPIRED_TOKEN`) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §2 (logout stateless ligne 116, refresh JWT 7 j lignes 493-494), §7.6 (Sessions/logout), §14 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-3 (partie refresh), §2.A A4, §2.B B6.

## Dépendances

- **STORY-120** (migration de la table `refresh_tokens`).
- Est un prérequis de : STORY-129 (révocation des refresh au changement de mot de passe).

## Sous-stories

*(section réservée — ampleur M, découpe non prévue a priori)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
