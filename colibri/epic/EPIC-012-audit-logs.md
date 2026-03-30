# EPIC-012 : Audit Logs

**Statut :** TODO
**Priorité :** Moyenne

## Vision
Système de traçabilité complète des actions utilisateur. Les administrateurs peuvent voir l'historique de toutes les actions effectuées, filtrer par utilisateur, action, type d'entité, environnement et date, et exporter les logs pour conformité.

## Liste des Stories liées
- [ ] STORY-001 : Voir l'historique de toutes les actions effectuées
- [ ] STORY-002 : Filtrer les logs par utilisateur, action, type d'entité, environnement, date
- [ ] STORY-003 : Exporter les logs d'audit
- [ ] STORY-004 : Voir les détails d'un log d'audit (IP, user agent, détails JSON)
- [ ] STORY-005 : Les logs incluent les actions sur les conteneurs, images, volumes, réseaux, stacks, utilisateurs, etc.

## Notes de conception
- Table audit_logs avec index sur user_id et created_at
- Actions trackées : CRUD sur toutes les entités, opérations de cycle de vie, authentification, configuration
- Enregistrement automatique via middleware/hooks
- Détails JSON pour les changements de configuration
- Export en JSON ou CSV
- Nettoyage automatique des anciens logs (configurable)
- Support multi-environnement avec filtrage
- Adresse IP et user agent enregistrés pour chaque action
