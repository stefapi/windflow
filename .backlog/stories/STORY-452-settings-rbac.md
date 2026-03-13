# STORY-452 : Gestion RBAC depuis la page Settings

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'administrateur, je veux gérer les rôles et permissions des utilisateurs depuis la page Settings afin d'appliquer le principe de moindre privilège sans modifier la base de données manuellement.

## Critères d'acceptation (AC)
- [ ] AC 1 : Sous-onglet ou section RBAC dans l'onglet Utilisateurs de Settings
- [ ] AC 2 : Affichage des rôles disponibles (super_admin, admin, operator, viewer) avec leurs permissions
- [ ] AC 3 : Attribution/modification du rôle d'un utilisateur via dropdown dans la ligne utilisateur
- [ ] AC 4 : Matrice de permissions visible (lecture seule) montrant quelles actions chaque rôle peut effectuer
- [ ] AC 5 : Changement de rôle sauvegardé immédiatement via API (`PUT /api/v1/users/{id}`) avec notification de succès
- [ ] AC 6 : Un super_admin ne peut pas se retirer son propre rôle super_admin (protection)
- [ ] AC 7 : Seuls les super_admin peuvent modifier les rôles (bouton grisé pour les admin simples)

## État d'avancement technique
- [ ] Section/sous-onglet RBAC dans Settings
- [ ] Matrice de permissions (composant `PermissionMatrix.vue`)
- [ ] Dropdown rôles inline dans la table utilisateurs
- [ ] Appel API PUT pour changement de rôle
- [ ] Protection auto-suppression super_admin
- [ ] Gestion droits d'accès (conditionnel sur le rôle courant)
- [ ] Tests Vitest
