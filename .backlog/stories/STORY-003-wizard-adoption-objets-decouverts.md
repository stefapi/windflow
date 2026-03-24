# STORY-003 : Wizard d'adoption d'objets découverts

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux adopter un objet découvert (container, composition Compose ou release Helm) via un wizard en 3 étapes afin de l'intégrer sous contrôle WindFlow comme une stack managée.

## Contexte technique
- Nouveau composant `components/AdoptionWizard.vue` (dialog en 3 étapes)
- APIs : `GET /discovery/{type}/{id}/adoption-data`, `POST /discovery/adopt`
- Types TypeScript : `AdoptionRequest` (avec support `helm_release` + options Helm), `AdoptionWizardData`
- Étape 1 — Inventaire : configuration détectée (services, env, volumes, réseaux, ports)
- Étape 2 — Mapping : choix nom stack, stratégie volumes/réseaux, options Helm si applicable
- Étape 3 — Validation : preview Compose/Helm généré + confirmation

## Critères d'acceptation (AC)
- [ ] AC 1 : Le wizard s'ouvre depuis le bouton "↗ Adopter" d'un objet découvert et charge les données via `GET /discovery/{type}/{id}/adoption-data`
- [ ] AC 2 : L'étape 1 affiche la configuration détectée (services, env, volumes, réseaux, ports)
- [ ] AC 3 : L'étape 2 permet de choisir le nom de la stack, la stratégie volumes/réseaux et les options Helm (si type helm_release)
- [ ] AC 4 : L'étape 3 affiche un preview du Compose/Helm généré et déclenche `POST /discovery/adopt` à la confirmation
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-002 (Section Discovered — point d'entrée du wizard)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
