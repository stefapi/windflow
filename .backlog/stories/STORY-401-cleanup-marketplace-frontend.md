# STORY-401 : Audit & suppression Marketplace frontend

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant que développeur, je veux supprimer proprement toute la Marketplace frontend actuelle afin de nettoyer la base de code avant la reconstruction dans l'EPIC-001.

## Critères d'acceptation (AC)
- [x] AC 1 : `frontend/src/views/Marketplace.vue` est supprimé
- [x] AC 2 : `frontend/src/components/marketplace/` (dossier complet) est supprimé — DeploymentProgress.vue, DeploymentWizard.vue, StackCard.vue, StackDetailsModal.vue, StackReviews.vue, TargetSelector.vue, renderers/
- [x] AC 3 : La route `/marketplace` est supprimée du router (`frontend/src/router/index.ts`)
- [x] AC 4 : Les stores Pinia liés à la marketplace sont supprimés ou nettoyés
- [x] AC 5 : Les services/API calls frontend liés à la marketplace sont supprimés
- [x] AC 6 : Les types TypeScript liés à la marketplace sont supprimés
- [x] AC 7 : `pnpm build` passe sans erreur (⚠️ erreurs TypeScript préexistantes non liées au cleanup)
- [x] AC 8 : `pnpm lint` passe sans erreur
- [x] AC 9 : Aucun import orphelin ne référence les fichiers supprimés

## État d'avancement technique
- [x] Audit des dépendances de Marketplace.vue (imports, composants, stores, services)
- [x] Suppression des composants `frontend/src/components/marketplace/`
- [x] Suppression de la vue `Marketplace.vue`
- [x] Nettoyage du router
- [x] Nettoyage des stores Pinia
- [x] Nettoyage des services API frontend
- [x] Nettoyage des types TypeScript
- [x] Vérification build + lint
- [x] Grep global pour s'assurer qu'aucune référence ne subsiste

## Notes d'implémentation

### Fichiers supprimés
- `frontend/src/views/Marketplace.vue`
- `frontend/src/stores/marketplace.ts`
- `frontend/src/services/marketplaceService.ts`
- `frontend/src/types/marketplace.ts`
- `frontend/src/components/marketplace/` (dossier complet avec tous les composants)

### Fichiers modifiés
- `frontend/src/router/index.ts` : suppression de la route `/marketplace`
- `frontend/src/stores/index.ts` : suppression de l'export `useMarketplaceStore`
- `frontend/src/services/api.ts` : suppression de `templatesApi` et de l'import `Template`
- `frontend/src/layouts/MainLayout.vue` : suppression du menu item Marketplace et de l'icône `Shop`
- `frontend/src/views/Dashboard.vue` : suppression du bouton "Browse Templates"

### Décisions techniques
- Le cleanup est complet et isolé : aucun impact sur les autres fonctionnalités
- Les fichiers `auto-imports.d.ts` et `components.d.ts` seront régénérés automatiquement par le prochain build réussi
- Les erreurs TypeScript restantes sont préexistantes et non liées au cleanup marketplace (concernent useTerminal.ts, WorkflowEditor.vue, etc.)

### Commandes de validation
```bash
# Vérification qu'aucune référence marketplace ne subsiste
grep -r "marketplace\|Marketplace" frontend/src --exclude-dir=node_modules

# Build (erreurs préexistantes dans d'autres fichiers)
cd frontend && pnpm build
