# STORY-501 : Enrichir UnoCSS + theme.css avec variables terminal/logs/code blocks

**Statut :** TODO
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux enrichir la configuration UnoCSS et le fichier theme.css avec les variables CSS pour terminal, logs et code blocks afin de disposer d'une infrastructure de thème complète pour la migration des composants.

## Contexte technique
Cette story est le prérequis à toutes les autres stories de l'epic. Elle consiste à ajouter :
- Les variables CSS terminal (palette VS Code) dans `theme.css`
- Les variables CSS pour logs et code blocks
- Les shortcuts UnoCSS correspondants dans `uno.config.ts`

Fichiers de référence :
- `frontend/uno.config.ts` — Configuration UnoCSS actuelle
- `frontend/src/styles/theme.css` — Variables CSS de thème existantes

## Critères d'acceptation (AC)
- [ ] AC 1 : Les variables CSS `--color-terminal-*` (16 couleurs) sont ajoutées dans `theme.css`
- [ ] AC 2 : Les variables CSS `--color-log-*` (error, warning, info, debug, line-number) sont ajoutées
- [ ] AC 3 : Les variables CSS `--color-code-*` (bg, fg) sont ajoutées
- [ ] AC 4 : Les shortcuts UnoCSS `log-error`, `log-warning`, `log-info`, `log-debug`, `log-line-number` sont créés
- [ ] AC 5 : Les shortcuts UnoCSS `code-block`, `code-console` sont créés
- [ ] AC 6 : Le build frontend passe sans erreur

## Dépendances
Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
