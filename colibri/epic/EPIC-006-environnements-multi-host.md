# EPIC-006 : Gestion des Environnements Multi-Host

**Statut :** TODO
**Priorité :** Haute

## Vision
Permettre la gestion de plusieurs environnements Docker depuis une seule interface. Les utilisateurs peuvent ajouter des environnements locaux (socket Unix) et distants (HTTP/HTTPS, Hawser Standard, Hawser Edge) pour gérer plusieurs hôtes Docker depuis un seul tableau de bord.

## Liste des Stories liées
- [ ] STORY-001 : Afficher la liste des environnements avec statut de connexion
- [ ] STORY-002 : Ajouter un environnement local (socket Unix)
- [ ] STORY-003 : Ajouter un environnement distant direct (HTTP/HTTPS avec TLS)
- [ ] STORY-004 : Ajouter un environnement via Hawser Standard (HTTP avec token)
- [ ] STORY-005 : Ajouter un environnement via Hawser Edge (WebSocket)
- [ ] STORY-006 : Tester la connexion à un environnement
- [ ] STORY-007 : Configurer un icône et des labels pour un environnement
- [ ] STORY-008 : Activer/désactiver la collecte d'activité et de métriques
- [ ] STORY-009 : Configurer le fuseau horaire d'un environnement
- [ ] STORY-010 : Voir les informations de l'hôte Docker (version, OS, ressources)

## Notes de conception
- Support de 4 types de connexion : socket, direct, hawser-standard, hawser-edge
- Détection automatique du socket Docker (Linux, macOS, OrbStack)
- Support TLS avec certificats CA, client et skip verify
- Cache des configurations d'environnement avec TTL de 30 minutes
- Pool d'agents HTTPS avec keepAlive pour les connexions distantes
- Circuit breaker pour les environnements hors ligne
- Ping régulier pour vérifier la disponibilité
- Support de la traduction des chemins pour Dockhand dans Docker
