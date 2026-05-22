# STORY-039.2 : Documentation utilisateur — Images, Volumes, Réseaux et Système Docker

**Statut :** TODO
**Story Parente :** STORY-039 — Documentation utilisateur — Nouvelles fonctionnalités
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
Rédiger les guides utilisateur pour la gestion des ressources Docker dans WindFlow : images (liste, pull, suppression, détail, import/export de tar), volumes (liste, création, suppression), réseaux (visualisation), et informations système Docker (widget dashboard + page dédiée).

## Critères d'acceptation (AC)
- [ ] AC 2 : Documentation pour la gestion des images (liste, pull, remove, détail, import/export)
- [ ] AC 3 : Documentation pour les volumes (liste, création, suppression)
- [ ] AC 4 : Documentation pour les réseaux (visualisation)
- [ ] AC 5 : Documentation pour les informations système Docker

## Contexte technique
### Images
- Vue : `frontend/src/views/Images.vue`, `frontend/src/views/ImageDetail.vue`
- API : `imagesApi.list`, `imagesApi.pull`, `imagesApi.remove`
- Types : `ImageResponse`, `ImagePullRequest`, `ImagePullResponse`

### Volumes
- Vue : `frontend/src/views/Volumes.vue`
- API : `volumesApi.list`, `volumesApi.create`, `volumesApi.remove`
- Types : `VolumeResponse`, `VolumeCreateRequest`

### Réseaux
- Vue : `frontend/src/views/Networks.vue`
- API : `networksApi.list`
- Types : `NetworkResponse`

### Système Docker
- Widget : `frontend/src/components/DockerInfoWidget.vue`
- Page : `frontend/src/views/SystemInfo.vue`
- API : `dockerSystemApi.info`, `dockerSystemApi.version`, `dockerSystemApi.ping`
- Types : `SystemInfoResponse`, `SystemVersionResponse`, `PingResponse`

## Dépendances
- Aucune

## Tâches d'implémentation détaillées

### Tâche 1 : Rédiger le guide de gestion des images Docker
**Objectif :** Créer `docs/user-guide/docker-images.md` couvrant la liste des images, le pull depuis un registre, la suppression d'images, la visualisation du détail (tags, digests, taille, labels), et l'import/export de fichiers tar.
**Fichiers :**
- `docs/user-guide/docker-images.md` — Créer — Guide complet de gestion des images
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 2 : Rédiger le guide de gestion des volumes Docker
**Objectif :** Créer `docs/user-guide/docker-volumes.md` couvrant la liste des volumes, la création d'un volume (nom, driver, labels), et la suppression avec option force.
**Fichiers :**
- `docs/user-guide/docker-volumes.md` — Créer — Guide complet de gestion des volumes
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 3 : Rédiger le guide de visualisation des réseaux Docker
**Objectif :** Créer `docs/user-guide/docker-networks.md` couvrant la liste des réseaux, les propriétés affichées (driver, scope, subnet, gateway, internal, attachable, ingress).
**Fichiers :**
- `docs/user-guide/docker-networks.md` — Créer — Guide de visualisation des réseaux
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 4 : Rédiger le guide des informations système Docker
**Objectif :** Créer `docs/user-guide/system-info.md` couvrant le widget dashboard (aperçu rapide : version, containers, images, ressources) et la page dédiée SystemInfo (détails complets : kernel, OS, architecture, root dir, driver).
**Fichiers :**
- `docs/user-guide/system-info.md` — Créer — Guide des informations système Docker
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

## Tests à écrire

### Validation documentation
- Vérifier que tous les liens internes sont valides
- Vérifier la cohérence des termes avec l'UI
- Vérifier que les noms de composants et endpoints sont corrects

### Commandes de validation
```bash
# Vérifier la syntaxe Markdown
npx markdownlint docs/user-guide/docker-images.md docs/user-guide/docker-volumes.md docs/user-guide/docker-networks.md docs/user-guide/system-info.md || true
```

## État d'avancement technique
- [ ] Tâche 1 : Rédiger le guide de gestion des images Docker
- [ ] Tâche 2 : Rédiger le guide de gestion des volumes Docker
- [ ] Tâche 3 : Rédiger le guide de visualisation des réseaux Docker
- [ ] Tâche 4 : Rédiger le guide des informations système Docker

## Notes d'implémentation
<!-- Ajoutées à la clôture par treat-story -->
