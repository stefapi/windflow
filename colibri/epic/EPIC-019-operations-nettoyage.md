# EPIC-019 : Opérations de Nettoyage (Prune)

**Statut :** TODO
**Priorité :** Basse

## Vision
Nettoyage des ressources Docker inutilisées. Les utilisateurs peuvent nettoyer les conteneurs arrêtés, les images inutilisées, les volumes non utilisés et les réseaux orphelins pour libérer de l'espace disque.

## Liste des Stories liées
- [ ] STORY-001 : Nettoyer les conteneurs arrêtés
- [ ] STORY-002 : Nettoyer les images inutilisées (dangling ou toutes)
- [ ] STORY-003 : Nettoyer les volumes inutilisés
- [ ] STORY-004 : Nettoyer les réseaux inutilisés
- [ ] STORY-005 : Effectuer un nettoyage complet (toutes les ressources)
- [ ] STORY-006 : Voir l'espace disque récupéré
- [ ] STORY-007 : Planifier le nettoyage automatique des images

## Notes de conception
- Utilisation de l'API Docker prune (/containers/prune, /images/prune, /volumes/prune, /networks/prune)
- Option dangling pour les images (true = seulement les non-taguées, false = toutes les inutilisées)
- Rapport d'espace récupéré par type de ressource
- Nettoyage complet en séquence (conteneurs, images, volumes, réseaux)
- Planification automatique via le scheduler (image_prune)
- Confirmation avant nettoyage (destructif)
- Support multi-environnement
