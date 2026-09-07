# EPIC-011 : P0 — Sécurité bloquante (remédiation backend)

**Statut :** DONE
**Priorité :** Haute

## Vision

Éliminer les failles de sécurité actives du backend avant tout autre travail de remédiation. Cette vague P0 du plan de remédiation ([`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4) couvre les cinq items bloquants identifiés par le rapport d'écart : authentification WebSocket non forcée (connexions anonymes acceptées), secrets de développement acceptés en production, rate limiting inopérant sans Redis, credentials de cibles stockés en clair, et absence de protection contre le brute-force sur le login.

Spécifications de référence : [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) (audit trail, secrets, protection des endpoints), complétées par [`docs/technical_specs/WEBSOCKET-REAL-TIME.md`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) pour le canal WS.

## Description

Chaque item P0 du plan de remédiation devient une story :

| Story | Item plan | Objectif | Ampleur |
|-------|-----------|----------|---------|
| STORY-100 | P0-1 (B1) | Auth WS obligatoire : refuser les connexions sans token valide — `get_current_user_ws()` retourne `None` sans token → connexions anonymes acceptées | S |
| STORY-101 | P0-2 (B12) | Garde-fou secrets dev en prod : démarrage bloqué si `jwt_secret` par défaut ou admin `changeme123` en `environment=production` | S |
| STORY-102 | P0-3 (B2) | Rate limiting effectif sans Redis : backend mémoire process-local + warning unique | M |
| STORY-103 | P0-4 (A6, B3, C12 partiel) | SecretManager Fernet/AES + chiffrement des credentials cibles et env vars de stacks, migration double-lecture | L |
| STORY-104 | P0-5 (C2) | Protection brute-force login : compteur 5 essais/10 min par username, blocage 5 min, Redis ou mémoire | M |

**Dépendances internes** : STORY-104 dépend de STORY-102 (même mécanique de stockage). STORY-103 est conçue sans migration de schéma (chiffrement du contenu JSON, double lecture clair → ré-encryptage au premier accès).

**Critères de done (reprends fidèlement le plan)** :
- P0-1 : connexion WS sans token → refusée (401/fermeture) sur les 5 canaux ; `disable_auth` continue de fonctionner en dev.
- P0-2 : settings prod + secret par défaut → exception au startup avec message explicite ; `env.example` à jour.
- P0-3 : sans `RATE_LIMIT_STORAGE_URL`, 6 requêtes/min sur `/auth/login` → 429 ; warning unique dans les logs.
- P0-4 : round-trip chiffrement testé ; migration ancienne ligne clair → lue puis ré-encryptée au premier accès ; 0 credential lisible en base après exécution.
- P0-5 : 6e essai → 429 avec `Retry-After` ; reset après fenêtre ; compteur par username (pas par IP seule).

**Garde-fous** (plan §2.G) : ne pas régresser les middlewares sécurité existants (CSP/HSTS/correlation/timing) ni le module WebSocket modulaire — STORY-100 étend l'auth sans casser l'architecture plugins.

## Liste des Stories liées

> ⚠️ Cette epic est fermée. Toutes les stories ont été supprimées le 2026-09-07.

## Historique de clôture

- **Date de fermeture :** 2026-09-07
- **Stories supprimées :** STORY-100, STORY-101, STORY-102, STORY-103, STORY-103.1, STORY-103.2, STORY-103.3, STORY-103.4, STORY-104
- **Raison :** Epic terminée

## Notes de conception

- **Plage de numéros réservée** : STORY-100 à STORY-119 (seules 100-104 sont affectées à ce stade ; les numéros 105-119 restent disponibles pour d'éventuelles sous-découpes, ex. STORY-103 ampleur L).
- Source principale : [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 « Vague P0 », items B1/B2/B3/B12/C2/A6 du rapport d'écart.
- STORY-103 est le prérequis des chaînes critiques P1-9 (SSH keys) et P2-3 (plugins réels) — cf. plan §5.
- Aucun autre item ne démarre avant la fin de cette vague (règle « remettre d'équerre l'existant avant d'étendre »).

## Critères de succès (Definition of Done)

- [ ] Les 5 stories P0 sont DONE avec leurs critères de done vérifiables validés (tests unitaires passants).
- [ ] Aucun credential ni secret lisible en base (chiffrement effectif via STORY-103).
- [ ] Aucune connexion WebSocket anonyme possible en mode auth activé.
- [ ] Le rate limiting et la protection brute-force fonctionnent sans Redis (mode léger RPi).
- [ ] Les garde-fous §2.G du plan sont préservés (middlewares sécurité, WS modulaire).
- [ ] Couverture de tests ≥ 80 % sur les modules touchés (rules 35).

## Rapport de finalisation

**Date :** 2026-09-07
**Verdict :** ✅ CONFORME — prête pour clôture
**Score :** 97 % (35/36 vérifications passées ; 1 réserve environnementale non bloquante)

### Résumé

- Stories vérifiées : 5/5 DONE (STORY-103 découpée en 4 sous-stories 103.1–103.4, toutes DONE) — 9 fichiers story audités
- Critères de succès epic validés : **6/6** (vérification par analyse de code + exécution)
- Anomalies critiques : **0** — Anomalies mineures : **4** — Avertissements : **3**
- Code quality : tests **999 unit + 68 intégration passants (0 échec)**, couverture modules critiques **90–100 %**, ruff clean sur tous les modules créés par l'epic

### Détail par phase

**Phase 1 — Cohérence backlog :** ✅ Les 9 stories (5 + 4 sous-stories) sont cochées `[x]` dans l'epic et positionnées en ✅ DONE dans le kanban ; 47/47 fichiers livrables listés dans les notes d'implémentation existent sur disque ; chaque story possède statut, AC cochés, tâches cochées et notes d'implémentation complètes.

**Phase 2 — Rapport par story :** 9/9 CONFORMES. STORY-100 (5/5 AC, 46 tests WS), STORY-101 (5/5 AC, 13 tests garde-fou), STORY-102 (5/5 AC, 18+9 tests, couv. 100 %), STORY-103.1–103.4 (AC validés, couv. 95–100 % par sous-story), STORY-104 (5/5 AC, 19+10 tests, couv. 97 %).

**Phase 3 — Critères épic (6/6) :** ① 5 stories DONE avec tests passants ✓ ; ② 0 credential lisible en base — `SecretManager` Fernet (PBKDF2HMAC, salt `windflow-secrets-v1`, 480 000 it.) + `encrypt_credentials_for_storage()` / `encrypt_variables_for_storage()` + masquage API `_mask_sensitive_values()` + test E2E SQL brut `test_secret_encryption.py` ✓ ; ③ 0 connexion WS anonyme — `get_current_user_ws` lève `WebSocketException 1008` sur les 3 canaux dédiés, helper `authenticate_ws_first_message` sur général/terminal ✓ ; ④ rate limiting + brute-force sans Redis — `MemoryRateLimiter` et `BruteforceProtector` mémoire avec 429 + `Retry-After` ✓ ; ⑤ garde-fous §2.G — middlewares (correlation/security/timing/logging) et plugins WS intacts ✓ ; ⑥ couverture ≥ 80 % mesurée ce jour : dependencies 90 %, bruteforce 97 %, rate_limit 100 %, secret_manager 100 %, models/target 98 %, models/deployment 99 %, schemas/deployment 100 % ✓.

**Phase 4 — Code quality :** tests 1067 passants via `.venv-test` (Python 3.11) ; `ruff check` All checks passed sur les modules créés par l'epic. **Limite environnementale (non bloquante)** : `make backend-lint` complet (black/isort/flake8/mypy/bandit) indisponible dans le venv courant — 24 erreurs ruff relevées sur `main.py`/`database_seed.py` sont une **baseline préexistante** (print debug d'oct. 2025, commit fa4cf27 — ciblée par STORY-250/P3), non imputable à l'epic.

**Phase 5 — Architecture & standards :** 6/6 conformes — API-first (OpenAPI login enrichie 429 + `Retry-After`, schémas Pydantic, masquage côté schéma), type safety (exceptions `SecretEncryptionError`/`SecretDecryptionError` héritant `WindFlowException`, 0 `dict[str, Any]` non justifié), nommage snake_case/core, clean code (DRY helper centralisé WS), sécurité (aucun secret en dur hors liste noire config, jamais de token/mot de passe en logs — vérifié), observabilité (loggers dédiés `windflow.*`, état rate limiting 3 états au startup, URL Redis masquée).

### Anomalies & avertissements (non bloquants)

- 🟡 Statut epic `IN_PROGRESS` alors que toutes les stories sont DONE — transition `DONE` à effectuer via `close-epic` (nominal, non fait par `finalise-epic`)
- 🟡 Résidu d'index git : `backend/tests/unit/test_api/test_debug_story1033.py` en état AD (ajouté à l'index, supprimé du disque) — à nettoyer
- 🟡 Baseline lint préexistante : 24 erreurs E402/E712 (`main.py`, `database_seed.py`) — déjà couverte par STORY-250 (P3)
- 🟢 `mypy`/`bandit`/`black`/`isort`/`flake8` + `poetry build` non exécutés (outils absents du venv) — repasser via `make backend-lint` / `make ci-full` en CI une fois l'environnement réparé
- 🟢 Recommandations résiduelles STORY-103 : opérationnaliser la rotation de clé maîtresse ; réparer le venv Poetry racine (Python 3.14/fastuuid)

### Prochaine étape

→ Lancer `close-epic` pour clôturer EPIC-011 : « Ferme l'epic EPIC-011 »
