# 40 — Sécurité (obligatoire)

> Prime sur toute autre règle (`02` §2). En cas de doute : l'option la plus restrictive, signalée.

## 1. Principes

OWASP Top 10 ; least privilege ; zero trust ; chiffrement en transit et au repos ; ne jamais logger de données sensibles ; aucune confiance dans ce qu'envoie le client — la validation serveur fait foi.

## 2. Authentification

- JWT + refresh (spécification `docs/general_specs/07-authentification.md`) : refresh tokens opaques révocables `wf_rt_` avec rotation (STORY-123) ; clés API `wf_ak_` via l'en-tête `X-API-Key` (STORY-124).
- Hash Argon2id effectif, double lecture bcrypt legacy avec re-hash automatique au login uniquement (STORY-130.1) ; bcrypt en voie de retrait post-migration (STORY-250).
- Protection brute-force login : 5 échecs par username sur fenêtre glissante de 10 min → lockout 5 min (STORY-104).
- Bibliothèques : python-jose (JWT), passlib + argon2-cffi, email-validator.
- Mode dev sans auth : `disable_auth: bool = False` par défaut ; signaler toute activation hors environnement de développement.
- Keycloak SSO optionnel (`keycloak_enabled = False` par défaut), activable via `make enable-sso`.
- Token d'accès côté frontend conservé **en mémoire** (store Pinia auth) — jamais en `localStorage` ni `sessionStorage`.

## 3. Autorisation (RBAC)

- Source de vérité côté API : 4 rôles `viewer < operator < admin < super_admin` (spécification `docs/general_specs/08-rbac-permissions.md`).
- `require_role(...)` (et alias `require_viewer`, `require_operator`, `require_admin`, `require_super_admin`) sur les endpoints REST — `backend/app/auth/` ; `ensure_role_ws` / `require_role_ws` sur les canaux WebSocket (`21` §3).
- Isolation des ressources : un utilisateur ne peut pas accéder aux ressources d'un autre ; vérifier l'appartenance dans les services.
- Un endpoint ou canal sensible sans `require_role` alors que ses voisins en ont un est une escalade : à signaler en revue.

## 4. Validation et exposition

- Validation des inputs côté client ET serveur (Pydantic côté backend fait foi) ; paramètres de path/query typés et bornés.
- Champs sensibles exclus explicitement des schémas `*Response` (`exclude={"password", "token", …}`).
- Messages d'erreur génériques côté client : jamais de stack trace, SQL ou chemin de fichier dans une réponse.
- En-têtes de sécurité : CSP configurable, HSTS, X-Frame-Options (security headers middleware, `20` §5). CORS : origines configurées — tout élargissement (`"*"`) est signalé.
- Rate limiting fastapi-limiter (Redis, fallback mémoire process-local STORY-102), configurable par endpoint.
- CSRF pour opérations critiques.

## 5. Secrets

- **Jamais de secrets en dur**, ni dans les logs, ni dans une URL ; variables d'environnement (`07` §5).
- SecretManager Fernet (AES-256, clé dérivée PBKDF2) effectif pour les credentials en base (STORY-103).
- HashiCorp Vault optionnel (`vault_enabled = False` par défaut), activable via `make enable-secrets`.
- Audit trail applicatif : modèle `AuditLog` + émission sur actions critiques + `GET /admin/audit` (STORY-125).
- `.env.example` / `.env.prod.example` mis à jour dans le même commit qu'une nouvelle variable.

## 6. Données sensibles

Jamais dans les journaux, les réponses d'erreur, les URL ni les labels de métriques (jamais de query string, `45` §4) : mots de passe, tokens (`wf_rt_`, `wf_ak_`, JWT), clés API LLM, credentials SSH/hosts, cookies, contenu de fichiers de configuration des cibles.

**Interdit** : `eval`/`exec`/`pickle` sur des données non maîtrisées ; `yaml.load` (utiliser `yaml.safe_load`) ; SQL construite par concaténation (paramètres liés uniquement) ; `subprocess` avec `shell=True` ; `v-html`/`innerHTML` avec un contenu non maîtrisé ; désactivation de la vérification TLS.

## 7. Scans

bandit/semgrep côté backend, `pnpm audit` côté frontend (`make ci-security-backend`, `make ci-security-frontend`).

## 8. Checklist sécurité lors de l'analyse d'une story

Lors de la phase d'analyse (`analyse-story`), évaluer obligatoirement :

### Authentification & autorisation
- [ ] L'endpoint/fonctionnalité nécessite-t-il une authentification ? → `get_current_user` injecté
- [ ] Quels rôles peuvent y accéder ? → `require_role(...)` sur la route, `ensure_role_ws` sur le canal
- [ ] Les accès RBAC sont-ils vérifiés côté API (source de vérité), pas seulement côté frontend ?
- [ ] Des ressources par utilisateur sont-elles exposées ? → isolation vérifiée dans le service

### Validation & injection
- [ ] Inputs entièrement validés via Pydantic ? Paramètres typés et bornés ?
- [ ] Risque d'injection (SQL, shell, YAML, JSON) ? → sanitisation prévue
- [ ] Uploads validés (type MIME, taille max) le cas échéant ?

### Exposition de données sensibles
- [ ] Champs sensibles exclus des schémas `*Response` ?
- [ ] Logs et métriques sans données sensibles ?
- [ ] Messages d'erreur génériques ?

### Audit & traçabilité
- [ ] L'opération doit-elle être tracée (audit log) — suppression, déploiement, modification de config ?
- [ ] Les événements émis (bus, WebSocket) contiennent-ils des données sensibles ?

### Tests de sécurité à spécifier dans la story
Pour tout nouvel endpoint ou feature modifiant des données : `401` sans token, `403` rôle insuffisant, `422` body invalide, `404` introuvable, isolation par utilisateur, champs sensibles absents (`35` §5). Frontend : redirection `/login` sans auth, actions admin masquées pour `viewer`, aucun token dans le DOM.
