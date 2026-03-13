# STORY-401 : Audit & suppression Marketplace frontend

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant que développeur, je veux supprimer proprement toute la Marketplace frontend actuelle afin de nettoyer la base de code avant la reconstruction dans l'EPIC-001.

## Critères d'acceptation (AC)
- [ ] AC 1 : `frontend/src/views/Marketplace.vue` est supprimé
- [ ] AC 2 : `frontend/src/components/marketplace/` (dossier complet) est supprimé — DeploymentProgress.vue, DeploymentWizard.vue, StackCard.vue, StackDetailsModal.vue, StackReviews.vue, TargetSelector.vue, renderers/
- [ ] AC 3 : La route `/marketplace` est supprimée du router (`frontend/src/router/index.ts`)
- [ ] AC 4 : Les stores Pinia liés à la marketplace sont supprimés ou nettoyés
- [ ] AC 5 : Les services/API calls frontend liés à la marketplace sont supprimés
- [ ] AC 6 : Les types TypeScript liés à la marketplace sont supprimés
- [ ] AC 7 : `pnpm build` passe sans erreur
- [ ] AC 8 : `pnpm lint` passe sans erreur
- [ ] AC 9 : Aucun import orphelin ne référence les fichiers supprimés

## État d'avancement technique
- [ ] Audit des dépendances de Marketplace.vue (imports, composants, stores, services)
- [ ] Suppression des composants `frontend/src/components/marketplace/`
- [ ] Suppression de la vue `Marketplace.vue`
- [ ] Nettoyage du router
- [ ] Nettoyage des stores Pinia
- [ ] Nettoyage des services API frontend
- [ ] Nettoyage des types TypeScript
- [ ] Vérification build + lint
- [ ] Grep global pour s'assurer qu'aucune référence ne subsiste
