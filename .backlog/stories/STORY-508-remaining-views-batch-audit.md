# STORY-508 : Refactoriser toutes les autres views (batch audit - ~15 fichiers)

**Statut :** IN_PROGRESS
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques de toutes les views restantes par des variables CSS thémées afin de compléter l'homogénéisation du design system sur l'ensemble de l'application.

## Contexte technique
Résultat de l'audit complet (scan regex `#[0-9a-fA-F]{3,8}|rgba?([^)]+)`) sur `frontend/src/views/`, `frontend/src/components/` et `frontend/src/layouts/`.

> **Note :** L'estimation initiale (~15 fichiers) était largement surévaluée. La majorité des views `Targets`, `Containers`, `Deployments`, `Schedules`, `Workflows`, etc. sont déjà propres. La réalité : **6 couleurs statiques dans `<style>` + 9 en JS (ECharts) réparties sur 7 fichiers.**

### Couleurs statiques dans `<style>` (CSS)

| Fichier | Sélecteur | Couleur statique | Remplacement |
|---------|-----------|-----------------|--------------|
| `frontend/src/views/Settings.vue` | `.access-denied .el-icon` | `color: #f56c6c` | `color: var(--color-error)` |
| `frontend/src/views/Dashboard.vue` | `.clickable-card:hover` | `box-shadow: 0 4px 12px rgba(0,0,0,0.15)` | `box-shadow: var(--shadow-md)` |
| `frontend/src/views/WorkflowEditor.vue` | `.workflow-canvas` | `border: 1px solid #e0e0e0` | `border: 1px solid var(--color-border)` |
| `frontend/src/views/WorkflowEditor.vue` | `.node-palette` | `background-color: #f5f5f5` | `background-color: var(--color-bg-elevated)` |
| `frontend/src/components/SidebarNav.vue` | `.nav-badge` | `color: #fff` | Supprimer la règle, convertir `.nav-badge` en classes UnoCSS dans le template |
| `frontend/src/layouts/MainLayout.vue` | `.mobile-overlay` (ou similaire) | `background-color: rgba(0,0,0,0.5)` | Nouvelle var CSS `--color-overlay` dans `theme.css` |

### Couleurs statiques dans JS (ECharts — section `<script>`)

| Fichier | Contexte | Couleur | Remplacement |
|---------|----------|---------|--------------|
| `frontend/src/components/dashboard/ResourceMetricsWidget.vue` | Tooltip `backgroundColor` | `rgba(0,0,0,0.8)` | `getCssVar('--color-bg-elevated')` |
| `frontend/src/components/dashboard/ResourceMetricsWidget.vue` | Tooltip `textStyle.color` | `'#fff'` | `getCssVar('--color-text-primary')` |
| `frontend/src/components/dashboard/ResourceMetricsWidget.vue` | Série CPU `itemStyle.color` | `'#409EFF'` | `getCssVar('--color-accent')` |
| `frontend/src/components/dashboard/ResourceMetricsWidget.vue` | Série Memory `itemStyle.color` | `'#E6A23C'` | `getCssVar('--color-warning')` |
| `frontend/src/components/ContainerStats.vue` | Gradient série réseau/CPU `colorStops` | `rgba(64,158,255, 0.4/0.05)` | `getCssVar('--color-accent')` + opacité |
| `frontend/src/components/ContainerStats.vue` | Gradient série mémoire/succès `colorStops` | `rgba(103,194,58, 0.4/0.05)` | `getCssVar('--color-success')` + opacité |
| `frontend/src/components/ContainerStats.vue` | Gradient série info/disk `colorStops` | `rgba(144,147,153, 0.3/0.05)` | `getCssVar('--color-info')` + opacité |
| `frontend/src/components/ContainerStats.vue` | Gradient série warning `colorStops` | `rgba(230,162,60, 0.3/0.05)` | `getCssVar('--color-warning')` + opacité |
| `frontend/src/components/ContainerStats.vue` | Gradient série error `colorStops` | `rgba(245,108,108, 0.3/0.05)` | `getCssVar('--color-error')` + opacité |

### Fichiers inchangés — déjà propres
- `Targets.vue`, `Containers.vue`, `Deployments.vue`, `DeploymentDetail.vue`, `Schedules.vue`, `Workflows.vue` — aucune couleur statique
- `Volumes.vue`, `Networks.vue`, `Images.vue`, `VMs.vue`, `Marketplace.vue`, `Plugins.vue`, `Audit.vue` — non existants (stubs futurs)

### Patterns de référence (STORY-507 + STORY-501)
- CSS `<style scoped>` : remplacer couleur par `var(--color-*)` (variables dans `theme.css`)
- Template UnoCSS : utiliser classes `bg-[var(--color-*)] text-white` pour éléments badge
- ECharts JS : fonction `getCssVar(name)` via `getComputedStyle(document.documentElement).getPropertyValue(name).trim()` pour lire les variables CSS au moment du rendu
- Pour les gradients ECharts : construire les `colorStops` dynamiquement avec les valeurs résolues des CSS vars

