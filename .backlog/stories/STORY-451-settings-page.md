# STORY-451 : Page Settings — Organisations, Environnements, Utilisateurs

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'administrateur, je veux une page Settings avec onglets pour gérer les organisations, environnements et utilisateurs afin de configurer WindFlow sans passer par l'API directement.

## Critères d'acceptation (AC)
- [ ] AC 1 : Vue `Settings.vue` accessible via `/settings` dans la sidebar (section Administration)
- [ ] AC 2 : Onglet « Organisations » : liste des organisations, création, édition, suppression
- [ ] AC 3 : Onglet « Environnements » : liste des environnements par organisation, CRUD
- [ ] AC 4 : Onglet « Utilisateurs » : tableau avec nom, email, rôle, dernière connexion, actions (éditer, supprimer)
- [ ] AC 5 : Formulaires de création/édition via drawer ou modale Element Plus
- [ ] AC 6 : Confirmation avant suppression d'un utilisateur ou d'une organisation
- [ ] AC 7 : Les données proviennent des APIs existantes (`/api/v1/organizations`, `/api/v1/users`)
- [ ] AC 8 : Accès restreint aux rôles admin/super_admin (sinon redirection ou message d'erreur)

## État d'avancement technique
- [ ] Création `frontend/src/views/Settings.vue` avec el-tabs
- [ ] Onglet Organisations (CRUD)
- [ ] Onglet Environnements (CRUD)
- [ ] Onglet Utilisateurs (liste + drawer édition)
- [ ] Guard de route pour vérifier le rôle
- [ ] Services frontend pour les appels API orgs/users
- [ ] Tests Vitest
