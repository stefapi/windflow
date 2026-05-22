# Guide utilisateur — System Information

## Vue d'ensemble

La **vue System Information** permet de surveiller l'état du daemon Docker et du système sur vos machines cibles. Elle agrège des informations de version, de connectivité et de ressources sous forme de cartes synthétiques, avec la possibilité d'afficher les données brutes au format JSON.

### Accès

Depuis la barre latérale principale : **Docker → System Info**.

---

## Table des matières

1. [Cartes d'information](#cartes-dinformation)
2. [Affichage JSON](#affichage-json)
3. [Rafraîchissement](#rafraîchissement)

---

## Cartes d'information

La vue affiche trois cartes d'information côte à côte, chacune correspondant à un endpoint API distinct.

### Docker Version

Cette carte affiche les informations de version du daemon Docker, récupérées via `GET /system/version` (voir [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py)).

| Information | Source API | Description |
|-------------|------------|-------------|
| **Version** | `version.version` | Version du daemon Docker (ex : `26.1.0`) |
| **API Version** | `version.api_version` | Version de l'API Docker exposée |
| **Go Version** | `version.go_version` | Version de Go utilisée pour compiler le daemon |
| **OS/Arch** | `version.os` / `version.arch` | Système d'exploitation et architecture |
| **Git Commit** | `version.git_commit` | Hash du commit Git du build Docker |
| **Build Time** | `version.build_time` | Date de compilation du daemon |

### System Ping

Cette carte affiche l'état de connectivité avec le daemon Docker, récupéré via `GET /system/ping`.

| Information | Source API | Description |
|-------------|------------|-------------|
| **Statut** | `ping.status` | `pong` si le daemon répond, `error` sinon |
| **Latence** | Calculée côté frontend | Temps de réponse de l'API en millisecondes |
| **Message** | `ping.message` | Message détaillé en cas d'erreur |

Le statut s'affiche en **vert** avec une icône de succès si le daemon répond, et en **rouge** avec une icône d'erreur sinon.

### System Info

Cette carte affiche les informations détaillées du système Docker, récupérées via `GET /system/info`.

| Information | Source API | Description |
|-------------|------------|-------------|
| **Containers** | `info.containers` / `info.containers_running` / `info.containers_paused` / `info.containers_stopped` | Nombre total, en cours, en pause et arrêtés |
| **Images** | `info.images` | Nombre total d'images sur la machine |
| **Volumes** | `info.driver` / `info.driver_status` | Driver de stockage et son statut |
| **Networks** | `info.networks` | Nombre de réseaux existants |
| **Mémoire** | `info.mem_total` | Mémoire totale disponible sur le host |
| **CPUs** | `info.ncpu` | Nombre de processeurs logiques |
| **Kernel Version** | `info.kernel_version` | Version du noyau Linux |
| **OS Type** | `info.ostype` / `info.os_version` | Type et version du système d'exploitation |
| **Architecture** | `info.architecture` | Architecture du processeur |

---

## Affichage JSON

Un bouton **Toggle JSON** permet de basculer entre l'affichage des cartes synthétiques et l'affichage brut des réponses API au format JSON.

### Mode carte (défaut)

Les informations sont présentées sous forme de cartes visuelles avec des icônes, des couleurs et une mise en page structurée. Ce mode est optimisé pour une lecture rapide.

### Mode JSON

Les trois réponses API (`/system/version`, `/system/ping`, `/system/info`) sont affichées dans des blocs de code formatés ([`json`](https://element-plus.org/en-US/component/code.html)) avec coloration syntaxique. Ce mode est utile pour le débogage ou l'accès à des champs non affichés dans les cartes.

> **Note** : le basculement entre les deux modes est instantané et ne déclenche pas de nouvel appel API.

![Vue System Info](../assets/screenshots/system-info-overview.png)

![JSON détaillé](../assets/screenshots/system-info-json.png)

---

## Rafraîchissement

Un bouton **Refresh** dans l'en-tête de la vue permet de recharger manuellement les données des trois cartes.

### Comportement

- **Clic sur Refresh** : déclenche simultanément trois appels API (`GET /system/version`, `GET /system/ping`, `GET /system/info`)
- **Indicateur de chargement** : chaque carte affiche un skeleton animé pendant le rechargement
- **Erreur** : si un appel échoue, la carte concernée affiche un message d'erreur avec un bouton de retry

### Rafraîchissement automatique

Par défaut, la vue ne se rafraîchit pas automatiquement. Les données affichées correspondent à l'état au moment du chargement de la page ou du dernier clic sur **Refresh**.

---

## Référence des endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/system/version` | `GET` | Informations de version du daemon Docker |
| `/system/ping` | `GET` | Test de connectivité avec le daemon |
| `/system/info` | `GET` | Informations détaillées du système Docker |

Voir l'implémentation complète dans [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py).
