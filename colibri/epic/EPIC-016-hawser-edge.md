# EPIC-016 : Hawser Edge (Connexions Distantes)

**Statut :** TODO
**Priorité :** Haute

## Vision
Système de connexions WebSocket pour gérer des environnements Docker distants via des agents Hawser. Les agents se connectent au serveur Dockhand via WebSocket et permettent le routage des requêtes Docker, la collecte de métriques et la réception d'événements en temps réel.

## Liste des Stories liées
- [ ] STORY-001 : Générer un token d'agent Hawser pour un environnement
- [ ] STORY-002 : Révoquer un token existant
- [ ] STORY-003 : Les agents se connectent via WebSocket avec authentification par token
- [ ] STORY-004 : Le système route les requêtes Docker via la connexion WebSocket
- [ ] STORY-005 : Le système collecte les métriques depuis les agents (CPU, mémoire, disque, réseau)
- [ ] STORY-006 : Le système reçoit les événements conteneurs depuis les agents
- [ ] STORY-007 : Le système supporte le streaming de logs et de terminal via WebSocket
- [ ] STORY-008 : Le système gère les reconnexions et les timeouts
- [ ] STORY-009 : Le système protège contre les tempêtes de reconnexion (throttling)

## Notes de conception
- Protocole WebSocket avec messages JSON
- Types de messages : hello, welcome, request, response, stream, stream_end, metrics, ping, pong, error
- Support des exec bidirectionnels pour le terminal
- Heartbeat toutes les 5 secondes
- Timeout de 90 secondes (3 heartbeats manqués)
- Tokens hashés avec Argon2id et préfixe pour identification rapide
- Throttling des reconnexions avec cooldown progressif (30s, 60s, 120s, 300s)
- Cache des échecs d'authentification (5 min cooldown)
- Support des données binaires (base64) pour les uploads de fichiers
- Nettoyage automatique des connexions expirées
- Remplacement gracieux des connexions existantes
