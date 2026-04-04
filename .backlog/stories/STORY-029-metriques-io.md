# STORY-029 : Backend + Frontend — Métriques Network I/O et Disk I/O dans Stats

**Statut :** TODO
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
En tant qu'utilisateur, je veux voir les métriques Network I/O (↑↓ débit réseau) et Disk I/O (↑↓ débit disque) dans l'onglet Stats du Container Detail afin de pouvoir surveiller l'activité réseau et disque du container en temps réel.

## Contexte technique
L'onglet Stats actuel dans `ContainerDetail.vue` affiche uniquement CPU et Memory via le endpoint `GET /api/v1/docker/containers/{id}/stats`. L'API Docker stats retourne aussi les blocs `networks` (rx_bytes, tx_bytes, rx_packets, tx_packets, rx_errors, tx_errors, rx_dropped, tx_dropped) et `blkio_stats` (io_service_bytes_recursive avec majors/minors et opérations read/write).

Le backend retourne déjà les stats bruts du Docker daemon. Il faut extraire et structurer les données Network I/O et Block I/O dans le schéma de réponse et les afficher dans le frontend.

## Critères d'acceptation (AC)
- [ ] AC 1 : Le schéma de réponse des stats inclut un objet `network` avec les métriques par interface réseau : rx_bytes, tx_bytes, rx_packets, tx_packets, rx_errors, tx_errors, rx_dropped, tx_dropped
- [ ] AC 2 : Le schéma de réponse des stats inclut un objet `blkio` avec les métriques par device : io_service_bytes_recursive (read/write bytes), io_serviced_recursive (read/write ops)
- [ ] AC 3 : L'onglet Stats affiche une section **Network I/O** avec : débit montant (↑ tx) et débit descendant (↓ rx) en KB/s ou MB/s, calculés par delta entre deux échantillons
- [ ] AC 4 : L'onglet Stats affiche une section **Disk I/O** avec : lecture (↓ read MB/s) et écriture (↑ write MB/s), calculées par delta entre deux échantillons
- [ ] AC 5 : Les métriques I/O sont affichées sous forme de mini-graphiques temporels (au moins les 60 dernières secondes) en plus des valeurs instantanées
- [ ] AC 6 : Les compteurs cumulatifs (total bytes depuis le démarrage) sont aussi affichés (ex: "Total: ↑ 2.4 GB ↓ 890 MB")
- [ ] AC 7 : Si le container est arrêté, les sections I/O affichent "Non disponible"
- [ ] AC 8 : Les erreurs et drops réseau sont affichés en surbrillance si > 0 (badge warning)

## Dépendances
- STORY-024 (schémas structurés) — pour structurer les stats dans des sous-modèles

## État d'avancement technique
- [ ] Backend : Structurer les métriques network et blkio dans le schéma de stats
- [ ] Frontend : Ajouter les sections Network I/O et Disk I/O dans l'onglet Stats
- [ ] Frontend : Calculer les débits par delta entre échantillons
- [ ] Frontend : Afficher les mini-graphiques temporels
- [ ] Frontend : Afficher les compteurs cumulatifs et erreurs

## Tâches d'implémentation détaillées
<!-- Section remplie par la skill analyse-story -->

## Tests à écrire
<!-- Section remplie par la skill analyse-story -->
