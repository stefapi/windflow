# STORY-039.2 : Documentation utilisateur — Images, Volumes, Réseaux et Système Docker

**Statut :** DONE
**Story Parente :** STORY-039 — Documentation utilisateur — Nouvelles fonctionnalités
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
Rédiger les guides utilisateur pour la gestion des ressources Docker dans WindFlow : images (liste, pull, suppression, détail, import/export de tar), volumes (liste, création, suppression), réseaux (visualisation), et informations système Docker (widget dashboard + page dédiée).

## Critères d'acceptation (AC)
- [x] AC 2 : Documentation pour la gestion des images (liste, pull, remove, détail, import/export)
- [x] AC 3 : Documentation pour les volumes (liste, création, suppression)
- [x] AC 4 : Documentation pour les réseaux (visualisation)
- [x] AC 5 : Documentation pour les informations système Docker

## Contexte technique

**Couches impactées :** Documentation utilisateur uniquement (pas de code backend/frontend/CLI)

**Fichiers de référence :**
- Guide modèle → pattern : `docs/user-guide/compute.md` (structure : H1 titre → introduction → table des matières → sections H2 par fonctionnalité → sous-sections H3 → placeholders captures d'écran → référence API)
- Vue Images → référence : `frontend/src/views/Images.vue` (444 lignes, liste paginée, filtres, actions inspect/pull/delete/prune, vue détail ImageDetail.vue)
- Vue Volumes → référence : `frontend/src/views/Volumes.vue` (272 lignes, liste paginée, filtres, actions create/delete/prune, dialogue création)
- Vue Networks → référence : `frontend/src/views/Networks.vue` (159 lignes, liste paginée, filtres par driver, actions inspect/create/delete/prune)
- Vue System Info → référence : `frontend/src/views/SystemInfo.vue` (205 lignes, cartes info version/ping/info système, affichage JSON formaté, refresh manuel)
- Endpoints API → référence : `backend/app/api/v1/docker.py` (routes images, volumes, networks, system)

**Exigences sécurité identifiées :**
- Auth : non spécifique — les vues sont protégées par le middleware auth global
- RBAC : non spécifique — documentation utilisateur, pas de logique d'autorisation à documenter
- Validation : aucune — documentation pure
- Exposition données sensibles : aucune — pas de secrets dans ces vues
- Audit : non requis

## Tâches d'implémentation détaillées

### Tâche 1 : Rédiger le guide utilisateur Docker Images
**Objectif :** Documenter la vue Images et ses fonctionnalités (liste, filtres, actions, détail image)
**Fichiers :**
- `docs/user-guide/docker-images.md` — Créer — Nouveau guide (pattern: `docs/user-guide/compute.md`). Structure attendue :
  - H1 : "Docker Images"
  - Introduction : rôle de la vue (gestion des images Docker sur les targets)
  - Table des matières
  - Section "Liste des images" : description de la table paginée, colonnes (ID, Repository, Tag, Size, Created, In Use), tri, recherche
  - Section "Filtres" : filtre par target, filtre "In Use Only", filtre "Dangling Only"
  - Section "Actions sur les images" :
    - "Inspecter une image" : clic sur ligne → vue détail avec onglets Info/History/Layers
    - "Pull une image" : bouton Pull, saisie repository:tag, appel API `POST /docker/images/pull`
    - "Supprimer une image" : bouton Delete, confirmation, appel API `DELETE /docker/images/{id}`
    - "Prune les images" : bouton Prune, suppression des dangling images, appel API `POST /docker/images/prune`
  - Section "Détail d'une image" : onglets Info (métadonnées), History (couches), Layers (analyse)
  - Placeholders captures d'écran : `![Liste des images](../assets/screenshots/docker-images-list.png)`, `![Détail image](../assets/screenshots/docker-images-detail.png)`
  - Référence API : liens vers `backend/app/api/v1/docker.py` (routes images)
**Exigences sécurité :** Aucune exigence spécifique (documentation pure)
**Dépend de :** Aucune

### Tâche 2 : Rédiger le guide utilisateur Docker Volumes
**Objectif :** Documenter la vue Volumes et ses fonctionnalités (liste, création, suppression, prune)
**Fichiers :**
- `docs/user-guide/docker-volumes.md` — Créer — Nouveau guide (pattern: `docs/user-guide/compute.md`). Structure attendue :
  - H1 : "Docker Volumes"
  - Introduction : rôle de la vue (gestion des volumes persistants Docker)
  - Table des matières
  - Section "Liste des volumes" : description de la table paginée, colonnes (Name, Driver, Mountpoint, Size, Created), tri, recherche
  - Section "Filtres" : filtre par target, filtre "Dangling Only"
  - Section "Créer un volume" : bouton Create, dialogue avec champs Name, Driver, Driver Options, appel API `POST /docker/volumes`
  - Section "Actions sur les volumes" :
    - "Supprimer un volume" : bouton Delete, confirmation, appel API `DELETE /docker/volumes/{name}`
    - "Prune les volumes" : bouton Prune, suppression des volumes non utilisés, appel API `POST /docker/volumes/prune`
  - Placeholders captures d'écran : `![Liste des volumes](../assets/screenshots/docker-volumes-list.png)`, `![Création volume](../assets/screenshots/docker-volumes-create.png)`
  - Référence API : liens vers `backend/app/api/v1/docker.py` (routes volumes)
**Exigences sécurité :** Aucune exigence spécifique (documentation pure)
**Dépend de :** Aucune

### Tâche 3 : Rédiger le guide utilisateur Docker Networks
**Objectif :** Documenter la vue Networks et ses fonctionnalités (liste, création, suppression, inspect)
**Fichiers :**
- `docs/user-guide/docker-networks.md` — Créer — Nouveau guide (pattern: `docs/user-guide/compute.md`). Structure attendue :
  - H1 : "Docker Networks"
  - Introduction : rôle de la vue (gestion des réseaux Docker sur les targets)
  - Table des matières
  - Section "Liste des réseaux" : description de la table paginée, colonnes (ID, Name, Driver, Scope, Subnet, Gateway), tri, recherche
  - Section "Filtres" : filtre par target, filtre par driver (bridge, host, overlay, etc.)
  - Section "Créer un réseau" : bouton Create, dialogue avec champs Name, Driver, Subnet, Gateway, appel API `POST /docker/networks`
  - Section "Actions sur les réseaux" :
    - "Inspecter un réseau" : clic sur ligne → modal/panneau avec détails JSON (containers attachés, options, labels)
    - "Supprimer un réseau" : bouton Delete, confirmation, appel API `DELETE /docker/networks/{id}`
    - "Prune les réseaux" : bouton Prune, suppression des réseaux non utilisés, appel API `POST /docker/networks/prune`
  - Placeholders captures d'écran : `![Liste des réseaux](../assets/screenshots/docker-networks-list.png)`, `![Inspect réseau](../assets/screenshots/docker-networks-inspect.png)`
  - Référence API : liens vers `backend/app/api/v1/docker.py` (routes networks)
**Exigences sécurité :** Aucune exigence spécifique (documentation pure)
**Dépend de :** Aucune

### Tâche 4 : Rédiger le guide utilisateur System Info
**Objectif :** Documenter la vue System Info et ses fonctionnalités (version Docker, ping, info système)
**Fichiers :**
- `docs/user-guide/system-info.md` — Créer — Nouveau guide (pattern: `docs/user-guide/compute.md`). Structure attendue :
  - H1 : "System Information"
  - Introduction : rôle de la vue (surveillance de l'état du daemon Docker et du système)
  - Table des matières
  - Section "Cartes d'information" : description des 3 cartes affichées :
    - "Docker Version" : version du daemon Docker, API version, Go version, OS/Arch, appel API `GET /system/version`
    - "System Ping" : état de connectivité avec le daemon (pong/erreur), latence, appel API `GET /system/ping`
    - "System Info" : informations détaillées du système (nombre de containers, images, volumes, networks, mémoire totale, CPUs, kernel version), appel API `GET /system/info`
  - Section "Affichage JSON" : bouton pour basculer l'affichage brut JSON formaté des réponses API
  - Section "Rafraîchissement" : bouton Refresh pour recharger les données manuellement
  - Placeholders captures d'écran : `![Vue System Info](../assets/screenshots/system-info-overview.png)`, `![JSON détaillé](../assets/screenshots/system-info-json.png)`
  - Référence API : liens vers `backend/app/api/v1/docker.py` (routes system)
**Exigences sécurité :** Aucune exigence spécifique (documentation pure)
**Dépend de :** Aucune

## Tests à écrire

> Cette story est purement documentation. Aucun test unitaire/backend/frontend n'est requis.
> La validation se fait par relecture et vérification de la cohérence avec le code source.

### Validation documentation
- Vérifier la syntaxe Markdown de chaque fichier créé
- Vérifier que tous les liens internes (placeholders images, références API) sont cohérents
- Vérifier que la structure suit le pattern de `docs/user-guide/compute.md`
- Vérifier que les noms de routes API mentionnés correspondent bien à `backend/app/api/v1/docker.py`
- Vérifier que les noms de composants/vues correspondent bien aux fichiers `frontend/src/views/*.vue`

### Commandes de validation
```bash
# Vérifier la présence des 4 fichiers
ls -la docs/user-guide/docker-images.md docs/user-guide/docker-volumes.md docs/user-guide/docker-networks.md docs/user-guide/system-info.md

# Vérifier la syntaxe markdown (si markdownlint disponible)
cd docs && npx markdownlint user-guide/*.md 2>/dev/null || echo "markdownlint non installé, vérification manuelle requise"

# Vérifier que les liens vers les vues frontend sont cohérents
grep -l "Images.vue\|Volumes.vue\|Networks.vue\|SystemInfo.vue" docs/user-guide/*.md

# Vérifier que les routes API mentionnées existent dans le backend
grep -E "GET /docker/images|GET /docker/volumes|GET /docker/networks|GET /system/info|GET /system/version|GET /system/ping" docs/user-guide/*.md
```

## État d'avancement technique
- [x] Tâche 1 : Rédiger le guide utilisateur Docker Images
- [x] Tâche 2 : Rédiger le guide utilisateur Docker Volumes
- [x] Tâche 3 : Rédiger le guide utilisateur Docker Networks
- [x] Tâche 4 : Rédiger le guide utilisateur System Info
- [x] Validation syntaxe Markdown et cohérence des liens
- [x] Vérification alignement avec le code source (vues + routes API)

## Notes d'implémentation

**Date :** 2026-05-22

**Fichiers créés :**
- `docs/user-guide/docker-images.md` — Guide utilisateur Docker Images (liste, filtres, actions pull/delete/prune, détail avec onglets Info/History/Layers)
- `docs/user-guide/docker-volumes.md` — Guide utilisateur Docker Volumes (liste, filtres, création, suppression, prune)
- `docs/user-guide/docker-networks.md` — Guide utilisateur Docker Networks (liste, filtres par driver, création, inspection, suppression, prune)
- `docs/user-guide/system-info.md` — Guide utilisateur System Information (cartes Version/Ping/Info, affichage JSON, refresh manuel)

**Résumé :**
Les 4 guides utilisateur ont été rédigés en suivant le pattern de `docs/user-guide/compute.md` (H1 titre → introduction → table des matières → sections H2 → sous-sections H3 → placeholders captures d'écran → référence API). Chaque document est en français, inclut des liens vers les vues frontend (`frontend/src/views/*.vue`) et les routes backend (`backend/app/api/v1/docker.py`), ainsi que les placeholders d'images vers `../assets/screenshots/`. La syntaxe Markdown a été vérifiée et la structure est cohérente sur les 4 fichiers.
