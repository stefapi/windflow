# EPIC-005 : Gestion des Stacks Docker Compose

**Statut :** TODO
**Priorité :** Haute

## Vision
Permettre la gestion complète des stacks Docker Compose avec support Git intégré. Les utilisateurs peuvent créer, déployer, synchroniser et gérer des stacks Compose depuis l'interface web, avec support du déploiement depuis des dépôts Git et des webhooks pour le déploiement automatique.

## Liste des Stories liées
- [ ] STORY-001 : Afficher la liste des stacks avec statut et conteneurs
- [ ] STORY-002 : Créer une nouvelle stack avec fichier compose YAML
- [ ] STORY-003 : Modifier le fichier compose d'une stack existante
- [ ] STORY-004 : Déployer une stack (docker compose up)
- [ ] STORY-005 : Arrêter une stack (docker compose stop)
- [ ] STORY-006 : Redémarrer une stack (docker compose restart)
- [ ] STORY-007 : Supprimer une stack (docker compose down + nettoyage fichiers)
- [ ] STORY-008 : Tirer les images d'une stack (docker compose pull)
- [ ] STORY-009 : Gérer les variables d'environnement (secrets et non-secrets)
- [ ] STORY-010 : Visualiser le graphe de dépendances des services
- [ ] STORY-011 : Importer une stack existante depuis Docker (adoption)
- [ ] STORY-012 : Déployer une stack depuis un dépôt Git
- [ ] STORY-013 : Synchroniser manuellement une stack Git
- [ ] STORY-014 : Configurer des webhooks pour déploiement automatique
- [ ] STORY-015 : Voir les logs d'exécution des opérations
- [ ] STORY-016 : Mettre à jour un service spécifique d'une stack
- [ ] STORY-017 : Naviguer dans les fichiers d'une stack

## Notes de conception
- Exécution des commandes compose via child_process.spawn
- Support des connexions locales (socket) et distantes (Hawser)
- Variables d'environnement : secrets injectés via shell env, non-secrets via .env
- Fichier .env.dockhand pour les overrides DB sur les stacks Git
- Traduction des chemins relatifs pour Dockhand dans Docker (host path rewriting)
- Lock par stack pour éviter les conditions de course
- Timeout configurable pour les opérations compose (défaut 15 min)
- Support des fichiers compose override (compose.override.yaml)
- Nettoyage des conteneurs orphelins après les opérations
