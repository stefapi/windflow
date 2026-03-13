# STORY-445 : ContainerDetail — onglet Terminal

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux ouvrir un terminal interactif dans un container depuis l'UI afin d'exécuter des commandes de debug sans passer par SSH + docker exec.

## Critères d'acceptation (AC)
- [ ] AC 1 : Onglet « Terminal » dans ContainerDetail ouvrant un shell interactif dans le container
- [ ] AC 2 : Réutilise le composant existant `ContainerTerminal.vue`
- [ ] AC 3 : Connexion WebSocket vers l'API existante (`/api/v1/websockets/terminal`)
- [ ] AC 4 : Shell par défaut : `/bin/sh` avec fallback, détection de `/bin/bash` si disponible
- [ ] AC 5 : Le terminal s'adapte à la taille du panneau (resize automatique)
- [ ] AC 6 : Bouton « Déconnecter » pour fermer la session proprement
- [ ] AC 7 : Police monospace JetBrains Mono (STORY-422)
- [ ] AC 8 : Le terminal n'est disponible que si le container est en statut running

## État d'avancement technique
- [ ] Intégration de `ContainerTerminal.vue` comme onglet dans ContainerDetail
- [ ] Passage du container_id en prop
- [ ] Gestion du resize terminal (xterm.js fit addon)
- [ ] Désactivation de l'onglet si container stopped
- [ ] Bouton déconnexion
- [ ] Tests Vitest (rendu conditionnel, props)
