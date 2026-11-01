# Sécurité (obligatoire)

## Principes
- OWASP Top 10
- least privilege
- zero trust
- chiffrement en transit et au repos
- ne jamais logger de données sensibles

## AuthN/AuthZ
- JWT + refresh (voir `docs/general_specs/07-authentification.md`)
- RBAC côté API (source de vérité) — voir `docs/general_specs/08-rbac-permissions.md`
- Hash Argon2id effectif, double lecture bcrypt legacy avec re-hash automatique au login (STORY-130.1)
- Refresh tokens opaques révocables `wf_rt_` avec rotation (STORY-123) ; clés API `wf_ak_` via `X-API-Key` (STORY-124)
- RBAC granulaire 4 rôles (`viewer < operator < admin < super_admin`) via `require_role(...)` sur les endpoints REST et `ensure_role_ws` sur les canaux WebSocket (STORY-121/122)
- Protection brute-force login : 5 échecs par username sur fenêtre glissante de 10 min → lockout 5 min (STORY-104)
- validation inputs côté client ET serveur (Pydantic côté backend)
- protection CSRF pour opérations critiques

### Bibliothèques d'authentification
- python-jose (JWT)
- passlib + argon2-cffi (hash des mots de passe)
- email-validator

### Mode dev sans auth
- `disable_auth: bool = False` par défaut
- Permet de contourner JWT en développement

### Keycloak SSO
- Optionnel (`keycloak_enabled: bool = False` par défaut)
- Extension activable via `make enable-sso`

## Rate limiting
- fastapi-limiter avec Redis comme stockage
- Fallback mémoire process-local effectif sans Redis (STORY-102)
- Configuration par endpoint

## Headers de sécurité
- CSP configurable
- HSTS
- X-Frame-Options
- Security headers middleware dédié

## Secrets
- HashiCorp Vault **optionnel** (`vault_enabled: bool = False` par défaut)
- Activable via `make enable-secrets`
- SecretManager Fernet (AES-256, clé dérivée PBKDF2) effectif pour les credentials en base (STORY-103)
- jamais de secrets en dur
- rotation + audit trail
- audit trail applicatif : modèle `AuditLog` + émission sur actions critiques + `GET /admin/audit` (STORY-125)

## Scans
- bandit/semgrep côté backend
- npm audit côté frontend

---

## Checklist sécurité lors de l'analyse d'une story

Lors de la phase d'analyse (`analyse-story`), évaluer **obligatoirement** les points suivants :

### Authentification & autorisation

- [ ] L'endpoint/fonctionnalité nécessite-t-il une authentification ? → Si oui, vérifier que `get_current_user` est injecté
- [ ] Quels rôles peuvent accéder à cette fonctionnalité ? → Lister les rôles autorisés et les rôles à exclure (RBAC)
- [ ] Les accès RBAC sont-ils vérifiés côté API (source de vérité) ? → Pas seulement côté frontend
- [ ] Des ressources appartenant à un utilisateur sont-elles exposées ? → Vérifier l'isolation (un user ne peut pas accéder aux ressources d'un autre)

### Validation & injection

- [ ] Les inputs utilisateur sont-ils entièrement validés via Pydantic (backend) ?
- [ ] Les paramètres de path/query sont-ils typés et bornés (min/max, regex si applicable) ?
- [ ] Les entrées sont-elles susceptibles d'injection (SQL, commande shell, YAML, JSON) ? → Prévoir une sanitisation
- [ ] Les uploads de fichiers (si applicable) sont-ils validés (type MIME, taille max) ?

### Exposition de données sensibles

- [ ] La réponse API expose-t-elle des champs sensibles (mots de passe, tokens, secrets) ? → Les exclure explicitement dans les schémas Pydantic Response
- [ ] Les logs produits contiennent-ils des données sensibles ? → Utiliser des masques/hash pour les secrets dans les logs
- [ ] Les messages d'erreur révèlent-ils des informations internes (stack traces, noms de tables) ? → Retourner des messages génériques

### Audit & traçabilité

- [ ] L'opération doit-elle être tracée (qui a fait quoi, quand) ? → Prévoir un audit log pour les actions critiques (suppression, déploiement, modification de config)
- [ ] Les events Redis émis contiennent-ils des données sensibles non chiffrées ?

---

## Checklist des tests de sécurité à spécifier dans une story

Pour **tout nouvel endpoint** ou **feature modifiant des données**, les tests suivants DOIVENT être présents dans la section `## Tests à écrire` de la story :

### Backend — tests obligatoires

| Cas | Test attendu |
|-----|-------------|
| Accès sans token | `test_xxx_returns_401_without_token` |
| Accès avec rôle insuffisant | `test_xxx_returns_403_for_viewer` (ou autre rôle insuffisant) |
| Body invalide / champ manquant | `test_xxx_returns_422_on_invalid_body` |
| Ressource introuvable | `test_xxx_returns_404_when_not_found` |
| Accès à ressource d'un autre user | `test_xxx_returns_403_for_foreign_resource` (si applicable) |
| Champs sensibles absents de la réponse | `test_xxx_response_does_not_expose_password` (si applicable) |

### Frontend — tests obligatoires

| Cas | Test attendu |
|-----|-------------|
| Route protégée sans auth | redirige vers `/login` |
| Actions admin masquées pour viewer | éléments conditionnels non affichés |
| Pas de secret/token visible dans le DOM | assertions `not.toContain` sur les tokens |

---

## Application dans les tâches d'implémentation

Lors de la rédaction des tâches (`analyse-story`), intégrer les exigences sécurité **directement dans les tâches concernées** :

- Pour tout endpoint : mentionner explicitement la dépendance `require_role(...)` ou `get_current_user`
- Pour les schémas Pydantic Response : mentionner les champs à **exclure** (`exclude={"password", "token"}`)
- Pour les services : mentionner la vérification d'appartenance (`assert resource.owner_id == current_user.id`)
- Pour les logs : mentionner `logger.info("...", extra={"user_id": ...})` sans données sensibles

**Référencer** `docs/general_specs/07-authentification.md` et `docs/general_specs/08-rbac-permissions.md` pour les détails des rôles.
