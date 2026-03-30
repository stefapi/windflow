# EPIC-001 : Gestion des Conteneurs Docker

**Statut :** TODO
**Priorité :** Haute

## Vision
Permettre la gestion complète des conteneurs Docker avec opérations en temps réel, terminal interactif et navigation dans le système de fichiers. Cette fonctionnalité est le cœur de l'application et permet aux utilisateurs de gérer leurs conteneurs depuis une interface web moderne.

## Liste des Stories liées
- [ ] STORY-001 : Afficher la liste des conteneurs avec informations détaillées
- [ ] STORY-002 : Démarrer, arrêter, redémarrer, mettre en pause et reprendre un conteneur
- [ ] STORY-003 : Créer un nouveau conteneur avec configuration complète
- [ ] STORY-004 : Modifier un conteneur existant (recréation avec préservation des paramètres)
- [ ] STORY-005 : Supprimer un conteneur avec option force
- [ ] STORY-006 : Renommer un conteneur
- [ ] STORY-007 : Inspecter un conteneur (configuration JSON complète)
- [ ] STORY-008 : Voir les logs d'un conteneur en temps réel (streaming)
- [ ] STORY-009 : Accéder au terminal interactif d'un conteneur via WebSocket
- [ ] STORY-010 : Naviguer dans le système de fichiers d'un conteneur (list, upload, download, create, delete, rename, chmod)
- [ ] STORY-011 : Voir les statistiques en temps réel (CPU, mémoire, réseau, disque)
- [ ] STORY-012 : Voir la liste des processus en cours d'exécution (top)
- [ ] STORY-013 : Effectuer des opérations par lot sur plusieurs conteneurs
- [ ] STORY-014 : Filtrer et trier les conteneurs par différents critères
- [ ] STORY-015 : Configurer des mises à jour automatiques pour un conteneur

## Notes de conception
- Utiliser l'API Docker directe via fetch (pas de dockerode)
- Support des connexions socket Unix, HTTP/HTTPS et Hawser Edge
- Terminal via WebSocket avec xterm.js
- Streaming des logs via Server-Sent Events (SSE)
- Statistiques en temps réel via polling Docker API
- Système de fichiers via exec dans le conteneur (ls, cat, tar)
- Opérations par lot avec exécution parallèle via Promise.allSettled
