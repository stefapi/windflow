# STORY-462 : Vue stub Plugins installés

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir une page Plugins dans la navigation afin de savoir que la gestion des plugins est prévue et sera livrée avec le système de plugins (EPIC-001).

## Critères d'acceptation (AC)
- [ ] AC 1 : Vue `Plugins.vue` accessible via `/plugins` dans la sidebar (section Marketplace)
- [ ] AC 2 : Affiche un message informatif : « Aucun plugin installé » avec icône, description et mention « Prévu pour la v1.1 — Phase 2 »
- [ ] AC 3 : Bouton « Découvrir la Marketplace » désactivé avec tooltip « Bientôt disponible » (pointe vers la future route `/marketplace`)
- [ ] AC 4 : Design cohérent avec les stubs Volumes/Networks/Images (réutilise `StubPage.vue` de STORY-461)
- [ ] AC 5 : La route est enregistrée dans le router et fonctionnelle
- [ ] AC 6 : L'entrée sidebar est visible avec badge « Bientôt »

## État d'avancement technique
- [ ] Création `frontend/src/views/Plugins.vue` utilisant `StubPage.vue`
- [ ] Ajout de la route dans le router
- [ ] Bouton Marketplace désactivé avec tooltip
- [ ] Vérification intégration sidebar
- [ ] Tests Vitest
