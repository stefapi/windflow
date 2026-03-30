# EPIC-008 : Notifications Multi-Canal

**Statut :** TODO
**Priorité :** Moyenne

## Vision
Système de notifications multi-canal permettant aux utilisateurs de recevoir des alertes sur différents événements (démarrage/arrêt de conteneurs, mises à jour, vulnérabilités, etc.) via email (SMTP) ou des services tiers (Discord, Slack, Telegram, etc.) via Apprise.

## Liste des Stories liées
- [ ] STORY-001 : Configurer des notifications par email (SMTP)
- [ ] STORY-002 : Configurer des notifications via Apprise (Discord, Slack, Telegram, Mattermost, Gotify, ntfy, Pushover, webhook JSON)
- [ ] STORY-003 : Tester une configuration de notification
- [ ] STORY-004 : Souscrire à des événements spécifiques par environnement
- [ ] STORY-005 : Recevoir des notifications pour les événements conteneurs (start, stop, restart, die, oom, unhealthy)
- [ ] STORY-006 : Recevoir des notifications pour les mises à jour automatiques
- [ ] STORY-007 : Recevoir des notifications pour les synchronisations Git
- [ ] STORY-008 : Recevoir des notifications pour les vulnérabilités critiques
- [ ] STORY-009 : Activer/désactiver des canaux de notification

## Notes de conception
- Support SMTP avec cache de transporteur (réutilisation des connexions TLS)
- Support Apprise avec protocoles : discord, slack, mmost, tgram, gotify, ntfy, pushover, json
- Notifications par environnement avec filtrage par type d'événement
- Notifications globales pour les événements système
- Exclusion des conteneurs scanner (Trivy, Grype) des notifications
- Types d'événements : container_*, auto_update_*, git_sync_*, vulnerability_*
- Priorités adaptées au canal (ex: priorité 8 pour les erreurs Gotify)
- Échappement Markdown pour Telegram
