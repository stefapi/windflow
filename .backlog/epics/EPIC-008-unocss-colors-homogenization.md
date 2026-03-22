# EPIC-008 : Homogénéisation des couleurs UnoCSS

**Statut :** IN_PROGRESS
**Priorité :** Haute

## Vision
Uniformiser l'ensemble des composants Vue pour utiliser exclusivement les variables CSS de thème et les classes utilitaires UnoCSS, garantissant une cohérence visuelle parfaite et un support complet du dark/light theme.

## Contexte
Le projet dispose déjà d'une configuration UnoCSS (`uno.config.ts`) et de variables CSS de thème (`theme.css`) complètes. Cependant, **152 occurrences de couleurs statiques** (hex, rgb, rgba) subsistent dans ~25 composants Vue, créant :
- Incohérences visuelles entre écrans
- Difficultés de maintenance
- Support partiel du dark/light theme
- Duplication de code

### Répartition des occurrences
| Catégorie | Fichiers | Occurrences |
|-----------|----------|-------------|
| Logs/Terminal | ContainerLogs.vue, DeploymentLogs.vue, ContainerTerminal.vue | ~50 |
| Login/Splash | Login.vue, SplashScreen.vue | ~30 |
| Composants UI | WindFlowLogo.vue, StatusBadge.vue, CounterCard.vue, DynamicFormField.vue | ~25 |
| Views avec code | Stacks.vue, ContainerDetail.vue | ~20 |
| Autres | Divers (Settings, Targets, etc.) | ~27 |

## Objectifs
1. Éliminer toutes les couleurs statiques des composants Vue
2. Enrichir UnoCSS avec les shortcuts manquants (logs, terminal, code blocks)
3. Ajouter les variables CSS pour terminal thémé (VS Code style)
4. Garantir le support dark/light theme sur tous les composants
5. Améliorer la maintenabilité du design system

## Liste des Stories liées

### Phase 1 : Infrastructure UnoCSS
- [x] STORY-501 : Enrichir UnoCSS + theme.css avec variables terminal/logs/code blocks

### Phase 2 : Composants critiques (haute visibilité)
- [x] STORY-502 : Refactoriser Login.vue + SplashScreen.vue → variables CSS thémées
- [x] STORY-503 : Refactoriser ContainerLogs.vue + DeploymentLogs.vue → classes UnoCSS
- [ ] STORY-504 : Refactoriser ContainerTerminal.vue → variables CSS thémées (palette VS Code)

### Phase 3 : Composants UI réutilisables
- [x] STORY-505 : Refactoriser WindFlowLogo.vue + StatusBadge.vue + CounterCard.vue
- [ ] STORY-506 : Refactoriser DynamicFormField.vue + composants settings UI

### Phase 4 : Views principales et secondaires
- [ ] STORY-507 : Refactoriser Stacks.vue + ContainerDetail.vue (code blocks)
- [ ] STORY-508 : Refactoriser toutes les autres views (batch audit - ~15 fichiers)

## Critères de succès (Definition of Done)
- [ ] Aucune couleur statique (hex, rgb, rgba) dans les `<style>` des composants Vue
- [ ] Tous les composants utilisent les classes UnoCSS ou les variables CSS
- [ ] Support dark/light theme validé sur tous les écrans
- [ ] Tests visuels passants (screenshots comparaison si disponible)
- [ ] Documentation mise à jour (guide de style)

## Notes de conception

### Règles de migration
1. **Backgrounds** : `#0c0e14` → `var(--color-bg-primary)`, `#1e1e1e` → `var(--color-bg-secondary)`
2. **Textes** : `#d4d4d4` → `var(--color-text-primary)`, `#7c8098` → `var(--color-text-secondary)`
3. **Status** : Utiliser les variables `--color-success`, `--color-error`, etc.
4. **Borders** : `#252838` → `var(--color-border)`, `#3a3f54` → `var(--color-border-focus)`
5. **Terminal** : Utiliser les nouvelles variables `--color-terminal-*` (palette VS Code thémée)

### Variables CSS à ajouter (theme.css)
```css
/* Terminal colors - VS Code style */
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

/* Log colors */
--color-log-error: #f48771;
--color-log-warning: #cca700;
--color-log-info: #4fc3f7;
--color-log-debug: #858585;
--color-log-line-number: #858585;

/* Code blocks */
--color-code-bg: #1e1e1e;
--color-code-fg: #d4d4d4;
```

### Shortcuts UnoCSS à ajouter
```typescript
'log-error': 'text-[var(--color-log-error)]',
'log-warning': 'text-[var(--color-log-warning)]',
'log-info': 'text-[var(--color-log-info)]',
'log-debug': 'text-[var(--color-log-debug)] italic',
'log-line-number': 'text-[var(--color-log-line-number)] select-none pr-3',
'code-block': 'bg-[var(--color-code-bg)] text-[var(--color-code-fg)] font-mono',
'code-console': 'bg-[var(--color-terminal-bg)] text-[var(--color-terminal-fg)] font-mono',
```

### Patterns à suivre
```vue
<!-- Avant -->
<style scoped>
.my-component {
  background-color: #1e1e1e;
  color: #d4d4d4;
}
</style>

<!-- Après -->
<template>
  <div class="my-component bg-bg-primary text-text-primary">
</template>
```

## Risques
- Régressions visuelles possibles lors de la migration
- Temps de validation important pour chaque composant
- Certains composants peuvent avoir des cas limites non couverts par les variables actuelles

## Estimation
- **Phase 1** : 1 story (infrastructure)
- **Phases 2-4** : 7 stories (composants groupés)
- **Total** : 8 stories
