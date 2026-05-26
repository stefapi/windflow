# STORY-005 : Configuration plugin depuis l'UI (formulaires dynamiques générés depuis manifest)

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant qu'Utilisateur, je veux configurer un plugin installé depuis l'interface via des formulaires dynamiques générés à partir du manifest afin de personnaliser le comportement du plugin sans éditer manuellement des fichiers de configuration.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
Le composant `DynamicFormField.vue` existe déjà dans le frontend. La section `config` du manifest YAML définit les champs de configuration avec leurs types, valeurs par défaut et contraintes. L'UI doit générer le formulaire dynamiquement à partir de cette définition.

## Critères d'acceptation (AC)
- [ ] AC 1 : L'UI affiche un formulaire de configuration généré dynamiquement à partir de la section `config` du manifest du plugin
- [ ] AC 2 : Le composant `DynamicFormField.vue` existant est réutilisé pour le rendu des champs
- [ ] AC 3 : La validation côté client et côté serveur est appliquée selon les contraintes définies dans le manifest
- [ ] AC 4 : Les valeurs de configuration sont persistées et rechargées correctement après redémarrage
- [ ] AC 5 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-001 : Format manifest YAML (spécification + validation Pydantic)
- STORY-002 : API REST Plugin Manager — CRUD plugins

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
