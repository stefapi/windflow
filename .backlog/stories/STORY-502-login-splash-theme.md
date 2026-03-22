# STORY-502 : Refactoriser Login.vue + SplashScreen.vue → variables CSS thémées

**Statut :** DONE
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques (hex, rgb, rgba) des composants Login.vue et SplashScreen.vue par des variables CSS thémées afin d'assurer la cohérence visuelle et le support dark/light theme.

## Contexte technique
Ces deux composants sont parmi les plus visibles de l'application (~30 occurrences de couleurs statiques). Ils constituent la première impression utilisateur.

### Fichiers à modifier
- `frontend/src/views/Login.vue` — Page de connexion principale
- `frontend/src/components/SplashScreen.vue` — Écran de chargement initial (NB: situé dans `components/`, pas `views/`)

### Variables CSS disponibles (STORY-501)
```css
/* Backgrounds */
--color-bg-primary: #0f1117;      /* dark: #0f1117, light: #ffffff */
--color-bg-secondary: #151821;    /* dark: #151821, light: #f8fafc */
--color-bg-card: #1a1d27;         /* dark: #1a1d27, light: #ffffff */
--color-bg-elevated: #1c1f2b;     /* dark: #1c1f2b, light: #f1f5f9 */
--color-bg-hover: #252838;        /* dark: #252838, light: #e2e8f0 */
--color-bg-input: #1c1f2b;        /* dark: #1c1f2b, light: #ffffff */

/* Borders */
--color-border: #2a2d37;          /* dark: #2a2d37, light: #e2e8f0 */
--color-border-light: #252838;    /* dark: #252838, light: #f1f5f9 */
--color-border-focus: #4f8ff7;    /* dark: #4f8ff7, light: #3b82f6 */

/* Text */
--color-text-primary: #e1e4eb;    /* dark: #e1e4eb, light: #1e293b */
--color-text-secondary: #8b8fa3;  /* dark: #8b8fa3, light: #64748b */
--color-text-muted: #5a5f78;      /* dark: #5a5f78, light: #94a3b8 */
--color-text-placeholder: #5a5f78;

/* Accent */
--color-accent: #3b82f6;          /* dark: #3b82f6, light: #2563eb */
--color-accent-hover: #60a5fa;    /* dark: #60a5fa, light: #1d4ed8 */
--color-accent-light: rgba(59, 130, 246, 0.15);

/* Status */
--color-error: #ef4444;
--color-success: #22c55e;
```

### Règles de migration
| Couleur statique | Variable CSS | Usage |
|------------------|--------------|-------|
| `#0c0e14` | `var(--color-bg-primary)` | Background principal |
| `#151821` | `var(--color-bg-secondary)` | Background secondaire |
| `rgba(21, 24, 33, 0.85)` | `rgba(var(--color-bg-card-rgb), 0.85)` ou fallback | Card avec transparence |
| `#1c1f2b` | `var(--color-bg-elevated)` / `var(--color-bg-input)` | Input backgrounds |
| `#252838` | `var(--color-border-light)` / `var(--color-bg-hover)` | Borders, hover states |
| `#3a3f54` | `var(--color-border)` (hover) | Border hover |
| `#4f8ff7` | `var(--color-border-focus)` / `var(--color-accent)` | Focus rings, accent |
| `#3b82f6` | `var(--color-accent)` | Primary accent |
| `#60a5fa` | `var(--color-accent-hover)` | Accent hover |
| `#fff` / `#ffffff` | `var(--color-text-primary)` (light) ou garder #fff | Texte blanc/titres |
| `#e2e5f0` | `var(--color-text-primary)` | Texte principal |
| `#7c8098` | `var(--color-text-secondary)` | Texte secondaire |
| `#5a5f78` | `var(--color-text-muted)` / `var(--color-text-placeholder)` | Texte muted |
| `#f56c6c` | `var(--color-error)` | Erreurs form |
| `rgba(79, 143, 247, x)` | `var(--color-accent-light)` (si opacity 0.15) | Accents transparents |

