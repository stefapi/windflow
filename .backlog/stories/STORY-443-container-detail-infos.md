# STORY-443 : ContainerDetail — onglet Infos

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir les informations détaillées d'un container (ID, image, ports, volumes, réseau, variables d'environnement) dans un onglet Infos afin de comprendre sa configuration sans passer par la CLI.

## Critères d'acceptation (AC)
- [x] AC 1 : Vue `ContainerDetail.vue` accessible via `/containers/:id` avec navigation par onglets (el-tabs)
- [x] AC 2 : Onglet Infos actif par défaut — affiche : ID (tronqué + copie), image, date de création, stack parente (si applicable)
- [x] AC 3 : Section Ports : liste des mappings (host → container)
- [x] AC 4 : Section Volumes : liste des montages avec bouton « Parcourir » (lien vers futur Volume Browser — EPIC-002)
- [x] AC 5 : Section Réseau : nom du réseau Docker, IP interne
- [x] AC 6 : Section Variables d'environnement : tableau key/value, mots de passe masqués avec bouton révéler (👁)
- [x] AC 7 : Boutons d'actions en haut : Stop, Restart, Logs, Terminal, Inspect
- [x] AC 8 : Les données proviennent de l'API Docker existante (`/api/v1/docker/containers/{id}`)

## État d'avancement technique
- [x] Création `frontend/src/views/ContainerDetail.vue` avec el-tabs
- [x] Onglet Infos : sections Ports, Volumes, Réseau, Env
- [x] Masquage mots de passe (regex sur clés *PASSWORD*, *SECRET*, *KEY*, *TOKEN*)
- [x] Bouton copier ID dans le presse-papier
- [x] Mise à jour du router (`/containers/:id`)
- [x] Service frontend Docker inspect
- [x] Tests Vitest

## Notes d'implémentation

### Fichiers créés/modifiés
- `frontend/src/types/api.ts` : Ajout des types ContainerDetail, ContainerEnvVar, ContainerPortMapping, ContainerMount, ContainerNetworkInfo
- `frontend/src/services/api.ts` : Ajout de la méthode `inspect` dans containersApi
- `frontend/src/stores/containers.ts` : Ajout de l'action `inspectContainer` et des états `containerDetail`, `detailLoading`
- `frontend/src/composables/useSecretMasker.ts` : Nouveau composable pour le masquage des secrets
- `frontend/src/views/ContainerDetail.vue` : Nouvelle vue avec onglets et sections
- `frontend/src/router/index.ts` : Ajout de la route `/containers/:id`
- `frontend/tests/unit/views/ContainerDetail.spec.ts` : Tests unitaires

### Décisions techniques
- Utilisation d'un composable `useSecretMasker` pour gérer le masquage/révélation des secrets
- Les secrets sont détectés par regex sur les patterns : password, secret, key, token, credential, jwt, etc.
- Les onglets Stats et Console sont présents mais désactivés (placeholder pour futures fonctionnalités)
- Le drawer de logs permet de rafraîchir et de configurer le nombre de lignes

### Difficultés rencontrées
- Aucune difficulté majeure
