---
name: analyse-story
description: Analyse en profondeur une story du backlog et rédige les tâches d'implémentation détaillées directement dans le fichier story, sans écrire de code
---

# analyse-story

Cette skill effectue une **analyse complète** d'une story du backlog et produit un plan d'implémentation détaillé **écrit directement dans le fichier story**. L'objectif est de pré-mâcher tout le travail d'analyse pour que l'implémentation ultérieure (via `treat-story`) soit **mécanique, rapide et avec un minimum d'hallucinations IA**.

**Aucun code n'est écrit.** Seul le fichier story est enrichi.

## Usage

Utilise cette skill quand :
- L'utilisateur demande d'analyser une story (ex: "Analyse STORY-481")
- L'utilisateur veut préparer/planifier une story avant implémentation
- L'utilisateur demande de "détailler les tâches" d'une story
- L'utilisateur veut comprendre l'impact et les dépendances d'une story

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le fichier story existe dans `.backlog/stories/`
- [ ] La story est à l'état `TODO` (ou `IN_PROGRESS` si reprise d'analyse)
- [ ] L'epic parent référencé dans la story existe

## Résultat attendu

Le fichier story est enrichi avec une section `## Tâches d'implémentation détaillées` contenant :
- Des tâches numérotées, ordonnées, avec objectif clair
- Pour chaque tâche : les fichiers exacts à créer/modifier et **ce qu'il faut faire dans chaque fichier**
- Les dépendances entre tâches
- Une section tests au niveau de la story
- Le statut de la story reste à `TODO` (pas de passage à IN_PROGRESS)

---

## Phase 1 : Lecture et compréhension de la story

### 1.1 Sélection de la story

Si l'utilisateur n'a pas spécifié de story, lister les stories disponibles dans `.backlog/stories/` avec statut `TODO` :

```
Quelle story souhaitez-vous analyser ?

Stories disponibles (TODO) :
- STORY-XXX : [Titre] (EPIC-YYY)
- STORY-XXX : [Titre] (EPIC-YYY)
...
```

### 1.2 Lecture complète de la story

Lire le fichier `.backlog/stories/STORY-XXX-*.md` et extraire :
- **Titre et numéro**
- **Epic parent** (numéro + titre)
- **Description** (format "En tant que...")
- **Critères d'acceptation (AC)** — les lire un par un, ils guident tout
- **État d'avancement technique** existant (tâches préliminaires)
- **Contexte technique** si présent
- **Dépendances** éventuelles mentionnées

### 1.3 Lecture de l'epic parent

