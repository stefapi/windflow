# STORY-413 : Responsive sidebar rétractable (tablette)

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur sur tablette, je veux que la sidebar se rétracte en mode icônes afin de libérer de l'espace pour le contenu principal.

## Critères d'acceptation (AC)
- [x] AC 1 : Sur écrans ≥1024px, la sidebar est affichée en mode complet (icônes + labels)
- [x] AC 2 : Sur écrans 768px–1023px, la sidebar est rétractée (icônes uniquement) avec tooltip au survol
- [x] AC 3 : Sur écrans ≤767px, la sidebar est cachée et accessible via un bouton hamburger
- [x] AC 4 : Un bouton permet de rétractable/déplier la sidebar manuellement sur desktop
- [x] AC 5 : La préférence d'état de la sidebar est persistée en localStorage
- [x] AC 6 : Le contenu principal occupe la largeur disponible (transition fluide)

## État d'avancement technique
- [x] Ajout du mode rétracté au composant SidebarNav (prop `collapsed`)
- [x] CSS transitions pour l'animation ouverture/fermeture
- [x] Media queries pour les breakpoints tablette/mobile
- [x] Bouton hamburger pour mobile
- [x] Persistence état sidebar en localStorage
- [x] Tests Vitest responsive (mock window.innerWidth)

## Notes d'implémentation

### Fichiers modifiés/créés
- `frontend/src/composables/useSidebar.ts` (nouveau) - Composable pour gérer l'état responsive de la sidebar
- `frontend/src/components/SidebarNav.vue` (modifié) - Ajout mode rétracté, tooltips, bouton toggle
- `frontend/src/layouts/MainLayout.vue` (modifié) - Largeur dynamique, bouton hamburger, overlay mobile
- `frontend/tests/unit/components/SidebarNav.spec.ts` (modifié) - Tests responsive STORY-413

### Décisions techniques
1. **Composable `useSidebar`** : Gestion centralisée de l'état avec:
   - Détection du type d'écran (mobile/tablet/desktop)
   - Persistence localStorage automatique
   - Actions toggle, openMobile, closeMobile

2. **Breakpoints** :
   - Mobile: < 768px (sidebar cachée, accessible via hamburger)
   - Tablette: 768px - 1023px (sidebar rétractée par défaut)
   - Desktop: ≥ 1024px (sidebar complète, toggle manuel disponible)

3. **CSS Transitions** : Animation fluide de 300ms sur la largeur de la sidebar

4. **Tooltips Element Plus** : Affichés au survol en mode rétracté (disabled sur mobile)

5. **Bug fix mobile (15/03/2026)** : Correction de l'affichage de la sidebar sur mobile
   - **Problème** : La sidebar restait invisible sur mobile même après clic sur le hamburger menu
   - **Cause racine** : `isCollapsed` computed dans `SidebarNav.vue` retournait toujours `true` sur mobile car `effectiveCollapsed` du composable retourne toujours `true` pour les devices mobiles
   - **Solution** : Modification du computed `isCollapsed` pour retourner `!isMobileOpen.value` sur mobile au lieu de `isCollapsed.value`
   ```typescript
   const isCollapsed = computed(() => {
     if (sidebar.isMobile.value) {
       return !sidebar.isMobileOpen.value // Sur mobile, collapsed = fermé
     }
     return sidebar.isCollapsed.value
   })
   ```
   - **Tests** : Correction des tests unitaires (mountComponent déplacé hors du describe, test localStorage simplifié)
