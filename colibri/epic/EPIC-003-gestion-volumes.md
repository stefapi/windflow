# EPIC-003 : Gestion des Volumes Docker

**Statut :** TODO
**Priorité :** Haute

## Vision
Permettre la gestion complète des volumes Docker avec navigation dans leur contenu. Les utilisateurs peuvent créer, supprimer, inspecter et naviguer dans les volumes pour gérer les données persistantes de leurs conteneurs.

## Liste des Stories liées
- [ ] STORY-001 : Afficher la liste des volumes avec informations (nom, driver, point de montage, labels, date de création, conteneurs utilisant le volume)
- [ ] STORY-002 : Créer un nouveau volume avec configuration (nom, driver, options driver, labels)
- [ ] STORY-003 : Supprimer un volume avec option force
- [ ] STORY-004 : Inspecter un volume
- [ ] STORY-005 : Naviguer dans le contenu d'un volume (list, download, upload, create, delete, rename)
- [ ] STORY-006 : Cloner un volume (copier le contenu vers un nouveau volume)
- [ ] STORY-007 : Voir quels conteneurs utilisent un volume

## Notes de conception
- Navigation dans les volumes via conteneurs helper temporaires (busybox)
- Cache des conteneurs helper avec TTL de 5 minutes pour les performances
- Support du mode lecture seule et lecture-écriture pour la navigation
- Clonage via conteneur temporaire avec montage des deux volumes
- Nettoyage automatique des conteneurs helper expirés
- Support rootless Docker avec bind mounts et ownership correct
