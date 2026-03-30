# EPIC-007 : Authentification et Autorisation

**Statut :** TODO
**Priorité :** Haute

## Vision
Système d'authentification complet avec support multi-provider (local, LDAP, OIDC) et contrôle d'accès basé sur les rôles (RBAC). Les utilisateurs peuvent se connecter via différents providers et les administrateurs peuvent gérer les permissions de manière fine.

## Liste des Stories liées
- [ ] STORY-001 : Se connecter avec un compte local (username/password)
- [ ] STORY-002 : Se connecter via LDAP/Active Directory
- [ ] STORY-003 : Se connecter via OIDC/SSO (Keycloak, Azure AD, etc.)
- [ ] STORY-004 : Activer l'authentification à deux facteurs (MFA/TOTP)
- [ ] STORY-005 : Utiliser des codes de secours pour le MFA
- [ ] STORY-006 : Gérer les utilisateurs (créer, modifier, désactiver, supprimer)
- [ ] STORY-007 : Gérer les rôles et permissions (RBAC Enterprise)
- [ ] STORY-008 : Configurer les paramètres LDAP (serveur, filtres, groupes, mappings)
- [ ] STORY-009 : Configurer les paramètres OIDC (issuer, client, scopes, claims)
- [ ] STORY-010 : Définir un timeout de session
- [ ] STORY-011 : Voir les sessions actives
- [ ] STORY-012 : Protection contre les attaques par force brute (rate limiting)

## Notes de conception
- Hash des mots de passe avec Argon2id (memory-hard, résistant aux attaques temporelles)
- Tokens de session cryptographiquement sécurisés (32 bytes, base64url)
- Cookies HttpOnly avec SameSite=Strict (protection CSRF)
- Flag Secure protocol-aware (x-forwarded-proto ou COOKIE_SECURE env var)
- MFA via TOTP (RFC 6238) avec QR code et codes de secours
- Support LDAP avec recherche de groupes et mappings de rôles
- Support OIDC avec PKCE (S256) et discovery document
- Rate limiting en mémoire avec lockout progressif
- Permissions par environnement (RBAC Enterprise)
- Édition gratuite : tous les utilisateurs authentifiés sont admins
