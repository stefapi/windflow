# STORY-471 : Refonte Page Login avec Design Unifié et Nouveau Logo

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace
**Priorité :** Haute
**Type :** Improvement

## Description

En tant qu'utilisateur WindFlow, je veux une page de login au design cohérent avec l'application principale et un logo moderne, afin d'avoir une expérience visuelle professionnelle et unifiée dès le premier contact avec l'application.

## Contexte

La page de login actuelle utilise un gradient violet/bleu (`#667eea` → `#764ba2`) qui est complètement déconnecté du thème sombre de l'application principale (`#0c0e14`). Le logo actuel est un simple emoji `🌀` dans la sidebar et un SVG basique dans le SplashScreen. Cette incohérence visuelle nuit à l'expérience utilisateur et à l'image de marque de WindFlow.

## Critères d'acceptation (AC)

### AC-1 : Thème sombre unifié
- [x] Le fond de la page login utilise le même thème sombre que la sidebar (`#0c0e14`)
- [x] Les couleurs d'accent sont alignées sur le design system (`#4f8ff7`, `#3b82f6`)
- [x] La carte de login utilise des bordures subtiles (`#252838`) et un fond semi-transparent

### AC-2 : Nouveau logo WindFlow
- [x] Un composant `WindFlowLogo.vue` est créé avec un SVG moderne
- [x] Le logo représente le concept "vent/flow" avec une spirale/tourbillon stylisée
- [x] Le logo supporte une animation subtile (rotation lente ou pulsation) désactivable via prop
- [x] Le logo est disponible en plusieurs tailles (small, medium, large) via props
- [x] Le composant est réutilisable dans Login, SidebarNav et SplashScreen

### AC-3 : Formulaire de login stylisé
- [x] Les inputs utilisent le thème sombre avec bordures subtiles
- [x] Le bouton de login a un gradient et un effet hover moderne
- [x] Les labels et textes sont dans la couleur `#e2e5f0`
- [x] Le formulaire est centré et responsive

### AC-4 : Intégration du logo
- [x] Le nouveau logo remplace l'emoji `🌀` dans SidebarNav
- [x] Le nouveau logo est utilisé dans la page Login avec animation
- [x] Le nouveau logo est utilisé dans SplashScreen (remplace le SVG existant)

### AC-5 : Animations et transitions
- [x] Animation d'entrée fluide pour la carte de login
- [x] Animation subtile du logo (pulsation 4s avec glow)
- [x] Transitions hover sur les éléments interactifs

### AC-6 : Responsive design
- [x] La page s'adapte aux écrans mobiles (< 768px)
- [x] Le logo et le formulaire restent lisibles sur petit écran
- [x] Les inputs sont utilisables sur tactile

## Analyse d'impact

### Fichiers modifiés
| Fichier | Impact | Description |
|---------|--------|-------------|
| `frontend/src/views/Login.vue` | Majeur | Refonte complète du template et des styles |
| `frontend/src/components/SidebarNav.vue` | Mineur | Remplacement emoji par composant logo |
| `frontend/src/components/SplashScreen.vue` | Mineur | Remplacement SVG par composant logo |

### Nouveaux fichiers
| Fichier | Description |
|---------|-------------|
| `frontend/src/components/WindFlowLogo.vue` | Composant logo réutilisable |

### Dépendances
- Aucune nouvelle dépendance requise
- Utilise Element Plus existant pour les inputs/boutons

## Plan de non-régression

### Tests à effectuer
1. **Fonctionnel**
   - [ ] Le login fonctionne correctement (credentials valides/invalides)
   - [ ] La redirection après login fonctionne
   - [ ] Le message d'erreur s'affiche correctement

2. **Visuel**
   - [ ] Vérifier l'affichage sur Chrome, Firefox, Safari
   - [ ] Vérifier le responsive (desktop, tablette, mobile)
   - [ ] Vérifier les animations (pas de saccades)

3. **Accessibilité**
   - [ ] Contraste couleurs suffisant (WCAG AA)
   - [ ] Navigation clavier fonctionnelle
   - [ ] Labels accessibles

### Points d'attention
- Le composant logo doit être testé dans les 3 contextes d'utilisation
- Vérifier que l'animation du logo ne perturbe pas la saisie du formulaire

## Estimation

**Complexité :** Moyenne
**Effort estimé :** 4-6 heures

| Tâche | Durée |
|-------|-------|
| Création composant WindFlowLogo.vue | 2h |
| Refonte Login.vue | 2h |
| Intégration SidebarNav + SplashScreen | 1h |
| Tests et ajustements | 1h |

## Notes d'implémentation

**Date :** 15/03/2026

### Fichiers créés
- `frontend/src/components/WindFlowLogo.vue` : Composant logo SVG réutilisable avec props `size` (small/medium/large), `animate` (pulsation), `showText` (texte "WindFlow")
- `frontend/tests/unit/components/WindFlowLogo.spec.ts` : 17 tests unitaires couvrant tous les props et l'accessibilité
- `frontend/tests/unit/views/Login.spec.ts` : 14 tests unitaires couvrant thème, logo, formulaire et structure

### Fichiers modifiés
- `frontend/src/views/Login.vue` : Refonte complète — fond sombre `#0c0e14`, carte semi-transparente avec backdrop-filter, particules de fond animées, inputs dark theme via `:deep()`, bouton gradient bleu, animation d'entrée fadeIn
- `frontend/src/components/SidebarNav.vue` : Remplacement emoji `🌀` par composant `WindFlowLogo` (size="small", showText dynamique selon état collapsed)
- `frontend/src/components/SplashScreen.vue` : Remplacement SVG inline par composant `WindFlowLogo` (size="large", animate=true), fond sombre unifié

### Décisions techniques
- **SVG avec gradients** : Utilisation de `linearGradient` pour des couleurs riches dans le logo (3 gradients : main, light, accent)
- **Animation pulsation** : Préféré à une rotation pour le logo car plus subtil et non distrayant pendant la saisie du formulaire
- **Backdrop-filter** : Effet de flou derrière la carte de login pour un rendu glassmorphism élégant
- **Particules de fond** : 3 divs avec blur et animation float pour donner de la profondeur sans surcharger le GPU
- **Override Element Plus** : Utilisation de `:deep(.el-input__wrapper)` pour styler les inputs en thème sombre

### Tests
- `WindFlowLogo.spec.ts` : 17/17 tests passent ✅
- `Login.spec.ts` : 14/14 tests passent ✅
- `SidebarNav.spec.ts` : 22/22 tests passent (non-régression) ✅
- Total : 53/53 tests passent
- Build Vite : ✅

---

**Créé le :** 15/03/2026
**Terminé le :** 15/03/2026
