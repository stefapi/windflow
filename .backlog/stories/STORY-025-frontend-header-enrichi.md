# STORY-025 : Frontend — Header enrichi du Container Detail

**Statut :** TODO
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
En tant qu'utilisateur, je veux voir un header enrichi sur la page Container Detail avec la machine cible, l'uptime, un résumé des ressources (CPU/RAM) et toutes les actions contextuelles (Start, Stop, Restart, Delete, Pause) afin d'avoir une vue synthétique immédiate de l'état du container.

## Contexte technique
Le header actuel dans `frontend/src/views/ContainerDetail.vue` affiche uniquement le nom du container et son statut textuel. La maquette UI (`doc/general_specs/11-UI-mockups.md` Écran 3) prévoit un header riche avec : nom + image + statut coloré (🟢/🔴), Target, Uptime, résumé CPU/RAM, et une barre d'actions complète.

Les données de ressources sont déjà disponibles via le endpoint stats existant. Les actions Stop/Restart existent déjà dans le service API.

## Critères d'acceptation (AC)
- [ ] AC 1 : Le header affiche le **nom du container**, **l'image**, et le **statut** avec un badge coloré (🟢 running, 🔴 exited, 🟡 paused, etc.)
- [ ] AC 2 : Le header affiche la **machine cible** (Target) sur laquelle tourne le container (ex: "local" ou le nom du target SSH)
- [ ] AC 3 : Le header affiche l'**uptime/durée** depuis le démarrage (ex: "Running (15 jours)" ou "Arrêté depuis 3 jours") calculé à partir de `started_at`/`finished_at`
- [ ] AC 4 : Le header affiche un **résumé des ressources** : CPU % et RAM utilisée (ex: "CPU: 5% │ RAM: 342 MB") sous forme de mini-barres ou chiffres
- [ ] AC 5 : Le bouton **Start** est visible et fonctionnel quand le container est arrêté (statut `exited`, `dead`)
- [ ] AC 6 : Le bouton **Delete** est visible et fonctionnel (avec confirmation via ElMessageBox)
- [ ] AC 7 : Le bouton **Pause** est visible quand le container est running ; **Unpause** quand il est paused
- [ ] AC 8 : Les boutons **Stop** et **Restart** sont visibles quand le container est running (déjà existants, à conserver)
- [ ] AC 9 : Les actions disabled affichent un tooltip expliquant pourquoi (ex: "Container déjà arrêté")
- [ ] AC 10 : Le design correspond au style de la maquette UI (aligné avec le design system Element Plus existant)

## Dépendances
- STORY-024 (schémas backend structurés) — pour bénéficier des champs `started_at`, `finished_at`, `oom_killed` structurés. Peut démarrer en parallèle avec le schéma actuel.

## État d'avancement technique
- [ ] Enrichir le header de ContainerDetail.vue avec Target, Uptime, Résumé ressources
- [ ] Ajouter les actions Start, Delete, Pause/Unpause
- [ ] Calculer l'uptime à partir des dates started_at/finished_at
- [ ] Afficher les mini-métriques CPU/RAM dans le header
- [ ] Ajouter les appels API manquants (start, delete, pause/unpause)
- [ ] Gérer les états disabled/tooltips des boutons

## Tâches d'implémentation détaillées
<!-- Section remplie par la skill analyse-story -->

## Tests à écrire
<!-- Section remplie par la skill analyse-story -->
