# EPIC-011 : Dashboard et Métriques

**Statut :** TODO
**Priorité :** Moyenne

## Vision
Tableau de bord personnalisable avec métriques en temps réel et historique. Les utilisateurs peuvent voir l'état de tous leurs environnements, les métriques CPU/mémoire, l'utilisation disque, les conteneurs les plus consommateurs et les événements récents.

## Liste des Stories liées
- [ ] STORY-001 : Voir un aperçu de tous les environnements avec leur statut
- [ ] STORY-002 : Voir les métriques CPU et mémoire en temps réel (graphiques)
- [ ] STORY-003 : Voir l'utilisation disque de chaque environnement
- [ ] STORY-004 : Voir les conteneurs les plus consommateurs de ressources
- [ ] STORY-005 : Voir les événements récents
- [ ] STORY-006 : Voir un résumé de l'état de santé
- [ ] STORY-007 : Personnaliser la disposition du dashboard (grille draggable)
- [ ] STORY-008 : Voir les statistiques par conteneur (CPU, mémoire, réseau, disque)
- [ ] STORY-009 : Les métriques sont collectées depuis les agents Hawser Edge

## Notes de conception
- Métriques stockées dans un ring buffer en mémoire (dernières 60 données)
- Collecte depuis les agents Hawser Edge via messages WebSocket
- Normalisation du CPU par nombre de cœurs
- Graphiques avec layerchart (D3-based)
- Grille draggable avec svelte-dnd-action
- Préférences de dashboard par utilisateur
- Événements en temps réel via Server-Sent Events (SSE)
- Tuiles d'environnement avec statut de connexion
- Bannière de santé avec alertes visuelles
