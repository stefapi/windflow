# EPIC-028 : Rôles et Permissions (RBAC)

**Statut :** TODO
**Priorité :** Haute

## Vision
Système de contrôle d'accès basé sur les rôles permettant aux administrateurs de définir des permissions granulaires sur les ressources (conteneurs, images, volumes, réseaux, stacks, etc.) et de les assigner aux utilisateurs par environnement.

## Liste des Stories liées
- [ ] STORY-001 : Créer un rôle avec nom, description et permissions
- [ ] STORY-002 : Modifier un rôle existant
- [ ] STORY-003 : Supprimer un rôle
- [ ] STORY-004 : Assigner un rôle à un utilisateur (globalement ou par environnement)
- [ ] STORY-005 : Révoquer un rôle d'un utilisateur
- [ ] STORY-006 : Voir les permissions d'un utilisateur
- [ ] STORY-007 : Les permissions sont vérifiées avant chaque action
- [ ] STORY-008 : Le rôle Admin a toutes les permissions

## Notes de conception
- Tables roles, user_roles
- Permissions structurées par ressource : containers, images, volumes, networks, stacks, environments, registries, notifications, configsets, settings, users, git, license, audit_logs, activity, schedules
- Actions par ressource : view, create, update, delete, start, stop, restart, etc.
- Permissions par environnement (user_roles.environment_id)
- Rôle Admin système (is_system=true) avec toutes les permissions
- Vérification des permissions via checkPermission()
- Édition gratuite : tous les utilisateurs sont admins
- Édition Enterprise : RBAC complet
- Guards UI via permission-guard.svelte
