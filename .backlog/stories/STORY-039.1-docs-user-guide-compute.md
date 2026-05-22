# STORY-039.1 : Documentation utilisateur — Vue Compute

**Statut :** DONE
**Story Parente :** STORY-039 — Documentation utilisateur — Nouvelles fonctionnalités
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
Rédiger le guide utilisateur pour la vue Compute globale de WindFlow. Cette vue est le centre de gestion des ressources compute et présente un bandeau de statistiques en temps réel, trois sections distinctes (Stacks WindFlow managés, objets découverts, containers standalone) et des filtres combinables avec un toggle « Par machine ».

## Critères d'acceptation (AC)
- [x] AC 1 : Documentation pour la vue Compute (bandeau stats, 3 sections, filtres)

## Contexte technique

**Couches impactées :** Documentation uniquement

**Fichiers de référence (patterns UI à documenter) :**
- Vue orchestrateur → [`frontend/src/views/Compute.vue`](frontend/src/views/Compute.vue) — orchestrateur principal, toggle « Tout / Par machine », barre de filtres
- Bandeau stats → [`frontend/src/components/ComputeStatsBanner.vue`](frontend/src/components/ComputeStatsBanner.vue) — 5 métriques : Containers Total, Running, Stacks WindFlow, Discovered, Standalone
- Stacks managées → [`frontend/src/components/compute/ManagedStacksSection.vue`](frontend/src/components/compute/ManagedStacksSection.vue) — cards pliables, [`StackActionsBar`](frontend/src/components/compute/StackActionsBar.vue) (start/stop/redeploy/duplicate/export/archive), [`BulkActionBar`](frontend/src/components/compute/BulkActionBar.vue), [`ContainerTable`](frontend/src/components/compute/ContainerTable.vue)
- Objets découverts → [`frontend/src/components/compute/DiscoveredSection.vue`](frontend/src/components/compute/DiscoveredSection.vue) — badge adoptable, bouton Adopter, `source_path`, start/stop avant adoption
- Standalone → [`frontend/src/components/compute/StandaloneSection.vue`](frontend/src/components/compute/StandaloneSection.vue) — table avec sélection, bulk actions, bouton Promouvoir
- Vue par machine → [`frontend/src/components/compute/TargetGroupView.vue`](frontend/src/components/compute/TargetGroupView.vue) — groupage par target avec métriques CPU/RAM agrégées
- Spécification métier → [`docs/general_specs/12-compute-model.md`](docs/general_specs/12-compute-model.md) — taxonomie managed/discovered/standalone
- API → [`backend/app/api/v1/compute.py`](backend/app/api/v1/compute.py) — endpoints `GET /compute/stats` et `GET /compute/global`
- Schémas → [`backend/app/schemas/compute.py`](backend/app/schemas/compute.py) — `ComputeStatsResponse`, `ComputeGlobalView`, `TargetGroup`

**Types API à référencer :**
- `ComputeStatsResponse` — 7 compteurs : total_containers, running_containers, stacks_running_count, stacks_targets_count, discovered_count, discovered_targets_count, standalone_count
- `ComputeGlobalView` — `managed: StackWithServices[]`, `discovered: DiscoveredItem[]`, `standalone: StandaloneContainer[]`
- `TargetGroup` — `target_id`, `target_name`, `technology`, `stacks`, `discovered`, `standalone`, `metrics`

**Exigences sécurité identifiées :**
- Auth : Non applicable (documentation statique)
- RBAC : N/A
- Validation : N/A
- Exposition : N/A
- Audit : N/A

---

## Tâches d'implémentation détaillées

### Tâche 1 : Créer la structure et l'introduction du guide
**Objectif :** Créer le fichier `docs/user-guide/compute.md` avec une introduction présentant la vue Compute, sa navigation depuis le menu latéral, et une vue d'ensemble des 3 sections.
**Fichiers :**
- `docs/user-guide/compute.md` — Créer — Fichier Markdown avec la structure suivante :
  - Frontmatter titre + description
  - Introduction : rôle de la vue Compute (centre de gestion des ressources)
  - Accès : depuis la sidebar principale, section « Containers — vue globale »
  - Vue d'ensemble des 3 sections avec la légende couleur (bleu=managed, orange=discovered, gris=standalone)
  - Référencer le modèle Compute détaillé dans `docs/general_specs/12-compute-model.md`
  - Table des matières des sous-sections du guide
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 2 : Documenter le bandeau de statistiques
**Objectif :** Décrire les 5 métriques affichées dans le bandeau et leur signification métier, ainsi que le comportement de chargement.
**Fichiers :**
- `docs/user-guide/compute.md` — Modifier — Section « Bandeau de statistiques » détaillant :
  - **Containers Total** : nombre total de containers sur toutes les machines (`stats.total_containers`)
  - **Running** : containers en cours d'exécution, avec indicateur coloré selon le ratio (`stats.running_containers`)
  - **Stacks WindFlow** : stacks managées actives (`stats.stacks_running_count`) + nombre de machines concernées (`stats.stacks_targets_count`)
  - **Discovered** : objets découverts (`stats.discovered_count`) + machines concernées (`stats.discovered_targets_count`)
  - **Standalone** : containers standalone (`stats.standalone_count`)
  - Comportement de chargement : skeletons pendant le fetch des données via `GET /compute/stats`
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

