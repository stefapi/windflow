# STORY-504 : Refactoriser ContainerTerminal.vue → variables CSS thémées (palette VS Code)

**Statut :** DONE
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques du composant ContainerTerminal par les variables CSS de la palette terminal VS Code afin d'assurer un affichage cohérent et thémable du terminal.

## Contexte technique

### Fichier à modifier
- `frontend/src/components/ContainerTerminal.vue`

### Patterns existants (STORY-501)

**Variables CSS disponibles dans `theme.css` :**
- `--color-terminal-bg`, `--color-terminal-fg`, `--color-terminal-cursor`, `--color-terminal-selection`
- Les 16 couleurs ANSI standard : `--color-terminal-red/green/yellow/blue/magenta/cyan/white`
- Les 8 bright variants : `--color-terminal-bright-black` à `--color-terminal-bright-white`
- Variables de status : `--color-success`, `--color-warning`, `--color-info`

**Shortcuts UnoCSS disponibles dans `uno.config.ts` :**
- `code-console` : `bg-[var(--color-terminal-bg)] text-[var(--color-terminal-fg)] font-mono p-4 rounded-lg`
- `bg-success`, `bg-warning`, `bg-info` pour les status

### Couleurs hardcodées identifiées

**1. Dans le JavaScript (xterm.js theme) - lignes 94-128 :**
```typescript
theme: props.theme === 'dark' ? {
  background: '#0c0c0c',
  foreground: '#cccccc',
  cursor: '#ffffff',
  cursorAccent: '#000000',
  selectionBackground: '#264f78',
  black: '#000000',
  red: '#cd3131',
  green: '#0dbc79',
  yellow: '#e5e510',
  blue: '#2472c8',
  magenta: '#bc3fbc',
  cyan: '#11a8cd',
  white: '#e5e5e5',
  brightBlack: '#666666',
  brightRed: '#f14c4c',
  brightGreen: '#23d18b',
  brightYellow: '#f5f543',
  brightBlue: '#3b8eea',
  brightMagenta: '#d670d6',
  brightCyan: '#29b8db',
  brightWhite: '#ffffff',
} : {
  background: '#ffffff',
  foreground: '#000000',
  // ... light theme simplifié
}
```

**2. Dans le CSS scoped - lignes 340-346 :**
```css
.terminal-container.theme-dark {
  background-color: #0c0c0c;
}
.terminal-container.theme-light {
  background-color: #ffffff;
}
```

**3. Status dots - lignes 296-307 :**
```css
.status-dot.connected { background-color: #67c23a; }
.status-dot.connecting { background-color: #e6a23c; }
.status-dot.disconnected { background-color: #909399; }
```

### Contrainte technique importante
**xterm.js ne supporte pas les variables CSS directement** dans son objet `theme`. Il faut lire les valeurs via `getComputedStyle()` et les injecter dynamiquement.

## Critères d'acceptation (AC)
- [x] AC 1 : Aucune couleur statique dans les `<style>` de ContainerTerminal.vue
- [x] AC 2 : Le terminal utilise les variables CSS `--color-terminal-*`
- [x] AC 3 : Les 16 couleurs ANSI sont correctement thémées
- [x] AC 4 : Le rendu visuel est identique en mode light et dark
- [x] AC 5 : Le build et les tests passent

## Dépendances
- STORY-501 (infrastructure UnoCSS + theme.css) — ✅ DONE

## État d'avancement technique
- [x] Tâche 1 : Créer la fonction helper `getTerminalThemeFromCSS()`
- [x] Tâche 2 : Refactoriser `initTerminal()` pour utiliser le helper
- [x] Tâche 3 : Remplacer les couleurs CSS hardcodées par des variables CSS
- [x] Tâche 4 : Simplifier le template (supprimer classes theme-dark/light)
- [x] Tâche 5 : Vérifier le build frontend
- [x] Tests unitaires
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Créer la fonction helper `getTerminalThemeFromCSS()`

**Objectif :** Créer une fonction qui lit dynamiquement les variables CSS terminal depuis `theme.css` et retourne un objet theme compatible xterm.js. Cette fonction permet de contourner la limitation de xterm.js qui ne supporte pas les variables CSS directement.

**Fichiers :**
- `frontend/src/components/ContainerTerminal.vue` — Modifier — Ajouter la fonction `getTerminalThemeFromCSS()` dans le bloc `<script setup>`, avant la fonction `initTerminal()`. La fonction doit :
  - Utiliser `getComputedStyle(document.documentElement)` pour lire les variables CSS
  - Retourner un objet `Terminal.Theme` avec les 18 propriétés de thème (background, foreground, cursor, selectionBackground, + 16 couleurs ANSI)
  - Mapper chaque propriété vers la variable CSS correspondante : `--color-terminal-bg`, `--color-terminal-fg`, `--color-terminal-cursor`, `--color-terminal-selection`, `--color-terminal-red/green/yellow/blue/magenta/cyan/white`, `--color-terminal-bright-*`

**Pattern de référence :** Pattern existant dans le composant pour la lecture de `--font-mono` (ligne 87)

**Dépend de :** Aucune

---

### Tâche 2 : Refactoriser `initTerminal()` pour utiliser le helper

**Objectif :** Remplacer l'objet theme hardcodé (dark/light conditionnel) par un appel unique à `getTerminalThemeFromCSS()`, ce qui simplifie le code et rend le thème automatiquement réactif aux changements de thème global.

**Fichiers :**
- `frontend/src/components/ContainerTerminal.vue` — Modifier — Dans la fonction `initTerminal()` (lignes 88-130), remplacer l'objet `theme` conditionnel par `theme: getTerminalThemeFromCSS()`. Supprimer tout le bloc conditionnel `props.theme === 'dark' ? { ... } : { ... }`.

