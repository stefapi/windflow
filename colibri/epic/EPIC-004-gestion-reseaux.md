# EPIC-004 : Gestion des Réseaux Docker

**Statut :** TODO
**Priorité :** Moyenne

## Vision
Permettre la gestion complète des réseaux Docker. Les utilisateurs peuvent créer, supprimer, inspecter les réseaux et gérer les connexions des conteneurs aux réseaux avec support des adresses IP statiques et des alias.

## Liste des Stories liées
- [ ] STORY-001 : Afficher la liste des réseaux avec informations (nom, driver, scope, IPAM, conteneurs connectés)
- [ ] STORY-002 : Créer un nouveau réseau avec configuration (nom, driver, interne, attachable, IPv6, IPAM, options, labels)
- [ ] STORY-003 : Supprimer un réseau
- [ ] STORY-004 : Inspecter un réseau
- [ ] STORY-005 : Connecter un conteneur à un réseau (avec alias, IP statique, gateway priority)
- [ ] STORY-006 : Déconnecter un conteneur d'un réseau

## Notes de conception
- Support des drivers bridge, overlay, macvlan, etc.
- Configuration IPAM avec sous-réseaux, passerelles et plages d'adresses
- Support de l'IPv6 avec EnableIPv6
- Gateway priority pour Docker Engine 28+
- Réseaux internes (pas d'accès externe) et attachables
- Labels pour la métadonnée personnalisée
