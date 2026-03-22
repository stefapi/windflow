# EPIC-008 : Homogénéisation des couleurs UnoCSS

**Statut :** TODO
**Priorité :** Haute

## Vision
Uniformiser l'ensemble des composants Vue pour utiliser exclusivement les variables CSS de thème et les classes utilitaires UnoCSS, garantissant une cohérence visuelle parfaite et un support complet du dark/light theme.

## Contexte
Le projet dispose déjà d'une configuration UnoCSS (`uno.config.ts`) et de variables CSS de thème (`theme.css`) complètes. Cependant, **200+ occurrences de couleurs statiques** (hex, rgb, rgba) subsistent dans les composants Vue, créant :
- Incohérences visuelles entre écrans
- Difficultés de maintenance
- Support partiel du dark/light theme
- Duplication de code

## Objectifs
1. Éliminer toutes les couleurs statiques des composants Vue
2. Enrichir UnoCSS avec les shortcuts manquants
3. Garantir le support dark/light theme sur tous les composants
4. Améliorer la maintenabilité du design system

## Liste des Stories liées

### Phase 1 : Infrastructure UnoCSS
- [ ] STORY-XXX : Enrichir UnoCSS avec shortcuts pour logs/terminal/status

### Phase 2 : Composants critiques (haute visibilité)
- [ ] STORY-XXX : Refactoriser Login.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser ContainerLogs.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser DeploymentLogs.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser ContainerTerminal.vue - palette de couleurs thémée

### Phase 3 : Composants UI réutilisables
- [ ] STORY-XXX : Refactoriser SplashScreen.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser WindFlowLogo.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser CounterCard.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser StatusBadge.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser DynamicFormField.vue - couleurs statiques → UnoCSS

### Phase 4 : Views principales
- [ ] STORY-XXX : Refactoriser Dashboard.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Containers.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser ContainerDetail.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Stacks.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Deployments.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Targets.vue - couleurs statiques → UnoCSS

### Phase 5 : Views secondaires
- [ ] STORY-XXX : Refactoriser Settings.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Images.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Networks.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Volumes.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Audit.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Schedules.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser VMs.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Plugins.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Marketplace.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Workflows.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser WorkflowEditor.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser DeploymentDetail.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser DeploymentHistory.vue - couleurs statiques → UnoCSS

### Phase 6 : Composants dashboard/widgets
- [ ] STORY-XXX : Refactoriser ResourceMetricsWidget.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser ActivityFeedWidget.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser AlertsNotificationsWidget.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser DeploymentMetricsWidget.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser RecentDeploymentsWidget.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser TargetHealthWidget.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser PlaceholderWidget.vue - couleurs statiques → UnoCSS

### Phase 7 : Composants settings
- [ ] STORY-XXX : Refactoriser OrganizationsTab.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser UsersTab.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser OrganizationDialog.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser UserDialog.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser PasswordDialog.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser UserDetailsDrawer.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser BulkDeleteDialog.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser BulkAssignDialog.vue - couleurs statiques → UnoCSS

### Phase 8 : Autres composants
- [ ] STORY-XXX : Refactoriser ContainerStats.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser ContainerProcesses.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser SidebarNav.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser MainLayout.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser ThemeToggle.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser Breadcrumb.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser ActionButtons.vue - couleurs statiques → UnoCSS
- [ ] STORY-XXX : Refactoriser ResourceBar.vue - couleurs statiques → UnoCSS

## Critères de succès (Definition of Done)
- [ ] Aucune couleur statique (hex, rgb, rgba) dans les `<style>` des composants Vue
- [ ] Tous les composants utilisent les classes UnoCSS ou les variables CSS
- [ ] Support dark/light theme validé sur tous les écrans
- [ ] Tests visuels passants (screenshots comparaison si disponible)
- [ ] Documentation mise à jour (guide de style)

## Notes de conception

### Règles de migration
1. **Backgrounds** : `#0c0e14` → `bg-primary`, `#1e1e1e` → `bg-primary`, etc.
2. **Textes** : `#d4d4d4` → `text-primary`, `#7c8098` → `text-secondary`
3. **Status** : Utiliser les variables `--color-success`, `--color-error`, etc.
4. **Borders** : `#252838` → `border`, `#3a3f54` → `border-focus`

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

### Exceptions autorisées
- **Terminal** : Palette de couleurs spécifique (VS Code style) mais thémée via variables
- **Graphiques ECharts** : Couleurs dynamiques injectées via JS

## Risques
- Régressions visuelles possibles lors de la migration
- Temps de validation important pour chaque composant
- Certains composants peuvent avoir des cas limites non couverts par les variables actuelles

## Estimation
- **Phase 1** : 1 story (infrastructure)
- **Phases 2-8** : ~45 stories (composants)
- **Total** : ~46 stories
