# STORY-013 : Registre officiel (index JSON ou API simple)

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux un registre officiel de plugins accessible via un index JSON ou une API simple afin de centraliser la distribution des plugins officiels WindFlow.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
Le registre officiel est la source de vérité pour les plugins maintenus par l'équipe WindFlow. Il expose un index des plugins disponibles avec leurs versions, checksums et URLs de téléchargement. L'implémentation peut être un simple fichier JSON hébergé ou une API légère.

## Critères d'acceptation (AC)
- [ ] AC 1 : Le registre expose un endpoint/index listant tous les plugins officiels avec leurs métadonnées (nom, version, description, checksum, URL)
- [ ] AC 2 : Chaque plugin du registre pointe vers un package téléchargeable avec son checksum SHA-256
- [ ] AC 3 : Le backend WindFlow peut interroger le registre pour récupérer la liste des plugins et les détails d'un plugin spécifique
- [ ] AC 4 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-001 : Format manifest YAML (spécification + validation Pydantic)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
