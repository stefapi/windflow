# STORY-010 : Installation one-click depuis la Marketplace

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant qu'Utilisateur, je veux installer un plugin en un seul clic depuis la Marketplace afin de pouvoir ajouter rapidement des fonctionnalités à mon instance WindFlow sans manipulation technique.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
L'installation one-click combine l'appel à l'API Plugin Manager (STORY-002) avec l'UI Marketplace (STORY-009). Le flux doit gérer la vérification de compatibilité, la résolution des dépendances, le téléchargement et l'installation, avec un feedback en temps réel via WebSocket.

## Critères d'acceptation (AC)
- [ ] AC 1 : Un bouton "Installer" sur la fiche plugin déclenche le flux complet d'installation (vérification → téléchargement → installation → configuration)
- [ ] AC 2 : La progression de l'installation est affichée en temps réel dans l'UI via WebSocket
- [ ] AC 3 : En cas d'erreur (incompatibilité, dépendance manquante), un message clair est affiché avec des suggestions de résolution
- [ ] AC 4 : Après installation, le plugin apparaît dans la liste des plugins installés et est démarré automatiquement
- [ ] AC 5 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-002 : API REST Plugin Manager — CRUD plugins
- STORY-008 : API Marketplace — catalogue, recherche, filtres par catégorie
- STORY-009 : UI Marketplace — catalogue browsable avec fiches plugin

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
