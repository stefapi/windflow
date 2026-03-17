# STORY-434 : Zone widgets plugins sur le dashboard

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux une zone dédiée aux widgets plugins sur le dashboard afin que les plugins puissent y injecter des informations pertinentes (Uptime Kuma, Traefik, Restic…) sans modifier le code core.

## Critères d'acceptation (AC)
- [x] AC 1 : Une zone « Widgets Plugins » est visible en bas du dashboard
- [x] AC 2 : Si aucun plugin n'est installé, la zone n'est **pas** affichée (pas de section vide)
- [x] AC 3 : Le store Pinia `usePluginWidgetStore` permet aux plugins d'enregistrer des widgets (composant + props)
- [x] AC 4 : Les widgets sont rendus dynamiquement via `<component :is="...">` depuis le store
- [x] AC 5 : Un widget placeholder de démonstration est créé pour tester le mécanisme (affiché uniquement en mode dev)
- [x] AC 6 : La zone widgets s'adapte en grille responsive (2 colonnes desktop, 1 colonne tablette)

## État d'avancement technique
- [x] Création du store `usePluginWidgetStore` (Pinia) — register/unregister widgets
- [x] Composant `PluginWidgetZone.vue` avec rendu dynamique
- [x] Intégration dans le Dashboard (conditionnel : masqué si 0 widget)
- [x] Widget placeholder de test (mode dev uniquement)
- [x] Layout grille responsive
- [x] Tests Vitest du store et du composant

## Notes d'implémentation

### Fichiers créés
- `frontend/src/stores/pluginWidget.ts` — Store Pinia pour gérer l'enregistrement des widgets plugins
- `frontend/src/components/dashboard/PluginWidgetZone.vue` — Composant de zone de widgets avec grille responsive
- `frontend/src/components/dashboard/plugins/PlaceholderWidget.vue` — Widget de démonstration (mode dev uniquement)
- `frontend/tests/unit/stores/pluginWidget.spec.ts` — Tests du store (17 tests)
- `frontend/tests/unit/components/dashboard/PluginWidgetZone.spec.ts` — Tests du composant (10 tests)

### Fichiers modifiés
- `frontend/src/stores/index.ts` — Export du nouveau store
- `frontend/src/views/Dashboard.vue` — Intégration de PluginWidgetZone et enregistrement du widget placeholder en mode dev

### API du store
```typescript
// Enregistrer un widget
pluginWidgetStore.registerWidget({
  pluginId: 'my-plugin',
  widget: {
    id: 'my-widget',
    component: MyWidgetComponent,
    title: 'My Widget',  // optionnel
    order: 10,           // optionnel, défaut 100
    props: { foo: 'bar' } // optionnel
  }
})

// Retirer un widget
pluginWidgetStore.unregisterWidget('my-widget')

// Retirer tous les widgets d'un plugin
pluginWidgetStore.unregisterPlugin('my-plugin')
```

### Tests
- 27 tests passent (17 store + 10 composant)
- Couverture : enregistrement, désinscription, ordonnancement, réactivité, rendu conditionnel
