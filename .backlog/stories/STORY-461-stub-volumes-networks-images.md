# STORY-461 : Vues stubs Volumes, Networks, Images

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir des pages placeholder pour Volumes, Networks et Images dans la navigation afin de savoir que ces fonctionnalités sont prévues et arrivent bientôt (EPIC-002).

## Critères d'acceptation (AC)
- [x] AC 1 : Vue `Volumes.vue` accessible via `/volumes` dans la sidebar (section Stockage & Réseau)
- [x] AC 2 : Vue `Networks.vue` accessible via `/networks` dans la sidebar
- [x] AC 3 : Vue `Images.vue` accessible via `/images` dans la sidebar
- [x] AC 4 : Chaque vue affiche un message informatif : icône, titre, description courte, et mention « Prévu pour la v1.1 — Phase 2 »
- [x] AC 5 : Design cohérent avec le thème sombre et les composants du design system
- [x] AC 6 : Les routes sont enregistrées dans le router et fonctionnelles
- [x] AC 7 : Les entrées sidebar correspondantes sont visibles (avec icône grisée ou badge « Bientôt »)

## État d'avancement technique
- [x] Composant réutilisable `StubPage.vue` (props : titre, description, icône, version prévue)
- [x] Création `frontend/src/views/Volumes.vue` utilisant StubPage
- [x] Création `frontend/src/views/Networks.vue` utilisant StubPage
- [x] Création `frontend/src/views/Images.vue` utilisant StubPage
- [x] Ajout des 3 routes dans le router
- [x] Vérification intégration sidebar
- [x] Tests Vitest (rendu, props)

## Pages supplémentaires implémentées
- [x] `frontend/src/views/VMs.vue` - Section Infrastructure
- [x] `frontend/src/views/Marketplace.vue` - Section Marketplace
- [x] `frontend/src/views/Plugins.vue` - Section Marketplace
- [x] `frontend/src/views/Audit.vue` - Section Administration
- [x] Routes et sidebar mises à jour pour ces pages

## Notes d'implémentation

### Fichiers créés/modifiés
- `frontend/src/components/ui/StubPage.vue` - Composant réutilisable avec props (title, description, icon, version)
- `frontend/src/views/Volumes.vue` - Page stub Volumes (icône: FolderOpened)
- `frontend/src/views/Networks.vue` - Page stub Networks (icône: Link)
- `frontend/src/views/Images.vue` - Page stub Images (icône: PictureFilled)
- `frontend/src/views/VMs.vue` - Page stub VMs (icône: Monitor)
- `frontend/src/views/Marketplace.vue` - Page stub Marketplace (icône: ShoppingCart)
- `frontend/src/views/Plugins.vue` - Page stub Plugins (icône: Grid)
- `frontend/src/views/Audit.vue` - Page stub Audit (icône: DocumentChecked)
- `frontend/src/router/index.ts` - Routes déjà présentes
- `frontend/src/components/SidebarNav.vue` - Sidebar déjà configurée avec badges "Bientôt"
- `frontend/tests/unit/components/StubPage.spec.ts` - Tests unitaires complets (13 tests)

### Décisions techniques
- Utilisation de `markRaw()` pour l'icône afin d'éviter les warnings Vue sur les composants réactifs
- Design cohérent avec les variables CSS du thème (--color-bg-card, --color-text-primary, etc.)
- Bouton "Retour au Dashboard" pour la navigation

### Tests
- 13 tests unitaires passent (Vitest)
- Couverture : rendu de base, props, structure CSS
