# WindFlow Design System

> Référence : EPIC-008 — Homogénéisation des couleurs UnoCSS  
> Source de vérité : `frontend/src/styles/theme.css` + `frontend/uno.config.ts`  
> Dernière mise à jour : 2026-03-23

## Sommaire

1. [Introduction](#1-introduction)
2. [Typographie](#2-typographie)
3. [Variables CSS (tokens)](#3-variables-css-tokens)
4. [Raccourcis UnoCSS](#4-raccourcis-unocss)
5. [Overrides Element Plus](#5-overrides-element-plus)
6. [Règles de migration](#6-règles-de-migration)
7. [Couleurs statiques interdites](#7-couleurs-statiques-interdites)
8. [Exemples avant / après](#8-exemples-avant--après)
9. [Utilitaires TypeScript](#9-utilitaires-typescript)

---

## 1. Introduction

WindFlow utilise un système de design tokens basé sur des **variables CSS custom properties** définies dans `frontend/src/styles/theme.css`. Ces variables supportent automatiquement les thèmes **dark** (défaut) et **light** (via `[data-theme='light']`).

Les tokens WCAG AA ont été vérifiés :
- `text-primary` sur `bg-primary` : **12,63:1** ✓
- `text-secondary` sur `bg-primary` : **5,01:1** ✓
- `accent` sur `bg-primary` : **4,68:1** ✓

### Principe

- **Jamais de couleur statique** (`#hex`, `rgb()`, `rgba()`) dans le code source.
- **Toujours** utiliser une variable CSS (`var(--color-xxx)`) ou un raccourci UnoCSS.
- Pour les bibliothèques JS comme **ECharts**, utiliser le helper `getCssVar()` / `getCssVarRgba()` depuis `@/utils/css`.

---

## 2. Typographie

Les tokens typographiques sont définis dans `:root` de `theme.css` et sont indépendants du thème.

### 2.1 Polices

| Variable | Valeur | Usage |
|---|---|---|
| `--font-sans` | `Inter`, IBM Plex Sans, system-ui… | Interface utilisateur (textes, labels, boutons) |
| `--font-mono` | `JetBrains Mono`, Fira Code, Consolas… | Code, terminal, logs |

Les polices **Inter** (400/500/600) et **JetBrains Mono** (400/500) sont auto-hébergées dans `frontend/src/assets/fonts/`.

### 2.2 Tailles

| Variable | Valeur | Pixels équivalents |
|---|---|---|
| `--text-xs` | `0.75rem` | 12px |
| `--text-sm` | `0.875rem` | 14px |
| `--text-base` | `1rem` | 16px |
| `--text-lg` | `1.125rem` | 18px |
| `--text-xl` | `1.25rem` | 20px |
| `--text-2xl` | `1.5rem` | 24px |
| `--text-3xl` | `1.875rem` | 30px |

### 2.3 Hauteurs de ligne

| Variable | Valeur |
|---|---|
| `--leading-tight` | `1.25` |
| `--leading-normal` | `1.5` |
| `--leading-relaxed` | `1.625` |

### 2.4 Graisses

| Variable | Valeur |
|---|---|
| `--font-normal` | `400` |
| `--font-medium` | `500` |
| `--font-semibold` | `600` |

### 2.5 Espacement des lettres

| Variable | Valeur |
|---|---|
| `--tracking-tight` | `-0.025em` |
| `--tracking-normal` | `0` |
| `--tracking-wide` | `0.025em` |

---

## 3. Variables CSS (tokens)

### 3.1 Backgrounds

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-bg-primary` | `#0f1117` | `#f0f4ff` | Fond principal de la page |
| `--color-bg-secondary` | `#151821` | `#e8eeff` | Fond des zones secondaires |
| `--color-bg-card` | `#1a1d27` | `#f5f8ff` | Fond des cartes / panels |
| `--color-bg-card-alpha` | `rgba(26,29,39,0.85)` | `rgba(245,248,255,0.92)` | Cartes avec effet glass |
| `--color-bg-elevated` | `#1c1f2b` | `#dce6fb` | Fond surélevé (headers, toolbar) |
| `--color-bg-hover` | `#252838` | `#c7d7f7` | État hover des éléments |
| `--color-bg-input` | `#1c1f2b` | `#f8faff` | Fond des champs de saisie |

> **Note thème light :** Les fonds light utilisent une teinte bleue cohérente (pas blanc pur) pour maintenir l'harmonie visuelle avec l'accent bleu.

### 3.2 Texte

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-text-primary` | `#e1e4eb` | `#0f172a` | Texte principal |
| `--color-text-secondary` | `#8b8fa3` | `#334155` | Texte secondaire / labels |
| `--color-text-muted` | `#5a5f78` | `#4e6080` | Texte atténué / désactivé |
| `--color-text-placeholder` | `#5a5f78` | `#607898` | Placeholder des inputs |

### 3.3 Bordures

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-border` | `#2a2d37` | `#bfcef5` | Bordure standard |
| `--color-border-light` | `#252838` | `#d4e0fb` | Bordure légère |
| `--color-border-focus` | `#4f8ff7` | `#2563eb` | Bordure focus (inputs) |

### 3.4 Couleur d'accent

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-accent` | `#3b82f6` | `#1d4ed8` | Actions principales, liens actifs |
| `--color-accent-hover` | `#60a5fa` | `#1e40af` | État hover de l'accent |
| `--color-accent-light` | `rgba(59,130,246,0.15)` | `rgba(29,78,216,0.12)` | Fond accent semi-transparent |
| `--color-accent-border` | `rgba(59,130,246,0.3)` | `rgba(37,99,235,0.3)` | Bordure accent (tags primary) |

### 3.5 Couleurs de statut

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-success` | `#22c55e` | `#16a34a` | Succès, running, OK |
| `--color-success-light` | `rgba(34,197,94,0.15)` | `rgba(22,163,74,0.1)` | Fond success |
| `--color-success-border` | `rgba(34,197,94,0.3)` | `rgba(22,163,74,0.3)` | Bordure success |
| `--color-error` | `#ef4444` | `#dc2626` | Erreur, danger, critique |
| `--color-error-light` | `rgba(239,68,68,0.15)` | `rgba(220,38,38,0.1)` | Fond erreur |
| `--color-error-border` | `rgba(239,68,68,0.3)` | `rgba(220,38,38,0.3)` | Bordure erreur |
| `--color-warning` | `#f59e0b` | `#d97706` | Avertissement, pending |
| `--color-warning-light` | `rgba(245,158,11,0.15)` | `rgba(217,119,6,0.1)` | Fond warning |
| `--color-warning-border` | `rgba(245,158,11,0.3)` | `rgba(217,119,6,0.3)` | Bordure warning |
| `--color-info` | `#9ca3af` | `#6b7280` | Information, neutre |
| `--color-info-light` | `rgba(107,114,128,0.15)` | `rgba(107,114,128,0.1)` | Fond info |
| `--color-info-border` | `rgba(107,114,128,0.3)` | `rgba(107,114,128,0.2)` | Bordure info |

### 3.6 Ombres

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.3)` | `0 1px 3px rgba(15,40,100,0.08)` | Élévation légère |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.4)` | `0 4px 8px rgba(15,40,100,0.12)` | Carte standard |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.5)` | `0 10px 20px rgba(15,40,100,0.16)` | Modal, dialog |

> **Note thème light :** Les ombres light sont teintées bleues (`rgba(15,40,100,...)`) pour cohérence avec la palette.

### 3.7 Overlay

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-overlay` | `rgba(0,0,0,0.5)` | `rgba(10,20,60,0.45)` | Backdrop modal, sidebar overlay |

### 3.8 Couleurs terminal

Ces variables sont utilisées exclusivement dans le composant `ContainerTerminal`. Style **VS Code Dark** en dark, **VS Code Light** en light.

| Variable | Dark | Light | Description |
|---|---|---|---|
| `--color-terminal-bg` | `#0c0c0c` | `#ffffff` | Fond du terminal |
| `--color-terminal-fg` | `#cccccc` | `#333333` | Texte par défaut |
| `--color-terminal-cursor` | `#ffffff` | `#000000` | Curseur |
| `--color-terminal-selection` | `#264f78` | `#add6ff` | Sélection de texte |
| `--color-terminal-black` | `#000000` | `#000000` | ANSI black |
| `--color-terminal-red` | `#cd3131` | `#cd3131` | ANSI red |
| `--color-terminal-green` | `#0dbc79` | `#008000` | ANSI green |
| `--color-terminal-yellow` | `#e5e510` | `#795e26` | ANSI yellow |
| `--color-terminal-blue` | `#2472c8` | `#0000ff` | ANSI blue |
| `--color-terminal-magenta` | `#bc3fbc` | `#af00db` | ANSI magenta |
| `--color-terminal-cyan` | `#11a8cd` | `#0598bc` | ANSI cyan |
| `--color-terminal-white` | `#e5e5e5` | `#666666` | ANSI white |
| `--color-terminal-bright-*` | Variantes bright | Variantes bright | Couleurs ANSI bright |

### 3.9 Couleurs logs

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-log-error` | `#f48771` | `#cd3131` | Ligne d'erreur |
| `--color-log-warning` | `#dcdcaa` | `#795e26` | Ligne de warning |
| `--color-log-info` | `#4ec9b0` | `#0598bc` | Ligne d'info |
| `--color-log-debug` | `#858585` | `#6b7280` | Ligne de debug |
| `--color-log-line-number` | `#858585` | `#6b7280` | Numéros de ligne |
| `--color-log-error-bg` | `rgba(244,135,113,0.15)` | `rgba(205,49,49,0.1)` | Fond ligne erreur |
| `--color-log-warning-bg` | `rgba(220,200,170,0.15)` | `rgba(121,94,38,0.1)` | Fond ligne warning |
| `--color-log-hover-bg` | `rgba(255,255,255,0.05)` | `rgba(0,0,0,0.03)` | Hover sur ligne |

### 3.10 Blocs de code

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-code-bg` | `#1e1e1e` | `#f5f5f5` | Fond des blocs `<pre>`, `<code>` |
| `--color-code-fg` | `#d4d4d4` | `#333333` | Texte des blocs de code |

---

## 4. Raccourcis UnoCSS

Les raccourcis sont définis dans `frontend/uno.config.ts`. Ils utilisent les tokens CSS définis ci-dessus.

### 4.1 Layout

| Shortcut | Classes équivalentes |
|---|---|
| `flex-center` | `flex items-center justify-center` |
| `flex-between` | `flex items-center justify-between` |
| `flex-col-center` | `flex flex-col items-center justify-center` |

### 4.2 Cartes

| Shortcut | Usage |
|---|---|
| `card` | Carte standard avec fond `bg-card`, bordure, ombre |
| `card-elevated` | Carte avec fond `bg-elevated`, ombre plus prononcée |
| `card-interactive` | Carte cliquable avec effet hover |
| `card-header` | En-tête de carte (fond `bg-elevated`) |

### 4.3 Panels

| Shortcut | Usage |
|---|---|
| `panel` | Section avec fond `bg-secondary` |
| `panel-elevated` | Section avec fond `bg-elevated` |

### 4.4 Boutons

| Shortcut | Sémantique |
|---|---|
| `btn-primary` | Action principale (accent) |
| `btn-secondary` | Action secondaire (elevated + bordure) |
| `btn-success` / `btn-warning` / `btn-danger` | Boutons de statut colorés |
| `btn-ghost` | Bouton transparent |

### 4.5 Textes

| Shortcut | Usage |
|---|---|
| `text-heading` | Titre / en-tête (primary + semibold) |
| `text-body` | Texte courant |
| `text-muted` | Texte atténué |
| `text-label` | Label small (muted + sm) |

### 4.6 Badges de statut

| Shortcut | Couleur |
|---|---|
| `badge-success` | Vert |
| `badge-warning` | Orange |
| `badge-error` | Rouge |
| `badge-info` | Gris |

### 4.7 Tables

| Shortcut | Usage |
|---|---|
| `table-container` | Wrapper de tableau (card + overflow hidden) |
| `table-header` | En-tête de tableau (elevated) |
| `table-row` | Ligne avec hover |
| `table-row-alternate` | Ligne alternante (striped) |

### 4.8 Logs & Terminal

| Shortcut | Usage |
|---|---|
| `logs-container` | Wrapper du composant logs (mono, bordure) |
| `logs-header` | En-tête du panneau logs |
| `logs-content` | Corps scrollable des logs |
| `logs-footer` | Pied de page du panneau |
| `log-error` / `log-warning` / `log-info` / `log-debug` | Colorisation des lignes |
| `log-line-number` | Numéro de ligne (non sélectionnable) |
| `terminal-container` | Zone du terminal xterm.js |
| `terminal-wrapper` | Conteneur global terminal |
| `terminal-toolbar` | Barre d'outils du terminal |
| `terminal-status-connected` | Indicateur vert (connecté, pulsation) |
| `terminal-status-connecting` | Indicateur orange (connexion en cours) |
| `terminal-status-disconnected` | Indicateur gris (déconnecté) |

### 4.9 Blocs de code

| Shortcut | Usage |
|---|---|
| `code-block` | Bloc de code formaté (`bg-code`) |
| `code-console` | Bloc style terminal (`bg-terminal`) |
| `code-inline` | Code inline dans du texte |

### 4.10 Page de login

| Shortcut | Usage |
|---|---|
| `login-page` | Fond pleine page centré |
| `login-card` | Carte login avec glassmorphism |
| `login-btn` | Bouton de connexion avec dégradé |
| `login-particle` | Particule décorative d'arrière-plan |

### 4.11 Classes arbitraires UnoCSS

Pour des cas non couverts par les shortcuts, utiliser la syntaxe arbitraire avec les variables CSS :

```html
<!-- Fond avec variable -->
<div class="bg-[var(--color-bg-elevated)]">...</div>

<!-- Texte avec variable -->
<span class="text-[var(--color-accent)]">...</span>

<!-- Bordure avec variable -->
<div class="border border-[var(--color-border)]">...</div>

<!-- Variables typographiques -->
<p class="text-[var(--text-sm)] font-[var(--font-semibold)]">...</p>
```

---

## 5. Overrides Element Plus

`theme.css` surcharge les variables internes d'Element Plus pour garantir la cohérence visuelle dans les deux thèmes. Ces règles sont **automatiquement appliquées** — aucune action supplémentaire n'est nécessaire côté développeur.

### 5.1 Variables globales El+

Mappages définis dans `:root` / `[data-theme='light']` :

| Variable El+ | Token WindFlow |
|---|---|
| `--el-bg-color` | `--color-bg-primary` |
| `--el-bg-color-overlay` | `--color-bg-card` |
| `--el-text-color-primary` | `--color-text-primary` |
| `--el-text-color-secondary` | `--color-text-secondary` |
| `--el-text-color-placeholder` | `--color-text-placeholder` |
| `--el-border-color` | `--color-border` |
| `--el-fill-color` | `--color-bg-elevated` |
| `--el-color-primary` | `--color-accent` |
| `--el-color-success` | `--color-success` |
| `--el-color-warning` | `--color-warning` |
| `--el-color-danger` | `--color-error` |
| `--el-color-info` | `--color-info` |

### 5.2 Composants surchargés

Les composants suivants sont intégralement thémés via `theme.css` :

| Composant | Notes |
|---|---|
| `el-table` | Cellules, header, lignes striped, colonnes fixes |
| `el-card` | Header, body |
| `el-dialog` | Header, body, footer, tous les inputs internes |
| `el-drawer` | Fond et texte |
| `el-button` | Default, hover, disabled (nécessite `!important`) |
| `el-menu` | Background, items, active, hover |
| `el-tag` | Toutes variantes : default, success, warning, danger, info, primary, dark, plain |
| `el-input` | Wrapper, inner, placeholder, disabled, sizes |
| `el-textarea` | Border, focus, disabled |
| `el-select` | Wrapper, dropdown, options, groupes |
| `el-input-number` | Boutons +/−, inner |
| `el-switch` | Track, dot, checked, disabled, label |
| `el-checkbox` | Inner, checked, indeterminate, disabled |
| `el-radio` | Inner |
| `el-tabs` | Nav, active bar, items, disabled |
| `el-pagination` | Background, couleurs |
| `el-form` | Labels |
| `el-popover` | Fond, bordure |
| `el-dropdown-menu` | Items, hover |
| `el-message-box` | Fond, bordure |
| `el-breadcrumb` | Liens, séparateur, hover |
| `el-descriptions` | Labels, cellules, header |
| `el-tree` | Items, current, hover |
| `el-progress` | Track, inner, statuts, striped |
| `el-skeleton` | Gradient animé (adapté thème light) |
| `el-alert` | Tous types (info, success, warning, error, dark) |
| `el-tooltip` | Popper dark |
| `el-loading` | Mask |
| `el-empty` | Description |
| `el-popper` | is-light / is-dark |
| `el-date-picker` | Input, popper, cellules |

> **Règle technique :** Certains composants El+ utilisent des variables CSS au niveau de l'élément (même spécificité que `:root`), ce qui impose l'usage de `!important` pour les surcharges dans `theme.css`. C'est documenté dans le CSS source.

---

## 6. Règles de migration

### Règle 1 — CSS `<style scoped>` : variables CSS

```css
/* ❌ INTERDIT */
.my-element { color: #f56c6c; background: #1a1d27; }

/* ✅ CORRECT */
.my-element { color: var(--color-error); background: var(--color-bg-card); }
```

### Règle 2 — Templates Vue : classes UnoCSS

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

Les bibliothèques de visualisation nécessitent des valeurs résolues (pas des chaînes `var(...)`). Utiliser les helpers de `@/utils/css` :

```typescript
import { getCssVar, getCssVarRgba } from '@/utils/css'

const accentColor = getCssVar('--color-accent')          // → '#3b82f6'
const textColor   = getCssVar('--color-text-primary')    // → '#e1e4eb'
const accentAlpha = getCssVarRgba('--color-accent', 0.4) // → 'rgba(59, 130, 246, 0.4)'
```

```typescript
// ❌ INTERDIT — figé en dark mode
colorStops: [
  { offset: 0, color: 'rgba(64, 158, 255, 0.4)' },
  { offset: 1, color: 'rgba(64, 158, 255, 0.05)' },
]

// ✅ CORRECT — suit le thème courant
colorStops: [
  { offset: 0, color: getCssVarRgba('--color-accent', 0.4) },
  { offset: 1, color: getCssVarRgba('--color-accent', 0.05) },
]
```

> **Note :** `getCssVar()` et `getCssVarRgba()` lisent les valeurs au moment de l'appel. Dans un `computed()`, ils seront réévalués si les dépendances réactives changent. Pour suivre le changement de thème, écouter `watch(currentTheme, ...)` si nécessaire.

---

## 7. Couleurs statiques interdites

Les valeurs suivantes sont **bannies** du code source (hors `theme.css` et `uno.config.ts`) :

### Anciens bleus El+ (→ `--color-accent`)
- `#409EFF`, `#409eff`
- `rgba(64, 158, 255, ...)`, `rgb(64, 158, 255)`

### Anciens verts El+ (→ `--color-success`)
- `#67C23A`, `#67c23a`
- `rgba(103, 194, 58, ...)`

### Anciens oranges/warnings El+ (→ `--color-warning`)
- `#E6A23C`, `#e6a23c`
- `rgba(230, 162, 60, ...)`

### Anciens rouges El+ (→ `--color-error`)
- `#F56C6C`, `#f56c6c`
- `rgba(245, 108, 108, ...)`

### Anciens gris El+ (→ `--color-info` ou variables texte)
- `rgba(144, 147, 153, ...)`

### Bordures statiques (→ `--color-border`)
- `#e0e0e0`, `#ddd`, `#d4d7de`

### Fonds statiques (→ variables `--color-bg-*`)
- `#f5f5f5`, `#f0f0f0`, `#1a1d27`, `#1c1f2b` (hardcodés)

### Overlays statiques (→ `--color-overlay`)
- `rgba(0, 0, 0, 0.5)`, `rgba(0, 0, 0, 0.4)` utilisés comme backdrop

---

## 8. Exemples avant / après

### 8.1 Composant Vue — style scoped

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

### 8.2 Layout overlay

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

### 8.3 ECharts — graphique avec gradient

```typescript
// ❌ AVANT — couleurs figées dark mode
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

### 8.4 Badge inline avec UnoCSS

```vue
<!-- ❌ AVANT — classe CSS avec couleur statique -->
<span class="nav-badge">NEW</span>
<style scoped>
.nav-badge { background-color: var(--color-accent); color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 10px; }
</style>

<!-- ✅ APRÈS — classes UnoCSS pures avec variable -->
<span class="bg-[var(--color-accent)] text-white text-[11px] px-1.5 py-0.5 rounded-xl">NEW</span>
```

### 8.5 Ombre au hover

```css
/* ❌ AVANT */
.clickable-card:hover { box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); }

/* ✅ APRÈS */
.clickable-card:hover { box-shadow: var(--shadow-md); }
```

### 8.6 Typographie

```css
/* ❌ AVANT */
.section-title { font-size: 18px; font-weight: 600; }

/* ✅ APRÈS */
.section-title { font-size: var(--text-lg); font-weight: var(--font-semibold); }
```

---

## 9. Utilitaires TypeScript

### `getCssVar(name)`

```typescript
// frontend/src/utils/css.ts
getCssVar('--color-accent')         // → '#3b82f6' (dark) ou '#1d4ed8' (light)
getCssVar('--color-text-primary')   // → '#e1e4eb' (dark) ou '#0f172a' (light)
getCssVar('--color-success')        // → '#22c55e' (dark) ou '#16a34a' (light)
```

### `getCssVarRgba(varName, opacity)`

```typescript
// Construit rgba() à partir d'une variable CSS hex
getCssVarRgba('--color-accent', 0.4)    // → 'rgba(59, 130, 246, 0.4)'
getCssVarRgba('--color-success', 0.15)  // → 'rgba(34, 197, 94, 0.15)'
getCssVarRgba('--color-error', 0.3)     // → 'rgba(239, 68, 68, 0.3)'
```

> **Limitation :** `getCssVarRgba()` fonctionne uniquement avec des variables CSS dont la valeur est une couleur hex (`#rrggbb` ou `#rgb`). Pour des variables déjà en `rgba()`, utiliser directement `getCssVar()`.
