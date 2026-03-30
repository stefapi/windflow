# EPIC-022 : Scripts d'Urgence

**Statut :** TODO
**Priorité :** Moyenne

## Vision
Scripts de maintenance et de récupération pour les situations d'urgence. Les administrateurs peuvent sauvegarder, restaurer, réinitialiser la base de données, gérer les utilisateurs et exporter les stacks depuis la ligne de commande.

## Liste des Stories liées
- [ ] STORY-001 : Sauvegarder la base de données (backup-db.sh)
- [ ] STORY-002 : Restaurer la base de données (restore-db.sh)
- [ ] STORY-003 : Réinitialiser la base de données (reset-db.sh)
- [ ] STORY-004 : Créer un compte administrateur (create-admin.sh)
- [ ] STORY-005 : Réinitialiser un mot de passe (reset-password.sh)
- [ ] STORY-006 : Supprimer les sessions (clear-sessions.sh)
- [ ] STORY-007 : Désactiver l'authentification (disable-auth.sh)
- [ ] STORY-008 : Lister les utilisateurs (list-users.sh)
- [ ] STORY-009 : Exporter les stacks (export-stacks.sh)

## Notes de conception
- Scripts dans scripts/emergency/sqlite/ et scripts/emergency/postgres/
- Support de SQLite et PostgreSQL
- Scripts exécutables depuis le conteneur Docker
- Backup avec horodatage
- Restauration avec confirmation
- Export des stacks en JSON
- Scripts de récupération d'urgence pour les cas de lock-out
- Documentation dans les scripts (commentaires)
