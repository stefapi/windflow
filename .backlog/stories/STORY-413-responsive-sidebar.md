# STORY-413 : Responsive sidebar rétractable (tablette)

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur sur tablette, je veux que la sidebar se rétracte en mode icônes afin de libérer de l'espace pour le contenu principal.

## Critères d'acceptation (AC)
- [ ] AC 1 : Sur écrans ≥1024px, la sidebar est affichée en mode complet (icônes + labels)
- [ ] AC 2 : Sur écrans 768px–1023px, la sidebar est rétractée (icônes uniquement) avec tooltip au survol
- [ ] AC 3 : Sur écrans ≤767px, la sidebar est cachée et accessible via un bouton hamburger
- [ ] AC 4 : Un bouton permet de rétractable/déplier la sidebar manuellement sur desktop
- [ ] AC 5 : La préférence d'état de la sidebar est persistée en localStorage
- [ ] AC 6 : Le contenu principal occupe la largeur disponible (transition fluide)

## État d'avancement technique
- [ ] Ajout du mode rétracté au composant SidebarNav (prop `collapsed`)
- [ ] CSS transitions pour l'animation ouverture/fermeture
- [ ] Media queries pour les breakpoints tablette/mobile
- [ ] Bouton hamburger pour mobile
- [ ] Persistence état sidebar en localStorage
- [ ] Tests Vitest responsive (mock window.innerWidth)
