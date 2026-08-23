# WindFlow Design System

> **Statut** : Spécification technique · Implémenté
> **Périmètre** : Référence des design tokens (variables CSS, raccourcis UnoCSS, overrides Element Plus) dérivée du code frontend — LA source de vérité tokens.
> **Référence de fond** : [general_specs — ch. 13 principes UX](../general_specs/13-ui-principes.md) · [ch. 14 maquettes](../general_specs/14-ui-maquettes.md) · [ch. 05 stack technologique](../general_specs/05-stack-technologique.md)
> **Dernière mise à jour** : 2026-08-23 — **refondu vague 6** ([PLAN-REFONTE-TECHNICAL-SPECS.md](../../PLAN-REFONTE-TECHNICAL-SPECS.md)) · traçabilité : G36, G37, P3

> Référence : EPIC-008 — Homogénéisation des couleurs UnoCSS
> Sources de vérité (code, dans cet ordre) : [`frontend/src/styles/theme.css`](../../frontend/src/styles/theme.css) · [`frontend/uno.config.ts`](../../frontend/uno.config.ts) · [`frontend/src/utils/css.ts`](../../frontend/src/utils/css.ts)

Ce document décrit le **COMMENT** du design system (tokens, shortcuts, overrides, migration). Les principes fonctionnels — Mode App / Mode Infra, grammaire UI par famille, navigation de référence — sont définis dans le [ch. 13](../general_specs/13-ui-principes.md) et ne sont pas repris ici.

## Sommaire

