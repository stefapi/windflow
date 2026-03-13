# STORY-412 : Règle des 2 clics — validation et ajustement navigation

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux accéder à n'importe quelle ressource (container, VM, stack, plugin) en maximum 2 clics depuis le dashboard afin de gagner en efficacité au quotidien.

## Critères d'acceptation (AC)
- [ ] AC 1 : Depuis le Dashboard, un clic sur la sidebar mène à la liste de la catégorie choisie
- [ ] AC 2 : Depuis une liste, un clic sur un élément mène à son détail — soit 2 clics max depuis le dashboard
- [ ] AC 3 : Les tuiles du dashboard (Containers, VMs, Stacks) sont cliquables et mènent directement aux listes
- [ ] AC 4 : Aucune page ne nécessite plus de 2 niveaux de navigation (sauf Settings qui a des onglets internes)
- [ ] AC 5 : Le router Vue est restructuré pour refléter cette hiérarchie plate (pas de routes imbriquées au-delà de 2 niveaux)
- [ ] AC 6 : Le breadcrumb est présent sur chaque page pour indiquer la position

## État d'avancement technique
- [ ] Audit de toutes les routes actuelles et comptage des clics nécessaires
- [ ] Refactoring du router pour aplatir la navigation
- [ ] Ajout d'un composant Breadcrumb global
- [ ] Vérification de chaque parcours utilisateur (dashboard → liste → détail)
- [ ] Tests Vitest navigation
