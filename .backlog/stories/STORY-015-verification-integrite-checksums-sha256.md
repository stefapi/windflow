# STORY-015 : Vérification d'intégrité (checksums SHA-256)

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux que le système vérifie l'intégrité des plugins téléchargés via des checksums SHA-256 afin de garantir que les packages n'ont pas été altérés pendant le transit.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
La sécurité est un aspect critique du système de plugins. Chaque package plugin distribué via le registre doit inclure un checksum SHA-256. Le backend doit vérifier ce checksum après téléchargement et avant l'installation. En cas de non-correspondance, l'installation doit être refusée.

## Critères d'acceptation (AC)
- [ ] AC 1 : Le registre fournit le checksum SHA-256 attendu pour chaque package plugin
- [ ] AC 2 : Le backend calcule le checksum du package téléchargé et le compare avec celui du registre avant installation
- [ ] AC 3 : En cas de non-correspondance, l'installation est refusée avec un message d'erreur explicite et le package est supprimé
- [ ] AC 4 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-001 : Format manifest YAML (spécification + validation Pydantic)
- STORY-013 : Registre officiel (index JSON ou API simple)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