1. [Introduction](#1-introduction)
2. [Correspondance palette ch. 13 ↔ tokens réels (G36)](#2-correspondance-palette-ch-13--tokens-réels-g36)
3. [Typographie](#3-typographie)
4. [Variables CSS (tokens)](#4-variables-css-tokens)
5. [Raccourcis UnoCSS](#5-raccourcis-unocss)
6. [Overrides Element Plus](#6-overrides-element-plus)
7. [Règles de migration](#7-règles-de-migration)
8. [Couleurs statiques interdites](#8-couleurs-statiques-interdites)
9. [Exemples avant / après](#9-exemples-avant--après)
10. [Utilitaires TypeScript](#10-utilitaires-typescript)

---

## 1. Introduction

WindFlow utilise un système de design tokens basé sur des **variables CSS custom properties** définies dans [`theme.css`](../../frontend/src/styles/theme.css). Ces variables supportent automatiquement les thèmes **dark** (défaut, `:root` / `[data-theme='dark']`) et **light** (`[data-theme='light']`).

Les tokens WCAG AA ont été vérifiés (valeurs inscrites dans l'en-tête de `theme.css`, STORY-421) :
- `text-primary` sur `bg-primary` : **12,63:1** ✓
- `text-secondary` sur `bg-primary` : **5,01:1** ✓
- `accent` sur `bg-primary` : **4,68:1** ✓

### Principe

- **Jamais de couleur statique** (`#hex`, `rgb()`, `rgba()`) dans le code source (hors fichiers de définition des tokens).
- **Toujours** utiliser une variable CSS (`var(--color-xxx)`) ou un raccourci UnoCSS.
- Pour les bibliothèques JS comme **ECharts**, utiliser le helper `getCssVar()` / `getCssVarRgba()` depuis [`@/utils/css`](../../frontend/src/utils/css.ts).

### Fichiers sources

- [`frontend/src/styles/theme.css`](../../frontend/src/styles/theme.css) — tokens (dark/light), reset, overrides Element Plus ;
- [`frontend/uno.config.ts`](../../frontend/uno.config.ts) — couleurs/ombres/polices thémées + raccourcis UnoCSS ;
- [`frontend/src/utils/css.ts`](../../frontend/src/utils/css.ts) — helpers `getCssVar()` / `getCssVarRgba()`.

---

## 2. Correspondance palette ch. 13 ↔ tokens réels (G36)

> **⚠️ Écart connu (G36)** : la palette « direction esthétique » du [ch. 13](../general_specs/13-ui-principes.md) est **indicative et divergente** des tokens réels du code. **Ce document fait foi** pour toute valeur de token. L'alignement du ch. 13 (ou l'arbitrage inverse) est un sujet general_specs, tracé pour la Roadmap — hors périmètre de cette refonte.

Correspondance constatée (dark theme) — le ch. 13 ne couvre ni light ni les statuts `<light>`/`<border>` :

| Rôle | Ch. 13 (indicatif) | Token réel (`theme.css`) | Valeur réelle dark |
|---|---|---|---|
| Fond principal | `#0c0e14` | `--color-bg-primary` | `#0f1117` |
| Fond carte | `#151821` | `--color-bg-card` | `#1a1d27` |
| Fond hover | `#1c1f2b` | `--color-bg-hover` | `#252838` |
| Bordures | `#252838` | `--color-border` | `#2a2d37` |
| Texte principal | `#e2e5f0` | `--color-text-primary` | `#e1e4eb` |
| Texte secondaire | `#7c8098` | `--color-text-secondary` | `#8b8fa3` |
| Accent bleu | `#4f8ff7` | `--color-accent` | `#3b82f6` |
| Succès | `#34d399` | `--color-success` | `#22c55e` |
| Erreur | `#f87171` | `--color-error` | `#ef4444` |
| Warning | `#fbbf24` | `--color-warning` | `#f59e0b` |
| Info | `#60a5fa` | `--color-info` | `#9ca3af` |

Remarques : plusieurs valeurs du ch. 13 correspondent à d'**autres** tokens réels (`#151821` = `--color-bg-secondary`, `#1c1f2b` = `--color-bg-elevated`, `#4f8ff7` = `--color-border-focus`) — la palette y est proche en esprit mais décalée d'un cran ; le thème light réel (§4) utilise des fonds **bleutés** (`#f0f4ff`, `#e8eeff`…) et un accent `#1d4ed8`, non les neutres et l'accent `#3b82f6` (dark) du ch. 13.

---

## 3. Typographie

Les tokens typographiques sont définis dans `:root` de `theme.css` et sont indépendants du thème.

### 3.1 Polices

| Variable | Valeur | Usage |
|---|---|---|
| `--font-sans` | `Inter`, IBM Plex Sans, system-ui… | Interface utilisateur (textes, labels, boutons) |
| `--font-mono` | `JetBrains Mono`, Fira Code, Consolas… | Code, terminal, logs |

Les polices **Inter** (400/500/600) et **JetBrains Mono** (400/500) sont auto-hébergées dans `frontend/src/assets/fonts/` (`@font-face`, `font-display: swap`).

### 3.2 Tailles

| Variable | Valeur | Pixels équivalents |
|---|---|---|
| `--text-xs` | `0.75rem` | 12px |
| `--text-sm` | `0.875rem` | 14px |
| `--text-base` | `1rem` | 16px |
| `--text-lg` | `1.125rem` | 18px |
| `--text-xl` | `1.25rem` | 20px |
| `--text-2xl` | `1.5rem` | 24px |
| `--text-3xl` | `1.875rem` | 30px |

### 3.3 Hauteurs de ligne

| Variable | Valeur |
|---|---|
| `--leading-tight` | `1.25` |
| `--leading-normal` | `1.5` |
| `--leading-relaxed` | `1.625` |

### 3.4 Graisses

| Variable | Valeur |
|---|---|
| `--font-normal` | `400` |
| `--font-medium` | `500` |
| `--font-semibold` | `600` |

### 3.5 Espacement des lettres

| Variable | Valeur |
|---|---|
| `--tracking-tight` | `-0.025em` |
| `--tracking-normal` | `0` |
| `--tracking-wide` | `0.025em` |

---

## 4. Variables CSS (tokens)

### 4.1 Backgrounds

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-bg-primary` | `#0f1117` | `#f0f4ff` | Fond principal de la page |
| `--color-bg-secondary` | `#151821` | `#e8eeff` | Fond des zones secondaires |
| `--color-bg-card` | `#1a1d27` | `#f5f8ff` | Fond des cartes / panels |
| `--color-bg-card-alpha` | `rgb(26,29,39,0.85)` | `rgb(245,248,255,0.92)` | Cartes avec effet glass |
| `--color-bg-elevated` | `#1c1f2b` | `#dce6fb` | Fond surélevé (headers, toolbar) |
| `--color-bg-hover` | `#252838` | `#c7d7f7` | État hover des éléments |
| `--color-bg-input` | `#1c1f2b` | `#f8faff` | Fond des champs de saisie |

> **Note thème light :** les fonds light utilisent une teinte bleue cohérente (pas de blanc pur) pour maintenir l'harmonie visuelle avec l'accent bleu.

### 4.2 Texte

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-text-primary` | `#e1e4eb` | `#0f172a` | Texte principal |
| `--color-text-secondary` | `#8b8fa3` | `#334155` | Texte secondaire / labels |
| `--color-text-muted` | `#5a5f78` | `#4e6080` | Texte atténué / désactivé |
| `--color-text-placeholder` | `#5a5f78` | `#607898` | Placeholder des inputs |

### 4.3 Bordures

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-border` | `#2a2d37` | `#bfcef5` | Bordure standard |
| `--color-border-light` | `#252838` | `#d4e0fb` | Bordure légère |
| `--color-border-focus` | `#4f8ff7` | `#2563eb` | Bordure focus (inputs) |

### 4.4 Couleur d'accent

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-accent` | `#3b82f6` | `#1d4ed8` | Actions principales, liens actifs |
| `--color-accent-hover` | `#60a5fa` | `#1e40af` | État hover de l'accent |
| `--color-accent-light` | `rgb(59,130,246,0.15)` | `rgb(29,78,216,0.12)` | Fond accent semi-transparent |
| `--color-accent-border` | `rgb(59,130,246,0.3)` | `rgb(37,99,235,0.3)` | Bordure accent (tags primary) |

### 4.5 Couleurs de statut

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-success` | `#22c55e` | `#16a34a` | Succès, running, OK |
| `--color-success-light` | `rgb(34,197,94,0.15)` | `rgb(22,163,74,0.1)` | Fond success |
| `--color-success-border` | `rgb(34,197,94,0.3)` | `rgb(22,163,74,0.3)` | Bordure success |
| `--color-error` | `#ef4444` | `#dc2626` | Erreur, danger, critique |
| `--color-error-light` | `rgb(239,68,68,0.15)` | `rgb(220,38,38,0.1)` | Fond erreur |
| `--color-error-border` | `rgb(239,68,68,0.3)` | `rgb(220,38,38,0.3)` | Bordure erreur |
| `--color-warning` | `#f59e0b` | `#d97706` | Avertissement, pending |
| `--color-warning-light` | `rgb(245,158,11,0.15)` | `rgb(217,119,6,0.1)` | Fond warning |
| `--color-warning-border` | `rgb(245,158,11,0.3)` | `rgb(217,119,6,0.3)` | Bordure warning |
| `--color-info` | `#9ca3af` | `#6b7280` | Information, neutre |
| `--color-info-light` | `rgb(107,114,128,0.15)` | `rgb(107,114,128,0.1)` | Fond info |
| `--color-info-border` | `rgb(107,114,128,0.3)` | `rgb(107,114,128,0.2)` | Bordure info |

> **Note :** les valeurs semi-transparentes sont notées `rgb(r, g, b, a)` (syntaxe moderne du CSS) dans `theme.css` ; `rgba(...)` est équivalent.

### 4.6 Ombres

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--shadow-sm` | `0 1px 2px rgb(0,0,0,0.3)` | `0 1px 3px rgb(15,40,100,0.08)` | Élévation légère |
| `--shadow-md` | `0 4px 6px rgb(0,0,0,0.4)` | `0 4px 8px rgb(15,40,100,0.12)` | Carte standard |
| `--shadow-lg` | `0 10px 15px rgb(0,0,0,0.5)` | `0 10px 20px rgb(15,40,100,0.16)` | Modal, dialog |

> **Note thème light :** les ombres light sont teintées bleues (`rgb(15,40,100,...)`) pour cohérence avec la palette.

### 4.7 Overlay

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-overlay` | `rgb(0,0,0,0.5)` | `rgb(10,20,60,0.45)` | Backdrop modal, sidebar overlay |

### 4.8 Couleurs terminal

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
| `--color-terminal-bright-*` | Variantes bright | Variantes bright | Couleurs ANSI bright (`bright-black` → `bright-white`) |

### 4.9 Couleurs logs

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-log-error` | `#f48771` | `#cd3131` | Ligne d'erreur |
| `--color-log-warning` | `#dcdcaa` | `#795e26` | Ligne de warning |
| `--color-log-info` | `#4ec9b0` | `#0598bc` | Ligne d'info |
| `--color-log-debug` | `#858585` | `#6b7280` | Ligne de debug |
| `--color-log-line-number` | `#858585` | `#6b7280` | Numéros de ligne |
| `--color-log-error-bg` | `rgb(244,135,113,0.15)` | `rgb(205,49,49,0.1)` | Fond ligne erreur |
| `--color-log-warning-bg` | `rgb(220,200,170,0.15)` | `rgb(121,94,38,0.1)` | Fond ligne warning |
| `--color-log-hover-bg` | `rgb(255,255,255,0.05)` | `rgb(0,0,0,0.03)` | Hover sur ligne |

### 4.10 Blocs de code

| Variable | Dark | Light | Usage |
|---|---|---|---|
| `--color-code-bg` | `#1e1e1e` | `#f5f5f5` | Fond des blocs `<pre>`, `<code>` |
| `--color-code-fg` | `#d4d4d4` | `#333333` | Texte des blocs de code |

---

## 5. Raccourcis UnoCSS

Les raccourcis sont définis dans la section `shortcuts` de [`uno.config.ts`](../../frontend/uno.config.ts). Ils utilisent les tokens CSS définis ci-dessus. La section `theme` du même fichier expose en outre les couleurs nommées (`bg-card`, `text-primary`, `accent`…), les ombres (`shadow-sm/md/lg`) et les polices (`font-sans/mono`) mappées sur les variables CSS.

### 5.1 Layout

| Shortcut | Classes équivalentes |
|---|---|
| `flex-center` | `flex items-center justify-center` |
| `flex-between` | `flex items-center justify-between` |
| `flex-col-center` | `flex flex-col items-center justify-center` |

### 5.2 Cartes

| Shortcut | Usage |
|---|---|
| `card` | Carte standard avec fond `bg-card`, bordure, ombre, padding `p-4` |
| `card-elevated` | Carte avec fond `bg-elevated`, ombre plus prononcée |
| `card-interactive` | Carte cliquable avec effet hover |
| `card-header` | En-tête de carte (fond `bg-elevated`, bordure basse) |

### 5.3 Panels

| Shortcut | Usage |
|---|---|
| `panel` | Section avec fond `bg-secondary` |
| `panel-elevated` | Section avec fond `bg-elevated` |

### 5.4 Boutons

| Shortcut | Sémantique |
|---|---|
| `btn` | Base commune (`px-4 py-2 rounded cursor-pointer transition-all`) |
| `btn-primary` | Action principale (accent, texte blanc) |
| `btn-secondary` | Action secondaire (elevated + bordure) |
| `btn-success` / `btn-warning` / `btn-danger` | Boutons de statut colorés |
| `btn-ghost` | Bouton transparent |

### 5.5 Champs de saisie

| Shortcut | Usage |
|---|---|
| `input-base` | Input thémé complet (fond, bordure, placeholder, focus accent) |

### 5.6 Textes

| Shortcut | Usage |
|---|---|
| `text-heading` | Titre / en-tête (primary + semibold) |
| `text-body` | Texte courant |
| `text-muted` | Texte atténué |
| `text-label` | Label small (muted + sm) |

### 5.7 Badges de statut

| Shortcut | Couleur |
|---|---|
| `badge` | Base commune (`inline-flex px-2 py-0.5 rounded text-xs font-medium`) |
| `badge-success` | Vert (fond `success-light`, texte `success`) |
| `badge-warning` | Orange |
| `badge-error` | Rouge |
| `badge-info` | Gris |

### 5.8 Tables

| Shortcut | Usage |
|---|---|
| `table-container` | Wrapper de tableau (card + overflow hidden) |
| `table-header` | En-tête de tableau (elevated) |
| `table-row` | Ligne avec hover |
| `table-row-alternate` | Ligne alternante (striped) |

### 5.9 Séparateurs

| Shortcut | Usage |
|---|---|
| `divider` | Séparateur horizontal (`border-t border-border`) |
| `divider-vertical` | Séparateur vertical |

### 5.10 Logs & Terminal

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
| `terminal-status-dot` | Point d'état (base) |
| `terminal-status-connected` | Indicateur vert (connecté, pulsation) |
| `terminal-status-connecting` | Indicateur orange (connexion en cours) |
| `terminal-status-disconnected` | Indicateur gris (déconnecté) |

### 5.11 Blocs de code

| Shortcut | Usage |
|---|---|
| `code-block` | Bloc de code formaté (`code-bg`) |
| `code-console` | Bloc style terminal (`terminal-bg`) |
| `code-inline` | Code inline dans du texte |

### 5.12 Page de login

| Shortcut | Usage |
|---|---|
| `login-page` | Fond pleine page centré |
| `login-card` | Carte login avec glassmorphism (`bg-card-alpha`, backdrop-blur) |
| `login-card-header` / `-title` / `-subtitle` / `-form` / `-footer` / `-version` | Sous-blocs de la carte |
| `login-btn` (+ `-hover`, `-loading`) | Bouton de connexion avec dégradé (`border-focus` → `accent` → `accent-hover`) et états |
| `login-spinner` / `login-particle` | Spinner de chargement / particule décorative d'arrière-plan |

### 5.13 Classes arbitraires UnoCSS

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

## 6. Overrides Element Plus

`theme.css` surcharge les variables internes d'Element Plus pour garantir la cohérence visuelle dans les deux thèmes. Ces règles sont **automatiquement appliquées** — aucune action supplémentaire n'est nécessaire côté développeur.

### 6.1 Variables globales El+

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
| `--el-color-primary` (+ `light-3` à `light-9`) | `--color-accent` (et déclinaisons) |
| `--el-color-success` | `--color-success` |
| `--el-color-warning` | `--color-warning` |
| `--el-color-danger` | `--color-error` |
| `--el-color-info` | `--color-info` |

Des variables par composant sont également posées (`--el-menu-*`, `--el-table-*`, `--el-card-bg-color`, `--el-dialog-bg-color`, `--el-input-*`, `--el-button-*`, `--el-tag-*`…) — voir les sections « Component specific » de `theme.css`.

### 6.2 Composants surchargés

Les composants suivants sont intégralement thémés via `theme.css` :

| Composant | Notes |
|---|---|
| `el-table` | Cellules, header, lignes striped, colonnes fixes (variables au niveau élément) |
| `el-card` | Header, body |
| `el-collapse` | Header, wrap, content, arrow |
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

> **Règle technique :** certains composants El+ utilisent des variables CSS au niveau de l'élément (même spécificité que `:root`), ce qui impose l'usage de `!important` pour les surcharges dans `theme.css` (ex. `.el-table td.el-table__cell`). C'est documenté dans le CSS source.

---

## 7. Règles de migration

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

## 8. Couleurs statiques interdites

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

## 9. Exemples avant / après

### 9.1 Composant Vue — style scoped

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

### 9.2 Layout overlay

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

### 9.3 ECharts — graphique avec gradient

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

### 9.4 Badge inline avec UnoCSS

```vue
<!-- ❌ AVANT — classe CSS avec couleur statique -->
<span class="nav-badge">NEW</span>
<style scoped>
.nav-badge { background-color: var(--color-accent); color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 10px; }
</style>

<!-- ✅ APRÈS — classes UnoCSS pures avec variable -->
<span class="bg-[var(--color-accent)] text-white text-[11px] px-1.5 py-0.5 rounded-xl">NEW</span>
```

### 9.5 Ombre au hover

```css
/* ❌ AVANT */
.clickable-card:hover { box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); }

/* ✅ APRÈS */
.clickable-card:hover { box-shadow: var(--shadow-md); }
```

### 9.6 Typographie

```css
/* ❌ AVANT */
.section-title { font-size: 18px; font-weight: 600; }

/* ✅ APRÈS */
.section-title { font-size: var(--text-lg); font-weight: var(--font-semibold); }
```

---

## 10. Utilitaires TypeScript

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

> **Limitation :** `getCssVarRgba()` fonctionne uniquement avec des variables CSS dont la valeur est une couleur hex (`#rrggbb` ou `#rgb` — le format court est étendu). Pour des variables déjà en `rgba()`, utiliser directement `getCssVar()`.

---

## Voir aussi

- [Ch. 13 — Principes UX](../general_specs/13-ui-principes.md) — principes fonctionnels (Mode App/Infra, navigation), palette indicative
- [Ch. 14 — Maquettes](../general_specs/14-ui-maquettes.md) — les écrans maquettés
- [Ch. 05 — Stack technologique](../general_specs/05-stack-technologique.md) — Vue 3, UnoCSS, Element Plus
- [Ch. 19 — Glossaire](../general_specs/19-glossaire.md) — terminologie canonique
