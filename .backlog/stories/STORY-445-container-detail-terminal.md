# STORY-445 : ContainerDetail — onglet Terminal

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux ouvrir un terminal interactif dans un container depuis l'UI afin d'exécuter des commandes de debug sans passer par SSH + docker exec.

## Critères d'acceptation (AC)
- [x] AC 1 : Onglet « Terminal » dans ContainerDetail ouvrant un shell interactif dans le container
- [x] AC 2 : Réutilise le composant existant `ContainerTerminal.vue`
- [x] AC 3 : Connexion WebSocket vers l'API existante (`/api/v1/websockets/terminal`)
- [x] AC 4 : Shell par défaut : `/bin/sh` avec fallback, détection de `/bin/bash` si disponible
- [x] AC 5 : Le terminal s'adapte à la taille du panneau (resize automatique)
- [x] AC 6 : Bouton « Déconnecter » pour fermer la session proprement
- [x] AC 7 : Police monospace JetBrains Mono (STORY-422)
- [x] AC 8 : Le terminal n'est disponible que si le container est en statut running

## État d'avancement technique
- [x] Intégration de `ContainerTerminal.vue` comme onglet dans ContainerDetail
- [x] Passage du container_id en prop
- [x] Gestion du resize terminal (xterm.js fit addon)
- [x] Désactivation de l'onglet si container stopped
- [x] Bouton déconnexion
- [x] Tests Vitest (rendu conditionnel, props)

## Notes d'implémentation

### Fichiers modifiés
- `frontend/src/views/ContainerDetail.vue` : Ajout de l'onglet Terminal avec intégration du composant ContainerTerminal
- `frontend/tests/unit/views/ContainerDetail.spec.ts` : Ajout des tests pour l'onglet Terminal et stubbing de ContainerTerminal/ContainerLogs

### Décisions techniques
- L'onglet Terminal est désactivé (`disabled`) lorsque le container n'est pas en statut `running`
- Un message explicite est affiché lorsque le container est arrêté : "Le terminal n'est disponible que lorsque le container est en cours d'exécution (running)"
- Suppression de la fonction `goToTerminal` devenue inutile (navigation vers page Terminal séparée)
- Suppression de l'icône `Monitor` inutilisée dans les imports

### Tests
- 252 tests passent avec succès
- Les composants ContainerTerminal et ContainerLogs sont stubbés dans les tests unitaires pour éviter les erreurs xterm.js (besoin de DOM complet)
