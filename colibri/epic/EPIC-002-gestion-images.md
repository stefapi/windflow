# EPIC-002 : Gestion des Images Docker

**Statut :** TODO
**Priorité :** Haute

## Vision
Permettre la gestion complète des images Docker avec scan de vulnérabilités intégré. Les utilisateurs peuvent tirer, pousser, inspecter et scanner les images pour identifier les vulnérabilités de sécurité avant le déploiement.

## Liste des Stories liées
- [ ] STORY-001 : Afficher la liste des images avec tags, taille, date de création et nombre de conteneurs
- [ ] STORY-002 : Tirer (pull) une image depuis un registry avec affichage de la progression
- [ ] STORY-003 : Pousser (push) une image vers un registry
- [ ] STORY-004 : Supprimer une image avec option force
- [ ] STORY-005 : Tagger une image
- [ ] STORY-006 : Voir l'historique des couches d'une image
- [ ] STORY-007 : Inspecter une image (configuration complète)
- [ ] STORY-008 : Scanner une image pour les vulnérabilités (Grype et/ou Trivy)
- [ ] STORY-009 : Voir les résultats de scan avec détails par sévérité
- [ ] STORY-010 : Vérifier les mises à jour disponibles pour une image
- [ ] STORY-011 : Exporter (sauvegarder) une image en archive tar
- [ ] STORY-012 : Filtrer et trier les images par différents critères

## Notes de conception
- Support de l'authentification aux registries via X-Registry-Auth header
- Scan de vulnérabilités via conteneurs Grype et Trivy avec cache de base de données
- Vérification des mises à jour via comparaison de digests (HEAD request au registry)
- Support du flux OAuth2 Bearer token pour les registries privés
- Gestion des images digest-pinned (pas de vérification de mise à jour)
- Tags temporaires pour le pull sécurisé pendant les mises à jour automatiques
