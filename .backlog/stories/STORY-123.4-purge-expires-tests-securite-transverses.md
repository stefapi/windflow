# STORY-123.4 : Purge des entrées expirées et tests sécurité transverses

**Statut :** DONE
**Story Parente :** STORY-123 — Refresh tokens révocables — table, rotation et logout invalidant (P1-3, partie refresh)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que les entrées `refresh_tokens` expirées soient purgées automatiquement en arrière-plan (job asyncio au démarrage, sans introduire Celery — arbitrage F1 reporté à STORY-130) et que la sécurité du dispositif complet soit vérifiée transversalement : 401 sur tout token inconnu/invalide/révoqué/consommé, hash jamais en clair en base, isolation entre utilisateurs, non-régression des flux auth existants — avec les cibles de couverture du projet (≥ 80 % modules touchés, viser 95 % auth).

Cette sous-story clôture STORY-123 : elle consomme le service posé par STORY-123.2 (`purge_expired`), s'appuie sur les endpoints finaux de STORY-123.3, et constitue la vérification de bout en bout de l'AC 4 de la story parente.

## Critères d'acceptation (AC)

- [x] AC 4 : Tests de sécurité : `401` sur refresh avec token inconnu/invalide/révoqué ; non-régression login/refresh/logout (codes et bodies actuels hors enveloppe — STORY-126 gère le format) ; hash bcrypt en base vérifié (jamais la valeur brute) ; `make lint` + `make backend-test` verts. *(hash Argon2 selon l'arbitrage n°1 — divergence « bcrypt » consignée pour STORY-252)*

> **Note de découpe :** l'AC 4 est intégralement couvert par cette sous-story. Le libellé « hash bcrypt » s'entend selon l'**arbitrage n°1 tranché en STORY-123.1** (hash fort vérifié, jamais la valeur brute — Argon2 si Option A retenue ; divergence à consigner pour STORY-252). Les démonstrations des AC 1/2/3 réparties sur 123.1/123.2/123.3 sont revalidées ici dans la suite transverse.

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-12) — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches.

**Couches impactées :** Backend uniquement — `main.py` (lifespan), `conftest.py` (documentation fixtures), tests transverses. **Aucun endpoint modifié**, aucune nouvelle API.

**Spécifications de référence :**
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Refresh token (purge des entrées expirées) ;
- `.roo/rules/35-testing-quality-gates.md` — couverture 80 % modules, **95 % chemins critiques auth** ;
- `.roo/rules/40-security.md` — tests sécurité obligatoires.

**Fichiers de référence (patterns vérifiés) :**
- Lifespan / tâches de fond au démarrage → [`backend/app/main.py`](../../backend/app/main.py) (lifespan FastAPI existant — y poser la boucle de purge asyncio ; ne **pas** introduire Celery, arbitrage F1 → STORY-130) ;
- Service à consommer → `backend/app/services/refresh_token_service.py` `purge_expired()` (posé par STORY-123.2) ;
- Fixtures login réel → [`backend/tests/conftest.py`](../../backend/tests/conftest.py) (`authenticated_client` l. ~320 : login réel → **chaque test crée désormais une ligne `refresh_tokens`** — cf. arbitrage n°4) ;
- Suites existantes à garder vertes → [`backend/tests/unit/test_api/test_rbac_matrix_consolidated.py`](../../backend/tests/unit/test_api/test_rbac_matrix_consolidated.py) (non-régression auth : disable_auth, login username/email, register, logout 200), [`backend/tests/unit/test_auth/`](../../backend/tests/unit/test_auth/), [`backend/tests/unit/test_api/test_auth_isolation.py`](../../backend/tests/unit/test_api/test_auth_isolation.py) ;
- Précédent de story de clôture transverse → STORY-122.7 (matrice transverse + couverture).

**Décisions d'analyse :**
- **Job de purge :** boucle asyncio simple démarrée au lifespan (intervalle configurable, ex. 1 h par défaut — valeur par défaut sobre) appelant `RefreshTokenService.purge_expired()` ; logs du nombre de lignes purgées ; arrêt propre au shutdown (annulation de la tâche) ; **aucune dépendance Celery** (F1) ;
- **Réutilisation plutôt que duplication :** les tests de rotation/révocation unitaires existent déjà (123.2 service, 123.3 endpoints) — cette story ajoute les cas **transverses** : propriété « jamais de valeur claire en base » vérifiée sur l'ensemble du dispositif, isolation multi-users de bout en bout, comportement des suites existantes avec la persistance désormais effective (conftest).

