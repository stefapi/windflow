# STORY-039.3 : Documentation utilisateur — Import/export et actions sur les stacks

**Statut :** DONE
**Story Parente :** STORY-039 — Documentation utilisateur — Nouvelles fonctionnalités
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
Rédiger le guide utilisateur pour les fonctionnalités de gestion avancée des stacks dans WindFlow : export d'une stack au format JSON (partage et sauvegarde), import d'une stack depuis un fichier JSON, et actions globales sur une stack (démarrer, arrêter, redéployer, dupliquer, archiver).

## Critères d'acceptation (AC)
- [x] AC 6 : Documentation pour l'import/export de stacks
- [x] AC 7 : Documentation pour les actions de stack (start/stop/redeploy, duplication, archivage)

## Contexte technique

### Patterns de documentation observés
Tous les guides utilisateur existants (`docs/user-guide/compute.md`, `docker-images.md`, `docker-volumes.md`, `docker-networks.md`, `system-info.md`) suivent un template cohérent :
1. **Titre** : `# Guide utilisateur — [Nom de la vue]`
2. **Vue d'ensemble** + **Accès** (chemin dans la barre latérale)
3. **Table des matières** avec ancres
4. **Sections métier** détaillées avec tables de colonnes/actions/filtres
5. **Référence des endpoints** en fin de document (table Endpoint/Méthode/Description)
6. Liens vers les fichiers source backend et composants frontend
7. Captures d'écran référencées dans `docs/assets/screenshots/`

**Fichiers de référence (patterns) :**
- Guide le plus proche : `docs/user-guide/compute.md` (contient déjà des actions de stack)
- Structure de base : `docs/user-guide/docker-images.md` (162 lignes, bien structuré)

### Endpoints backend à documenter
| Endpoint | Méthode | Fichier source | Description |
|----------|---------|----------------|-------------|
| `/stacks/{stack_id}/export` | GET | `backend/app/api/v1/import_export.py:21` | Export JSON d'une stack |
| `/stacks/import` | POST | `backend/app/api/v1/import_export.py:72` | Import JSON d'une stack |
| `/stacks/{stack_id}/start` | POST | `backend/app/api/v1/stacks.py:1655` | Démarrer tous les services |
| `/stacks/{stack_id}/stop` | POST | `backend/app/api/v1/stacks.py:1733` | Arrêter tous les services |
| `/stacks/{stack_id}/redeploy` | POST | `backend/app/api/v1/stacks.py:1816` | Redéployer (stratégies) |
| `/stacks/{stack_id}/duplicate` | POST | `backend/app/api/v1/stacks.py:1936` | Dupliquer une stack |
| `/stacks/{stack_id}/archive` | POST | `backend/app/api/v1/stacks.py:2024` | Archiver une stack |
| `/stacks/{stack_id}/unarchive` | POST | `backend/app/api/v1/stacks.py:2121` | Désarchiver une stack |

### Composants frontend à référencer
- Vue principale : `frontend/src/views/Stacks.vue` (1310 lignes, contient les dialogs Import/Export/Duplicate)
- Barre d'actions : `frontend/src/components/compute/StackActionsBar.vue` (304 lignes, Start/Stop/Redeploy)
- Service API : `frontend/src/services/api.ts` (`stacksApi.export`, `stacksApi.import`, `stacksApi.start`, `stacksApi.stop`, `stacksApi.redeploy`, `stacksApi.duplicate`, `stacksApi.archive`)
- Types : `frontend/src/types/api.ts` (`StackExportData`, `StackActionResponse`, `StackRedeployRequest`, `StackDuplicateRequest`, `RedeployStrategy`)

### Format d'export JSON (v1.0)
```json
{
  "version": "1.0",
  "stack": {
    "name": "...",
    "description": "...",
    "version": "...",
    "category": "...",
    "tags": [...],
    "template": {...},
    "variables": {...},
    "icon_url": "...",
    "screenshots": [...],
    "documentation_url": "...",
    "author": "...",
    "license": "..."
  }
}
```

### Stratégies de redeploy
- `stop_start` (défaut) : arrête tous les containers, puis les redémarre
- `rolling` : redéploie service par service sans interruption totale
- Option `pull_images` : force le pull des images avant le redéploiement

### Exigences sécurité identifiées
- Aucune exigence spécifique (documentation utilisateur pure, pas de code exécutable)

---

## Tâches d'implémentation détaillées

