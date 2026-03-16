# STORY-423 : Composants de base harmonisés (badges, barres, icônes)

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant que développeur frontend, je veux un kit de composants de base harmonisés afin de construire les nouvelles vues avec une cohérence visuelle et sans duplication de code.

## Critères d'acceptation (AC)
- [x] AC 1 : Composant `StatusBadge.vue` — affiche un badge coloré selon le statut (running/stopped/error/deploying) avec icône et label
- [x] AC 2 : Composant `ResourceBar.vue` — barre de progression avec couleur dynamique (vert < 60%, orange < 85%, rouge ≥ 85%) pour CPU/RAM/disque
- [x] AC 3 : Composant `ActionButtons.vue` — groupe de boutons d'actions inline (start/stop/restart/logs/supprimer) avec icônes et tooltips
- [x] AC 4 : Composant `CounterCard.vue` — tuile compteur cliquable (nombre + label + icône + lien)
- [x] AC 5 : Tous les composants utilisent les tokens UnoCSS du design system (pas de couleur en dur)
- [x] AC 6 : Chaque composant a des props typées en TypeScript strict
- [x] AC 7 : Chaque composant a au moins un test Vitest (rendu, props, événements)
- [x] AC 8 : Les composants sont documentés (JSDoc ou commentaire d'usage)

## État d'avancement technique
- [x] Création `frontend/src/components/ui/StatusBadge.vue`
- [x] Création `frontend/src/components/ui/ResourceBar.vue`
- [x] Création `frontend/src/components/ui/ActionButtons.vue`
- [x] Création `frontend/src/components/ui/CounterCard.vue`
- [x] Types TypeScript pour les props de chaque composant
- [x] Tests Vitest pour chaque composant (50 tests passants)
- [x] Documentation d'usage (commentaires JSDoc)

## Notes d'implémentation

### Fichiers créés
- `frontend/src/components/ui/StatusBadge.vue` — Badge de statut avec icône et label
- `frontend/src/components/ui/ResourceBar.vue` — Barre de progression avec seuils de couleur
- `frontend/src/components/ui/ActionButtons.vue` — Groupe de boutons d'actions inline
- `frontend/src/components/ui/CounterCard.vue` — Tuile compteur cliquable
- `frontend/src/components/ui/index.ts` — Export centralisé des composants et types

### Fichiers de tests créés
- `frontend/tests/unit/components/ui/StatusBadge.spec.ts` (11 tests)
- `frontend/tests/unit/components/ui/ResourceBar.spec.ts` (16 tests)
- `frontend/tests/unit/components/ui/ActionButtons.spec.ts` (12 tests)
- `frontend/tests/unit/components/ui/CounterCard.spec.ts` (11 tests)

### Décisions techniques
1. **Tokens CSS** : Utilisation des variables CSS du design system (`--color-success`, `--color-warning`, `--color-error`, etc.)
2. **TypeScript strict** : Props entièrement typées avec interfaces exportées pour réutilisation
3. **Animation** : Animation de rotation pour l'icône du statut "deploying"
4. **Formatage** : Formatage automatique des grands nombres (K pour milliers, M pour millions)
5. **RouterLink** : CounterCard supporte la navigation via RouterLink ou reste un div simple

### Commande de test
```bash
cd frontend && pnpm test -- tests/unit/components/ui
```
