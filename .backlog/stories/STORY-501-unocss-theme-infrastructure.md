# STORY-501 : Enrichir UnoCSS + theme.css avec variables terminal/logs/code blocks

**Statut :** DONE
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux enrichir la configuration UnoCSS et le fichier theme.css avec les variables CSS pour terminal, logs et code blocks afin de disposer d'une infrastructure de thème complète pour la migration des composants.

## Contexte technique
Cette story est le prérequis à toutes les autres stories de l'epic. Elle consiste à ajouter :
- Les variables CSS terminal (palette VS Code) dans `theme.css`
- Les variables CSS pour logs et code blocks
- Les shortcuts UnoCSS correspondants dans `uno.config.ts`

### Fichiers de référence
- `frontend/uno.config.ts` — Configuration UnoCSS actuelle (shortcuts existants : `logs-container`, `logs-header`, `logs-footer`, `logs-content`)
- `frontend/src/styles/theme.css` — Variables CSS de thème existantes (dark/light themes)

### Patterns existants
Dans `theme.css` :
- Variables organisées par section avec commentaires `/* ===== Section ===== */`
- Définition dans `:root, [data-theme='dark']` pour dark theme
- Définition dans `[data-theme='light']` pour light theme

Dans `uno.config.ts` :
- Shortcuts utilisant `var(--color-xxx)` pour référencer les variables CSS
- Convention de nommage : `log-xxx`, `code-xxx`

### Composants impactés (consommation future)
- `frontend/src/components/DeploymentLogs.vue` — utilise hardcoded `#1e1e1e`, `#d4d4d4`, `#f48771`, `#dcdcaa`, `#4ec9b0`, `#858585`
- `frontend/src/components/ContainerLogs.vue` — même pattern
- `frontend/src/components/ContainerTerminal.vue` — nécessite palette VS Code

## Critères d'acceptation (AC)
- [x] AC 1 : Les variables CSS `--color-terminal-*` (16 couleurs) sont ajoutées dans `theme.css`
- [x] AC 2 : Les variables CSS `--color-log-*` (error, warning, info, debug, line-number) sont ajoutées
- [x] AC 3 : Les variables CSS `--color-code-*` (bg, fg) sont ajoutées
- [x] AC 4 : Les shortcuts UnoCSS `log-error`, `log-warning`, `log-info`, `log-debug`, `log-line-number` sont créés
- [x] AC 5 : Les shortcuts UnoCSS `code-block`, `code-console` sont créés
- [x] AC 6 : Le build frontend passe sans erreur

## Dépendances
Aucune

## État d'avancement technique
- [x] Ajouter les variables CSS terminal dans `theme.css` (dark theme)
- [x] Ajouter les variables CSS terminal dans `theme.css` (light theme)
- [x] Ajouter les variables CSS logs dans `theme.css` (dark + light)
- [x] Ajouter les variables CSS code blocks dans `theme.css` (dark + light)
- [x] Ajouter les shortcuts UnoCSS logs dans `uno.config.ts`
- [x] Ajouter les shortcuts UnoCSS code blocks dans `uno.config.ts`
- [x] Vérifier le build frontend

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter les variables CSS terminal (16 couleurs) dans `theme.css`

**Fichier :** `frontend/src/styles/theme.css`

**Objectif :** Ajouter la palette de couleurs terminal style VS Code pour le dark theme.

**Emplacement :** Après la section `/* Status colors */` dans le bloc `:root, [data-theme='dark']`

**Variables à ajouter :**
```css
/* Terminal colors - VS Code Dark style */
--color-terminal-bg: #0c0c0c;
--color-terminal-fg: #cccccc;
--color-terminal-cursor: #ffffff;
--color-terminal-selection: #264f78;
--color-terminal-red: #cd3131;
--color-terminal-green: #0dbc79;
--color-terminal-yellow: #e5e510;
--color-terminal-blue: #2472c8;
--color-terminal-magenta: #bc3fbc;
--color-terminal-cyan: #11a8cd;
--color-terminal-white: #e5e5e5;
--color-terminal-bright-black: #666666;
--color-terminal-bright-red: #f14c4c;
--color-terminal-bright-green: #23d18b;
--color-terminal-bright-yellow: #f5f543;
--color-terminal-bright-blue: #3b8eea;
--color-terminal-bright-magenta: #d670d6;
--color-terminal-bright-cyan: #29b8db;
--color-terminal-bright-white: #ffffff;
```

---

### Tâche 2 : Ajouter les variables CSS terminal pour le light theme

**Fichier :** `frontend/src/styles/theme.css`

**Objectif :** Ajouter la palette terminal adaptée au light theme.

**Emplacement :** Après la section `/* Status colors */` dans le bloc `[data-theme='light']`

