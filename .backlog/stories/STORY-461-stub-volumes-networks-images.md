# STORY-461 : Vues stubs Volumes, Networks, Images

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir des pages placeholder pour Volumes, Networks et Images dans la navigation afin de savoir que ces fonctionnalités sont prévues et arrivent bientôt (EPIC-002).

## Critères d'acceptation (AC)
- [ ] AC 1 : Vue `Volumes.vue` accessible via `/volumes` dans la sidebar (section Stockage & Réseau)
- [ ] AC 2 : Vue `Networks.vue` accessible via `/networks` dans la sidebar
- [ ] AC 3 : Vue `Images.vue` accessible via `/images` dans la sidebar
- [ ] AC 4 : Chaque vue affiche un message informatif : icône, titre, description courte, et mention « Prévu pour la v1.1 — Phase 2 »
- [ ] AC 5 : Design cohérent avec le thème sombre et les composants du design system
- [ ] AC 6 : Les routes sont enregistrées dans le router et fonctionnelles
- [ ] AC 7 : Les entrées sidebar correspondantes sont visibles (avec icône grisée ou badge « Bientôt »)

## État d'avancement technique
- [ ] Composant réutilisable `StubPage.vue` (props : titre, description, icône, version prévue)
- [ ] Création `frontend/src/views/Volumes.vue` utilisant StubPage
- [ ] Création `frontend/src/views/Networks.vue` utilisant StubPage
- [ ] Création `frontend/src/views/Images.vue` utilisant StubPage
- [ ] Ajout des 3 routes dans le router
- [ ] Vérification intégration sidebar
- [ ] Tests Vitest (rendu, props)