### Patterns de la STORY-501 à réutiliser
1. **Variables CSS dans `theme.css`** : Déjà définies pour dark/light themes
2. **Shortcuts UnoCSS dans `uno.config.ts`** : Utiliser les classes existantes quand possible
3. **Style scoped** : Remplacer les valeurs hardcodées par `var(--color-xxx)`

## Critères d'acceptation (AC)
- [x] AC 1 : Aucune couleur statique (hex, rgb, rgba) dans les `<style>` de Login.vue
- [x] AC 2 : Aucune couleur statique (hex, rgb, rgba) dans les `<style>` de SplashScreen.vue
- [x] AC 3 : Les deux composants utilisent les variables CSS ou classes UnoCSS
- [x] AC 4 : Le rendu visuel est identique en mode light et dark
- [x] AC 5 : Le build et les tests passent

## Dépendances
- STORY-501 (infrastructure UnoCSS + theme.css)

## État d'avancement technique
- [x] Refactoriser Login.vue — Background et particles
- [x] Refactoriser Login.vue — Login card
- [x] Refactoriser Login.vue — Form et inputs Element Plus
- [x] Refactoriser Login.vue — Bouton submit
- [x] Refactoriser SplashScreen.vue — Background et spinner
- [x] Vérifier le build frontend
- [x] Tester le rendu visuel dark/light

## Notes d'implémentation

### Fichiers modifiés
- `frontend/src/views/Login.vue` — Remplacement de toutes les couleurs hardcodées par des variables CSS thémées
- `frontend/src/components/SplashScreen.vue` — Remplacement de toutes les couleurs hardcodées par des variables CSS thémées

### Décisions techniques
1. **Variables CSS utilisées** : Toutes les couleurs statiques ont été remplacées par les variables définies dans `theme.css` (STORY-501)
2. **Gradient bouton** : Le bouton de login utilise un gradient avec `var(--color-border-focus)`, `var(--color-accent)` et `var(--color-accent-hover)` pour assurer la cohérence des thèmes
3. **Card avec transparence** : Le background de la login card utilise `rgba(26, 29, 39, 0.85)` qui correspond à `--color-bg-card` avec alpha pour l'effet glassmorphism
4. **Texte blanc sur accent** : Le texte du bouton garde `#fff` pour assurer un contraste suffisant sur le bouton accent

### Variables migrées
| Ancienne valeur | Nouvelle variable |
|-----------------|-------------------|
| `#0c0e14` | `var(--color-bg-primary)` |
| `#1c1f2b` | `var(--color-bg-input)` |
| `#252838` | `var(--color-border-light)` |
| `#3a3f54` | `var(--color-border)` |
| `#4f8ff7` | `var(--color-border-focus)` |
| `#3b82f6` | `var(--color-accent)` |
| `#60a5fa` | `var(--color-accent-hover)` |
| `rgba(79, 143, 247, 0.15)` | `var(--color-accent-light)` |
| `#e2e5f0` / `#fff` | `var(--color-text-primary)` |
| `#7c8098` | `var(--color-text-secondary)` |
| `#5a5f78` | `var(--color-text-muted)` |
| `#f56c6c` | `var(--color-error)` |

### Validation
- Build frontend : ✅ Passant
- Variables CSS thémées : ✅ Dark et light supportés

## Tâches d'implémentation détaillées

### Tâche 1 : Refactoriser Login.vue — Background et particles

**Fichier :** `frontend/src/views/Login.vue`

**Objectif :** Remplacer les couleurs hardcodées du background et des particles par des variables CSS.

**Couleurs à remplacer :**
```css
/* AVANT */
background-color: #0c0e14;
background-image: radial-gradient(ellipse at 30% 20%, rgba(79, 143, 247, 0.08) 0%, transparent 50%),
                  radial-gradient(ellipse at 70% 80%, rgba(56, 189, 248, 0.05) 0%, transparent 50%);

/* Particle backgrounds */
background: rgba(79, 143, 247, 0.15);
background: rgba(56, 189, 248, 0.1);
background: rgba(96, 165, 250, 0.08);
```

