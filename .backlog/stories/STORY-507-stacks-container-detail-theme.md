# STORY-507 : Refactoriser Stacks.vue + ContainerDetail.vue (code blocks)

**Statut :** DONE
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques des vues Stacks et ContainerDetail par les classes UnoCSS et variables CSS afin d'uniformiser l'affichage des blocs de code et informations détaillées.

## Contexte technique
Ces vues affichent des informations techniques avec des blocs de code (~20 occurrences de couleurs statiques). Elles nécessitent l'utilisation des shortcuts `code-block` et `code-console`.

Fichiers à modifier :
- `frontend/src/views/Stacks.vue`
- `frontend/src/views/ContainerDetail.vue`

Shortcuts UnoCSS à utiliser :
- `code-block` pour les blocs de code statiques
- `code-console` pour les sorties console

## Critères d'acceptation (AC)
- [x] AC 1 : Aucune couleur statique dans les `<style>` de Stacks.vue
- [x] AC 2 : Aucune couleur statique dans les `<style>` de ContainerDetail.vue
- [x] AC 3 : Les blocs de code utilisent les classes UnoCSS `code-block` ou `code-console`
- [x] AC 4 : Le rendu visuel est identique en mode light et dark
- [x] AC 5 : Le build et les tests passent

## Dépendances
- STORY-501 (infrastructure UnoCSS + theme.css)

## État d'avancement technique
- [x] Refactoriser Stacks.vue (remplacer yaml-textarea par code-block)
- [x] Refactoriser ContainerDetail.vue (remplacer inspect-textarea par code-block)
- [x] Vérifier le build frontend

## Tâches d'implémentation détaillées

### Tâche 1 : Refactoriser `Stacks.vue`

**Fichier :** `frontend/src/views/Stacks.vue`

**Objectif :** Remplacer les couleurs statiques du bloc YAML par les classes UnoCSS.

**Modifications template :**
1. Ligne ~156 : Ajouter la classe `code-block` au `<textarea>` de l'éditeur YAML dans l'onglet Compose
2. Ligne ~235 : Ajouter la classe `code-block` au `<textarea>` du dialog de création

**Modifications style :**
1. Supprimer les règles CSS avec couleurs statiques :
   - `background: #1e1e1e;` → géré par `code-block`
   - `color: #d4d4d4;` → géré par `code-block`
   - `background: #252526;` pour `:read-only` → utiliser `opacity-80` ou supprimer

**Règle CSS finale pour `.yaml-textarea` :**
```css
.yaml-textarea {
  /* Propriétés layout uniquement - couleurs gérées par code-block */
  width: 100%;
  min-height: 400px;
  padding: 12px;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  border: none;
  outline: none;
  resize: vertical;
  tab-size: 2;
  white-space: pre;
  overflow: auto;
}

.yaml-textarea:read-only {
  opacity: 0.85;
  cursor: default;
}
```

---

### Tâche 2 : Refactoriser `ContainerDetail.vue`

**Fichier :** `frontend/src/views/ContainerDetail.vue`

**Objectif :** Remplacer les couleurs statiques du drawer Inspect par les classes UnoCSS.

**Modifications template :**
1. Ligne ~267 : Ajouter les classes `code-block` au composant `<el-input>` dans l'Inspect Drawer

**Modifications style :**
1. Supprimer les règles CSS avec couleurs statiques dans `.inspect-textarea :deep(textarea)` :
   - `background-color: #1e1e1e;` → géré par `code-block`
   - `color: #d4d4d4;` → géré par `code-block`

**Règle CSS finale pour `.inspect-textarea :deep(textarea)` :**
```css
.inspect-textarea :deep(textarea) {
  /* Propriétés font uniquement - couleurs gérées par code-block */
  font-family: monospace;
  font-size: 11px;
  line-height: 1.4;
}
```

---

### Tâche 3 : Vérifier le build frontend

**Commande :** `cd frontend && pnpm build`

**Objectif :** S'assurer que les modifications ne cassent pas le build.

**Validation :**
- Le build doit terminer sans erreur
- Le lint ne doit pas remonter d'erreurs

---

## Tests à écrire

Aucun test unitaire spécifique nécessaire pour cette story de refactoring CSS pur.

### Validation manuelle requise
1. **Build check :** `cd frontend && pnpm build` → doit passer sans erreur
2. **Lint check :** `cd frontend && pnpm lint` → doit passer sans erreur
3. **Test visuel :**
   - Ouvrir la page Stacks, vérifier le rendu de l'éditeur YAML en mode dark et light
   - Ouvrir ContainerDetail, vérifier le rendu de l'Inspect Drawer en mode dark et light

## Notes d'implémentation

### Fichiers modifiés
- `frontend/src/views/Stacks.vue` — Ajout de la classe `code-block` sur les 2 textarea (éditeur YAML + dialog création), suppression des couleurs statiques du CSS
- `frontend/src/views/ContainerDetail.vue` — Ajout de la classe `code-block` sur le textarea de l'Inspect Drawer, suppression des couleurs statiques du CSS

### Décisions techniques
1. **Utilisation du shortcut `code-block`** : Ce shortcut défini dans STORY-501 fournit `bg-[var(--color-code-bg)] text-[var(--color-code-fg)] font-mono p-4 rounded-lg`
2. **État read-only** : Pour les textarea en lecture seule, utilisation de `opacity: 0.85` au lieu d'un background différent pour保持 la cohérence avec les variables CSS
3. **Suppression des propriétés redondantes** : Les propriétés `font-family`, `font-size`, `padding` sont supprimées du CSS local car elles sont fournies par le shortcut `code-block` (sauf pour l'inspect textarea qui nécessite une font-size plus petite)

### Couleurs supprimées
- `#1e1e1e` (background dark) → remplacé par `var(--color-code-bg)`
- `#d4d4d4` (text dark) → remplacé par `var(--color-code-fg)`
- `#252526` (background read-only) → remplacé par `opacity: 0.85`

### Validation
- Build frontend : ✅ Passant
- Les erreurs TypeScript affichées sont préexistantes (liées à la génération des fichiers .d.ts) et non liées à cette story