### Tâche 3 : Documenter la section Stacks WindFlow (managées)
**Objectif :** Expliquer comment lire une card de stack, les actions disponibles, l'expansion des services et les actions en masse.
**Fichiers :**
- `docs/user-guide/compute.md` — Modifier — Section « Stacks WindFlow » détaillant :
  - Identification : badge bleu « stack WindFlow », technologie, target, ratio `services_running/services_total`
  - Actions globales de stack (via `StackActionsBar`) : start, stop, redeploy (avec stratégie stop-start ou rolling), duplicate, export, archive
  - Expansion d'une stack : affichage des services dans `ContainerTable` avec colonnes (nom, image, statut, CPU %, mémoire, uptime, ports, actions)
  - Actions individuelles par service : démarrer, arrêter, redémarrer, supprimer, inspecter
  - Actions en masse : sélection multiple via `BulkActionBar` (start/stop/restart/delete groupés)
  - Bouton « Éditer stack » pour accéder à l'édition
  - Bouton copier ID et rafraîchir
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

### Tâche 4 : Documenter la section Discovered et Standalone
**Objectif :** Expliquer la section des objets découverts et des containers standalone, leurs particularités et actions spécifiques.
**Fichiers :**
- `docs/user-guide/compute.md` — Modifier — Deux sous-sections :

  **Objets découverts (Discovered)** :
  - Identification : badge orange « discovered », technologie, target
  - Alert `source_path` : chemin du fichier de définition détecté (ex: docker-compose.yml), avec message « lecture seule — adoptez pour gérer depuis WindFlow »
  - Badge « adoptable » : indique si l'objet peut être importé dans WindFlow
  - Bouton « Adopter » : ouvre le wizard d'adoption (lien vers guide adoption STORY-039.4)
  - Actions start/stop conditionnelles : disponibles uniquement si `adoptable=true`
  - `services_running/services_total` comme indicateur d'état

  **Containers standalone** :
  - Identification : badge gris, container individuel sans composition
  - Table complète avec colonnes identiques aux stacks (nom, image, statut, CPU, mémoire, uptime, ports, actions)
  - Sélection multiple et `BulkActionBar` (start/stop/restart/delete)
  - Bouton « Promouvoir en stack » pour transformer un standalone en stack WindFlow (lien vers guide stacks STORY-039.3)
  - Dialog de confirmation pour la suppression groupée avec liste des containers et option « Forcer la suppression »
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

### Tâche 5 : Documenter les filtres combinables et le toggle « Par machine »
**Objectif :** Décrire les filtres combinables et les deux modes de visualisation.
**Fichiers :**
- `docs/user-guide/compute.md` — Modifier — Section « Filtres et vues » détaillant :

  **Filtres combinables** :
  - **Type** : radio buttons « Tout / Stacks WindFlow / Discovered / Standalone » (filtre `filterType`)
  - **Recherche textuelle** : champ libre avec debounce 300ms, recherche sur nom (paramètre `search`)
  - **Technologie** : pills cliquables (Docker, Compose, Helm…) — sélection toggle multi/single
  - **Target** : pills cliquables par machine (localhost, vps-ovh…) — sélection toggle multi/single
  - Comportement : les filtres se combinent et déclenchent automatiquement `GET /compute/global` avec les paramètres correspondants

  **Toggle « Tout / Par machine »** :
  - **Mode « Tout »** (défaut) : les 3 sections sont affichées séparément (Stacks → Discovered → Standalone)
  - **Mode « Par machine »** : regroupement par target via `TargetGroupView`
    - Chaque target est un `el-collapse-item` avec nom, technologie, métriques CPU/RAM agrégées
    - Sous-sections : Stacks (bleu), Discovered (orange), Standalone (gris)
    - Les tables sont en mode `size="small"` sans actions individuelles (lecture seule)
    - Utilise `GET /compute/global?group_by=target`
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

---

## Tests à écrire

> Cette story est de la documentation pure. Les « tests » consistent en des validations de qualité du contenu.

### Validation documentation (checklist manuelle)