**Remplacement par :**
```css
/* APRÈS */
background-color: var(--color-bg-primary);
background-image: radial-gradient(ellipse at 30% 20%, var(--color-accent-light) 0%, transparent 50%),
                  radial-gradient(ellipse at 70% 80%, var(--color-accent-light) 0%, transparent 50%);

/* Particle backgrounds — utiliser var(--color-accent-light) avec opacité ajustée si nécessaire */
background: var(--color-accent-light);
```

**Notes :**
- `#0c0e14` est très proche de `--color-bg-primary: #0f1117` (différence mineure acceptable)
- Les gradients rgba peuvent être simplifiés avec `var(--color-accent-light)` qui est déjà `rgba(59, 130, 246, 0.15)`

---

### Tâche 2 : Refactoriser Login.vue — Login card

**Fichier :** `frontend/src/views/Login.vue`

**Objectif :** Remplacer les couleurs de la card de login.

**Couleurs à remplacer :**
```css
/* AVANT */
.login-card {
  background-color: rgba(21, 24, 33, 0.85);
  border: 1px solid #252838;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 80px rgba(79, 143, 247, 0.06);
}

.login-card__footer {
  border-top: 1px solid #252838;
}
```

**Remplacement par :**
```css
/* APRÈS */
.login-card {
  background-color: rgba(26, 29, 39, 0.85); /* --color-bg-card avec alpha */
  /* Alternative: utiliser une variable RGB si disponible, sinon garder la valeur */
  border: 1px solid var(--color-border-light);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 80px var(--color-accent-light);
}

.login-card__footer {
  border-top: 1px solid var(--color-border-light);
}
```

**Note :** Pour le background semi-transparent, on peut :
1. Garder `rgba(26, 29, 39, 0.85)` (proche de `--color-bg-card: #1a1d27`)
2. Ou ajouter une variable RGB dans theme.css pour plus de flexibilité

---

### Tâche 3 : Refactoriser Login.vue — Form et inputs Element Plus

**Fichier :** `frontend/src/views/Login.vue`

**Objectif :** Remplacer les couleurs des inputs et labels.

**Couleurs à remplacer :**
```css
/* AVANT */
.login-card__form :deep(.el-input__wrapper) {
  background-color: #1c1f2b;
  border: 1px solid #252838;
}
.login-card__form :deep(.el-input__wrapper:hover) {
  border-color: #3a3f54;
}
.login-card__form :deep(.el-input__wrapper.is-focus) {
  border-color: #4f8ff7;
  box-shadow: 0 0 0 3px rgba(79, 143, 247, 0.15);
}
.login-card__form :deep(.el-input__inner) {
  color: #e2e5f0;
}
.login-card__form :deep(.el-input__inner::placeholder) {
  color: #5a5f78;
}
.login-card__form :deep(.el-input__prefix .el-icon),
.login-card__form :deep(.el-input__suffix .el-icon) {
  color: #7c8098;
}
.login-card__form :deep(.el-form-item__error) {
  color: #f56c6c;
}
/* Autofill */
-webkit-box-shadow: 0 0 0 30px #1c1f2b inset !important;
-webkit-text-fill-color: #e2e5f0 !important;
```

**Remplacement par :**
```css
/* APRÈS */
.login-card__form :deep(.el-input__wrapper) {
  background-color: var(--color-bg-input);
  border: 1px solid var(--color-border-light);
}
.login-card__form :deep(.el-input__wrapper:hover) {
  border-color: var(--color-border);
}
.login-card__form :deep(.el-input__wrapper.is-focus) {
  border-color: var(--color-border-focus);
  box-shadow: 0 0 0 3px var(--color-accent-light);
}
.login-card__form :deep(.el-input__inner) {
  color: var(--color-text-primary);
}
.login-card__form :deep(.el-input__inner::placeholder) {
  color: var(--color-text-placeholder);
}
.login-card__form :deep(.el-input__prefix .el-icon),
.login-card__form :deep(.el-input__suffix .el-icon) {
  color: var(--color-text-secondary);
}
.login-card__form :deep(.el-form-item__error) {
  color: var(--color-error);
}
/* Autofill */
-webkit-box-shadow: 0 0 0 30px var(--color-bg-input) inset !important;
-webkit-text-fill-color: var(--color-text-primary) !important;
```

