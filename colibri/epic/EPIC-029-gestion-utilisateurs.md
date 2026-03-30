# EPIC-029 : Gestion des Utilisateurs

**Statut :** TODO
**Priorité :** Haute

## Vision
Gestion complète des utilisateurs permettant aux administrateurs de créer, modifier, désactiver et supprimer des comptes utilisateurs, ainsi que de gérer leurs rôles et permissions.

## Liste des Stories liées
- [ ] STORY-001 : Voir la liste des utilisateurs avec leurs informations
- [ ] STORY-002 : Créer un nouvel utilisateur (username, email, password, display_name)
- [ ] STORY-003 : Modifier un utilisateur existant
- [ ] STORY-004 : Désactiver un utilisateur (is_active=false)
- [ ] STORY-005 : Supprimer un utilisateur
- [ ] STORY-006 : Réinitialiser le mot de passe d'un utilisateur
- [ ] STORY-007 : Voir les rôles assignés à un utilisateur
- [ ] STORY-008 : Voir les dernières connexions d'un utilisateur

## Notes de conception
- Table users avec champs : username, email, password_hash, display_name, avatar, auth_provider, mfa_enabled, is_active, last_login
- Création avec hash Argon2id du mot de passe
- Support des providers : local, ldap, oidc
- Désactivation préférée à la suppression (soft delete)
- Réinitialisation de mot de passe par l'admin
- Liste des sessions actives par utilisateur
- Historique des connexions (last_login)
- Validation de l'unicité du username
