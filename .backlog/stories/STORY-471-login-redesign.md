# STORY-471 : Refonte Page Login avec Design Unifié et Nouveau Logo

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace
**Priorité :** Haute
**Type :** Improvement

## Description

En tant qu'utilisateur WindFlow, je veux une page de login au design cohérent avec l'application principale et un logo moderne, afin d'avoir une expérience visuelle professionnelle et unifiée dès le premier contact avec l'application.

## Contexte

La page de login actuelle utilise un gradient violet/bleu (`#667eea` → `#764ba2`) qui est complètement déconnecté du thème sombre de l'application principale (`#0c0e14`). Le logo actuel est un simple emoji `🌀` dans la sidebar et un SVG basique dans le SplashScreen. Cette incohérence visuelle nuit à l'expérience utilisateur et à l'image de marque de WindFlow.

## Critères d'acceptation (AC)

### AC-1 : Thème sombre unifié
- [ ] Le fond de la page login utilise le même thème sombre que la sidebar (`#0c0e14`)
- [ ] Les couleurs d'accent sont alignées sur le design system (`#4f8ff7`, `#3b82f6`)
- [ ] La carte de login utilise des bordures subtiles (`#252838`) et un fond semi-transparent

### AC-2 : Nouveau logo WindFlow
- [ ] Un composant `WindFlowLogo.vue` est créé avec un SVG moderne
- [ ] Le logo représente le concept "vent/flow" avec une spirale/tourbillon stylisée
- [ ] Le logo supporte une animation subtile (rotation lente ou pulsation) désactivable via prop
- [ ] Le logo est disponible en plusieurs tailles (small, medium, large) via props
- [ ] Le composant est réutilisable dans Login, SidebarNav et SplashScreen

### AC-3 : Formulaire de login stylisé
- [ ] Les inputs utilisent le thème sombre avec bordures subtiles
- [ ] Le bouton de login a un gradient et un effet hover moderne
- [ ] Les labels et textes sont dans la couleur `#e2e5f0`
- [ ] Le formulaire est centré et responsive

### AC-4 : Intégration du logo
- [ ] Le nouveau logo remplace l'emoji `🌀` dans SidebarNav
- [ ] Le nouveau logo est utilisé dans la page Login avec animation
- [ ] Le nouveau logo est utilisé dans SplashScreen (remplace le SVG existant)

### AC-5 : Animations et transitions
- [ ] Animation d'entrée fluide pour la carte de login
- [ ] Animation subtile du logo (rotation lente 10s ou pulsation)
- [ ] Transitions hover sur les éléments interactifs

### AC-6 : Responsive design
- [ ] La page s'adapte aux écrans mobiles (< 768px)
- [ ] Le logo et le formulaire restent lisibles sur petit écran
- [ ] Les inputs sont utilisables sur tactile

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

*(À compléter après implémentation)*

---

**Créé le :** 15/03/2026
**Assigné à :** —
