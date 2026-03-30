# EPIC-009 : Scan de Vulnérabilités

**Statut :** TODO
**Priorité :** Moyenne

## Vision
Scanner les images Docker pour les vulnérabilités de sécurité avec Grype et Trivy. Les utilisateurs peuvent identifier les failles de sécurité avant le déploiement et recevoir des notifications pour les vulnérabilités critiques.

## Liste des Stories liées
- [ ] STORY-001 : Scanner une image avec Grype
- [ ] STORY-002 : Scanner une image avec Trivy
- [ ] STORY-003 : Scanner avec les deux scanners simultanément
- [ ] STORY-004 : Voir les résultats détaillés des vulnérabilités (ID, sévérité, package, version, fix)
- [ ] STORY-005 : Configurer les arguments CLI des scanners
- [ ] STORY-006 : Mettre en cache les bases de données de vulnérabilités (volumes Docker)
- [ ] STORY-007 : Recevoir des notifications pour les vulnérabilités critiques
- [ ] STORY-008 : Voir les versions des scanners installés
- [ ] STORY-009 : Vérifier les mises à jour des scanners

## Notes de conception
- Exécution des scanners via conteneurs Docker (anchore/grype, aquasec/trivy)
- Cache des bases de données dans des volumes Docker (dockhand-grype-db, dockhand-trivy-db)
- Support rootless Docker avec bind mounts et ownership correct
- Lock par type de scanner pour éviter les conflits de base de données
- Détection des conteneurs en cours d'exécution pour éviter les scans dupliqués
- Parsing JSON avec sanitisation des caractères de contrôle
- Notifications basées sur la sévérité maximale trouvée
- Arguments CLI personnalisables globalement (défaut: -o json -v {image} pour Grype, image --format json {image} pour Trivy)