Lire le fichier epic dans `.backlog/epics/EPIC-XXX-*.md` pour comprendre :
- La **vision globale** et la valeur business
- Les **notes de conception** (décisions d'architecture déjà prises)
- Les **risques** identifiés
- Les **critères de succès** de l'epic
- Les **autres stories de l'epic** pour comprendre le contexte et éviter les doublons
- Les **stories déjà terminées** (DONE) dont cette story pourrait dépendre

### 1.4 Lecture des specs et contraintes

Consulter les documents pertinents selon le type de story :

**Toujours lire :**
- `.clinerules/` — Règles de code, architecture, tests, sécurité

**Selon le périmètre :**
- `doc/general_specs/07-api-design.md` — Si endpoints API concernés
- `doc/general_specs/11-UI-mockups.md` — Si UI frontend concernée
- `doc/general_specs/04-data-model.md` — Si modèles de données impactés
- `doc/general_specs/05-authentication.md` — Si auth/RBAC concerné
- `doc/general_specs/06-rbac-permissions.md` — Si permissions
- `doc/general_specs/16-workflows.md` — Si workflows métier
- `doc/WEBSOCKET-REAL-TIME.md` — Si WebSocket
- `doc/DYNAMIC-FORMS.md` — Si formulaires dynamiques
- `doc/STACK-DEFINITIONS.md` — Si stacks Docker

---

## Phase 2 : Exploration du codebase existant

### 2.1 Identification du périmètre technique

Déterminer les **couches impactées** par la story :
- [ ] **Backend API** (endpoints, routes)
- [ ] **Backend Services** (logique métier)
- [ ] **Backend Models** (SQLAlchemy, migrations)
- [ ] **Backend Schemas** (Pydantic)
- [ ] **Backend WebSocket** (temps réel)
- [ ] **Backend Tasks** (Celery, async)
- [ ] **Frontend Views** (pages/vues)
- [ ] **Frontend Components** (composants réutilisables)
- [ ] **Frontend Composables** (logique réutilisable)
- [ ] **Frontend Stores** (Pinia, état global)
- [ ] **Frontend Types** (TypeScript)
- [ ] **Frontend Router** (navigation)
- [ ] **Infrastructure** (Docker, config)

### 2.2 Exploration ciblée du code

Pour chaque couche identifiée, **lire les fichiers existants pertinents** :

**Backend :**
- Lire les services existants similaires dans `backend/app/services/`
- Lire les schemas Pydantic similaires dans `backend/app/schemas/`
- Lire les endpoints API similaires dans `backend/app/api/v1/`
- Lire les modèles dans `backend/app/models/` si DB concernée
- Lire les WebSocket handlers dans `backend/app/websocket/` si temps réel
- Identifier les **patterns existants** (nommage, structure, error handling)

**Frontend :**
- Lire les vues similaires dans `frontend/src/views/`
- Lire les composants similaires dans `frontend/src/components/`
- Lire les composables similaires dans `frontend/src/composables/`
- Lire les stores Pinia similaires dans `frontend/src/stores/`
- Lire les types dans `frontend/src/types/`
- Lire le router dans `frontend/src/router/`
- Identifier les **patterns existants** (Composition API, structure template, styles)

**Tests :**
- Lire les tests existants similaires dans `backend/tests/`
- Lire les tests existants similaires dans `frontend/tests/`
- Identifier les **patterns de tests** (mocks, fixtures, assertions)

### 2.3 Recherche de dépendances et impacts

Utiliser `search_files` (grep) pour :
- Trouver **tous les fichiers qui importent** les modules qu'on va modifier
- Trouver **toutes les références** aux composants/fonctions/routes qu'on va toucher
- Identifier les **effets de bord** possibles (qui d'autre utilise ce code ?)

**Exemple de recherches :**
```bash
# Qui importe ce service ?
grep -r "from.*services.*import.*XxxService" backend/
# Qui utilise ce composant ?
grep -r "XxxComponent" frontend/src/
# Quelle route pointe vers cette vue ?
grep -r "path.*xxx" frontend/src/router/
```

### 2.4 Identification des patterns à suivre

**Objectif critique** : identifier un **fichier de référence** pour chaque type de fichier à créer. Ce fichier servira de modèle lors de l'implémentation.

Exemples :
- "Pour le nouveau service, suivre le pattern de `docker_client_service.py`"
- "Pour le nouveau composant, suivre la structure de `ContainerStats.vue`"
- "Pour les tests, suivre le pattern de `test_container_stats.py`"

**Noter précisément :**
- Le nom du fichier de référence
- Les imports à réutiliser
- La structure (classes, fonctions, exports)
- Les conventions spécifiques (error handling, logging, types)

---

## Phase 3 : Rédaction des tâches dans la story

### 3.1 Structure de la section à écrire

Remplacer la section `## État d'avancement technique` existante par une version enrichie.
Ajouter une nouvelle section `## Tâches d'implémentation détaillées` après les AC.

**Format de chaque tâche :**

```markdown
### Tâche N : [Titre descriptif et concis]
**Objectif :** [Description claire en 1-2 phrases de ce que cette tâche accomplit]
**Fichiers :**
- `chemin/vers/fichier.ext` — [Action : Créer | Modifier | Supprimer] — [Description précise : "Créer la classe XxxService avec méthodes get_all(), create(), delete()" ou "Ajouter la route GET /api/v1/xxx dans le router" ou "Modifier la méthode fetch() pour ajouter le paramètre filter"]
- `chemin/vers/autre.ext` — [Action] — [Description précise]
**Dépend de :** [Tâche X, ou "Aucune" si indépendante]
```

### 3.2 Règles de décomposition en tâches

**Granularité :**
- Chaque tâche doit être **atomique** : elle produit un résultat testable
- Une tâche = une unité cohérente de travail (pas trop grosse, pas trop petite)
- Viser entre **3 et 10 tâches** par story selon la complexité
- Si plus de 10 tâches → la story est probablement trop grosse, le signaler

**Ordre des tâches (convention) :**
1. **Backend d'abord** (API-first) : models → schemas → services → endpoints
2. **Frontend ensuite** : types → stores/composables → composants → vues → router
3. **Tests à la fin** (ou dans chaque tâche si couplage fort)
4. **Nettoyage/refactoring** en dernier

**Précision dans les fichiers :**
- Toujours donner le **chemin complet** depuis la racine du projet
- Pour les créations : décrire les **classes, méthodes, types** à créer avec leurs signatures
- Pour les modifications : décrire **ce qui change** précisément (ajout méthode, modification paramètre, ajout import)
- Pour les suppressions : lister ce qui est supprimé et **vérifier les impacts**

**Patterns à référencer :**
- Pour chaque fichier à créer, indiquer le **fichier de référence** dont s'inspirer
- Exemple : `Créer — Nouveau composant (pattern: ContainerStats.vue)`

### 3.3 Section tests

Après les tâches, ajouter une section tests au niveau de la story :

```markdown
## Tests à écrire
### Backend
- `backend/tests/unit/test_xxx/test_yyy.py` — [Cas de test : "tester get_all() retourne liste vide, tester create() avec données valides, tester create() avec données invalides retourne 422"]
### Frontend
- `frontend/tests/unit/components/XxxComponent.spec.ts` — [Cas de test : "tester le rendu initial, tester le clic sur bouton, tester l'état loading"]
- `frontend/tests/unit/views/XxxView.spec.ts` — [Cas de test]
### Commandes de validation
```bash
# Backend
pytest backend/tests/unit/test_xxx/ -v
# Frontend
cd frontend && pnpm test -- tests/unit/components/XxxComponent
cd frontend && pnpm test -- tests/unit/views/XxxView
# Build & lint
cd frontend && pnpm build && pnpm lint
```
```

### 3.4 Mise à jour de la section "État d'avancement technique"

Réécrire la section `## État d'avancement technique` avec des checkboxes correspondant exactement aux tâches détaillées :

```markdown
## État d'avancement technique
- [ ] Tâche 1 : [Titre]
- [ ] Tâche 2 : [Titre]
- [ ] Tâche 3 : [Titre]
- [ ] Tests backend
- [ ] Tests frontend
- [ ] Build & lint OK
```

Ces checkboxes seront cochées par `treat-story` au fur et à mesure de l'implémentation.

---

## Phase 4 : Validation et présentation

### 4.1 Vérification de cohérence

Avant d'écrire dans la story, vérifier :
- [ ] Chaque AC est couvert par au moins une tâche
- [ ] Chaque fichier référencé existe bien (pour les modifications) ou le chemin est cohérent (pour les créations)
- [ ] L'ordre des tâches respecte les dépendances
- [ ] Les fichiers de référence (patterns) existent et sont pertinents
- [ ] Pas de tâche orpheline sans lien avec un AC

### 4.2 Présentation du résumé à l'utilisateur

Avant d'écrire dans le fichier, présenter un résumé :

```
## Analyse de STORY-XXX : [Titre]

### Périmètre identifié
- Backend : [Oui/Non] — [Services, API, Models concernés]
- Frontend : [Oui/Non] — [Vues, Composants, Stores concernés]
- Infra : [Oui/Non] — [Docker, Config concernés]

### Tâches identifiées (N tâches)
1. [Titre tâche 1] — [X fichiers]
2. [Titre tâche 2] — [X fichiers]
...

### Dépendances externes
- [Autres stories requises, si applicable]

### Estimation de complexité
- [Simple | Moyenne | Complexe]

Je vais maintenant écrire ces tâches dans le fichier story. Confirmez-vous ? (oui/non)
```

### 4.3 Écriture dans le fichier story

Utiliser `replace_in_file` pour :
1. **Remplacer** la section `## État d'avancement technique` par la version enrichie
2. **Ajouter** la section `## Tâches d'implémentation détaillées` après les AC
3. **Ajouter** la section `## Tests à écrire` après les tâches
4. **Ne pas modifier** le statut (reste `TODO`)
5. **Ne pas modifier** les AC existants
6. **Ne pas modifier** le Kanban

---

## Règles strictes

### Ce que cette skill fait
- ✅ Lire la story, l'epic, les specs, le code existant
- ✅ Analyser les dépendances et impacts
- ✅ Identifier les fichiers de référence (patterns)
- ✅ Écrire les tâches détaillées dans la story
- ✅ Décrire précisément les fichiers à toucher et les actions dans chaque fichier
- ✅ Décrire les tests à écrire

### Ce que cette skill ne fait PAS
- ❌ Écrire du code (aucun fichier source créé/modifié)
- ❌ Changer le statut de la story
- ❌ Modifier le Kanban
- ❌ Modifier l'epic parent
- ❌ Lancer des commandes de build/test
- ❌ Commencer l'implémentation

---

## Exemple complet

**Utilisateur :** "Analyse STORY-446"

**Résultat écrit dans la story :**

```markdown
## Tâches d'implémentation détaillées

### Tâche 1 : Endpoint WebSocket backend pour le streaming des stats container
**Objectif :** Créer le endpoint WebSocket qui stream les statistiques Docker d'un container en temps réel (CPU, RAM, Network, Disk I/O)
**Fichiers :**
- `backend/app/websocket/container_stats.py` — Créer — Nouveau module WebSocket (pattern: `backend/app/websocket/` existants). Créer la fonction `container_stats_endpoint(websocket, container_id)` qui :
  - Accepte la connexion WebSocket
  - Appelle `docker_client.containers.get(container_id).stats(stream=True)`
  - Parse les stats JSON Docker et extrait cpu_percent, memory_used, memory_limit, network_rx, network_tx, disk_read, disk_write
  - Envoie les stats formatées via WebSocket toutes les secondes
  - Gère la déconnexion proprement
- `backend/app/api/v1/websockets.py` — Modifier — Ajouter la route `@router.websocket("/docker/containers/{container_id}/stats")` pointant vers `container_stats_endpoint`
- `backend/app/schemas/docker.py` — Modifier — Ajouter le schéma Pydantic `ContainerStatsMessage(cpu_percent: float, memory_used: int, memory_limit: int, memory_percent: float, network_rx: int, network_tx: int, disk_read: int, disk_write: int, timestamp: datetime)`
**Dépend de :** Aucune

### Tâche 2 : Composable frontend pour la connexion WebSocket stats
**Objectif :** Créer le composable Vue qui gère la connexion WebSocket, la reconnexion, et expose les données réactives
**Fichiers :**
- `frontend/src/composables/useContainerStats.ts` — Créer — Nouveau composable (pattern: `useContainerProcesses.ts`). Exporter `useContainerStats(containerId: Ref<string>)` retournant :
  - `stats: Ref<ContainerStats | null>` — dernières stats reçues
  - `history: Ref<StatsHistoryEntry[]>` — historique 60 entrées
  - `isConnected: Ref<boolean>` — état de connexion
  - `error: Ref<string | null>` — erreur éventuelle
  - `connect()`, `disconnect()`, `reconnect()` — méthodes de contrôle
  - Gestion auto-reconnexion avec backoff
- `frontend/src/types/api.ts` — Modifier — Ajouter les interfaces `ContainerStats`, `StatsHistoryEntry`
**Dépend de :** Tâche 1

### Tâche 3 : Composant ContainerStats.vue
**Objectif :** Créer le composant qui affiche les stats avec barres de progression et graphiques temps réel
**Fichiers :**
- `frontend/src/components/ContainerStats.vue` — Créer — Nouveau composant (pattern: `ContainerProcesses.vue`). Template avec :
  - Section CPU : ResourceBar + pourcentage (seuils couleur : vert <60%, orange <85%, rouge ≥85%)
  - Section RAM : ResourceBar + détail (utilisé/limite formaté en Ko/Mo/Go)
  - Section Network : RX/TX en bytes formatés
  - Section Disk : Read/Write en bytes formatés
  - Graphique ECharts CPU (%) sur 60 dernières valeurs
  - Graphique ECharts RAM (bytes) avec autoscale
  - Indicateur de connexion (el-tag coloré)
  - Boutons toggle auto-refresh et reconnexion manuelle
  - Props : `containerId: string`, `containerStatus: string`
  - Émettre désactivation si `containerStatus === 'stopped'`
**Dépend de :** Tâche 2

### Tâche 4 : Intégration dans ContainerDetail.vue
**Objectif :** Ajouter l'onglet Stats dans la vue détail container
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — Modifier — Ajouter un `<el-tab-pane label="Stats" name="stats">` contenant `<ContainerStats :container-id="id" :container-status="container.status" />`. Désactiver l'onglet si container stopped.
**Dépend de :** Tâche 3

## Tests à écrire
### Backend
- `backend/tests/unit/test_docker/test_container_stats.py` — Tests du parsing des stats Docker, test du schéma Pydantic ContainerStatsMessage (données valides, invalides), test de la gestion d'erreur container introuvable
### Frontend
- `frontend/tests/unit/components/ContainerStats.spec.ts` — Test rendu initial avec mock stats, test affichage barres CPU/RAM avec seuils de couleur, test état déconnecté, test container stopped désactive le composant
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — Vérifier que l'onglet Stats est présent et s'active correctement
### Commandes de validation
```bash
pytest backend/tests/unit/test_docker/test_container_stats.py -v
cd frontend && pnpm test -- tests/unit/components/ContainerStats
cd frontend && pnpm test -- tests/unit/views/ContainerDetail
cd frontend && pnpm build && pnpm lint
```
```

---

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Story non trouvée | Demander un numéro valide parmi les stories existantes |
| Story déjà DONE | Informer l'utilisateur, proposer de ré-analyser si besoin |
| Epic parent introuvable | Signaler l'incohérence, demander correction |
| Fichier de référence inexistant | Chercher une alternative, signaler dans l'analyse |
| Story trop complexe (>10 tâches) | Proposer de découper en sous-stories |
| AC ambigus ou incomplets | Signaler à l'utilisateur, proposer des clarifications |
| Dépendance circulaire entre tâches | Réorganiser les tâches pour casser le cycle |

---

## Checklist de fin

Avant de conclure l'exécution de cette skill, vérifier :

- [ ] La story a été lue et comprise (AC, description, contexte)
- [ ] L'epic parent a été consulté
- [ ] Les specs pertinentes ont été consultées
- [ ] Le code existant a été exploré (fichiers similaires, patterns, dépendances)
- [ ] Les fichiers de référence (patterns) sont identifiés pour chaque type de fichier à créer
- [ ] Les tâches sont écrites dans la story avec le format détaillé
- [ ] Chaque tâche a : objectif, fichiers avec actions précises, dépendances
- [ ] L'état d'avancement technique est aligné avec les tâches
- [ ] La section tests est rédigée avec cas de test et commandes
- [ ] Chaque AC est couvert par au moins une tâche
- [ ] Le statut de la story est resté à `TODO`
- [ ] **Aucun code source n'a été écrit ou modifié**

---

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/stories/STORY-XXX-*.md` | Lecture + Enrichissement (tâches détaillées, tests) |
| `.backlog/epics/EPIC-XXX-*.md` | Lecture seule (contexte) |
| `doc/general_specs/*.md` | Lecture seule (contraintes, specs) |
| `.clinerules/*.md` | Lecture seule (règles de dev) |
| `backend/**/*.py` | Lecture seule (exploration patterns) |
| `frontend/src/**/*` | Lecture seule (exploration patterns) |
| `backend/tests/**/*.py` | Lecture seule (exploration patterns tests) |
| `frontend/tests/**/*` | Lecture seule (exploration patterns tests) |
