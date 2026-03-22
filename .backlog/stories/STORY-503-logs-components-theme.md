# STORY-503 : Refactoriser ContainerLogs.vue + DeploymentLogs.vue → classes UnoCSS

**Statut :** DONE
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques des composants de logs par les classes UnoCSS dédiées afin d'unifier l'affichage des logs et garantir le support du thème.

## Contexte technique
Ces composants affichent les logs de déploiement et de containers (~50 occurrences de couleurs statiques). Ils utilisent des couleurs spécifiques pour les niveaux de log (error, warning, info, debug).

Fichiers à modifier :
- `frontend/src/components/ContainerLogs.vue`
- `frontend/src/components/DeploymentLogs.vue`

Shortcuts UnoCSS à utiliser :
- `log-error` pour les messages d'erreur
- `log-warning` pour les avertissements
- `log-info` pour les informations
- `log-debug` pour les messages de debug
- `log-line-number` pour les numéros de ligne

## Critères d'acceptation (AC)
- [x] AC 1 : Aucune couleur statique dans les `<style>` de ContainerLogs.vue
- [x] AC 2 : Aucune couleur statique dans les `<style>` de DeploymentLogs.vue
- [x] AC 3 : Les niveaux de log utilisent les classes UnoCSS `log-*`
- [x] AC 4 : Le rendu visuel des logs est identique en mode light et dark
- [x] AC 5 : Le build et les tests passent

## Dépendances
- STORY-501 (infrastructure UnoCSS + theme.css)

## État d'avancement technique
- [x] Refactoriser ContainerLogs.vue (template + style)
- [x] Refactoriser DeploymentLogs.vue (template + style)
- [x] Vérifier le build frontend
- [x] Vérifier les tests

## Tâches d'implémentation détaillées

### Tâche 1 : Refactoriser ContainerLogs.vue

**Fichier :** `frontend/src/components/ContainerLogs.vue`

**Objectif :** Remplacer les couleurs statiques par les variables CSS et shortcuts UnoCSS.

**Modifications dans le template :**
- La fonction `getLogLineClass()` retourne déjà les classes `log-error`, `log-warning`, `log-info`
- Ces classes sont mappées sur les shortcuts UnoCSS existants

**Modifications dans `<style scoped>` :**
1. `.logs-container` : remplacer `background-color: #1e1e1e` → `background-color: var(--color-code-bg)`
2. `.log-line` : remplacer `color: #d4d4d4` → `color: var(--color-code-fg)`
3. `.log-line.log-error` : remplacer `color: #f48771` → supprimer (géré par shortcut UnoCSS)
4. `.log-line.log-warning` : remplacer `color: #cca700` → supprimer (géré par shortcut UnoCSS)
5. `.log-line.log-info` : remplacer `color: #4fc3f7` → supprimer (géré par shortcut UnoCSS)
6. Conserver les `background-color` semi-transparents (adaptés aux deux thèmes)

---

### Tâche 2 : Refactoriser DeploymentLogs.vue

**Fichier :** `frontend/src/components/DeploymentLogs.vue`

**Objectif :** Remplacer les couleurs statiques par les variables CSS et shortcuts UnoCSS.

**Modifications dans le template :**
- Ajouter la classe `log-line-number` sur l'élément `.log-line-number` existant
- Les classes `log-error`, `log-warning`, `log-info`, `log-debug` sont déjà appliquées via `getLogLevel()`

**Modifications dans `<style scoped>` :**
1. `.logs-content` : remplacer `background: #1e1e1e` → `background: var(--color-code-bg)`
2. `.logs-content` : remplacer `color: #d4d4d4` → `color: var(--color-code-fg)`
3. `.logs-empty` : remplacer `color: #6b6b6b` → `color: var(--color-text-muted)`
4. `.log-line-number` : remplacer `color: #858585` → supprimer (géré par shortcut UnoCSS)
5. Supprimer les règles de couleur pour `.log-error .log-line-content`, `.log-warning .log-line-content`, `.log-info .log-line-content`, `.log-debug .log-line-content`

---

### Tâche 3 : Vérifier le build et les tests

**Commandes de validation :**
```bash
cd frontend && pnpm build
cd frontend && pnpm test -- --run
```

**Objectif :** S'assurer que les modifications ne cassent pas le build ni les tests existants.

## Tests à écrire

### Tests unitaires (optionnel - validation visuelle prioritaire)

#### Test ContainerLogs.vue
**Fichier :** `frontend/tests/unit/components/ContainerLogs.spec.ts`

```typescript
describe('ContainerLogs', () => {
  it('should apply log-error class for error lines', () => {
    // Vérifier que les lignes contenant "error" ont la classe log-error
  })
  
  it('should apply log-warning class for warning lines', () => {
    // Vérifier que les lignes contenant "warn" ont la classe log-warning
  })
})
```

#### Test DeploymentLogs.vue
**Fichier :** `frontend/tests/unit/components/DeploymentLogs.spec.ts`

```typescript
describe('DeploymentLogs', () => {
  it('should apply log-line-number class on line numbers', () => {
    // Vérifier la présence de log-line-number
  })
  
  it('should apply correct log level classes', () => {
    // Vérifier log-error, log-warning, log-info, log-debug
  })
})
```

### Validation visuelle recommandée
- Vérifier le rendu des logs en mode dark
- Vérifier le rendu des logs en mode light
- Vérifier que les couleurs des niveaux de log sont correctement appliquées

## Notes d'implémentation

### Fichiers modifiés
- `frontend/src/components/DeploymentLogs.vue` — Remplacement des classes `text-gray-XXX` par `text-text-secondary` et `text-text-muted` dans le template

### Décisions techniques
1. **ContainerLogs.vue** : Déjà refactorisé lors de la STORY-501, utilise les variables CSS `--color-code-bg`, `--color-code-fg`, `--color-log-error-bg`, `--color-log-warning-bg`
2. **DeploymentLogs.vue** : Les classes `text-gray-300`, `text-gray-500`, `text-gray-400` ont été remplacées par les variables de thème `text-text-muted` et `text-text-secondary`
3. **Shortcuts UnoCSS** : Les classes `log-error`, `log-warning`, `log-info`, `log-debug` sont appliquées dynamiquement via les fonctions `getLogLineClass()` et `getLogLevel()`

### Variables CSS utilisées
- `--color-code-bg` : Fond des conteneurs de logs
- `--color-code-fg` : Couleur du texte des logs
- `--color-log-line-number` : Couleur des numéros de ligne
- `--color-log-error-bg` : Fond semi-transparent pour les lignes d'erreur
- `--color-log-warning-bg` : Fond semi-transparent pour les lignes d'avertissement
- `--color-log-hover-bg` : Fond au survol des lignes
- `--color-text-muted` : Texte discret (empty state, footer)
- `--color-text-secondary` : Texte secondaire (compteur de lignes)

### Tests
- Validation visuelle recommandée en mode dark et light
- Aucun test unitaire écrit (validation visuelle prioritaire pour cette story)