**Variables à ajouter :**
```css
/* Terminal colors - Light theme adapted */
--color-terminal-bg: #ffffff;
--color-terminal-fg: #333333;
--color-terminal-cursor: #000000;
--color-terminal-selection: #add6ff;
--color-terminal-red: #cd3131;
--color-terminal-green: #008000;
--color-terminal-yellow: #795e26;
--color-terminal-blue: #0000ff;
--color-terminal-magenta: #af00db;
--color-terminal-cyan: #0598bc;
--color-terminal-white: #666666;
--color-terminal-bright-black: #666666;
--color-terminal-bright-red: #cd3131;
--color-terminal-bright-green: #008000;
--color-terminal-bright-yellow: #795e26;
--color-terminal-bright-blue: #0000ff;
--color-terminal-bright-magenta: #af00db;
--color-terminal-bright-cyan: #0598bc;
--color-terminal-bright-white: #333333;
```

---

### Tâche 3 : Ajouter les variables CSS logs dans `theme.css`

**Fichier :** `frontend/src/styles/theme.css`

**Objectif :** Définir les couleurs pour les niveaux de logs.

**Emplacement :** Après les variables terminal, dans les deux blocs dark ET light

**Variables à ajouter (dark theme) :**
```css
/* Log colors */
--color-log-error: #f48771;
--color-log-warning: #dcdcaa;
--color-log-info: #4ec9b0;
--color-log-debug: #858585;
--color-log-line-number: #858585;
```

**Variables à ajouter (light theme) :**
```css
/* Log colors */
--color-log-error: #cd3131;
--color-log-warning: #795e26;
--color-log-info: #0598bc;
--color-log-debug: #6b7280;
--color-log-line-number: #6b7280;
```

---

### Tâche 4 : Ajouter les variables CSS code blocks dans `theme.css`

**Fichier :** `frontend/src/styles/theme.css`

**Objectif :** Définir les couleurs pour les blocs de code.

**Emplacement :** Après les variables logs, dans les deux blocs dark ET light

**Variables à ajouter (dark theme) :**
```css
/* Code blocks */
--color-code-bg: #1e1e1e;
--color-code-fg: #d4d4d4;
```

**Variables à ajouter (light theme) :**
```css
/* Code blocks */
--color-code-bg: #f5f5f5;
--color-code-fg: #333333;
```

---

### Tâche 5 : Ajouter les shortcuts UnoCSS logs dans `uno.config.ts`

**Fichier :** `frontend/uno.config.ts`

**Objectif :** Créer les classes utilitaires pour les logs.

**Emplacement :** Dans l'objet `shortcuts`, après les shortcuts existants `logs-xxx`

**Shortcuts à ajouter :**
```typescript
// Log level text colors
'log-error': 'text-[var(--color-log-error)]',
'log-warning': 'text-[var(--color-log-warning)]',
'log-info': 'text-[var(--color-log-info)]',
'log-debug': 'text-[var(--color-log-debug)] italic',
'log-line-number': 'text-[var(--color-log-line-number)] select-none pr-3 text-right',
```

---

### Tâche 6 : Ajouter les shortcuts UnoCSS code/terminal blocks dans `uno.config.ts`

**Fichier :** `frontend/uno.config.ts`

**Objectif :** Créer les classes utilitaires pour les blocs de code et console.

**Emplacement :** Dans l'objet `shortcuts`, après les shortcuts logs

**Shortcuts à ajouter :**
```typescript
// Code blocks styling
'code-block': 'bg-[var(--color-code-bg)] text-[var(--color-code-fg)] font-mono p-4 rounded-lg',
'code-console': 'bg-[var(--color-terminal-bg)] text-[var(--color-terminal-fg)] font-mono p-4 rounded-lg',
'code-inline': 'bg-[var(--color-code-bg)] text-[var(--color-code-fg)] font-mono px-1.5 py-0.5 rounded text-sm',
```

---

### Tâche 7 : Vérifier le build frontend

**Commande :** `cd frontend && pnpm build`

**Objectif :** S'assurer que les modifications ne cassent pas le build.

**Validation :**
- Le build doit terminer sans erreur
- Les fichiers CSS générés doivent contenir les nouvelles variables

## Tests à écrire

### Tests unitaires

#### Test 1 : Vérifier la présence des variables CSS terminal
**Fichier :** `frontend/tests/unit/styles/theme.spec.ts` (à créer si nécessaire)

