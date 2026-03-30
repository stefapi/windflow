# EPIC-010 : Planification des Tâches

**Statut :** TODO
**Priorité :** Haute

## Vision
Système de planification unifié permettant d'automatiser les mises à jour de conteneurs, les synchronisations Git, les vérifications de mises à jour et le nettoyage des ressources. Les tâches s'exécutent selon des expressions cron avec support des fuseaux horaires par environnement.

## Liste des Stories liées
- [ ] STORY-001 : Configurer des mises à jour automatiques pour les conteneurs (critères de vulnérabilité, fréquence)
- [ ] STORY-002 : Configurer des synchronisations automatiques pour les stacks Git
- [ ] STORY-003 : Configurer des vérifications de mises à jour par environnement
- [ ] STORY-004 : Configurer le nettoyage automatique des images inutilisées
- [ ] STORY-005 : Voir l'historique d'exécution des tâches planifiées
- [ ] STORY-006 : Déclencher manuellement une tâche planifiée
- [ ] STORY-007 : Les tâches utilisent le fuseau horaire de l'environnement
- [ ] STORY-008 : Le système nettoie automatiquement les anciens logs d'exécution
- [ ] STORY-009 : Le système nettoie automatiquement les anciens événements conteneurs
- [ ] STORY-010 : Le système nettoie automatiquement les conteneurs helper de volumes

## Notes de conception
- Utilisation de croner pour l'exécution des tâches cron
- Support des fuseaux horaires par environnement
- Types de tâches : container_update, git_stack_sync, env_update_check, image_prune, system_cleanup
- Vérification défensive avant exécution (tâche toujours activée)
- Lock par type de scanner pour éviter les conflits
- Historique d'exécution dans la table schedule_executions
- Nettoyage automatique des logs anciens (configurable)
- Nettoyage automatique des événements anciens (configurable)
- Nettoyage des conteneurs helper de volumes toutes les 30 minutes
- Récupération des états de synchronisation Git bloqués au démarrage