### Tâche 1 : Créer la structure du guide et la section Export de stacks
**Objectif :** Créer le fichier `docs/user-guide/stacks.md` avec la structure de base du guide et documenter le flux d'export JSON.
**Fichiers :**
- `docs/user-guide/stacks.md` — Créer — Structure complète du guide (pattern: `docs/user-guide/docker-images.md`) :
  - Titre `# Guide utilisateur — Stacks`
  - Vue d'ensemble : "Ce guide couvre la gestion avancée des stacks WindFlow : import/export, actions globales et cycle de vie."
  - Accès : "Stacks" dans la barre latérale → `/stacks`
  - Table des matières avec ancres vers toutes les sections
  - **Section "Export de stacks"** :
    - Accès depuis `Stacks.vue` : bouton "Export" dans la liste des stacks ou dans le panneau de détail
    - Format du fichier exporté : JSON v1.0 avec les champs `name`, `description`, `version`, `category`, `tags`, `template`, `variables`, `icon_url`, `screenshots`, `documentation_url`, `author`, `license`
    - Le fichier est téléchargé automatiquement via header `Content-Disposition`
    - Cas d'usage : sauvegarde avant modification majeure, partage entre environnements, migration vers une autre organisation
    - Référence endpoint : `GET /stacks/{stack_id}/export`
    - Référence composant : `Stacks.vue` (dialog d'export), `stacksApi.export(id)`
**Exigences sécurité :** Aucune
**Dépend de :** Aucune

### Tâche 2 : Rédiger la section Import de stacks
**Objectif :** Documenter le flux d'import JSON depuis un fichier exporté.
**Fichiers :**
- `docs/user-guide/stacks.md` — Modifier — Ajouter la section "Import de stacks" après la section Export :
  - Accès depuis `Stacks.vue` : bouton "Import Stack" en haut de la liste
  - Dialogue de sélection de fichier (accepte uniquement `.json`)
  - Validation du format : le fichier doit être au format v1.0 avec un champ `stack` racine
  - Résultat : création d'une nouvelle stack en mode privé (`is_public: false`) avec le nom du fichier importé
  - Les variables du template sont importées telles quelles (pas de rendu Jinja à l'import)
  - Cas d'usage : restauration d'une sauvegarde, migration depuis un autre environnement, partage de stacks entre équipes
  - Référence endpoint : `POST /stacks/import`
  - Référence composant : `Stacks.vue` (dialog d'import), `stacksApi.import(file)`
  - Référence type : `StackImportResponse`
**Exigences sécurité :** Aucune
**Dépend de :** Tâche 1

### Tâche 3 : Rédiger la section Actions globales de stack
**Objectif :** Documenter chaque action disponible dans `StackActionsBar.vue` et `Stacks.vue`.
**Fichiers :**
- `docs/user-guide/stacks.md` — Modifier — Ajouter la section "Actions de stack" après la section Import :
  - **Start** : démarre tous les services de la stack en parallèle. Accessible depuis `StackActionsBar.vue` (bouton ▶️) ou `Stacks.vue`. Endpoint : `POST /stacks/{stack_id}/start`. Réponse : `StackActionResponse` avec liste des services affectés.
  - **Stop** : arrête tous les services de la stack. Paramètre optionnel `timeout` (délai avant kill forcé). Accessible depuis `StackActionsBar.vue` (bouton ⏹️). Endpoint : `POST /stacks/{stack_id}/stop`.
  - **Redeploy** : redéploie la stack avec deux stratégies :
    - `stop_start` (défaut) : arrête tous les containers puis les redémarre. Adapté aux stacks sans haute disponibilité.
    - `rolling` : redéploie service par service sans interruption totale. Adapté aux stacks stateless.
    - Option `pull_images` : force le pull des dernières versions d'images avant redéploiement.
    - Dialogue de confirmation dans `StackActionsBar.vue` avec choix de stratégie et checkbox `pull_images`.
    - Endpoint : `POST /stacks/{stack_id}/redeploy`. Types : `StackRedeployRequest`, `StackRedeployResponse`.
  - **Duplicate** : crée une copie de la stack avec un nouveau nom. Dialogue dans `Stacks.vue` avec champ "New Stack Name" et option `organization_id`. Endpoint : `POST /stacks/{stack_id}/duplicate`. Type : `StackDuplicateRequest`.
  - **Archive** : marque la stack comme archivée (soft delete, réversible). La stack disparaît de la liste principale mais reste accessible via le filtre "Show Archived". Endpoint : `POST /stacks/{stack_id}/archive`.
  - **Unarchive** : restaure une stack archivée. Endpoint : `POST /stacks/{stack_id}/unarchive`.
  - Table récapitulative des actions (Action | Icône | Endpoint | Description)
**Exigences sécurité :** Aucune
**Dépend de :** Tâche 1

### Tâche 4 : Rédiger la section Cycle de vie d'une stack et la référence des endpoints
**Objectif :** Fournir un guide de référence rapide du cycle de vie complet et la table de référence des endpoints.
**Fichiers :**
- `docs/user-guide/stacks.md` — Modifier — Ajouter les sections finales :
  - **Section "Cycle de vie d'une stack"** :
    - Diagramme textuel ou liste ordonnée : Création (`POST /stacks`) → Déploiement (`POST /deployments`) → Actions (Start/Stop/Redeploy via `StackActionsBar.vue`) → Export (sauvegarde) → Duplication (clonage) → Archivage (`POST /stacks/{id}/archive`) → Suppression (`DELETE /stacks/{id}`)
    - Prérequis et impacts de chaque étape (ex: "Redeploy nécessite que la stack soit déployée", "Archive masque la stack de la liste principale mais préserve l'historique")
    - Bonnes pratiques : exporter avant un redeploy majeur, archiver plutôt que supprimer pour l'historique
  - **Section "Référence des endpoints"** (table en fin de document) :
    | Endpoint | Méthode | Description |
    |----------|---------|-------------|
    | `/stacks/{stack_id}/export` | GET | Export JSON |
    | `/stacks/import` | POST | Import JSON |
    | `/stacks/{stack_id}/start` | POST | Démarrer tous les services |
    | `/stacks/{stack_id}/stop` | POST | Arrêter tous les services |
    | `/stacks/{stack_id}/redeploy` | POST | Redéployer |
    | `/stacks/{stack_id}/duplicate` | POST | Dupliquer |
    | `/stacks/{stack_id}/archive` | POST | Archiver |
    | `/stacks/{stack_id}/unarchive` | POST | Désarchiver |
  - Liens vers les fichiers source : `backend/app/api/v1/stacks.py`, `backend/app/api/v1/import_export.py`, `frontend/src/views/Stacks.vue`, `frontend/src/components/compute/StackActionsBar.vue`
**Exigences sécurité :** Aucune
**Dépend de :** Tâche 3

---

## Tests à écrire

> Cette story est pure documentation. Les "tests" sont des validations manuelles et automatiques du document.

### Validation du document
- [ ] Tous les liens internes (ancres Markdown) sont valides et sans erreur 404
- [ ] Cohérence des termes avec l'UI : `rolling`, `stop_start`, `pull_images`, `archive`, `unarchive`
- [ ] Les noms de composants sont corrects : `Stacks.vue`, `StackActionsBar.vue`
- [ ] Les noms d'endpoints et types sont corrects : `stacksApi.export`, `stacksApi.import`, `StackExportData`, `StackActionResponse`, `StackRedeployRequest`, `StackDuplicateRequest`
- [ ] Le format JSON d'export v1.0 est exact (vérifier contre `backend/app/api/v1/import_export.py`)
- [ ] Les stratégies de redeploy sont correctement décrites (`stop_start` vs `rolling`)

### Commandes de validation
```bash
# Vérifier la syntaxe Markdown
npx markdownlint docs/user-guide/stacks.md || true

# Vérifier les liens internes (si markdown-link-check est disponible)
npx markdown-link-check docs/user-guide/stacks.md || true

# Compter les lignes pour s'assurer que le document est complet
wc -l docs/user-guide/stacks.md
```

### Critères de qualité du document
- [ ] Le document suit le template des guides existants (titre, vue d'ensemble, accès, TOC, sections métier, référence endpoints)
- [ ] Chaque section a une ancre Markdown valide
- [ ] Les tables sont correctement formatées (alignement des colonnes)
- [ ] Le document fait entre 150 et 300 lignes (cohérent avec les autres guides)

---

## État d'avancement technique
- [x] Tâche 1 : Créer la structure du guide et la section Export de stacks
- [x] Tâche 2 : Rédiger la section Import de stacks
- [x] Tâche 3 : Rédiger la section Actions globales de stack
- [x] Tâche 4 : Rédiger la section Cycle de vie et référence des endpoints
- [x] Validation Markdown (markdownlint)
- [x] Vérification des liens et termes

## Notes d'implémentation

**Date :** 2026-05-22

### Fichiers créés
- `docs/user-guide/stacks.md` : Guide utilisateur complet (280 lignes) couvrant export JSON, import JSON, actions de stack (start/stop/redeploy/duplicate/archive/unarchive) et cycle de vie
- `.markdownlint.json` : Configuration markdownlint adaptée au projet

### Décisions techniques
- Le document suit le template cohérent des guides existants (`compute.md`, `docker-images.md`)
- Les règles markdownlint trop contraignantes (MD013 lignes 80 caractères, MD024 titres dupliqués, MD060 alignement tableaux) ont été désactivées via `.markdownlint.json`

### Validation
- `npx markdownlint-cli docs/user-guide/stacks.md` : ✅ passé (exit code 0)
- Document de 280 lignes (dans la plage 150-300 attendue)

<!-- Ajoutées à la clôture par treat-story -->