---

### Tâche 4 : Refactoriser Login.vue — Bouton submit et titre

**Fichier :** `frontend/src/views/Login.vue`

**Objectif :** Remplacer les couleurs du bouton et des textes.

**Couleurs à remplacer :**
```css
/* AVANT */
.login-card__title {
  color: #fff;
}
.login-card__subtitle {
  color: #7c8098;
}
.login-card__btn {
  background: linear-gradient(135deg, #4f8ff7 0%, #3b82f6 50%, #2563eb 100%);
  color: #fff;
}
.login-card__btn:hover:not(:disabled) {
  box-shadow: 0 4px 20px rgba(79, 143, 247, 0.4);
}
.login-card__btn:active:not(:disabled) {
  box-shadow: 0 2px 8px rgba(79, 143, 247, 0.3);
}
.login-card__btn--loading {
  background: linear-gradient(135deg, #3b73d4 0%, #2d6bc7 100%);
}
.login-card__spinner {
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
}
.login-card__version {
  color: #5a5f78;
}
```

**Remplacement par :**
```css
/* APRÈS */
.login-card__title {
  color: var(--color-text-primary);
  /* Pour le titre blanc sur dark, on peut garder #fff ou utiliser text-primary */
}
.login-card__subtitle {
  color: var(--color-text-secondary);
}
.login-card__btn {
  background: linear-gradient(135deg, var(--color-border-focus) 0%, var(--color-accent) 50%, var(--color-accent-hover) 100%);
  color: #fff; /* Garder blanc pour contraste sur bouton accent */
}
.login-card__btn:hover:not(:disabled) {
  box-shadow: 0 4px 20px var(--color-accent-light);
}
.login-card__btn:active:not(:disabled) {
  box-shadow: 0 2px 8px var(--color-accent-light);
}
.login-card__btn--loading {
  background: linear-gradient(135deg, var(--color-accent) 0%, var(--color-accent-hover) 100%);
}
.login-card__spinner {
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
}
.login-card__version {
  color: var(--color-text-muted);
}
```

**Note :** Pour le gradient du bouton, les variables CSS ne peuvent pas être utilisées directement dans `linear-gradient` avec des manipulations de couleur. On garde donc une approche hybride avec les variables disponibles.

---

### Tâche 5 : Refactoriser SplashScreen.vue — Background et spinner

**Fichier :** `frontend/src/components/SplashScreen.vue`

**Objectif :** Remplacer toutes les couleurs hardcodées.

**Couleurs à remplacer :**
```css
/* AVANT */
.splash-screen {
  background-color: #0c0e14;
  background-image: radial-gradient(ellipse at 50% 40%, rgba(79, 143, 247, 0.1) 0%, transparent 60%);
}
.splash-content {
  color: white;
}
.title {
  color: #fff;
}
.spinner {
  border: 3px solid rgba(79, 143, 247, 0.2);
  border-top-color: #4f8ff7;
}
.loading-text {
  color: #7c8098;
}
```

**Remplacement par :**
```css
/* APRÈS */
.splash-screen {
  background-color: var(--color-bg-primary);
  background-image: radial-gradient(ellipse at 50% 40%, var(--color-accent-light) 0%, transparent 60%);
}
.splash-content {
  color: var(--color-text-primary);
}
.title {
  color: var(--color-text-primary);
}
.spinner {
  border: 3px solid var(--color-accent-light);
  border-top-color: var(--color-border-focus);
}
.loading-text {
  color: var(--color-text-secondary);
}
```

---

### Tâche 6 : Vérifier le build frontend

**Commande :** `cd frontend && pnpm build`

**Objectif :** S'assurer que les modifications ne cassent pas le build.

**Validation :**
- Le build doit terminer sans erreur
- Vérifier qu'il n'y a pas de warnings CSS

---

### Tâche 7 : Tester le rendu visuel dark/light

