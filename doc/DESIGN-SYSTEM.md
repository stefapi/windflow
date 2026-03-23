# WindFlow Design System — Système de Couleurs

> Référence : EPIC-008 — Homogénéisation des couleurs UnoCSS  
> Dernière mise à jour : 2026-03-23

## Sommaire

1. [Introduction](#1-introduction)
2. [Variables CSS (tokens)](#2-variables-css-tokens)
3. [Raccourcis UnoCSS](#3-raccourcis-unocss)
4. [Règles de migration](#4-règles-de-migration)
5. [Couleurs statiques interdites](#5-couleurs-statiques-interdites)
6. [Exemples avant / après](#6-exemples-avant--après)

---

## 1. Introduction

WindFlow utilise un système de design tokens basé sur des **variables CSS custom properties** définies dans `frontend/src/styles/theme.css`. Ces variables supportent automatiquement les thèmes **dark** (défaut) et **light** (via `[data-theme='light']`).

### Principe

- **Jamais de couleur statique** (`#hex`, `rgb()`, `rgba()`) dans le code source.
- **Toujours** utiliser une variable CSS (`var(--color-xxx)`) ou un raccourci UnoCSS.
- Pour les bibliothèques JS comme **ECharts**, utiliser le helper `getCssVar()` / `getCssVarRgba()` depuis `@/utils/css`.

---

## 2. Variables CSS (tokens)

### 2.1 Backgrounds

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-bg-primary` | `#0f1117` | `#ffffff` | Fond principal de la page |
| `--color-bg-secondary` | `#151821` | `#f8fafc` | Fond des zones secondaires |
| `--color-bg-card` | `#1a1d27` | `#ffffff` | Fond des cartes / panels |
| `--color-bg-card-alpha` | `rgba(26,29,39,0.85)` | `rgba(255,255,255,0.85)` | Cartes avec effet glass |
| `--color-bg-elevated` | `#1c1f2b` | `#f1f5f9` | Fond surélevé (headers, toolbar) |
| `--color-bg-hover` | `#252838` | `#e2e8f0` | État hover des éléments |
| `--color-bg-input` | `#1c1f2b` | `#ffffff` | Fond des champs de saisie |

### 2.2 Texte

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-text-primary` | `#e1e4eb` | `#1e293b` | Texte principal |
| `--color-text-secondary` | `#8b8fa3` | `#64748b` | Texte secondaire / labels |
| `--color-text-muted` | `#5a5f78` | `#94a3b8` | Texte atténué / désactivé |
| `--color-text-placeholder` | `#5a5f78` | `#94a3b8` | Placeholder des inputs |

### 2.3 Bordures

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-border` | `#2a2d37` | `#e2e8f0` | Bordure standard |
| `--color-border-light` | `#252838` | `#f1f5f9` | Bordure légère |
| `--color-border-focus` | `#4f8ff7` | `#3b82f6` | Bordure focus (inputs) |

### 2.4 Couleur d'accent

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-accent` | `#3b82f6` | `#2563eb` | Actions principales, liens actifs |
| `--color-accent-hover` | `#60a5fa` | `#1d4ed8` | État hover de l'accent |
| `--color-accent-light` | `rgba(59,130,246,0.15)` | `rgba(37,99,235,0.1)` | Fond accent semi-transparent |

### 2.5 Couleurs de statut

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-success` | `#22c55e` | `#16a34a` | Succès, running, OK |
| `--color-success-light` | `rgba(34,197,94,0.15)` | `rgba(22,163,74,0.1)` | Fond success |
| `--color-error` | `#ef4444` | `#dc2626` | Erreur, danger, critique |
| `--color-error-light` | `rgba(239,68,68,0.15)` | `rgba(220,38,38,0.1)` | Fond erreur |
| `--color-warning` | `#f59e0b` | `#d97706` | Avertissement, pending |
| `--color-warning-light` | `rgba(245,158,11,0.15)` | `rgba(217,119,6,0.1)` | Fond warning |
| `--color-info` | `#6b7280` | `#6b7280` | Information, neutre |
| `--color-info-light` | `rgba(107,114,128,0.15)` | `rgba(107,114,128,0.1)` | Fond info |

### 2.6 Ombres

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.3)` | `0 1px 2px rgba(0,0,0,0.05)` | Élévation légère |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.4)` | `0 4px 6px rgba(0,0,0,0.1)` | Carte standard |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.5)` | `0 10px 15px rgba(0,0,0,0.15)` | Modal, dialog |

### 2.7 Overlay

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-overlay` | `rgba(0,0,0,0.5)` | `rgba(0,0,0,0.4)` | Backdrop modal, sidebar overlay |

### 2.8 Couleurs terminal & logs

Ces variables sont utilisées exclusivement dans les composants Terminal et Logs. Leur usage direct dans les vues métier est déconseillé.

| Famille | Variables | Description |
|---|---|---|
| Terminal | `--color-terminal-bg/fg/cursor/selection` + couleurs ANSI | Émulateur de terminal (xterm.js) |
| Logs | `--color-log-error/warning/info/debug/line-number` | Colorisation des niveaux de log |
| Logs bg | `--color-log-error-bg/warning-bg/hover-bg` | Fonds semi-transparents lignes de log |
| Code | `--color-code-bg/fg` | Blocs de code (`<pre>`, `<code>`) |

---

## 3. Raccourcis UnoCSS

Les raccourcis sont définis dans `frontend/uno.config.ts`. Ils utilisent les tokens CSS définis ci-dessus.

### 3.1 Layout

| Shortcut | Classes équivalentes |
|---|---|
| `flex-center` | `flex items-center justify-center` |
| `flex-between` | `flex items-center justify-between` |
| `flex-col-center` | `flex flex-col items-center justify-center` |

### 3.2 Cartes

| Shortcut | Usage |
|---|---|
| `card` | Carte standard avec fond, bordure, ombre |
| `card-elevated` | Carte avec fond surélevé |
| `card-interactive` | Carte cliquable avec effet hover |
| `card-header` | En-tête de carte |

### 3.3 Boutons

| Shortcut | Sémantique |
|---|---|
| `btn-primary` | Action principale |
| `btn-secondary` | Action secondaire |
| `btn-success` / `btn-warning` / `btn-danger` | Boutons de statut |
| `btn-ghost` | Bouton transparent |

### 3.4 Badges de statut

| Shortcut | Couleur |
|---|---|
| `badge-success` | Vert (succès) |
| `badge-warning` | Orange (avertissement) |
| `badge-error` | Rouge (erreur) |
| `badge-info` | Gris (information) |

### 3.5 Logs & Terminal

| Shortcut | Usage |
|---|---|
| `logs-container` + `logs-header` + `logs-content` | Composant de visualisation de logs |
| `log-error` / `log-warning` / `log-info` / `log-debug` | Colorisation des lignes |
| `terminal-container` + `terminal-toolbar` | Wrapper du terminal |
| `terminal-status-connected` / `connecting` / `disconnected` | Indicateur de statut |

### 3.6 Classes arbitraires UnoCSS

Pour des cas non couverts par les shortcuts, utiliser la syntaxe arbitraire avec les variables CSS :

```html
<!-- Fond avec variable -->
<div class="bg-[var(--color-bg-elevated)]">...</div>

<!-- Texte avec variable -->
<span class="text-[var(--color-accent)]">...</span>

<!-- Bordure avec variable -->
<div class="border border-[var(--color-border)]">...</div>
```

---

## 4. Règles de migration

### Règle 1 — CSS `<style scoped>` : variables CSS

Dans les blocs `<style scoped>` des composants Vue, remplacer toutes les couleurs statiques par des variables CSS :

```css
/* ❌ INTERDIT */
.my-element { color: #f56c6c; background: #1a1d27; }

/* ✅ CORRECT */
.my-element { color: var(--color-error); background: var(--color-bg-card); }
```

### Règle 2 — Templates Vue : classes UnoCSS

Dans les templates, privilégier les classes UnoCSS ou les classes arbitraires avec variables CSS :

```html
<!-- ❌ INTERDIT -->
<div style="background-color: #1c1f2b">...</div>

<!-- ✅ CORRECT (shortcut) -->
<div class="card">...</div>

<!-- ✅ CORRECT (arbitraire) -->
<div class="bg-[var(--color-bg-elevated)]">...</div>
```

### Règle 3 — Ombres : jamais de `box-shadow` statique

```css
/* ❌ INTERDIT */
.card:hover { box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); }

/* ✅ CORRECT */
.card:hover { box-shadow: var(--shadow-md); }
```

### Règle 4 — Overlays : utiliser `--color-overlay`

```css
/* ❌ INTERDIT */
.backdrop { background-color: rgba(0, 0, 0, 0.5); }

/* ✅ CORRECT */
.backdrop { background-color: var(--color-overlay); }
```

### Règle 5 — ECharts / D3 / bibliothèques JS : `getCssVar()` et `getCssVarRgba()`

Les bibliothèques de visualisation comme ECharts nécessitent des valeurs de couleur résolues (pas des chaînes `var(...)`). Utiliser les helpers de `@/utils/css` :

```typescript
import { getCssVar, getCssVarRgba } from '@/utils/css'

// Lire une couleur CSS au runtime
const accentColor = getCssVar('--color-accent')     // → '#3b82f6'
const textColor   = getCssVar('--color-text-primary') // → '#e1e4eb'

// Construire une couleur rgba depuis une variable CSS hex
const accentAlpha = getCssVarRgba('--color-accent', 0.4)  // → 'rgba(59, 130, 246, 0.4)'
```

Utilisation dans une option ECharts (dans un `computed()`) :

```typescript
// ❌ INTERDIT — couleurs hardcodées, ne changent pas avec le thème
colorStops: [
  { offset: 0, color: 'rgba(64, 158, 255, 0.4)' },
  { offset: 1, color: 'rgba(64, 158, 255, 0.05)' },
]

// ✅ CORRECT — suit le thème, recalculé à chaque rendu
colorStops: [
  { offset: 0, color: getCssVarRgba('--color-accent', 0.4) },
  { offset: 1, color: getCssVarRgba('--color-accent', 0.05) },
]
```

> **Note :** `getCssVar()` et `getCssVarRgba()` lisent les valeurs au moment de l'appel. Dans un `computed()`, ils seront réévalués uniquement si les dépendances réactives changent. Pour une réactivité au changement de thème, écouter `watch(currentTheme, ...)` si nécessaire.

---

## 5. Couleurs statiques interdites

Les valeurs suivantes sont **bannies** du code source (hors fichiers de configuration de thème) :

### Anciens bleus (remplacer par `--color-accent`)
- `#409EFF`, `#409eff`
- `rgba(64, 158, 255, ...)`, `rgb(64, 158, 255)`

### Anciens verts (remplacer par `--color-success`)
- `#67C23A`, `#67c23a`
- `rgba(103, 194, 58, ...)`

### Anciens oranges/warnings (remplacer par `--color-warning`)
- `#E6A23C`, `#e6a23c`
- `rgba(230, 162, 60, ...)`
- `rgba(245, 158, 11, ...)`

### Anciens rouges (remplacer par `--color-error`)
- `#F56C6C`, `#f56c6c`
- `rgba(245, 108, 108, ...)`

### Anciens gris/info (remplacer par `--color-info` ou variables texte)
- `rgba(144, 147, 153, ...)`

### Bordures statiques (remplacer par `--color-border`)
- `#e0e0e0`, `#ddd`, `#d4d7de`

### Fonds statiques (remplacer par variables `--color-bg-*`)
- `#f5f5f5`, `#f0f0f0`, `#1a1d27` (hardcodé)

### Overlays (remplacer par `--color-overlay`)
- `rgba(0, 0, 0, 0.5)`, `rgba(0, 0, 0, 0.4)` utilisés comme backdrop

---

## 6. Exemples avant / après

### 6.1 Composant Vue — style scoped

```vue
<!-- ❌ AVANT -->
<style scoped>
.access-denied .el-icon { color: #f56c6c; }
.workflow-canvas { border: 1px solid #e0e0e0; }
.node-palette { background-color: #f5f5f5; }
</style>

<!-- ✅ APRÈS -->
<style scoped>
.access-denied .el-icon { color: var(--color-error); }
.workflow-canvas { border: 1px solid var(--color-border); }
.node-palette { background-color: var(--color-bg-elevated); color: var(--color-text-primary); }
</style>
```

### 6.2 Layout overlay

```vue
<!-- ❌ AVANT -->
<style scoped>
.sidebar-overlay { background-color: rgba(0, 0, 0, 0.5); }
</style>

<!-- ✅ APRÈS -->
<style scoped>
.sidebar-overlay { background-color: var(--color-overlay); }
</style>
```

### 6.3 ECharts — graphique avec gradient

```typescript
// ❌ AVANT — couleurs figées dans le thème dark
const chartOption = computed(() => ({
  series: [{
    areaStyle: {
      color: {
        type: 'linear',
        colorStops: [
          { offset: 0, color: 'rgba(64, 158, 255, 0.4)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0.05)' },
        ],
      },
    },
    lineStyle: { color: '#409EFF', width: 2 },
  }],
}))

// ✅ APRÈS — suit le thème courant
import { getCssVar, getCssVarRgba } from '@/utils/css'

const chartOption = computed(() => ({
  series: [{
    areaStyle: {
      color: {
        type: 'linear',
        colorStops: [
          { offset: 0, color: getCssVarRgba('--color-accent', 0.4) },
          { offset: 1, color: getCssVarRgba('--color-accent', 0.05) },
        ],
      },
    },
    lineStyle: { color: getCssVar('--color-accent'), width: 2 },
  }],
}))
```

### 6.4 Badge inline avec UnoCSS

```vue
<!-- ❌ AVANT — classe CSS avec couleur statique -->
<span class="nav-badge">NEW</span>
<style scoped>
.nav-badge { background-color: var(--color-accent); color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 10px; }
</style>

<!-- ✅ APRÈS — classes UnoCSS pures avec variable -->
<span class="bg-[var(--color-accent)] text-white text-[11px] px-1.5 py-0.5 rounded-xl">NEW</span>
```

### 6.5 Ombre au hover

```css
/* ❌ AVANT */
.clickable-card:hover { box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); }

/* ✅ APRÈS */
.clickable-card:hover { box-shadow: var(--shadow-md); }
```

---

## 7. Utilitaires TypeScript

### `getCssVar(name)`

```typescript
// frontend/src/utils/css.ts
getCssVar('--color-accent')        // → '#3b82f6' (dark) ou '#2563eb' (light)
getCssVar('--color-text-primary')  // → '#e1e4eb' (dark) ou '#1e293b' (light)
```

### `getCssVarRgba(varName, opacity)`

```typescript
// Construit rgba() à partir d'une variable CSS hex
getCssVarRgba('--color-accent', 0.4)   // → 'rgba(59, 130, 246, 0.4)'
getCssVarRgba('--color-success', 0.15) // → 'rgba(34, 197, 94, 0.15)'
getCssVarRgba('--color-error', 0.3)    // → 'rgba(239, 68, 68, 0.3)'
```

> **Limitation :** `getCssVarRgba()` fonctionne uniquement avec des variables CSS dont la valeur est une couleur hex (`#rrggbb` ou `#rgb`). Pour des variables déjà en `rgba()`, utiliser directement `getCssVar()`.
