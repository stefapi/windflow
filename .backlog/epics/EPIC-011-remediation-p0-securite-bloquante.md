# EPIC-011 : P0 — Sécurité bloquante (remédiation backend)

**Statut :** IN_PROGRESS
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

- [x] STORY-100 : Auth WebSocket obligatoire — refus des connexions sans token valide sur les 5 canaux (P0-1)
- [x] STORY-101 : Garde-fou de démarrage — refus des secrets dev par défaut en production (P0-2)
- [x] STORY-102 : Rate limiting effectif sans Redis — fallback mémoire + warning (P0-3)
- [ ] STORY-103 : SecretManager AES/Fernet — chiffrement au repos des credentials cibles et env vars de stacks (P0-4)
- [ ] STORY-104 : Protection brute-force du login — compteur par username, blocage temporaire (P0-5)

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
