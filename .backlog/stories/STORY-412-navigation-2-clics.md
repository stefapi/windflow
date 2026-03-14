# STORY-412 : Règle des 2 clics — validation et ajustement navigation

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux accéder à n'importe quelle ressource (container, VM, stack, plugin) en maximum 2 clics depuis le dashboard afin de gagner en efficacité au quotidien.

## Critères d'acceptation (AC)
- [x] AC 1 : Depuis le Dashboard, un clic sur la sidebar mène à la liste de la catégorie choisie
- [x] AC 2 : Depuis une liste, un clic sur un élément mène à son détail — soit 2 clics max depuis le dashboard
- [x] AC 3 : Les tuiles du dashboard (Containers, VMs, Stacks) sont cliquables et mènent directement aux listes
- [x] AC 4 : Aucune page ne nécessite plus de 2 niveaux de navigation (sauf Settings qui a des onglets internes)
- [x] AC 5 : Le router Vue est restructuré pour refléter cette hiérarchie plate (pas de routes imbriquées au-delà de 2 niveaux)
- [x] AC 6 : Le breadcrumb est présent sur chaque page pour indiquer la position

## État d'avancement technique
- [x] Audit de toutes les routes actuelles et comptage des clics nécessaires
- [x] Refactoring du router pour aplatir la navigation
- [x] Ajout d'un composant Breadcrumb global
- [x] Vérification de chaque parcours utilisateur (dashboard → liste → détail)
- [x] Tests Vitest navigation (18 tests passants)

## Notes d'implémentation

### Fichiers analysés
- `frontend/src/router/index.ts` : Router avec navigation plate (pas de routes imbriquées)
- `frontend/src/components/Breadcrumb.vue` : Composant breadcrumb fonctionnel
- `frontend/src/views/Dashboard.vue` : Tuiles cliquables vers les listes
- `frontend/src/layouts/MainLayout.vue` : Breadcrumb intégré
- `frontend/src/components/SidebarNav.vue` : Navigation par sections

### Validation
- Navigation plate : Toutes les routes sont de premier niveau (ex: `/containers`, `/deployments`, `/settings`)
- Breadcrumb : Affiche le chemin Dashboard > Page actuelle > Détail si applicable
- Dashboard : Tuiles avec `@click` naviguant vers les listes
- Tests : 18 tests passants (5 Breadcrumb + 13 SidebarNav)

### Configuration de test ajoutée
- `frontend/vitest.config.ts` : Configuration Vitest avec jsdom
- `frontend/package.json` : Ajout de jsdom et @vue/test-utils