## Critères d'acceptation (AC)
- [ ] AC 1 : Audit complet des couleurs statiques résiduelles effectué
- [ ] AC 2 : Aucune couleur statique (hex, rgb, rgba) dans les `<style>` des views traitées
- [ ] AC 3 : Toutes les views utilisent les variables CSS ou classes UnoCSS
- [ ] AC 4 : Le support dark/light theme est validé sur tous les écrans
- [ ] AC 5 : Le build et les tests passent
- [ ] AC 6 : Documentation du guide de style mise à jour

## Dépendances
- STORY-501 (infrastructure UnoCSS + theme.css)

## État d'avancement technique
- [ ] Tâche 1 : Migration CSS `<style>` — Settings, Dashboard, WorkflowEditor, MainLayout
- [ ] Tâche 2 : Migration SidebarNav.vue — nav-badge → UnoCSS template
- [ ] Tâche 3 : Créer l'utilitaire `getCssVar` dans `frontend/src/utils/css.ts`
- [ ] Tâche 4 : Migration ResourceMetricsWidget.vue — couleurs ECharts
- [ ] Tâche 5 : Migration ContainerStats.vue — couleurs ECharts gradients
- [ ] Tâche 6 : Ajouter `--color-overlay` dans `theme.css`
- [ ] Tâche 7 : Mise à jour documentation guide de style (`doc/DESIGN-SYSTEM.md`)
- [ ] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Migration CSS `<style>` — quick wins (Settings, Dashboard, WorkflowEditor, MainLayout)
**Objectif :** Remplacer les 6 couleurs statiques dans les sections `<style scoped>` par des variables CSS thémées. Fichiers tous indépendants, modifications atomiques.
**Fichiers :**
- `frontend/src/views/Settings.vue` — Modifier — Dans `<style scoped>`, dans le sélecteur `.access-denied .el-icon` : remplacer `color: #f56c6c` par `color: var(--color-error)`. La variable `--color-error` est déjà définie dans `theme.css` pour dark (`#ef4444`) et light (`#dc2626`).
- `frontend/src/views/Dashboard.vue` — Modifier — Dans `<style scoped>`, dans le sélecteur `.clickable-card:hover` : remplacer `box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15)` par `box-shadow: var(--shadow-md)`. La variable `--shadow-md` est déjà définie dans `theme.css` (valeurs différentes selon le thème).
- `frontend/src/views/WorkflowEditor.vue` — Modifier — Dans `<style scoped>` :
  1. Dans `.workflow-canvas` : remplacer `border: 1px solid #e0e0e0` par `border: 1px solid var(--color-border)`
  2. Dans `.node-palette` : remplacer `background-color: #f5f5f5` par `background-color: var(--color-bg-elevated)`. Ajouter aussi `color: var(--color-text-primary)` si absent pour assurer la lisibilité en dark mode.
- `frontend/src/layouts/MainLayout.vue` — Modifier — Localiser le sélecteur qui a `background-color: rgba(0, 0, 0, 0.5)` (overlay backdrop mobile sidebar) et remplacer par `background-color: var(--color-overlay)`. La variable `--color-overlay` sera ajoutée en Tâche 6.
**Dépend de :** Tâche 6 (pour MainLayout, si la variable `--color-overlay` est ajoutée séparément. Sinon, faire MainLayout en dernier dans cette tâche.)

---

### Tâche 2 : Migration SidebarNav.vue — nav-badge → UnoCSS
**Objectif :** Supprimer la règle CSS `.nav-badge { color: #fff }` (seule couleur statique dans ce composant) et convertir l'élément badge en classes UnoCSS directement dans le template, suivant la convention "maximum UnoCSS" de la story.
**Fichiers :**
- `frontend/src/components/SidebarNav.vue` — Modifier — 2 opérations :
  1. **Template** : Chercher tous les `<span v-if="item.badge" class="nav-badge">` dans les 4 sections de navigation (infrastructure, storage, marketplace, administration). Remplacer la classe `nav-badge` par des classes UnoCSS : `class="bg-[var(--color-accent)] text-white text-[11px] px-1.5 py-0.5 rounded-xl"`. Répéter pour tous les spans badge dans la boucle `v-for` (4 occurrences dans les différentes `<ul>` de navigation).
  2. **Style** : Supprimer entièrement la règle CSS `.nav-badge { background-color: var(--color-accent); color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 10px; }` du `<style scoped>`.
**Dépend de :** Aucune

---