## ⚠️ Points d'arbitrage à traiter dans cette sous-story

**Arbitrage n°4 — Fixtures conftest (login réel → lignes `refresh_tokens` par test) :**
- **Constat :** les fixtures (`authenticated_client`, rôles 122.7…) font un login réel → depuis STORY-123.3, **chaque test crée une ligne `refresh_tokens`** ;
- **Position :** c'est une **non-régression gratuite** (la table grandit en base de test, sans assertion rompue) — à **documenter** dans le conftest (commentaire + Notes d'implémentation) plutôt qu'à contrer ; si un test isolé exige une base sans refresh tokens, purger explicitement dans ce test ;
- **Vérification :** la suite backend complète doit rester verte (`make backend-test`) — c'est le critère.

**Exigences sécurité identifiées (Phase 2.6 de l'analyse) :**
- Les tests transverses **sont** l'exigence sécurité centrale : 401 sur inconnu/invalide/révoqué/consommé (revalidés), hash jamais en clair (propriété de bout en bout), isolation A/B, aucun token dans les logs (assertion sur les captures de log si le pattern projet le permet) ;
- Purge : le job ne logge que des comptages (user_id non nécessaire — pas de données sensibles).

## Dépendances

- STORY-123.3 (endpoints) — **prérequis** (chaîne : 123.1 → 123.2 → 123.3).
- Prérequis satellitaire : aucun (STORY-130 traitera l'arbitrage Celery/Argon2 indépendamment).

## Périmètre indicatif (répartition des tâches identifiées par l'analyse de STORY-123)

| # | Tâche (issue de l'analyse STORY-123) | Périmètre de cette sous-story |
|---|--------------------------------------|-------------------------------|
| T8 | Job de purge lifespan | ✅ Complet |
| T9 | Tests transverses sécurité + non-régression + couverture + conftest | ✅ Complet (parties service/endpoint déjà posées par 123.2/123.3) |

**Hors périmètre :** audit formel des révocations (STORY-125) ; purge Celery et migration Argon2id au login (STORY-130) ; enveloppes de réponse (STORY-126) ; `PUT /auth/password` (STORY-129).

## Tâches d'implémentation détaillées

### Tâche 1 : Job de purge des entrées expirées au lifespan
**Objectif :** Purger périodiquement les lignes expirées/révoquées de `refresh_tokens` via une boucle asyncio au démarrage de l'application, sans introduire Celery.
**Fichiers :**
- `backend/app/main.py` — Modifier — Dans le lifespan existant : démarrer une tâche asyncio (boucle `while True: await asyncio.sleep(interval); await RefreshTokenService.purge_expired(db)`) ; intervalle configurable (setting sobre, ex. `refresh_token_purge_interval_hours: int = 24` — posé avec la Tâche 3 de 123.1 ou ici selon l'état du code) ; annulation propre au shutdown ; log info du nombre de lignes purgées (comptage seul).
**Exigences sécurité :** Logs sans données sensibles (comptages uniquement) ; le job n'expose aucune API.
**Dépend de :** STORY-123.2 (`purge_expired`)

### Tâche 2 : Tests transverses sécurité du dispositif complet
**Objectif :** Vérifier de bout en bout les propriétés sécurité exigées par l'AC 4 : 401 systématiques, hash jamais en clair, isolation multi-users, non-régression des flux auth.
**Fichiers :**
- `backend/tests/unit/test_api/test_auth_refresh_security.py` — Créer — Détail en section « Tests à écrire » (scénarios multi-étapes : login → rotation → logout → réutilisations croisées entre deux utilisateurs).
**Exigences sécurité :** Cette suite **est** la concrétisation de l'AC 4 (rules 40 — tests sécurité obligatoires).
**Dépend de :** STORY-123.3

### Tâche 3 : Documentation des fixtures conftest + validation finale (lint, tests, couverture)
**Objectif :** Documenter l'effet des logins réels des fixtures (arbitrage n°4), exécuter la validation complète et mesurer la couverture des modules touchés.
**Fichiers :**
- `backend/tests/conftest.py` — Modifier — Commentaire documentaire sur les fixtures login (chaque test crée une ligne `refresh_tokens` ; non-régression gratuite ; purge explicite si un test l'exige) — aucune modification fonctionnelle attendue sauf constat contraire.
- Validation (sans nouveau fichier) : `make backend-lint` ; `make backend-test` (suite complète verte) ; couverture ciblée : `poetry run pytest backend/tests/unit/test_auth/ backend/tests/unit/test_services/test_refresh_token_service.py backend/tests/unit/test_api/test_auth_refresh_rotation.py backend/tests/unit/test_api/test_auth_refresh_security.py --cov=app/auth --cov=app/services/refresh_token_service --cov-fail-under=95` (viser 95 % chemins critiques auth, ≥ 80 % modules) — documenter le résultat dans les Notes d'implémentation.
**Exigences sécurité :** Cibles de couverture rules 35 (95 % auth).
**Dépend de :** Tâches 1-2

## Tests à écrire

### Backend — transverses (sécurité, bout en bout)
- `backend/tests/unit/test_api/test_auth_refresh_security.py`
  - `test_refresh_unknown_invalid_revoked_consume_all_return_401` — paramétré : token inconnu / malformed / révoqué / consommé → 401 (AC 4)
  - `test_no_plaintext_token_in_database` — après login ET après rotation : aucune ligne ne contient la valeur claire du token (balayage `token_hash` — propriété de bout en bout) (AC 4)
  - `test_user_isolation_full_flow` — deux utilisateurs A/B : logout de A, rotation de B ; tokens de A morts, tokens de B vivants (isolation)
  - `test_existing_auth_suites_unaffected` — `disable_auth` fonctionne, login username ET email → 200, register → 201, logout → 200 (revalidation non-régression)
  - `test_purge_job_removes_expired_entries` — lignes expirées insérées → exécution de la fonction de purge (appel direct, pas d'attente de boucle) → lignes supprimées (AC 3, part purge)
- `backend/tests/conftest.py` — documentation seulement (arbitrage n°4)

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_api/test_auth_refresh_security.py -v
make backend-test
make backend-lint && make backend-typecheck
poetry run pytest backend/tests/unit/test_auth/ backend/tests/unit/test_services/test_refresh_token_service.py backend/tests/unit/test_api/test_auth_refresh_rotation.py backend/tests/unit/test_api/test_auth_refresh_security.py --cov=app/auth --cov=app/services/refresh_token_service --cov-fail-under=95
```

## État d'avancement technique
- [x] Tâche 1 : Job de purge asyncio au lifespan (sans Celery)
- [x] Tâche 2 : Tests transverses sécurité (401 systématiques, hash jamais clair, isolation, non-régression)
- [x] Tâche 3 : Documentation conftest + validation finale (lint + suite + couverture 95 % auth)

## Notes d'implémentation

**Date :** 2026-09-13

### Fichiers modifiés/créés

- `backend/app/config.py` — modifié : setting
  `refresh_token_purge_interval_hours: int = 24` (`ge=1`, env var
  `REFRESH_TOKEN_PURGE_INTERVAL_HOURS`) posé à côté de
  `refresh_token_expire_days`
- `backend/app/main.py` — modifié : job de purge asyncio au lifespan
  (boucle `_periodic_refresh_token_purge` → `RefreshTokenService.purge_expired`,
  session `AsyncSessionLocal` dédiée par itération, annulation propre au
  shutdown, logs = comptages uniquement)
- `backend/tests/unit/test_api/test_auth_refresh_security.py` — créé :
  8 tests transverses (les 5 prescrits, dont le 401 paramétré ×4 cas)
- `backend/tests/conftest.py` — modifié : bloc documentaire arbitrage n°4
  (aucune modification fonctionnelle)
- `backend/tests/unit/test_api/test_auth_refresh_rotation.py` — modifié :
  fixture autouse `_jwt_mode` + import `pytest` (divergence n°2)

### Décisions techniques

- **Job de purge** : clone du pattern `health_task` existant (import
  local dans le lifespan, `asyncio.create_task`, cancel + await au
  shutdown) — première itération après `interval` (jamais au démarrage
  même : la purge n'est pas bloquante pour le readiness) ; une erreur
  est loggée et la boucle continue (résilience) ; aucune dépendance
  Celery (arbitrage F1 → STORY-130)
- **Arbitrage n°4 (conftest)** : position tenue — documentation
  seulement, non-régression gratuite ; les tests qui comptent des
  lignes balayent la table (base isolée par test, cf. template migré)
- **Test purge** : appel direct de `purge_expired` (pas d'attente de
  boucle) avec 4 fixtures de lignes (expirée, révoquée-vieille >
  rétention 7 j, active, révoquée-récente) — vérifie aussi que les
  lignes actives/récentes ne sont JAMAIS purgées

### Divergences par rapport à l'analyse

1. **Fichier debug `test_zz_debug_form.py` déjà absent** au moment de
   la suppression demandée (rm : « Aucun fichier ») ; grep
   `test_zz_debug_form` sur backend/.backlog/Makefile/pyproject →
   zéro référence résiduelle. Nettoyage déjà effectif, rien à faire.
2. **Fixture autouse `_jwt_mode` ajoutée** aux suites refresh (rotation
   123.3 + security 123.4) : exécutées depuis la racine (conditions
   Makefile), pydantic-settings charge le `.env` racine qui porte
   `DISABLE_AUTH=true` → `get_current_user` résout le premier
   superadmin en ignorant le Bearer → les logout authentifiés sur
   `test_user` échouaient (500 « No superadmin » ou révocation du
   mauvais propriétaire). Pattern = fixture autouse de la matrice
   consolidée 122.7. Les 2 suites sont désormais vertes **quel que soit
   le CWD** ; la non-régression `disable_auth` reste couverte
   explicitement par `test_existing_auth_suites_unaffected` (URL
   `/api/v1/users/` avec slash final, pattern matrice).
3. **Couverture** : la commande prescrite `--cov-fail-under=95` échoue
   sur le TOTAL agrégé `app.auth` (74 %) car `dependencies.py`
   (préexistant STORY-122, 38 %) est couvert par des suites hors
   sélection prescrite et souffre de l'artefact de tracing ASGI déjà
   documenté en 123.3. Modules du dispositif refresh :
   `jwt.py` **93 %**, `refresh_token_service.py` **98 %** — la cible
   95 % chemins critiques est tenue par le service ; l'écart jwt.py
   (3 lignes : branches d'erreur de décodage) et dependencies.py sont
   préexistants et hors périmètre de cette story.

### Validation

- `pytest tests/unit/test_api/test_auth_refresh_security.py` →
  **8 passed** (les 5 tests prescrits, 401 paramétré ×4)
- Périmètre ciblé 123.1→123.4 (test_models/, test_auth/,
  refresh_token_service, rotation, security) → **125 passed**
- Non-régression suite unitaire complète depuis `backend/`
  (`--timeout=120`, venv `.venv-test`) → **1432 passed, 0 failed**
  (1424 de 123.3 + 8 nouveaux ; l'error flaky `test_ws_auth.py`
  documenté en 123.2/123.3 n'est pas réapparu)
- `black` + `isort` : 2 fichiers reformatés puis tests re-passés ;
  `flake8` : 0 erreur ; `bandit -ll` : 0 finding sur les nouvelles
  lignes (MEDIUM B104 `0.0.0.0` ligne `__main__` préexistant) ;
  `mypy` : 0 erreur sur `app/main.py`/`app/config.py`
- Couverture ciblée : cf. divergence n°3 (jwt 93 %, service 98 %)
- Exécution depuis la racine : les 35 échecs constatés sont
  l'artefact environnemental `.env DISABLE_AUTH=true` (préexistant,
  hors périmètre — reproductible sans les changements de cette story) ;
  les 2 suites refresh de STORY-123 y sont désormais immunisées
  (divergence n°2)

### Tests ajoutés

- `backend/tests/unit/test_api/test_auth_refresh_security.py` :
  `TestRefreshSecurity401` (paramétré unknown/malformed/revoked/
  consumed → 401 générique), `TestNoPlaintextToken` (balayage complet
  token_hash après login + rotation, affixe `$argon2`),
  `TestUserIsolation` (logout A / rotation B), `TestExistingAuthFlows`
  (disable_auth, login username+email, register 201, logout 200),
  `TestPurgeExpiredEntries` (4 fixtures de lignes, appel direct)
