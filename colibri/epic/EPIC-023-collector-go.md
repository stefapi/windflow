# EPIC-023 : Collector (Agent Go)

**Statut :** TODO
**Priorité :** Basse

## Vision
Agent léger écrit en Go pour la collecte de métriques système. Le collector s'exécute sur l'hôte Docker et envoie les métriques (CPU, mémoire, disque, réseau) au serveur Dockhand via l'API.

## Liste des Stories liées
- [ ] STORY-001 : Collecter les métriques système (CPU, mémoire, disque, réseau)
- [ ] STORY-002 : Envoyer les métriques au serveur Dockhand
- [ ] STORY-003 : L'agent est léger et performant

## Notes de conception
- Écrit en Go pour la performance et la faible empreinte
- Collecte via /proc filesystem (Linux)
- Envoi des métriques via HTTP POST
- Configuration via variables d'environnement
- Support du mode daemon
- Logging structuré
- Gestion gracieuse des signaux (SIGTERM, SIGINT)
- Retry avec backoff exponentiel
