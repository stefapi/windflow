# Guide utilisateur — Adoption d'objets découverts

## Vue d'ensemble

Le **wizard d'adoption** permet d'importer dans WindFlow des objets découverts sur vos machines (containers orphelins, compositions Docker et releases Helm) afin de les transformer en **stacks managées**. Une fois adoptés, ces objets bénéficient du cycle de vie complet de WindFlow : déploiements versionnés, variables, actions globales et supervision.

### Accès

Depuis la [vue Compute](../../docs/user-guide/compute.md) : section **Objets découverts** → bouton **↗ Adopter** sur un objet adoptable.

Le wizard s'ouvre dans une boîte de dialogue [`el-dialog`](https://element-plus.org/en-US/component/dialog.html) pilotée par le composant [`AdoptionWizard.vue`](../../frontend/src/components/compute/AdoptionWizard.vue).

---

## Table des matières

1. [Prérequis](#prérequis)
2. [Le wizard d'adoption](#le-wizard-dadoption)
   1. [Étape 1 — Inventaire des composants détectés](#étape-1--inventaire-des-composants-détectés)
   2. [Étape 2 — Options d'adoption](#étape-2--options-dadoption)
   3. [Étape 3 — Confirmation et résultat](#étape-3--confirmation-et-résultat)
3. [Types d'objets supportés](#types-dobjets-supportés)
4. [Stratégies de volumes](#stratégies-de-volumes)
5. [Stratégies de réseaux](#stratégies-de-réseaux)
6. [Référence des endpoints](#référence-des-endpoints)
7. [Fichiers source](#fichiers-source)

---

## Prérequis

- L'objet doit avoir le statut **adoptable** (`adoptable: true`) dans la liste des objets découverts.
- L'utilisateur doit disposer des permissions adéquates sur la target et l'organisation.
- L'objet ne doit pas avoir déjà été adopté dans une stack WindFlow.

> **Note** : Les objets non adoptables sont affichés en lecture seule. Le bouton **↗ Adopter** est désactivé dans ce cas.

---

## Le wizard d'adoption

Le wizard se déroule en **3 étapes** présentées via le composant [`el-steps`](https://element-plus.org/en-US/component/steps.html). Chaque étape affiche des informations contextuelles dans [`el-descriptions`](https://element-plus.org/en-US/component/descriptions.html) et des tableaux [`el-table`](https://element-plus.org/en-US/component/table.html).

![Wizard étape 1](../../docs/assets/screenshots/adoption-wizard-step-1.png)

### Étape 1 — Inventaire des composants détectés

Cette étape présente un inventaire complet des services ou composants détectés dans l'objet découvert.

| Colonne | Description |
|---------|-------------|
| **Nom** | Nom du service ou du container |
| **Image** | Image Docker utilisée |
| **État** | Statut actuel (running, exited, etc.) |
| **Variables d'environnement** | Liste des variables `ENV` détectées |
| **Volumes** | Points de montage détectés |
| **Ports** | Mappings de ports exposés |
| **CPU** | Consommation processeur (%) |
| **Mémoire** | Usage mémoire actuel |

Pour les compositions Docker, un aperçu du `docker-compose.yml` généré est disponible dans un panneau repliable [`el-collapse-item`](https://element-plus.org/en-US/component/collapse.html). Cet aperçu est en lecture seule et sert de référence avant l'adoption.

> **Note** : Les données de cette étape proviennent de l'endpoint `GET /discovery/{item_type}/{item_id}/adoption-data`. Elles sont structurées dans le schéma [`AdoptionWizardData`](../../backend/app/schemas/adoption.py).

### Étape 2 — Options d'adoption

Cette étape présente un formulaire [`el-form`](https://element-plus.org/en-US/component/form.html) permettant de configurer la stack qui sera créée.

| Champ | Type | Description | Valeurs possibles |
|-------|------|-------------|-------------------|
| **Nom de la stack** | `string` | Nom de la nouvelle stack WindFlow | Libre, unique dans l'organisation |
| **Target** | `string` (lecture seule) | Machine cible où l'objet a été découvert | Affiché mais non modifiable |
| **Stratégie volumes** | `el-select` | Comment gérer les volumes existants | `keep_existing`, `create_named`, `bind_mount` |
| **Stratégie réseaux** | `el-select` | Comment gérer les réseaux existants | `keep_existing`, `create_new` |

Pour les releases Helm, des champs supplémentaires apparaissent :

| Champ | Type | Description |
|-------|------|-------------|
| **Namespace** | `string` | Namespace Kubernetes cible |
| **Values override** | `object` | Dictionnaire de surcharges de valeurs Helm |

> **Important** : Le nom de la stack doit être unique au sein de votre organisation. En cas de conflit, un message d'erreur s'affiche et l'adoption est bloquée.

### Étape 3 — Confirmation et résultat

Cette étape affiche un récapitulatif [`el-descriptions`](https://element-plus.org/en-US/component/descriptions.html) de l'opération avant confirmation :

- Nom de la stack créée
- Type d'objet adopté
- Target associée
- Stratégies de volumes et réseaux choisies
- Nombre de services qui seront importés

Après validation, l'API est appelée et le résultat s'affiche :

- **Succès** : Message de confirmation avec l'identifiant de la nouvelle stack et un lien vers sa page de détail.
- **Échec** : Message d'erreur détaillé (conflit de nom, target inaccessible, erreur Docker, etc.).

![Wizard étape 3](../../docs/assets/screenshots/adoption-wizard-step-3.png)

---

## Types d'objets supportés

Le wizard supporte trois types d'objets découverts, identifiés par le champ `type` :

### Container individuel

Un container Docker orphelin, détecté sur une machine mais non rattaché à une composition.

- **Adoption** : Crée une stack WindFlow mono-service contenant ce container.
- **Mapping** : Le container devient le seul service de la stack.
- **Volumes** : Les volumes du container sont mappés selon la stratégie choisie.

### Composition Docker

Un projet Docker Compose détecté via un fichier `docker-compose.yml` sur la machine cible.

- **Adoption** : Crée une stack WindFlow multi-services avec le template Docker Compose extrait.
- **Mapping** : Chaque service défini dans le compose devient un service de la stack.
- **Volumes et réseaux** : Les volumes nommés et les réseaux définis dans le compose sont mappés selon les stratégies choisies.
- **Source** : Le chemin du fichier source est affiché dans l'alerte `source_path` (ex : `/home/user/monitoring/docker-compose.yml`).

### Release Helm

Une release Helm détectée sur un cluster Kubernetes.

- **Adoption** : Crée une stack WindFlow de type `helm` avec le chart et les values extraits.
- **Options spécifiques** :
  - **Namespace** : Le namespace Kubernetes peut être conservé ou modifié.
  - **Values override** : Permet de surcharger des valeurs du `values.yaml` avant l'adoption.
- **Contrainte** : Nécessite une target de type Kubernetes avec Helm configuré.

---

## Stratégies de volumes

Lors de l'adoption, les volumes existants peuvent être gérés selon trois stratégies :

| Stratégie | Identifiant | Description | Impact |
|-----------|-------------|-------------|--------|
| **Conserver existants** | `keep_existing` | Réutilise les volumes Docker existants tels quels | Aucune perte de données ; les chemins de montage sont conservés |
| **Créer nommés** | `create_named` | Crée de nouveaux volumes nommés WindFlow et migre les données | Isolation des données dans des volumes managés ; migration automatique |
| **Bind mount** | `bind_mount` | Convertit les volumes en bind mounts sur le filesystem hôte | Les données restent sur le disque hôte ; attention aux permissions |

> **Note** : La stratégie `keep_existing` est recommandée pour minimiser les risques lors d'une première adoption. Vous pourrez migrer vers des volumes nommés par la suite.

---

## Stratégies de réseaux

Les réseaux Docker de l'objet découvert peuvent être gérés selon deux stratégies :

| Stratégie | Identifiant | Description | Impact |
|-----------|-------------|-------------|--------|
| **Conserver existants** | `keep_existing` | Réutilise les réseaux Docker existants (bridge, overlay, etc.) | Aucune interruption de connectivité ; les alias DNS sont conservés |
| **Créer nouveau** | `create_new` | Crée un nouveau réseau bridge dédié à la stack | Isolation réseau renforcée ; les services communiquent via le réseau de la stack |

> **Important** : Si vous choisissez `create_new`, assurez-vous que les services externes (bases de données, APIs tierces) restent accessibles depuis le nouveau réseau.

---

## Référence des endpoints

| Endpoint | Méthode | Description | Schéma |
|----------|---------|-------------|--------|
| `/discovery/{item_type}/{item_id}/adoption-data` | `GET` | Données du wizard d'adoption pour un objet découvert | [`AdoptionWizardData`](../../backend/app/schemas/adoption.py) |
| `/discovery/adopt` | `POST` | Adopter un objet découvert et créer une stack | [`AdoptionRequest`](../../backend/app/schemas/adoption.py) → [`AdoptionResponse`](../../backend/app/schemas/adoption.py) |

Les schémas Pydantic associés sont définis dans [`backend/app/schemas/adoption.py`](../../backend/app/schemas/adoption.py) :

- `AdoptionWizardData` — Données d'inventaire et de mapping (Étape 1 et 2)
- `AdoptionServiceData` — Données d'un service individuel dans l'inventaire
- `AdoptionRequest` — Requête d'adoption (type, ID, options)
- `AdoptionResponse` — Réponse d'adoption (stack créée, message, warnings)

## Fichiers source

**Backend :**
- [`backend/app/api/v1/discovery.py`](../../backend/app/api/v1/discovery.py) — Endpoints discovery (`/discovery/{type}/{id}/adoption-data`, `/discovery/adopt`)
- [`backend/app/services/adoption_service.py`](../../backend/app/services/adoption_service.py) — Logique métier d'adoption
- [`backend/app/schemas/adoption.py`](../../backend/app/schemas/adoption.py) — Schémas Pydantic (`AdoptionWizardData`, `AdoptionServiceData`, `AdoptionRequest`, `AdoptionResponse`)

**Frontend :**
- [`frontend/src/components/compute/AdoptionWizard.vue`](../../frontend/src/components/compute/AdoptionWizard.vue) — Composant wizard 3 étapes
- [`frontend/src/services/api.ts`](../../frontend/src/services/api.ts) — Service API (`discoveryApi.getAdoptionData`, `discoveryApi.adopt`)
- [`frontend/src/types/api.ts`](../../frontend/src/types/api.ts) — Types TypeScript (`AdoptionRequest`, `AdoptionWizardData`, `AdoptionResponse`)