### Tâche 3 : Créer l'utilitaire `getCssVar` dans `frontend/src/utils/css.ts`
**Objectif :** Créer une fonction utilitaire réutilisable qui lit la valeur effective d'une CSS custom property au moment du rendu, permettant d'utiliser les variables CSS thémées dans les configurations ECharts (qui nécessitent des valeurs de couleur concrètes, pas des strings `var(--...)` ).
**Fichiers :**
- `frontend/src/utils/css.ts` — Créer — Nouveau fichier utilitaire. Exporter les fonctions suivantes :

  ```typescript
  /**
   * Lit la valeur d'une CSS custom property au runtime.
   * Utilisé pour passer des couleurs thémées aux libs JS (ECharts, etc.)
   * qui ne supportent pas les CSS variables directement.
   */
  export function getCssVar(name: string): string {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  }

  /**
   * Retourne un rgba() à partir d'une CSS custom property hexadécimale et d'une opacité.
   * Utile pour les gradients ECharts (colorStops).
   * @param varName - Nom de la variable CSS (ex: '--color-accent')
   * @param opacity - Opacité entre 0 et 1
   */
  export function getCssVarRgba(varName: string, opacity: number): string {
    const hex = getCssVar(varName)
    // Convertir hex (#rrggbb ou #rgb) en rgb
    const full = hex.startsWith('#') ? hex : '#000000'
    const r = parseInt(full.slice(1, 3), 16)
    const g = parseInt(full.slice(3, 5), 16)
    const b = parseInt(full.slice(5, 7), 16)
    return `rgba(${r}, ${g}, ${b}, ${opacity})`
  }
  ```

**Dépend de :** Aucune

---

### Tâche 4 : Migration ResourceMetricsWidget.vue — couleurs ECharts JS
**Objectif :** Remplacer les 4 couleurs hardcodées dans la configuration ECharts par des appels à `getCssVar()`, rendant le graphique d'historique CPU/Memory sensible au thème dark/light.
**Fichiers :**
- `frontend/src/components/dashboard/ResourceMetricsWidget.vue` — Modifier — 3 changements :

  1. **Import** : Ajouter l'import de l'utilitaire en début de `<script setup>` :
     ```typescript
     import { getCssVar } from '@/utils/css'
     ```

  2. **Chart option tooltip** : Dans `chartOption` (computed), remplacer :
     ```typescript
     tooltip: {
       trigger: 'axis',
       backgroundColor: 'rgba(0, 0, 0, 0.8)',
       borderColor: 'transparent',
       textStyle: { color: '#fff' },
     },
     ```
     par :
     ```typescript
     tooltip: {
       trigger: 'axis',
       backgroundColor: getCssVar('--color-bg-elevated'),
       borderColor: getCssVar('--color-border'),
       textStyle: { color: getCssVar('--color-text-primary') },
     },
     ```

  3. **Series itemStyle colors** : Remplacer dans les deux séries :
     - CPU : `itemStyle: { color: '#409EFF' }` → `itemStyle: { color: getCssVar('--color-accent') }`
     - Memory : `itemStyle: { color: '#E6A23C' }` → `itemStyle: { color: getCssVar('--color-warning') }`

**Dépend de :** Tâche 3

---

### Tâche 5 : Migration ContainerStats.vue — couleurs ECharts gradients
**Objectif :** Remplacer les 10+ couleurs `rgba()` hardcodées dans les `colorStops` des gradients ECharts par des appels à `getCssVarRgba()`, rendant tous les graphiques de stats container sensibles au thème.
**Fichiers :**
- `frontend/src/components/ContainerStats.vue` — Modifier — 2 changements :

  1. **Import** : Ajouter en début de `<script setup>` :
     ```typescript
     import { getCssVarRgba, getCssVar } from '@/utils/css'
     ```

  2. **Remplacement des colorStops** : Dans la configuration des graphiques ECharts (section `chartOption` ou équivalent computed), localiser tous les blocs `colorStops` et remplacer comme suit :
     - `rgba(64, 158, 255, 0.4)` → `getCssVarRgba('--color-accent', 0.4)`
     - `rgba(64, 158, 255, 0.05)` → `getCssVarRgba('--color-accent', 0.05)`
     - `rgba(103, 194, 58, 0.4)` → `getCssVarRgba('--color-success', 0.4)`
     - `rgba(103, 194, 58, 0.05)` → `getCssVarRgba('--color-success', 0.05)`
     - `rgba(144, 147, 153, 0.3)` → `getCssVarRgba('--color-info', 0.3)`
     - `rgba(144, 147, 153, 0.05)` → `getCssVarRgba('--color-info', 0.05)`
     - `rgba(230, 162, 60, 0.3)` → `getCssVarRgba('--color-warning', 0.3)`
     - `rgba(230, 162, 60, 0.05)` → `getCssVarRgba('--color-warning', 0.05)`
     - `rgba(64, 158, 255, 0.3)` → `getCssVarRgba('--color-accent', 0.3)` *(doublon accent)*
     - `rgba(245, 108, 108, 0.3)` → `getCssVarRgba('--color-error', 0.3)`
     - `rgba(245, 108, 108, 0.05)` → `getCssVarRgba('--color-error', 0.05)`

  Si la configuration chart est dans un `computed()`, la valeur sera recalculée à chaque re-render, ce qui est correct. Si elle est dans un objet statique (non-réactif), envelopper dans un `computed()` pour que les couleurs se mettent à jour lors du changement de thème.

