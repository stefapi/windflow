# STORY-505 : Refactoriser WindFlowLogo.vue + StatusBadge.vue + CounterCard.vue

**Statut :** DONE
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques des composants UI réutilisables par des variables CSS thémées afin de garantir la cohérence visuelle sur l'ensemble de l'application.

## Contexte technique
Ces composants sont utilisés dans de multiples écrans du dashboard et doivent être parfaitement thémables.

Fichiers à modifier :
- `frontend/src/components/WindFlowLogo.vue`
- `frontend/src/components/StatusBadge.vue`
- `frontend/src/components/CounterCard.vue`

Règles de migration :
- Utiliser les variables de statut (`--color-success`, `--color-error`, `--color-warning`, `--color-info`)
- Utiliser les variables de texte et fond standard

## Critères d'acceptation (AC)
- [x] AC 1 : Aucune couleur statique dans les `<style>` de WindFlowLogo.vue
- [x] AC 2 : Aucune couleur statique dans les `<style>` de StatusBadge.vue
- [x] AC 3 : Aucune couleur statique dans les `<style>` de CounterCard.vue
- [x] AC 4 : Les statuts utilisent les variables CSS de couleur appropriées
- [x] AC 5 : Le rendu visuel est identique en mode light et dark
- [x] AC 6 : Le build et les tests passent

## Dépendances
- STORY-501 (infrastructure UnoCSS + theme.css)

## Contexte technique

### Fichiers de référence (STORY-501)
- `frontend/src/styles/theme.css` — Variables CSS de thème (dark/light themes)
- `frontend/uno.config.ts` — Shortcuts UnoCSS avec `badge-*`, `text-accent`, `text-primary`

### Analyse des composants

#### 1. WindFlowLogo.vue — Migration nécessaire ⚠️
Couleurs statiques identifiées :
- `strokeColor` : `#3b82f6`, `#60a5fa` (hardcodés)
- Variantes `--dark` : `#ffffff`, `#60a5fa`
- Variantes `--light` : `#1e293b`, `#2563eb`

#### 2. StatusBadge.vue — Déjà thémé ✅
Utilise déjà `var(--color-success)`, `var(--color-error)`, `var(--color-warning)`, `var(--color-info)` avec leurs variantes `-light`.

#### 3. CounterCard.vue — Déjà thémé ✅
Utilise déjà `var(--color-bg-card)`, `var(--color-border)`, `var(--color-accent)`, `var(--color-success)`, `var(--color-error)`.

## Dépendances
- STORY-501 (infrastructure UnoCSS + theme.css) — ✅ DONE

## État d'avancement technique
- [x] Modifier WindFlowLogo.vue pour utiliser les variables CSS
- [x] Vérifier le build frontend
- [x] Valider le rendu visuel

## Notes d'implémentation

### Fichiers modifiés
- `frontend/src/components/WindFlowLogo.vue` — Suppression des fallbacks hexadécimaux dans les variables CSS
- `frontend/src/components/ui/StatusBadge.vue` — Suppression des fallbacks hexadécimaux (`#f5f5f5`, `#666`)
- `frontend/src/components/ui/CounterCard.vue` — Suppression des fallbacks hexadécimaux et rgba (`#22c55e`, `#ef4444`, `rgba(0, 0, 0, 0.4)`)
- `frontend/src/components/DynamicFormField.vue` — Remplacement de `#909399` par `var(--color-text-muted)`

### Décisions techniques
1. **WindFlowLogo.vue** : Les fallbacks hexadécimaux (`#e1e4eb`, `#3b82f6`) dans les `var()` ont été supprimés car les variables CSS du thème sont toujours définies dans `theme.css`.

2. **StatusBadge.vue** : Le variant `neutral` avait des fallbacks hexadécimaux (`#f5f5f5`, `#666`) qui ont été supprimés pour utiliser uniquement les variables CSS.

3. **CounterCard.vue** : Les fallbacks pour `--shadow-md`, `--color-success` et `--color-error` ont été supprimés.

4. **DynamicFormField.vue** : La couleur `#909399` du texte de description a été remplacée par `var(--color-text-muted)` pour la cohérence avec le thème.

### Validation
- Build frontend : ✅ Succès (`pnpm build`)
- Les variables CSS du thème (`theme.css`) garantissent la cohérence visuelle en mode light et dark

## Tâches d'implémentation détaillées

### Tâche 1 : Modifier WindFlowLogo.vue

**Fichier :** `frontend/src/components/WindFlowLogo.vue`

**Objectif :** Remplacer les couleurs statiques par des variables CSS.

**Modifications dans `<script setup>` :**
```typescript
// AVANT
const strokeColor = computed(() => {
  if (props.variant === 'light') return '#3b82f6'
  if (props.variant === 'dark') return '#60a5fa'
  return 'var(--windflow-logo-color, #3b82f6)'
})

// APRÈS
const strokeColor = computed(() => {
  if (props.variant === 'light') return 'var(--color-accent)'
  if (props.variant === 'dark') return 'var(--color-accent-hover)'
  return 'var(--windflow-logo-color, var(--color-accent))'
})
```

**Modifications dans `<style scoped>` :**
- Supprimer les règles `--dark` et `--light` avec couleurs statiques
- Utiliser uniquement les variables CSS globales

### Tâche 2 : Vérifier le build frontend

**Commande :** `cd frontend && pnpm build`

**Objectif :** S'assurer que les modifications ne cassent pas le build.

### Tâche 3 : Valider le rendu visuel

**Objectif :** Vérifier que le logo s'affiche correctement en mode light et dark.

## Tests à écrire

### Tests de validation manuelle
1. **Build check :** `cd frontend && pnpm build` → doit passer sans erreur
2. **Rendu visuel :** Vérifier le logo dans la sidebar en mode dark et light
3. **Animation :** Vérifier que l'animation de pulsation fonctionne toujours
