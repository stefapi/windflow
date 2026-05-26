# STORY-014 : Support registre custom (self-hosted)

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant qu'Administrateur, je veux configurer des registres de plugins custom (self-hosted) afin de distribuer des plugins internes ou communautaires en dehors du registre officiel WindFlow.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
Les organisations peuvent vouloir héberger leurs propres plugins sur un registre interne. Le système doit supporter l'ajout de registres custom (URL + auth optionnelle) et agréger les plugins de tous les registres configurés dans la Marketplace.

## Critères d'acceptation (AC)
- [ ] AC 1 : L'administrateur peut ajouter, modifier et supprimer des registres custom via l'API et l'UI (settings)
- [ ] AC 2 : Les plugins des registres custom sont agrégés avec ceux du registre officiel dans la Marketplace
- [ ] AC 3 : L'authentification (token/API key) est supportée pour les registres custom qui le requièrent
- [ ] AC 4 : Les plugins des registres custom sont marqués comme "Communautaire" dans l'UI
- [ ] AC 5 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-013 : Registre officiel (index JSON ou API simple)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
