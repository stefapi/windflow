# STORY-423 : Composants de base harmonisés (badges, barres, icônes)

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant que développeur frontend, je veux un kit de composants de base harmonisés afin de construire les nouvelles vues avec une cohérence visuelle et sans duplication de code.

## Critères d'acceptation (AC)
- [ ] AC 1 : Composant `StatusBadge.vue` — affiche un badge coloré selon le statut (running/stopped/error/deploying) avec icône et label
- [ ] AC 2 : Composant `ResourceBar.vue` — barre de progression avec couleur dynamique (vert < 60%, orange < 85%, rouge ≥ 85%) pour CPU/RAM/disque
- [ ] AC 3 : Composant `ActionButtons.vue` — groupe de boutons d'actions inline (start/stop/restart/logs/supprimer) avec icônes et tooltips
- [ ] AC 4 : Composant `CounterCard.vue` — tuile compteur cliquable (nombre + label + icône + lien)
- [ ] AC 5 : Tous les composants utilisent les tokens UnoCSS du design system (pas de couleur en dur)
- [ ] AC 6 : Chaque composant a des props typées en TypeScript strict
- [ ] AC 7 : Chaque composant a au moins un test Vitest (rendu, props, événements)
- [ ] AC 8 : Les composants sont documentés (JSDoc ou commentaire d'usage)

## État d'avancement technique
- [ ] Création `frontend/src/components/ui/StatusBadge.vue`
- [ ] Création `frontend/src/components/ui/ResourceBar.vue`
- [ ] Création `frontend/src/components/ui/ActionButtons.vue`
- [ ] Création `frontend/src/components/ui/CounterCard.vue`
- [ ] Types TypeScript pour les props de chaque composant
- [ ] Tests Vitest pour chaque composant
- [ ] Documentation d'usage (commentaires ou storybook minimal)
