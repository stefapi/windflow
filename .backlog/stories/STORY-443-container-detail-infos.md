# STORY-443 : ContainerDetail — onglet Infos

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir les informations détaillées d'un container (ID, image, ports, volumes, réseau, variables d'environnement) dans un onglet Infos afin de comprendre sa configuration sans passer par la CLI.

## Critères d'acceptation (AC)
- [ ] AC 1 : Vue `ContainerDetail.vue` accessible via `/containers/:id` avec navigation par onglets (el-tabs)
- [ ] AC 2 : Onglet Infos actif par défaut — affiche : ID (tronqué + copie), image, date de création, stack parente (si applicable)
- [ ] AC 3 : Section Ports : liste des mappings (host → container)
- [ ] AC 4 : Section Volumes : liste des montages avec bouton « Parcourir » (lien vers futur Volume Browser — EPIC-002)
- [ ] AC 5 : Section Réseau : nom du réseau Docker, IP interne
- [ ] AC 6 : Section Variables d'environnement : tableau key/value, mots de passe masqués avec bouton révéler (👁)
- [ ] AC 7 : Boutons d'actions en haut : Stop, Restart, Logs, Terminal, Inspect
- [ ] AC 8 : Les données proviennent de l'API Docker existante (`/api/v1/docker/containers/{id}`)

## État d'avancement technique
- [ ] Création `frontend/src/views/ContainerDetail.vue` avec el-tabs
- [ ] Onglet Infos : sections Ports, Volumes, Réseau, Env
- [ ] Masquage mots de passe (regex sur clés *PASSWORD*, *SECRET*, *KEY*, *TOKEN*)
- [ ] Bouton copier ID dans le presse-papier
- [ ] Mise à jour du router (`/containers/:id`)
- [ ] Service frontend Docker inspect
- [ ] Tests Vitest
