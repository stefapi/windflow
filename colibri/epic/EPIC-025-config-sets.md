# EPIC-025 : Config Sets

**Statut :** TODO
**Priorité :** Moyenne

## Vision
Ensembles de configuration réutilisables permettant de définir des configurations complètes (variables d'environnement, labels, ports, volumes, mode réseau, politique de redémarrage) et de les appliquer rapidement lors de la création de conteneurs.

## Liste des Stories liées
- [ ] STORY-001 : Créer un Config Set avec nom, description et configuration complète
- [ ] STORY-002 : Modifier un Config Set existant
- [ ] STORY-003 : Supprimer un Config Set
- [ ] STORY-004 : Appliquer un Config Set lors de la création d'un conteneur
- [ ] STORY-005 : Voir la liste des Config Sets disponibles
- [ ] STORY-006 : Dupliquer un Config Set

## Notes de conception
- Table config_sets avec champs : name, description, env_vars, labels, ports, volumes, network_mode, restart_policy
- Stockage JSON pour les champs complexes (env_vars, labels, ports, volumes)
- Application lors de la création de conteneurs via le modal de création
- Support de l'import/export de Config Sets
- Validation des configurations avant sauvegarde