**Dépend de :** Tâche 3

---

### Tâche 6 : Ajouter la variable `--color-overlay` dans `theme.css`
**Objectif :** Formaliser la couleur de l'overlay semi-transparent (backdrop modal/sidebar mobile) comme variable CSS thémée plutôt qu'une valeur rgba hardcodée. La valeur est identique en dark et light (overlay noir semi-transparent universellement accepté en UI).
**Fichiers :**
- `frontend/src/styles/theme.css` — Modifier — Dans les deux sections `:root, [data-theme='dark']` et `[data-theme='light']`, ajouter dans le groupe « Shadows » (en fin de section) :

  Pour **dark** (`:root, [data-theme='dark']`) :
  ```css
  --color-overlay: rgba(0, 0, 0, 0.5);
  ```

  Pour **light** (`[data-theme='light']`) :
  ```css
  --color-overlay: rgba(0, 0, 0, 0.4);
  ```
  *(légèrement plus faible en light pour ne pas être trop agressif sur fond clair)*

**Dépend de :** Aucune

---

### Tâche 7 : Créer la documentation guide de style (`doc/DESIGN-SYSTEM.md`)
**Objectif :** Satisfaire l'AC 6 en documentant le design system WindFlow — variables CSS disponibles, shortcuts UnoCSS, règles de migration et exemples. Ce document sert de référence pour les futurs développeurs.
**Fichiers :**
- `doc/DESIGN-SYSTEM.md` — Créer — Nouveau document structuré avec les sections suivantes :
  1. **Introduction** : objectif du design system, référence à EPIC-008
  2. **Variables CSS** : tableau complet des variables disponibles par catégorie (backgrounds, textes, borders, statuts, terminal, logs, code, overlays) avec valeurs dark/light
  3. **Shortcuts UnoCSS** : liste des shortcuts disponibles dans `uno.config.ts` avec description et exemple d'usage (`card`, `badge-success`, `log-error`, `code-block`, etc.)
  4. **Règles de migration** : les 5 règles de l'EPIC-008 + règle ECharts (utiliser `getCssVar`/`getCssVarRgba`)
  5. **Ne jamais utiliser** : liste noire des couleurs statiques à bannir (`#1e1e1e`, `#d4d4d4`, etc.) + équivalents thémés
  6. **Exemples avant/après** : code avant (couleur statique) et après (variable CSS ou UnoCSS)

**Dépend de :** Aucune (peut être fait en parallèle)

## Tests à écrire

Cette story est un refactoring CSS/JS pur, sans modification de logique fonctionnelle. Aucun test unitaire spécifique n'est requis.

### Validation manuelle requise

1. **Audit résiduel** : Relancer le scan regex pour confirmer qu'il ne reste plus de couleurs statiques :
   ```bash
   grep -rn --include="*.vue" --include="*.ts" -E '#[0-9a-fA-F]{3,8}|rgba?\([^)]+\)' frontend/src/views/ frontend/src/components/ frontend/src/layouts/
   ```
   → Doit retourner 0 résultats dans les sections `<style>`.

2. **Test visuel dark/light** :
   - Ouvrir Settings page → vérifier que l'icône d'accès refusé est correctement rouge dans les deux thèmes
   - Ouvrir Dashboard → vérifier le box-shadow de `.clickable-card` hover
   - Ouvrir WorkflowEditor → vérifier la bordure du canvas et le background de la palette
   - Vérifier la sidebar → les badges "Bientôt" doivent être correctement colorés
   - Vérifier l'overlay sidebar sur mobile (ou simuler en réduisant la fenêtre)
   - Ouvrir un container avec stats → vérifier les graphiques ECharts en dark ET light
   - Ouvrir le Dashboard → vérifier les graphiques historiques ResourceMetricsWidget en dark ET light

### Commandes de validation
```bash
# Build & lint
cd frontend && pnpm build
cd frontend && pnpm lint

# Scan résiduel de couleurs statiques dans les styles
grep -rn --include="*.vue" -E 'color:\s*#[0-9a-fA-F]{3,8}|background(-color)?:\s*(#[0-9a-fA-F]{3,8}|rgba?\()' frontend/src/views/ frontend/src/components/ frontend/src/layouts/
```
