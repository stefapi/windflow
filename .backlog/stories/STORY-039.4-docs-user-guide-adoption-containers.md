# STORY-039.4 : Documentation utilisateur — Adoption, création et édition de containers

**Statut :** DONE
**Story Parente :** STORY-039 — Documentation utilisateur — Nouvelles fonctionnalités
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
Rédiger les guides utilisateur pour les fonctionnalités avancées de gestion des containers dans WindFlow : le wizard d'adoption d'objets découverts (container, composition Docker, release Helm), la création manuelle de containers via formulaire avancé, et l'édition à chaud des paramètres de configuration (restart policy, limites de ressources CPU/mémoire).

## Critères d'acceptation (AC)
- [x] AC 8 : Documentation pour l'adoption d'objets découverts
- [x] AC 9 : Documentation pour la création manuelle de containers
- [x] AC 10 : Documentation pour l'édition à chaud (restart policy, ressources)

## Contexte technique

**Couches impactées :** Documentation utilisateur (Markdown)

**Fichiers de référence (patterns de documentation) :**
- [`docs/user-guide/compute.md`](../../docs/user-guide/compute.md) — Structure canonique : Vue d'ensemble + Accès → Table des matières → Sections métier → Référence endpoints → Fichiers source
- [`docs/user-guide/stacks.md`](../../docs/user-guide/stacks.md) — Pattern tables d'actions, blockquotes Note/Important, liens relatifs vers code source
- [`.markdownlint.json`](../../.markdownlint.json) — Règles désactivées : MD013 (line length), MD024 (duplicate headings), MD032, MD040, MD060

**Exigences sécurité identifiées :**
- Auth : non applicable (documentation utilisateur, pas de code exécutable)
- RBAC : non applicable
- Validation : non applicable
- Exposition : non applicable
- Audit : non applicable

