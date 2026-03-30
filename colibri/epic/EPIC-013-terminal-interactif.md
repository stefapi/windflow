# EPIC-013 : Terminal Interactif

**Statut :** TODO
**Priorité :** Haute

## Vision
Accès terminal interactif aux conteneurs via WebSocket. Les utilisateurs peuvent ouvrir un shell dans un conteneur, exécuter des commandes et voir la sortie en temps réel avec support du redimensionnement TTY.

## Liste des Stories liées
- [ ] STORY-001 : Ouvrir un terminal interactif dans un conteneur
- [ ] STORY-002 : Le terminal supporte le redimensionnement (TTY)
- [ ] STORY-003 : Choisir le shell à utiliser (bash, sh, etc.)
- [ ] STORY-004 : Choisir l'utilisateur pour l'exécution
- [ ] STORY-005 : Le terminal fonctionne avec les environnements locaux et distants (via Hawser)

## Notes de conception
- WebSocket pour la communication bidirectionnelle
- xterm.js pour l'émulation terminal côté client
- Docker exec API pour l'exécution côté serveur
- Support du protocole Hawser Edge pour les environnements distants
- Redimensionnement via messages WebSocket (exec_resize)
- Support des addons xterm (fit, web-links)
- Gestion des sessions multiples (onglets)
- Nettoyage automatique des sessions inactives
- Support des environnements avec TLS
