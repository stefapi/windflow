# STORY-006 : Hooks lifecycle plugins (on_install, on_configure, on_start, on_stop, on_uninstall)

**Statut :** IN_PROGRESS
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux que chaque plugin expose des hooks de cycle de vie (on_install, on_configure, on_start, on_stop, on_uninstall) afin de permettre l'exécution de logique personnalisée à chaque étape de la vie du plugin.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
Les hooks lifecycle permettent aux plugins d'exécuter des actions spécifiques à chaque transition d'état. Ces hooks sont déclarés dans le manifest et implémentés comme scripts ou entrypoints dans le package du plugin. Le système doit les invoquer dans l'ordre correct et gérer les erreurs.

## Critères d'acceptation (AC)
- [ ] AC 1 : Les 5 hooks (on_install, on_configure, on_start, on_stop, on_uninstall) sont correctement invoqués lors des transitions d'état du plugin
- [ ] AC 2 : Un hook en échec ne laisse pas le plugin dans un état incohérent (rollback ou état d'erreur géré)
- [ ] AC 3 : Les logs d'exécution des hooks sont capturés et accessibles via l'API et l'UI
- [ ] AC 4 : Build/lint/tests passent avec couverture ≥ 80%

## Sous-stories
- [ ] STORY-006.1 : Backend — Service d'exécution des hooks lifecycle — Couvre AC 1, AC 2, AC 4
- [ ] STORY-006.2 : Frontend — UI d'affichage des logs d'exécution des hooks — Couvre AC 3

## Dépendances
- STORY-001 : Format manifest YAML (spécification + validation Pydantic)
- STORY-002 : API REST Plugin Manager — CRUD plugins

## Tâches d'implémentation détaillées

> ⚠️ Cette story a été découpée en sous-stories avant implémentation (complexité détectée par analyse-story).
> Toutes les tâches ont été redistribuées dans les sous-stories listées ci-dessus.
> Consulter chaque sous-story pour les tâches détaillées.

## Tests à écrire

> ⚠️ Les tests sont désormais définis dans les sous-stories individuelles.

## État d'avancement technique

> ⚠️ L'avancement technique est désormais suivi dans les sous-stories individuelles.

**Progression :** 0/2 sous-stories terminées
- [ ] STORY-006.1 : Backend — Service d'exécution des hooks lifecycle
- [ ] STORY-006.2 : Frontend — UI d'affichage des logs d'exécution des hooks
