# EPIC-024 : Mise à Jour Automatique de l'Application

**Statut :** TODO
**Priorité :** Basse

## Vision
Système de mise à jour automatique de Dockhand. Les utilisateurs peuvent vérifier les mises à jour disponibles et déclencher des mises à jour manuelles ou automatiques.

## Liste des Stories liées
- [ ] STORY-001 : Vérifier les mises à jour disponibles
- [ ] STORY-002 : Déclencher une mise à jour manuellement
- [ ] STORY-003 : Le système peut être configuré pour les mises à jour automatiques

## Notes de conception
- Script de mise à jour dans updater/update.sh
- Dockerfile pour le conteneur de mise à jour
- Vérification des versions via l'API GitHub
- Téléchargement et remplacement du conteneur
- Sauvegarde avant mise à jour
- Rollback en cas d'échec
- Notification de mise à jour disponible
- Support des mises à jour mineures et majeures
