# STORY-027 : Frontend — Onglet Aperçu synthétique conforme maquette UI

**Statut :** TODO
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
En tant qu'utilisateur, je veux un onglet "Aperçu" synthétique qui affiche en un coup d'œil les services de la stack, les ressources (CPU/RAM/Network/Disk I/O), les volumes et le réseau — sous forme de cards visuelles conformes à la maquette UI — afin d'avoir une vue d'ensemble rapide sans scroller dans une longue liste.

## Contexte technique
La maquette UI (`doc/general_specs/11-UI-mockups.md` Écran 3) définit un onglet "Aperçu" avec 3 cards : Services (liste des containers de la stack), Ressources (barres CPU/RAM + Network/Disk I/O), et Volumes (liste avec taille et bouton browse). Actuellement, ces informations sont éparpillées dans différents onglets ou absentes.

Le container peut appartenir à une stack (identifié par le label `com.docker.compose.project`) ou être standalone. Si standalone, la card "Services" affiche uniquement le container lui-même.

## Critères d'acceptation (AC)
- [ ] AC 1 : Un nouvel onglet **Aperçu** est le premier onglet affiché par défaut (avant Infos/Logs)
- [ ] AC 2 : Une card **Services** liste les containers de la même stack (même `com.docker.compose.project`) avec : nom, image, statut (badge coloré), port mapping. Si standalone, affiche uniquement le container courant.
- [ ] AC 3 : Une card **Ressources** affiche : barres de progression CPU % et RAM (utilisé/total), Network I/O (↑↓ KB/s), Disk I/O (↑↓ KB/s)
- [ ] AC 4 : Une card **Volumes** liste les volumes montés avec : nom du volume, chemin de montage, taille (si disponible), et bouton [📂] pour ouvrir le volume browser
- [ ] AC 5 : Une card **Réseau** résume les networks attachés avec : nom du réseau, IP, gateway, type de driver
- [ ] AC 6 : Si le container a un **health check**, une card **Santé** affiche le status (healthy/unhealthy/starting) et le failing streak
- [ ] AC 7 : Les cards utilisent le composant `el-card` avec des headers colorés et un layout responsive (2 colonnes sur desktop, 1 colonne sur mobile)
- [ ] AC 8 : Les données de ressources se rafraîchissent automatiquement toutes les 5 secondes si le container est running
- [ ] AC 9 : Si le container est arrêté, les cards Ressources et Santé affichent "Non disponible — container arrêté"

## Dépendances
- STORY-024 (schémas structurés) — pour les données de state, config structurées
- STORY-025 (header enrichi) — pour le résumé ressources dans le header (partage du composable de fetch stats)

## État d'avancement technique
- [ ] Créer l'onglet Aperçu comme premier onglet
- [ ] Implémenter la card Services (fetch des containers de la même stack)
- [ ] Implémenter la card Ressources (barres CPU/RAM + I/O)
- [ ] Implémenter la card Volumes (avec lien vers volume browser)
- [ ] Implémenter la card Réseau
- [ ] Implémenter la card Santé (health check)
- [ ] Ajouter le refresh automatique des métriques
- [ ] Layout responsive (2 colonnes desktop, 1 mobile)

## Tâches d'implémentation détaillées
<!-- Section remplie par la skill analyse-story -->

## Tests à écrire
<!-- Section remplie par la skill analyse-story -->