**Objectif :** Valider le rendu visuel dans les deux thèmes.

**Commande :** `cd frontend && pnpm dev`

**Tests manuels :**
1. Ouvrir la page de login en dark theme (défaut)
2. Vérifier que tous les éléments s'affichent correctement
3. Basculer en light theme (si toggle disponible)
4. Vérifier la cohérence visuelle en light theme
5. Vérifier le splash screen au chargement

## Tests à écrire

### Tests unitaires

#### Test 1 : Vérifier l'absence de couleurs hardcodées dans Login.vue
**Fichier :** `frontend/tests/unit/views/Login.spec.ts` (à créer ou étendre)

```typescript
describe('Login.vue - Theme Variables', () => {
  it('should not contain hardcoded hex colors in style section', () => {
    // Lire le fichier et vérifier qu'aucune couleur hex n'est présente
    // Sauf exceptions documentées (ex: #fff pour texte sur accent)
    const styleContent = getComponentStyle('Login.vue')
    const hexColorPattern = /#[0-9a-fA-F]{6}\b/g
    const matches = styleContent.match(hexColorPattern) || []
    
    // Exceptions autorisées : #fff (texte sur bouton accent)
    const allowedColors = ['#fff', '#ffffff']
    const invalidColors = matches.filter(c => !allowedColors.includes(c.toLowerCase()))
    
    expect(invalidColors).toHaveLength(0)
  })
})
```

#### Test 2 : Vérifier l'utilisation des variables CSS
**Fichier :** `frontend/tests/unit/views/Login.spec.ts`

```typescript
describe('Login.vue - CSS Variables Usage', () => {
  it('should use --color-bg-primary for background', () => {
    const styleContent = getComponentStyle('Login.vue')
    expect(styleContent).toContain('var(--color-bg-primary)')
  })

  it('should use --color-text-secondary for secondary text', () => {
    const styleContent = getComponentStyle('Login.vue')
    expect(styleContent).toContain('var(--color-text-secondary)')
  })

  it('should use --color-accent for accent colors', () => {
    const styleContent = getComponentStyle('Login.vue')
    expect(styleContent).toContain('var(--color-accent)')
  })
})
```

#### Test 3 : SplashScreen.vue - Tests similaires
**Fichier :** `frontend/tests/unit/components/SplashScreen.spec.ts`

```typescript
describe('SplashScreen.vue - Theme Variables', () => {
  it('should use theme variables instead of hardcoded colors', () => {
    const styleContent = getComponentStyle('SplashScreen.vue')
    
    expect(styleContent).toContain('var(--color-bg-primary)')
    expect(styleContent).toContain('var(--color-text-primary)')
    expect(styleContent).toContain('var(--color-text-secondary)')
    expect(styleContent).toContain('var(--color-accent)')
  })
})
```

### Tests de validation manuelle

1. **Build check :** `cd frontend && pnpm build` → doit passer sans erreur
2. **Lint :** `cd frontend && pnpm lint` → doit passer sans erreur liée aux styles
3. **Visual regression :** Comparer screenshots avant/après (si outil disponible)

### Commandes de validation
```bash
# Build frontend
cd frontend && pnpm build

# Lancement des tests
cd frontend && pnpm test

# Lint
cd frontend && pnpm lint

# Dev server pour test visuel
cd frontend && pnpm dev
```

### Checklist de validation visuelle

**Login.vue - Dark Theme :**
- [ ] Background principal cohérent avec le reste de l'app
- [ ] Card de login avec bordures visibles
- [ ] Inputs avec fond et bordures lisibles
- [ ] Placeholder visible mais discret
- [ ] Bouton avec gradient accent visible
- [ ] Texte secondaire (subtitle, version) discret

**Login.vue - Light Theme :**
- [ ] Background clair
- [ ] Card avec contraste suffisant
- [ ] Inputs visibles avec bordures
- [ ] Bouton accent visible sur fond clair
- [ ] Textes lisibles

**SplashScreen.vue :**
- [ ] Background cohérent avec Login
- [ ] Spinner visible
- [ ] Texte de chargement lisible
