# EPIC-017 : Paramètres et Configuration

**Statut :** TODO
**Priorité :** Haute

## Vision
Interface de configuration complète de l'application. Les administrateurs peuvent configurer tous les aspects de Dockhand : authentification, environnements, registries, notifications, Git, thèmes, fuseaux horaires et plus encore.

## Liste des Stories liées
- [ ] STORY-001 : Configurer les paramètres généraux (nom de l'application, thème, fuseau horaire par défaut)
- [ ] STORY-002 : Configurer les paramètres d'authentification
- [ ] STORY-003 : Configurer les environnements Docker
- [ ] STORY-004 : Configurer les registries Docker
- [ ] STORY-005 : Configurer les notifications
- [ ] STORY-006 : Configurer les credentials Git
- [ ] STORY-007 : Configurer les Config Sets (ensembles de configuration réutilisables)
- [ ] STORY-008 : Voir les informations de licence
- [ ] STORY-009 : Voir les dépendances du projet
- [ ] STORY-010 : Voir les informations de version et le changelog

## Notes de conception
- Pages de paramètres organisées par section (general, auth, environments, registries, notifications, git, config-sets, license, about)
- Paramètres stockés dans la table settings (key-value)
- Paramètres par environnement dans la table environment_notifications
- Config Sets pour les ensembles de configuration réutilisables (env vars, labels, ports, volumes, network mode, restart policy)
- Thèmes clair/sombre avec persistance des préférences
- Sélecteur de fuseau horaire avec support IANA
- Page À propos avec version, dépendances et changelog
- Génération automatique des pages légales (privacy, terms)
