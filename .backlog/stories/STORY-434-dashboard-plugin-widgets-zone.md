# STORY-434 : Zone widgets plugins sur le dashboard

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux une zone dédiée aux widgets plugins sur le dashboard afin que les plugins puissent y injecter des informations pertinentes (Uptime Kuma, Traefik, Restic…) sans modifier le code core.

## Critères d'acceptation (AC)
- [ ] AC 1 : Une zone « Widgets Plugins » est visible en bas du dashboard
- [ ] AC 2 : Si aucun plugin n'est installé, la zone n'est **pas** affichée (pas de section vide)
- [ ] AC 3 : Le store Pinia `usePluginWidgetStore` permet aux plugins d'enregistrer des widgets (composant + props)
- [ ] AC 4 : Les widgets sont rendus dynamiquement via `<component :is="...">` depuis le store
- [ ] AC 5 : Un widget placeholder de démonstration est créé pour tester le mécanisme (affiché uniquement en mode dev)
- [ ] AC 6 : La zone widgets s'adapte en grille responsive (2 colonnes desktop, 1 colonne tablette)

## État d'avancement technique
- [ ] Création du store `usePluginWidgetStore` (Pinia) — register/unregister widgets
- [ ] Composant `PluginWidgetZone.vue` avec rendu dynamique
- [ ] Intégration dans le Dashboard (conditionnel : masqué si 0 widget)
- [ ] Widget placeholder de test (mode dev uniquement)
- [ ] Layout grille responsive
- [ ] Tests Vitest du store et du composant
