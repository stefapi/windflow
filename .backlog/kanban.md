# KANBAN BOARD

## 📋 BACKLOG

### EPIC-001 : Système de Plugins & Marketplace
- [ ] STORY-004 : Vérification compatibilité architecture (arm64/amd64) et ressources
- [ ] STORY-005 : Configuration plugin depuis l'UI (formulaires dynamiques générés depuis manifest)
- [~] STORY-006 : Hooks lifecycle plugins (on_install, on_configure, on_start, on_stop, on_uninstall)
  - [~] STORY-006.1 : Backend — Service d'exécution des hooks lifecycle
  - [ ] STORY-006.2 : Frontend — UI d'affichage des logs d'exécution des hooks
- [ ] STORY-007 : Support 3 types de plugins (service, extension, hybrid)
- [ ] STORY-008 : API Marketplace — catalogue, recherche, filtres par catégorie
- [ ] STORY-009 : UI Marketplace — catalogue browsable avec fiches plugin
- [ ] STORY-010 : Installation one-click depuis la Marketplace
- [ ] STORY-011 : Mise à jour plugins avec affichage changelog
- [ ] STORY-012 : Distinction plugins officiels vs communautaires (badges, tri)
- [ ] STORY-014 : Support registre custom (self-hosted)
- [ ] STORY-015 : Vérification d'intégrité (checksums SHA-256)
- [ ] STORY-016 : Plugin Traefik — reverse proxy + TLS automatique Let's Encrypt
- [ ] STORY-017 : Plugin PostgreSQL — détection containers, create DB/users/grants, backup
- [ ] STORY-018 : Plugin Redis — détection containers, monitoring clés/stats
- [ ] STORY-019 : Plugin Uptime Kuma — déploiement + widget status dashboard

## 🏗️ IN PROGRESS

_(vide)_

## 🚫 BLOCKED

_(vide)_

## 🚧 REVIEW

_(vide)_

## ✅ DONE

- [x] STORY-001 : Format manifest YAML (spécification + validation Pydantic)
- [x] STORY-002 : API REST Plugin Manager — CRUD plugins (install/update/uninstall)
- [x] STORY-003 : Gestion des dépendances entre plugins
- [x] STORY-013 : Registre officiel (index JSON ou API simple)
- [x] STORY-006.1 : Backend — Service d'exécution des hooks lifecycle