```typescript
describe('Theme CSS Variables', () => {
  it('should define all terminal colors in dark theme', () => {
    const root = getComputedStyle(document.documentElement)
    expect(root.getPropertyValue('--color-terminal-bg')).toBeTruthy()
    expect(root.getPropertyValue('--color-terminal-fg')).toBeTruthy()
    expect(root.getPropertyValue('--color-terminal-red')).toBeTruthy()
    // ... tester les 16 couleurs terminal
  })

  it('should define all log colors', () => {
    const root = getComputedStyle(document.documentElement)
    expect(root.getPropertyValue('--color-log-error')).toBeTruthy()
    expect(root.getPropertyValue('--color-log-warning')).toBeTruthy()
    expect(root.getPropertyValue('--color-log-info')).toBeTruthy()
    expect(root.getPropertyValue('--color-log-debug')).toBeTruthy()
    expect(root.getPropertyValue('--color-log-line-number')).toBeTruthy()
  })

  it('should define code block colors', () => {
    const root = getComputedStyle(document.documentElement)
    expect(root.getPropertyValue('--color-code-bg')).toBeTruthy()
    expect(root.getPropertyValue('--color-code-fg')).toBeTruthy()
  })
})
```

#### Test 2 : Vérifier les shortcuts UnoCSS
**Fichier :** `frontend/tests/unit/uno/shortcuts.spec.ts` (à créer si nécessaire)

```typescript
import { createGenerator } from 'unocss'
import config from '@/uno.config'

describe('UnoCSS Shortcuts', () => {
  const uno = createGenerator(config)

  it('should generate log-error class', async () => {
    const { css } = await uno.generate('log-error')
    expect(css).toContain('--color-log-error')
  })

  it('should generate code-block class', async () => {
    const { css } = await uno.generate('code-block')
    expect(css).toContain('--color-code-bg')
    expect(css).toContain('font-mono')
  })

  it('should generate code-console class', async () => {
    const { css } = await uno.generate('code-console')
    expect(css).toContain('--color-terminal-bg')
  })
})
```

### Tests de validation manuelle

1. **Build check :** `cd frontend && pnpm build` → doit passer sans erreur
2. **Type check :** `cd frontend && pnpm type-check` → doit passer sans erreur
3. **Lint :** `cd frontend && pnpm lint` → doit passer sans erreur

### Commandes de validation
```bash
# Build frontend
cd frontend && pnpm build

# Type check (si disponible)
cd frontend && pnpm type-check

# Lancement des tests
cd frontend && pnpm test
```

## Notes d'implémentation

### Fichiers modifiés
- `frontend/src/styles/theme.css` — Ajout des variables CSS terminal (16 couleurs), logs (5 couleurs) et code blocks (2 couleurs) pour les thèmes dark et light
- `frontend/uno.config.ts` — Ajout des shortcuts UnoCSS `log-error`, `log-warning`, `log-info`, `log-debug`, `log-line-number`, `code-block`, `code-console`, `code-inline`

### Décisions techniques
1. **Palette terminal VS Code** : Les 16 couleurs terminal suivent la palette standard VS Code pour une cohérence avec les habitudes développeur
2. **Thème light adapté** : Les couleurs terminal ont été ajustées pour le thème light (contraste amélioré, couleurs moins saturées)
3. **Shortcuts avec utilitaires combinés** : `log-debug` inclut `italic`, `log-line-number` inclut `select-none pr-3 text-right` pour faciliter l'usage

### Variables ajoutées

#### Terminal (dark theme)
```css
--color-terminal-bg: #0c0c0c;
--color-terminal-fg: #cccccc;
--color-terminal-cursor: #ffffff;
--color-terminal-selection: #264f78;
--color-terminal-red: #cd3131;
--color-terminal-green: #0dbc79;
--color-terminal-yellow: #e5e510;
--color-terminal-blue: #2472c8;
--color-terminal-magenta: #bc3fbc;
--color-terminal-cyan: #11a8cd;
--color-terminal-white: #e5e5e5;
--color-terminal-bright-black: #666666;
--color-terminal-bright-red: #f14c4c;
--color-terminal-bright-green: #23d18b;
--color-terminal-bright-yellow: #f5f543;
--color-terminal-bright-blue: #3b8eea;
--color-terminal-bright-magenta: #d670d6;
--color-terminal-bright-cyan: #29b8db;
--color-terminal-bright-white: #ffffff;
```

#### Logs (dark theme)
```css
--color-log-error: #f48771;
--color-log-warning: #dcdcaa;
--color-log-info: #4ec9b0;
--color-log-debug: #858585;
--color-log-line-number: #858585;
```

#### Code blocks (dark theme)
```css
--color-code-bg: #1e1e1e;
--color-code-fg: #d4d4d4;
```

### Tests
Les tests unitaires proposés dans l'analyse n'ont pas été implémentés car cette story est une infrastructure de base. Les tests seront plus pertinents lors de la migration des composants consommateurs (STORY-503, STORY-504).

### Validation
- Build frontend : ✅ Passant
- Variables CSS disponibles pour les stories suivantes de l'epic
```