**Patterns UI à documenter :**
- Émojis actions : ▶ Démarrer, ⏹ Arrêter, 🔄 Redémarrer, 🗑️ Supprimer, 📋 Logs, ↗ Adopter
- Composants Element Plus : [`el-dialog`](https://element-plus.org/en-US/component/dialog.html), [`el-steps`](https://element-plus.org/en-US/component/steps.html), [`el-descriptions`](https://element-plus.org/en-US/component/descriptions.html), [`el-table`](https://element-plus.org/en-US/component/table.html), [`el-form`](https://element-plus.org/en-US/component/form.html), [`el-input`](https://element-plus.org/en-US/component/input.html), [`el-select`](https://element-plus.org/en-US/component/select.html), [`el-switch`](https://element-plus.org/en-US/component/switch.html)

**Références croisées à inclure :**
- Liens vers [`compute.md`](../../docs/user-guide/compute.md) (vue Compute, objets découverts)
- Liens vers [`stacks.md`](../../docs/user-guide/stacks.md) (stacks managées, import/export)
- Liens vers [`docker-images.md`](../../docs/user-guide/docker-images.md), [`docker-volumes.md`](../../docs/user-guide/docker-volumes.md), [`docker-networks.md`](../../docs/user-guide/docker-networks.md)

---

## Tâches d'implémentation détaillées

### Tâche 1 : Rédiger le guide d'adoption d'objets découverts
**Objectif :** Créer `docs/user-guide/adoption.md` couvrant le wizard d'adoption en 3 étapes pour les 3 types d'objets découverts (container, composition, helm_release).
**Fichiers :**
- `docs/user-guide/adoption.md` — **Créer** — Guide d'adoption (pattern: [`docs/user-guide/stacks.md`](../../docs/user-guide/stacks.md)). Structure obligatoire :
  - `# Guide utilisateur — Adoption d'objets découverts`
  - `## Vue d'ensemble` + `### Accès` (chemin UI : Compute → section Objets découverts → bouton ↗ Adopter)
  - `## Table des matières` numérotée avec ancres
  - `---`
  - `## Prérequis` : objet découvert non encore adopté, permissions adéquates
  - `## Le wizard d'adoption` : description du flux 3 étapes
    - `### Étape 1 — Inventaire des composants détectés` : table des services (nom, image, état, env vars, volumes, ports, CPU, mémoire). Mentionner l'aperçu `docker-compose.yml` en collapse [`el-collapse-item`](https://element-plus.org/en-US/component/collapse.html)
    - `### Étape 2 — Options d'adoption` : champs du formulaire (Nom stack, Target lecture seule, Stratégie volumes, Stratégie réseaux) avec table Champ/Type/Description/Valeurs possibles
    - `### Étape 3 — Confirmation et résultat` : récapitulatif [`el-descriptions`](https://element-plus.org/en-US/component/descriptions.html), résultat succès/échec
  - `## Types d'objets supportés` :
    - `### Container individuel` : adoption en stack mono-service
    - `### Composition Docker` : adoption multi-services avec mapping volumes/réseaux
    - `### Release Helm` : options spécifiques (namespace, values override)
  - `## Stratégies de volumes` : table VolumeStrategy (keep_existing, create_named, bind_mount) avec description et impact
  - `## Stratégies de réseaux` : table NetworkStrategy (keep_existing, create_new) avec description et impact
  - `---`
  - `## Référence des endpoints` : table avec Endpoint/Méthode/Description/Schéma
    - `GET /discovery/{item_type}/{item_id}/adoption-data` — [`AdoptionWizardData`](../../backend/app/schemas/adoption.py)
    - `POST /discovery/adopt` — [`AdoptionRequest`](../../backend/app/schemas/adoption.py) → [`AdoptionResponse`](../../backend/app/schemas/adoption.py)
  - `## Fichiers source`
    - **Backend** : [`backend/app/api/v1/discovery.py`](../../backend/app/api/v1/discovery.py), [`backend/app/services/adoption_service.py`](../../backend/app/services/adoption_service.py), [`backend/app/schemas/adoption.py`](../../backend/app/schemas/adoption.py)
    - **Frontend** : [`frontend/src/components/compute/AdoptionWizard.vue`](../../frontend/src/components/compute/AdoptionWizard.vue)
  - Placeholders captures d'écran : `![Wizard étape 1](../../docs/assets/screenshots/adoption-wizard-step-1.png)` etc.
**Exigences sécurité :** Aucune exigence spécifique (documentation)
**Dépend de :** Aucune
**Couvre AC :** AC 8

### Tâche 2 : Rédiger le guide de création manuelle de containers
**Objectif :** Créer la section "Création manuelle de containers" dans `docs/user-guide/containers.md`.
**Fichiers :**
- `docs/user-guide/containers.md` — **Créer** — Guide complet des containers (pattern: [`docs/user-guide/compute.md`](../../docs/user-guide/compute.md)). Structure :
  - `# Guide utilisateur — Containers`
  - `## Vue d'ensemble` + `### Accès` (chemin UI : Compute → bouton "Créer un container" OU Containers → vue liste → bouton "+")
  - `## Table des matières`
  - `---`
  - `## Création manuelle de containers` :
    - `### Ouverture du formulaire` : dialog [`el-dialog`](https://element-plus.org/en-US/component/dialog.html) [`ContainerCreateDialog.vue`](../../frontend/src/components/ContainerCreateDialog.vue)
    - `### Champs obligatoires` : table Nom (pattern `^[a-zA-Z0-9][a-zA-Z0-9_.-]*$`), Image
    - `### Variables d'environnement` : tableau dynamique clé/valeur, mention masquage automatique des secrets (PASSWORD, SECRET, TOKEN, etc. via [`useSecretMasker`](../../frontend/src/composables/useSecretMasker.ts))
    - `### Mappings de ports` : format `hôte:container`, protocole TCP/UDP
    - `### Volumes` : format source:destination
    - `### Options avancées` : table Restart policy (no/always/on-failure/unless-stopped), Network mode (bridge par défaut), Privileged (false par défaut)
    - `### Validation et création` : bouton Créer, erreurs possibles (409 nom déjà pris)
    - `> **Note** :` Le container est créé mais non démarré automatiquement. Utilisez ▶ Démarrer depuis la liste.
    - `> **Important** :` Différence avec la création via stack : ici pas de `docker-compose.yml`, pas de gestion de version, pas de déploiement orchestré.
  - `---`
  - `## Référence des endpoints` :
    - `POST /docker/containers` — [`ContainerCreateRequest`](../../backend/app/schemas/docker.py) → [`ContainerDetailResponse`](../../backend/app/schemas/docker.py)
  - `## Fichiers source`
    - **Backend** : [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py), [`backend/app/services/container_builder.py`](../../backend/app/services/container_builder.py), [`backend/app/schemas/docker.py`](../../backend/app/schemas/docker.py)
    - **Frontend** : [`frontend/src/components/ContainerCreateDialog.vue`](../../frontend/src/components/ContainerCreateDialog.vue)
**Exigences sécurité :** Aucune exigence spécifique (documentation)
**Dépend de :** Aucune
**Couvre AC :** AC 9

### Tâche 3 : Rédiger le guide d'édition à chaud des containers
**Objectif :** Ajouter la section "Édition à chaud" dans `docs/user-guide/containers.md`.
**Fichiers :**
- `docs/user-guide/containers.md` — **Modifier** — Ajouter après la section "Création manuelle" :
  - `## Édition à chaud des containers` :
    - `### Accès` : Détail container → onglet Configuration [`ContainerConfigTab.vue`](../../frontend/src/components/ContainerConfigTab.vue)
    - `### Modifications sans recréation (à chaud)` :
      - `#### Restart Policy` : table des 4 options (no, always, on-failure, unless-stopped) avec description comportementale. Mention `on-failure` → champ "Max retry count" apparaît. Bouton "Appliquer" → `PATCH /docker/containers/{id}/restart-policy`
      - `#### Resource Limits` : table Memory limit (MB/GB), CPU shares (min 0), PIDs limit (-1 = illimité). Bouton "Appliquer" → `PATCH /docker/containers/{id}/resources`
      - `> **Note** :` Ces modifications sont appliquées immédiatement sans interruption du service.
    - `### Modifications avec recréation` :
      - `#### Variables d'environnement` : tableau éditable, ⚠️ alerte "Le layer writable sera perdu"
      - `#### Labels` : tableau éditable, même alerte
      - `#### Image` : champ nouvelle image + checkbox "Puller avant recréation", ⚠️ alerte layer writable
      - `#### Ports` : tableau Host IP/Host Port/Container Port/Protocole, validation doublons, ⚠️ alerte layer writable
      - `> **Important** :` Toute modification dans ces sections déclenche un arrêt + recréation du container. Les données non persistées dans un volume seront perdues.
    - `### Différence entre à chaud et recréation` : table comparative Édition à chaud vs Recréation requise (impact, disponibilité, données)
  - Mettre à jour `## Référence des endpoints` pour ajouter :
    - `PATCH /docker/containers/{id}/restart-policy` — [`ContainerUpdateRestartPolicyRequest`](../../backend/app/schemas/docker.py)
    - `PATCH /docker/containers/{id}/resources` — [`ContainerUpdateResourcesRequest`](../../backend/app/schemas/docker.py)
    - `POST /docker/containers/{id}/recreate` — [`ContainerRecreateRequest`](../../backend/app/schemas/docker.py) → [`ContainerRecreateResponse`](../../backend/app/schemas/docker.py)
  - Mettre à jour `## Fichiers source` pour ajouter :
    - **Backend** : [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py) (endpoints PATCH/POST recreate)
    - **Frontend** : [`frontend/src/components/ContainerConfigTab.vue`](../../frontend/src/components/ContainerConfigTab.vue)
**Exigences sécurité :** Aucune exigence spécifique (documentation)
**Dépend de :** Tâche 2
**Couvre AC :** AC 10

### Tâche 4 : Rédiger la section cycle de vie d'un container
**Objectif :** Ajouter la section "Cycle de vie d'un container" dans `docs/user-guide/containers.md`.
**Fichiers :**
- `docs/user-guide/containers.md` — **Modifier** — Ajouter en dernière section métier (avant Référence des endpoints) :
  - `## Cycle de vie d'un container` :
    - `### Diagramme de flux` : étapes séquentielles — Création (manuelle ou via stack) → Démarrage (▶) → Supervision (logs, stats, processes) → Édition à chaud (restart, ressources) → Recréation (image, ports, env) → Adoption (standalone → stack managée via [`adoption.md`](../../docs/user-guide/adoption.md)) → Arrêt (⏹) → Suppression (🗑️)
    - `### Table des actions par état` : table État/Actions disponibles/Endpoints
      - `running` : ⏹ Arrêter, 🔄 Redémarrer, ⏸ Pause, 📋 Logs, 🔧 Config
      - `paused` : ▶ Reprendre, ⏹ Arrêter
      - `stopped` : ▶ Démarrer, 🗑️ Supprimer, ↗ Promouvoir en stack
      - `exited` : ▶ Démarrer, 🗑️ Supprimer
    - `### Promotion en stack` : mentionner `POST /docker/containers/{id}/promote` pour transformer un container standalone en stack managée
    - `### Actions batch` : mentionner les actions groupées (démarrage/arrêt multiples) via `POST /docker/containers/batch/start` et `POST /docker/containers/batch/stop`
  - Mettre à jour `## Référence des endpoints` pour ajouter :
    - `POST /docker/containers/{id}/start` | `stop` | `restart` | `pause` | `unpause`
    - `DELETE /docker/containers/{id}`
    - `POST /docker/containers/{id}/promote`
    - `POST /docker/containers/batch/start` | `batch/stop`
    - `GET /docker/containers/{id}/logs` | `stats` | `top` | `shells`
**Exigences sécurité :** Aucune exigence spécifique (documentation)
**Dépend de :** Tâche 3
**Couvre AC :** AC 9, AC 10 (complément)

---

## Tests à écrire

> Cette story est pure documentation. Les "tests" sont des validations de qualité du contenu Markdown.

### Validation documentation
- [ ] Vérifier que tous les liens internes (ancres, références croisées) sont valides
- [ ] Vérifier la cohérence des termes avec l'UI réelle (adoption, discovered, standalone, promote, recreate)
- [ ] Vérifier que les noms de composants Vue et endpoints API sont corrects et existent dans le codebase
- [ ] Vérifier que les schémas Pydantic référencés existent dans `backend/app/schemas/`
- [ ] Vérifier que les liens relatifs `../../` pointent vers les bons fichiers
- [ ] Vérifier que les placeholders de captures d'écran suivent le pattern `docs/assets/screenshots/`
- [ ] Vérifier la conformité au template de documentation (Vue d'ensemble → Table des matières → Sections → Référence → Fichiers source)

### Commandes de validation
```bash
# Vérifier la syntaxe Markdown (markdownlint avec .markdownlint.json)
npx markdownlint docs/user-guide/adoption.md docs/user-guide/containers.md || true

# Vérifier que les liens relatifs ne sont pas cassés (si outil disponible)
# Ex: markdown-link-check ou équivalent

# Vérifier la présence des fichiers référencés
ls -la docs/user-guide/adoption.md docs/user-guide/containers.md
```

## État d'avancement technique
- [x] Tâche 1 : Rédiger le guide d'adoption d'objets découverts
- [x] Tâche 2 : Rédiger le guide de création manuelle de containers
- [x] Tâche 3 : Rédiger le guide d'édition à chaud des containers
- [x] Tâche 4 : Rédiger la section cycle de vie d'un container
- [x] Validation documentation (liens, termes, composants, endpoints)
- [x] Syntaxe Markdown OK (markdownlint)

## Notes d'implémentation

**Date :** 2026-05-22

### Fichiers créés
- `docs/user-guide/adoption.md` — Guide d'adoption d'objets découverts (wizard 3 étapes, types supportés, stratégies volumes/réseaux)
- `docs/user-guide/containers.md` — Guide complet des containers (création manuelle, édition à chaud, cycle de vie)

### Fichiers modifiés
- `.backlog/stories/STORY-039.4-docs-user-guide-adoption-containers.md` — Statut TODO → DONE, AC cochés, tâches cochées
- `.backlog/kanban.md` — Déplacement de STORY-039.4 vers ✅ DONE

### Décisions techniques
- Structure canonique respectée : Vue d'ensemble → Accès → Table des matières → Sections métier → Référence des endpoints → Fichiers source
- Liens relatifs `../../` utilisés pour les références au code source et aux autres guides
- Placeholders captures d'écran placés dans `docs/assets/screenshots/` (fichiers non créés — pure documentation)
- Blockquotes `> **Note** :` et `> **Important** :` utilisés pour les mises en garde
- Tables Markdown utilisées pour toute donnée structurée
- Émojis cohérents avec l'UI : ▶ ⏹ 🔄 🗑️ 📋 ↗ 🔧 ⏸

### Validation
- markdownlint : 0 erreur sur `adoption.md`, 0 erreur sur `containers.md`
- Fichiers présents et lisibles
- Pas de divergence par rapport à l'analyse