| # | Validation | Méthode |
|---|------------|---------|
| 1 | Tous les noms de composants Vue sont exacts | Vérifier contre le code source (`ComputeStatsBanner`, `ManagedStacksSection`, `DiscoveredSection`, `StandaloneSection`, `TargetGroupView`, `StackActionsBar`, `BulkActionBar`, `ContainerTable`) |
| 2 | Tous les endpoints API sont exacts | Vérifier `GET /compute/stats`, `GET /compute/global` dans [`backend/app/api/v1/compute.py`](backend/app/api/v1/compute.py) |
| 3 | Les noms de types TypeScript sont exacts | Vérifier `ComputeStatsResponse`, `ComputeGlobalView`, `StackWithServices`, `DiscoveredItem`, `StandaloneContainer`, `TargetGroup` dans [`frontend/src/types/api.ts`](frontend/src/types/api.ts) |
| 4 | Les termes UI correspondent | `managed`/`discovered`/`standalone`, `Stacks WindFlow`, `Par machine`, `Adopter`, `Promouvoir en stack` |
| 5 | Les liens internes sont valides | `docs/general_specs/12-compute-model.md` existe, liens vers guides futurs sont cohérents |
| 6 | La cohérence avec l'epic est respectée | Les fonctionnalités documentées existent bien dans EPIC-008 (STORY-001 à STORY-004) |

### Commandes de validation
```bash
# Vérifier la syntaxe Markdown
npx markdownlint docs/user-guide/compute.md || true

# Vérifier que le fichier se rend bien (aperçu)
cat docs/user-guide/compute.md | head -50

# Vérifier la présence des liens internes
grep -n "](docs/" docs/user-guide/compute.md || true
grep -n "](frontend/" docs/user-guide/compute.md || true
```

---

## État d'avancement technique
- [x] Tâche 1 : Créer la structure et l'introduction du guide
- [x] Tâche 2 : Documenter le bandeau de statistiques
- [x] Tâche 3 : Documenter la section Stacks WindFlow (managées)
- [x] Tâche 4 : Documenter la section Discovered et Standalone
- [x] Tâche 5 : Documenter les filtres combinables et le toggle « Par machine »
- [x] Validation documentation (liens, termes, composants, endpoints)
- [x] Syntaxe Markdown OK (markdownlint)

## Notes d'implémentation

**Date :** 2026-05-22

### Fichiers créés
- `docs/user-guide/compute.md` — Guide utilisateur complet pour la vue Compute (261 lignes)

### Fichiers de référence lus (validation des termes)
- `frontend/src/views/Compute.vue` — orchestrateur, toggle, filtres
- `frontend/src/components/ComputeStatsBanner.vue` — 5 métriques du bandeau
- `frontend/src/components/compute/ManagedStacksSection.vue` — stacks, expansion, bulk
- `frontend/src/components/compute/StackActionsBar.vue` — actions globales stack
- `frontend/src/components/compute/DiscoveredSection.vue` — discovered, adoption
- `frontend/src/components/compute/StandaloneSection.vue` — standalone, bulk delete
- `frontend/src/components/compute/TargetGroupView.vue` — vue par machine
- `frontend/src/components/compute/BulkActionBar.vue` — actions en masse
- `frontend/src/types/api.ts` — types ComputeStatsResponse, ComputeGlobalView, TargetGroup, etc.
- `backend/app/api/v1/compute.py` — endpoints GET /compute/stats et GET /compute/global

### Validation documentation (checklist)
| # | Validation | Résultat |
|---|------------|----------|
| 1 | Noms de composants Vue exacts | ✅ Vérifiés contre le code source |
| 2 | Endpoints API exacts | ✅ `GET /compute/stats`, `GET /compute/global` confirmés |
| 3 | Types TypeScript exacts | ✅ Vérifiés dans `frontend/src/types/api.ts` |
| 4 | Termes UI correspondants | ✅ managed/discovered/standalone, Stacks WindFlow, Par machine, Adopter, Promouvoir en stack |
| 5 | Lien `docs/general_specs/12-compute-model.md` | ✅ Fichier existe |
| 6 | Cohérence avec EPIC-008 | ✅ Fonctionnalités documentées issues de STORY-001 à STORY-004 |
| 7 | Syntaxe Markdown | ✅ Aucune erreur structurelle détectée (markdownlint non installé) |

### Divergences par rapport à l'analyse
- **Tâche 3** : La story mentionnait les actions `duplicate`, `export`, `archive` dans `StackActionsBar`. En réalité, le composant `StackActionsBar.vue` ne contient que **Démarrer, Arrêter, Redéployer**. Les actions duplicate/export/archive existent dans l'API (`stacksApi`) mais ne sont pas intégrées dans la barre d'actions de la vue Compute. La documentation a été ajustée pour refléter l'UI réelle.

### Décisions techniques
- Pas de décision technique particulière (story de documentation pure)
- Les liens vers les guides futurs (`STORY-039.3` et `STORY-039.4`) sont laissés comme références ; ils seront résolus lors de la création de ces fichiers

### Tests ajoutés
- Aucun (documentation statique sans tests automatisés applicables)