**Avant :**
```typescript
theme: props.theme === 'dark' ? {
  background: '#0c0c0c',
  foreground: '#cccccc',
  // ... 30+ lignes de couleurs hardcodées
} : {
  background: '#ffffff',
  foreground: '#000000',
  // ...
}
```

**Après :**
```typescript
theme: getTerminalThemeFromCSS(),
```

**Dépend de :** Tâche 1

---

### Tâche 3 : Remplacer les couleurs CSS hardcodées par des variables CSS

**Objectif :** Supprimer toutes les couleurs hexadécimales hardcodées dans la section `<style scoped>` et les remplacer par des variables CSS. Cela couvre à la fois le conteneur terminal et les indicateurs de status.

**Fichiers :**
- `frontend/src/components/ContainerTerminal.vue` — Modifier — Dans la section `<style scoped>` :
  - **Container terminal (lignes ~340-346) :** Remplacer `.terminal-container.theme-dark { background-color: #0c0c0c; }` et `.terminal-container.theme-light { background-color: #ffffff; }` par une seule règle `.terminal-container { background-color: var(--color-terminal-bg); }`
  - **Status dots (lignes ~296-307) :** Remplacer `#67c23a` par `var(--color-success)`, `#e6a23c` par `var(--color-warning)`, `#909399` par `var(--color-info)`

**Dépend de :** Tâche 2

---

### Tâche 4 : Simplifier le template (supprimer classes theme-dark/light)

**Objectif :** Le template n'a plus besoin de classes conditionnelles pour le thème puisque les variables CSS s'adaptent automatiquement via `theme.css`. Simplifier le binding `:class`.

**Fichiers :**
- `frontend/src/components/ContainerTerminal.vue` — Modifier — Dans le template, trouver le `<div ref="terminalRef" class="terminal-container" :class="{ 'theme-dark': theme === 'dark', 'theme-light': theme === 'light' }">` et supprimer le `:class` conditionnel. Le thème est maintenant géré entièrement par les variables CSS.

**Avant :**
```vue
<div ref="terminalRef" class="terminal-container" :class="{ 'theme-dark': theme === 'dark', 'theme-light': theme === 'light' }" />
```

**Après :**
```vue
<div ref="terminalRef" class="terminal-container" />
```

**Dépend de :** Tâche 3

---

### Tâche 5 : Vérifier le build frontend

**Objectif :** S'assurer que les modifications ne cassent pas le build et que le composant fonctionne correctement dans les deux modes de thème.

**Fichiers :**
- Aucun fichier à modifier

**Commandes de validation :**
```bash
cd frontend && pnpm build
cd frontend && pnpm lint
```

**Critères de succès :**
- Build passe sans erreur
- Lint passe sans erreur (ou warnings acceptables)
- Le terminal s'affiche correctement en dark mode et light mode (validation visuelle manuelle si nécessaire)

**Dépend de :** Tâche 4

---

## Tests à écrire

### Tests unitaires

#### Test 1 : Vérifier la fonction `getTerminalThemeFromCSS()`
**Fichier :** `frontend/tests/unit/components/ContainerTerminal.spec.ts` (à créer si inexistant)

**Cas de test :**
- `should return a valid xterm theme object` — Mock `getComputedStyle` avec des valeurs de test, vérifier que la fonction retourne un objet avec toutes les 18 clés attendues (background, foreground, cursor, selectionBackground, black, red, green, yellow, blue, magenta, cyan, white, brightBlack, brightRed, brightGreen, brightYellow, brightBlue, brightMagenta, brightCyan, brightWhite)
- `should handle missing CSS variables gracefully` — Vérifier le comportement si une variable CSS est manquante (retourne chaîne vide)

#### Test 2 : Vérifier l'absence de couleurs hardcodées
**Fichier :** `frontend/tests/unit/components/ContainerTerminal.spec.ts`

**Cas de test :**
- `should not contain hardcoded hex colors in <style>` — Lire le source du composant, vérifier qu'aucune couleur hex `#[0-9a-fA-F]{6}` n'est présente dans la section `<style>` (sauf éventuellement dans les commentaires)

### Commandes de validation
```bash
# Tests unitaires
cd frontend && pnpm test -- tests/unit/components/ContainerTerminal

# Build & lint
cd frontend && pnpm build && pnpm lint
```

## Notes d'implémentation

### Fichiers modifiés
- `frontend/src/components/ContainerTerminal.vue` — Refactorisation complète du theming

### Décisions techniques
1. **Helper `getTerminalThemeFromCSS()`** : Création d'une fonction qui lit les variables CSS via `getComputedStyle()` pour contourner la limitation de xterm.js qui ne supporte pas les variables CSS directement dans son objet `theme`.

2. **Interface `XtermTheme`** : Ajout d'une interface TypeScript locale pour typer le thème xterm.js avec les 18 propriétés de couleur.

3. **Simplification CSS** : 
   - Suppression des classes `.theme-dark` et `.theme-light` du CSS
   - Utilisation de `var(--color-terminal-bg)` pour le conteneur
   - Utilisation de `var(--color-success)`, `var(--color-warning)`, `var(--color-info)` pour les status dots

4. **Simplification du template** : Suppression du `:class` conditionnel sur `.terminal-container` car le thème est maintenant géré entièrement par les variables CSS.

### Tests
- 5 tests unitaires créés dans `frontend/tests/unit/components/ContainerTerminal.spec.ts`
- Tous les tests passent (5/5)
- Build frontend réussi

### Difficultés rencontrées
Aucune. L'implémentation s'est déroulée comme prévu dans l'analyse.
```
