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
- Les exigences de sécurité intégrées dans les tâches concernées
- Les dépendances entre tâches
- Une section tests détaillée (unitaires, intégration, sécurité, commandes)
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

### 1.4 Lecture des règles et contraintes du projet

**Lire obligatoirement tous les fichiers `.clinerules/` pertinents** — ils font autorité sur toutes les décisions d'implémentation :

| Fichier `.clinerules/` | Ce qu'il apporte à l'analyse |
|------------------------|------------------------------|
| `.clinerules/05-tech-stack.md` | Stack technique (langages, frameworks, outils) |
| `.clinerules/20-architecture-and-api.md` | Principes API-first, architecture, résilience |
| `.clinerules/30-code-standards.md` | Conventions de nommage, clean code, gestion d'erreurs |
| `.clinerules/35-testing-quality-gates.md` | Patterns de tests, couverture minimale, outillage |
| `.clinerules/40-security.md` | Checklist sécurité, tests obligatoires, exigences RBAC |
| `.clinerules/45-observability.md` | Logging structuré, corrélation, métriques |
| `.clinerules/55-project-structure.md` | Organisation des répertoires, localisation des fichiers de test |

**Selon le périmètre de la story, lire également :**
- `doc/general_specs/07-api-design.md` — Si endpoints API concernés
- `doc/general_specs/11-UI-mockups.md` — Si UI frontend concernée
- `doc/general_specs/04-data-model.md` — Si modèles de données impactés
- `doc/general_specs/05-authentication.md` — Si auth/RBAC concerné
- `doc/general_specs/06-rbac-permissions.md` — Si permissions (rôles autorisés/interdits)
- `doc/general_specs/16-workflows.md` — Si workflows métier
- `doc/WEBSOCKET-REAL-TIME.md` — Si WebSocket
- `doc/DYNAMIC-FORMS.md` — Si formulaires dynamiques
- `doc/STACK-DEFINITIONS.md` — Si stacks Docker

---

## Phase 2 : Exploration du codebase existant

### 2.1 Identification du périmètre technique

Déterminer les **couches impactées** par la story et se référer à `.clinerules/55-project-structure.md` pour la structure complète.

### 2.2 Exploration ciblée du code

Pour chaque couche identifiée, **lire les fichiers existants pertinents** en suivant la structure du projet. Par exemple :

**Backend :**
- Lire les services existants similaires dans `backend/app/services/`
- Lire les schemas Pydantic similaires dans `backend/app/schemas/`
- Lire les endpoints API similaires dans `backend/app/api/v1/`
- Lire les modèles dans `backend/app/models/` si DB concernée
- Lire les WebSocket handlers dans `backend/app/websocket/` si temps réel
- Identifier les **patterns existants** (nommage, structure, error handling, logging)

**Frontend :**
- Lire les vues similaires dans `frontend/src/views/`
- Lire les composants similaires dans `frontend/src/components/`
- Lire les composables similaires dans `frontend/src/composables/`
- Lire les stores Pinia similaires dans `frontend/src/stores/`
- Lire les types dans `frontend/src/types/`
- Lire le router dans `frontend/src/router/`
- Identifier les **patterns existants** (Composition API, structure template, gestion d'erreurs)

**Tests :**
- Lire les tests existants similaires dans `backend/tests/`
- Lire les tests existants similaires dans `frontend/tests/`
- Identifier les **fixtures et mocks** déjà disponibles (conftest.py)

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

## Phase 2.5 : Évaluation de complexité et décision de découpe

**Avant de rédiger les tâches**, évaluer si la story est traitable en une seule session LLM (~200k tokens context window).

### Critères de complexité

Une story est considérée **complexe** si elle remplit **au moins un** des critères suivants :
- **Plus de 5 tâches d'implémentation** identifiées lors de l'exploration (Phase 2)
- **Plus de 6 fichiers** à modifier/créer
- **Mélange backend + frontend** (couche full-stack avec modifications significatives des deux côtés)
- **Plus de 8 critères d'acceptation** (AC)

### Processus de décision

```
### Évaluation de complexité — STORY-XXX

**Critères remplis :**
- [ ] > 5 tâches identifiées → [Oui/Non — compter les tâches envisagées]
- [ ] > 6 fichiers impactés → [Oui/Non — lister les fichiers]
- [ ] Backend + Frontend → [Oui/Non]
- [ ] > 8 AC → [Oui/Non — nombre d'AC]

**Verdict :** [Simple | Complexe]
```

#### Si la story est SIMPLE → passer à Phase 2.6 (analyse sécurité) puis Phase 3 (rédaction classique des tâches)

#### Si la story est COMPLEXE → lancer le processus de découpe en sous-stories

### Processus de découpe en sous-stories

#### Étape A : Analyser les groupes de tâches

Regrouper les tâches envisagées par **cohésion fonctionnelle** :
- Backend API / Services / Models / Schemas
- Frontend Composants / Stores / Composables / Types
- Helpers / Utils / Shared
- Tests

#### Étape B : Proposer le découpage à l'utilisateur

Présenter la proposition AVANT toute création de fichier :

```
## ⚠️ STORY-XXX est complexe — Découpe proposée

**Raison :** [critères remplis]

**Sous-stories proposées :**

### STORY-XXX.1 : [Titre] — Backend API
- **Périmètre :** [description]
- **AC couverts :** AC 1, AC 2, AC 3
- **Fichiers :** [liste]
- **Tâches estimées :** N

### STORY-XXX.2 : [Titre] — Frontend composants
- **Périmètre :** [description]
- **AC couverts :** AC 4, AC 5
- **Fichiers :** [liste]
- **Tâches estimées :** N

### STORY-XXX.3 : [Titre] — Tests & intégration
- **Périmètre :** [description]
- **AC couverts :** AC 6, AC 7, AC 8
- **Fichiers :** [liste]
- **Tâches estimées :** N

**Dépendances :** STORY-XXX.2 dépend de STORY-XXX.1, STORY-XXX.3 dépend de STORY-XXX.2

Validez-vous ce découpage ? (oui / modifications souhaitées)
```

#### Étape C : Après validation utilisateur — Créer les fichiers de sous-stories

Pour chaque sous-story, créer un fichier `.backlog/stories/STORY-XXX.N-titre-court.md` en utilisant le template `.backlog/sub-story.md` :

```markdown
# STORY-XXX.N : [Titre de la sous-story]

**Statut :** TODO
**Story Parente :** STORY-XXX — [Titre de la Story]
**Epic Parent :** EPIC-YYY — [Titre de l'Epic]

## Description
[Sous-ensemble de la description parente, spécifique à cette sous-story]

## Critères d'acceptation (AC)
- [ ] AC X : [Critère hérité de la story parente]
- [ ] AC Y : [Critère hérité de la story parente]

## Contexte technique
[Fichiers concernés, patterns, prérequis — rempli grâce à l'exploration Phase 2]

## Dépendances
- STORY-XXX.(N-1) : [si dépendance, ou "Aucune"]

## Tâches d'implémentation détaillées
[Remplies comme en Phase 3 classique — 2 à 4 tâches ciblées par sous-story]

## Tests à écrire
[Spécifiques à cette sous-story — voir Phase 3.3 pour le format]

## État d'avancement technique
- [ ] Tâche 1 ...
- [ ] Tâche 2 ...

## Notes d'implémentation
<!-- Ajoutées à la clôture par treat-story -->
```

**Rédiger les tâches détaillées dans chaque sous-story** en suivant le même format que la Phase 3 classique (§3.1 à §3.3).

#### Étape D : Transformer la story parente

Modifier le fichier story parent pour :
1. **Retirer** la section `## État d'avancement technique` détaillée (remplacer par une note)
2. **Retirer** la section `## Tâches d'implémentation détaillées` si elle existait
3. **Ajouter** la section `## Sous-stories` :

```markdown
## Sous-stories
- [ ] STORY-XXX.1 : [Titre sous-story 1] — Couvre AC 1, AC 2, AC 3
- [ ] STORY-XXX.2 : [Titre sous-story 2] — Couvre AC 4, AC 5
- [ ] STORY-XXX.3 : [Titre sous-story 3] — Couvre AC 6, AC 7, AC 8
```

4. **Ajouter** les dépendances entre sous-stories dans la section `## Dépendances` existante

#### Principes de découpe à respecter

- **Cohésion fonctionnelle** : chaque sous-story couvre un domaine cohérent
- **Autonomie** : chaque sous-story peut être implémentée et testée indépendamment
- **Ordre logique** : numérotation séquentielle (.1, .2, .3...) dans l'ordre d'implémentation
- **AC répartis** : chaque AC de la story parente est couvert par exactement une sous-story
- **Taille cible** : 2-4 tâches d'implémentation par sous-story
- **Sous-stories non listées dans l'epic parent** (uniquement dans la story parente)

---

## Phase 2.6 : Analyse des exigences de sécurité

> Se référer à `.clinerules/40-security.md` pour la checklist complète et les exigences détaillées.

Avant de rédiger les tâches, passer en revue **obligatoirement** les points suivants et noter les conclusions dans le contexte technique de la story :

### Authentification & autorisation

- **Authentification requise ?** → Identifier si `get_current_user` doit être injecté dans les endpoints
- **Rôles concernés ?** → Lister les rôles autorisés et interdits (consulter `doc/general_specs/06-rbac-permissions.md`)
- **Isolation des ressources ?** → Si des ressources appartiennent à un user, vérifier que l'accès cross-user est bloqué

### Validation & injection

- **Inputs exposés à l'injection ?** → SQL, shell, YAML, JSON — identifier les champs à valider strictement
- **Validation Pydantic suffisante ?** → Vérifier que les schémas bornent les champs (min/max, regex, enum)

### Exposition de données sensibles

- **Champs sensibles dans les réponses ?** → Identifier les champs à exclure des schémas `*Response` (mots de passe, tokens, secrets)
- **Logging sécurisé ?** → Vérifier que les logs ne contiendront pas de données sensibles

### Audit & traçabilité

- **Action critique à tracer ?** → Si oui, prévoir un audit log (suppression, déploiement, modification config)

### Synthèse sécurité

Documenter les conclusions sous forme d'une note dans le contexte technique :

```
**Exigences sécurité identifiées :**
- Auth : [oui/non — dépendance require_role("xxx")]
- RBAC : [rôles autorisés : admin, operator — rôles interdits : viewer]
- Validation : [champs sensibles à valider : xxx]
- Exposition : [champs à exclure de la réponse : xxx]
- Audit : [oui/non — action à tracer]
```

---

## Phase 3 : Rédaction des tâches dans la story (si story simple)

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
**Exigences sécurité :** [Dépendance require_role("xxx"), ou champs à exclure, ou "Aucune exigence spécifique"]
**Dépend de :** [Tâche X, ou "Aucune" si indépendante]
```

### 3.2 Règles de décomposition en tâches

> Se référer à `.clinerules/20-architecture-and-api.md` pour le principe API-first, `.clinerules/30-code-standards.md` pour les conventions de nommage et gestion d'erreurs, `.clinerules/55-project-structure.md` pour les chemins de fichiers.

**Granularité :**
- Chaque tâche doit être **atomique** : elle produit un résultat testable
- Une tâche = une unité cohérente de travail (pas trop grosse, pas trop petite)
- Viser entre **3 et 10 tâches** par story selon la complexité
- Si plus de 10 tâches → la story est probablement trop grosse, le signaler

**Ordre des tâches (API-first — conforme `.clinerules/20-architecture-and-api.md`) :**
1. **Backend d'abord** : models → schemas → services → endpoints
2. **Frontend ensuite** : types → stores/composables → composants → vues → router
3. **Tests à la fin** (ou dans chaque tâche si couplage fort)
4. **Nettoyage/refactoring** en dernier

**Exigences sécurité dans les tâches (conforme `.clinerules/40-security.md`) :**
- Pour tout endpoint : mentionner explicitement `require_role(...)` ou `get_current_user`
- Pour les schémas `*Response` : lister les champs à exclure (`exclude={"password", "token"}`)
- Pour les services : mentionner la vérification d'appartenance si applicable

**Précision dans les fichiers :**
- Toujours donner le **chemin complet** depuis la racine du projet
- Pour les créations : décrire les **classes, méthodes, types** à créer avec leurs signatures
- Pour les modifications : décrire **ce qui change** précisément (ajout méthode, modification paramètre, ajout import)
- Pour les suppressions : lister ce qui est supprimé et **vérifier les impacts**

**Patterns à référencer :**
- Pour chaque fichier à créer, indiquer le **fichier de référence** dont s'inspirer
- Exemple : `Créer — Nouveau composant (pattern: ContainerStats.vue)`

### 3.3 Section tests

> Se référer à `.clinerules/35-testing-quality-gates.md` pour les patterns de tests détaillés, la couverture minimale, et les cas obligatoires par type d'endpoint.
> Se référer à `.clinerules/40-security.md` section "Checklist des tests de sécurité" pour les tests de sécurité obligatoires.

Après les tâches, ajouter une section tests complète au niveau de la story :

```markdown
## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Backend
- `backend/tests/unit/test_services/test_xxx_service.py`
  - `test_get_all_returns_empty_list` — cas nominal : liste vide
  - `test_get_all_returns_items` — cas nominal : liste avec éléments
  - `test_create_with_valid_data` — cas nominal : création réussie
  - `test_create_raises_on_duplicate` — cas d'erreur : conflit (409)
  - `test_delete_raises_when_not_found` — cas d'erreur : ressource introuvable

- `backend/tests/unit/test_api/test_xxx.py`
  - `test_xxx_returns_200_authenticated` — cas nominal avec auth
  - `test_xxx_returns_401_without_token` — **sécurité** : accès sans token
  - `test_xxx_returns_403_for_viewer` — **sécurité RBAC** : rôle insuffisant
  - `test_xxx_returns_422_on_invalid_body` — validation Pydantic
  - `test_xxx_returns_404_when_not_found` — ressource absente
  - `test_xxx_response_does_not_expose_password` — **sécurité** : champs sensibles absents (si applicable)

### Unitaires Frontend
- `frontend/tests/unit/components/XxxComponent.spec.ts`
  - `affiche le spinner pendant le chargement` — rendu initial
  - `affiche les données quand chargées` — rendu nominal
  - `affiche un message d'erreur si l'API échoue` — état d'erreur
  - `émet l'événement 'action' au clic` — interaction
  - `masque les actions pour rôle viewer` — **sécurité** : accès conditionnel (si applicable)

- `frontend/tests/unit/views/XxxView.spec.ts`
  - `redirige vers /login si non authentifié` — **sécurité** : route protégée
  - `affiche les données après chargement` — rendu nominal
  - `n'affiche pas les tokens/secrets dans le DOM` — **sécurité** : exposition (si applicable)

### Intégration (si applicable)
- `backend/tests/integration/test_api_xxx.py`
  - Tester le flux complet avec DB réelle si la logique métier l'exige

### Commandes de validation
```bash
# Backend (voir Makefile)
poetry run pytest backend/tests/unit/test_services/test_xxx_service.py -v
poetry run pytest backend/tests/unit/test_api/test_xxx.py -v --tb=short

# Frontend (voir Makefile)
cd frontend && pnpm test -- tests/unit/components/XxxComponent
cd frontend && pnpm test -- tests/unit/views/XxxView
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
- [ ] Tests unitaires backend
- [ ] Tests unitaires frontend
- [ ] Build & lint OK
```

Ces checkboxes seront cochées par `treat-story` au fur et à mesure de l'implémentation.

---

## Phase 4 : Validation et présentation

### 4.1 Vérification de cohérence

Avant d'écrire dans la story, vérifier :
- [ ] Chaque AC est couvert par au moins une tâche
- [ ] Chaque fichier référencé existe bien (pour les modifications) ou le chemin est cohérent (pour les créations)
- [ ] L'ordre des tâches respecte les dépendances et le principe API-first (`.clinerules/20-architecture-and-api.md`)
- [ ] Les fichiers de référence (patterns) existent et sont pertinents
- [ ] Pas de tâche orpheline sans lien avec un AC
- [ ] Les exigences sécurité sont intégrées dans les tâches concernées (`.clinerules/40-security.md`)
- [ ] Les tests de sécurité obligatoires sont listés (401, 403, 422 au minimum)

### 4.2 Présentation du résumé à l'utilisateur

Avant d'écrire dans le fichier, présenter un résumé :

```
## Analyse de STORY-XXX : [Titre]

### Périmètre identifié
- Backend : [Oui/Non] — [Services, API, Models concernés]
- Frontend : [Oui/Non] — [Vues, Composants, Stores concernés]
- Infra : [Oui/Non] — [Docker, Config concernés]

### Exigences sécurité
- Auth : [oui/non]
- RBAC : [rôles autorisés / rôles interdits]
- Validation : [points à surveiller]
- Exposition données sensibles : [champs à exclure]

### Tâches identifiées (N tâches)
1. [Titre tâche 1] — [X fichiers]
2. [Titre tâche 2] — [X fichiers]
...

### Tests planifiés
- Backend : N tests (dont X tests sécurité)
- Frontend : N tests (dont X tests sécurité)

### Dépendances externes
- [Autres stories requises, si applicable]

### Estimation de complexité
- [Simple | Moyenne | Complexe]

Je vais maintenant écrire ces tâches dans le fichier story. Confirmez-vous ? (oui/non)
```

### 4.3 Écriture dans le fichier story

Utiliser `replace_in_file` pour :
1. **Ajouter ou enrichir** la section `## Contexte technique` avec les patterns identifiés et les exigences sécurité
2. **Ajouter** la section `## Tâches d'implémentation détaillées` après les AC
3. **Ajouter** la section `## Tests à écrire` après les tâches
4. **Remplacer** la section `## État d'avancement technique` par la version enrichie
5. **Ne pas modifier** le statut (reste `TODO`)
6. **Ne pas modifier** les AC existants
7. **Ne pas modifier** le Kanban

---

## Règles strictes

### Ce que cette skill fait
- ✅ Lire la story, l'epic, les specs, le code existant
- ✅ Lire **tous** les fichiers `.clinerules/` pertinents avant de rédiger les tâches
- ✅ Analyser les dépendances et impacts
- ✅ Identifier les fichiers de référence (patterns)
- ✅ Évaluer les exigences de sécurité (phase 2.6) et les intégrer dans les tâches
- ✅ Écrire les tâches détaillées dans la story
- ✅ Décrire précisément les fichiers à toucher et les actions dans chaque fichier
- ✅ Décrire des tests complets (nominaux + erreurs + sécurité) avec commandes d'exécution

### Ce que cette skill ne fait PAS
- ❌ Écrire du code (aucun fichier source créé/modifié)
- ❌ Changer le statut de la story
- ❌ Modifier le Kanban
- ❌ Modifier l'epic parent
- ❌ Lancer des commandes de build/test
- ❌ Commencer l'implémentation
- ❌ Dupliquer dans la story le contenu des `.clinerules/` (référencer, ne pas recopier)

---

## Exemple complet

**Utilisateur :** "Analyse STORY-446"

**Résultat écrit dans la story :**

```markdown
## Contexte technique

**Couches impactées :** Backend WebSocket, Backend Schemas, Backend API, Frontend Composable, Frontend Composant, Frontend Vue

**Fichiers de référence :**
- Service WebSocket → pattern : `backend/app/websocket/` existants
- Composable → pattern : `useContainerProcesses.ts`
- Composant → pattern : `ContainerProcesses.vue`
- Tests backend → pattern : `backend/tests/unit/test_docker/`
- Tests frontend → pattern : `frontend/tests/unit/components/`

**Exigences sécurité identifiées :**
- Auth : oui — `get_current_user` requis sur l'endpoint WebSocket
- RBAC : rôles autorisés = viewer, operator, admin (lecture seule : stats en lecture)
- Validation : container_id doit être validé (UUID format)
- Exposition : aucun champ sensible dans les stats Docker
- Audit : non requis (lecture seule)

---

## Tâches d'implémentation détaillées

### Tâche 1 : Endpoint WebSocket backend pour le streaming des stats container
**Objectif :** Créer le endpoint WebSocket qui stream les statistiques Docker d'un container en temps réel (CPU, RAM, Network, Disk I/O)
**Fichiers :**
- `backend/app/websocket/container_stats.py` — Créer — Nouveau module WebSocket (pattern: modules existants `backend/app/websocket/`). Créer la fonction `container_stats_endpoint(websocket, container_id, current_user)` qui :
  - Injecte `get_current_user` pour authentifier la connexion
  - Accepte la connexion WebSocket
  - Appelle `docker_client.containers.get(container_id).stats(stream=True)`
  - Parse les stats JSON Docker et extrait cpu_percent, memory_used, memory_limit, network_rx, network_tx, disk_read, disk_write
  - Envoie les stats formatées via WebSocket toutes les secondes
  - Gère la déconnexion proprement avec try/except WebSocketDisconnect
  - Log `logger.info("ws_stats_connected", extra={"user_id": current_user.id, "container_id": container_id})`
- `backend/app/api/v1/websockets.py` — Modifier — Ajouter la route `@router.websocket("/docker/containers/{container_id}/stats")` pointant vers `container_stats_endpoint`
- `backend/app/schemas/docker.py` — Modifier — Ajouter le schéma Pydantic `ContainerStatsMessage(cpu_percent: float, memory_used: int, memory_limit: int, memory_percent: float, network_rx: int, network_tx: int, disk_read: int, disk_write: int, timestamp: datetime)`
**Exigences sécurité :** `get_current_user` injecté — container_id validé au format UUID
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
**Exigences sécurité :** Token JWT transmis dans le header WebSocket — ne pas afficher le token dans les logs console
**Dépend de :** Tâche 1

### Tâche 3 : Composant ContainerStats.vue
**Objectif :** Créer le composant qui affiche les stats avec barres de progression et graphiques temps réel
**Fichiers :**
- `frontend/src/components/ContainerStats.vue` — Créer — Nouveau composant (pattern: `ContainerProcesses.vue`). Template avec :
  - Section CPU : ResourceBar + pourcentage (seuils couleur : vert <60%, orange <85%, rouge ≥85%)
  - Section RAM : ResourceBar + détail (utilisé/limite formaté en Ko/Mo/Go)
  - Section Network : RX/TX en bytes formatés
  - Section Disk : Read/Write en bytes formatés
  - Graphique CPU (%) sur 60 dernières valeurs
  - Graphique RAM (bytes) avec autoscale
  - Indicateur de connexion (el-tag coloré)
  - Props : `containerId: string`, `containerStatus: string`
  - Émettre désactivation si `containerStatus === 'stopped'`
**Exigences sécurité :** Aucune exigence spécifique (lecture seule, pas de données sensibles affichées)
**Dépend de :** Tâche 2

### Tâche 4 : Intégration dans ContainerDetail.vue
**Objectif :** Ajouter l'onglet Stats dans la vue détail container
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — Modifier — Ajouter un `<el-tab-pane label="Stats" name="stats">` contenant `<ContainerStats :container-id="id" :container-status="container.status" />`. Désactiver l'onglet si container stopped.
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 3

---

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Backend
- `backend/tests/unit/test_docker/test_container_stats.py`
  - `test_stats_message_schema_valid` — cas nominal : schéma Pydantic ContainerStatsMessage avec données valides
  - `test_stats_message_schema_invalid_type` — validation : type incorrect → erreur Pydantic
  - `test_container_stats_endpoint_unauthenticated` — **sécurité** : connexion WebSocket sans token → rejet
  - `test_container_stats_endpoint_unknown_container` — cas d'erreur : container_id inexistant → 404

### Unitaires Frontend
- `frontend/tests/unit/components/ContainerStats.spec.ts`
  - `affiche le spinner de connexion en attente` — rendu initial
  - `affiche les barres CPU et RAM avec les données reçues` — rendu nominal
  - `applique la couleur rouge quand CPU > 85%` — seuil de couleur
  - `affiche l'état déconnecté avec le tag approprié` — état déconnecté
  - `désactive et masque le composant si container stopped` — accès conditionnel
  - `n'affiche pas le token JWT dans le DOM` — **sécurité** : exposition tokens

- `frontend/tests/unit/views/ContainerDetail.spec.ts`
  - `affiche l'onglet Stats dans le détail container` — rendu nominal
  - `désactive l'onglet Stats si container stopped` — état conditionnel
  - `redirige vers /login si non authentifié` — **sécurité** : route protégée

### Commandes de validation
```bash
# Backend (voir Makefile)
poetry run pytest backend/tests/unit/test_docker/test_container_stats.py -v

# Frontend (voir Makefile)
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
| Exigences sécurité non clarifiées | Lister les points d'incertitude dans la section "Exigences sécurité" |

---

## Checklist de fin

Avant de conclure l'exécution de cette skill, vérifier :

- [ ] La story a été lue et comprise (AC, description, contexte)
- [ ] L'epic parent a été consulté
- [ ] Les fichiers `.clinerules/` pertinents ont tous été consultés (05, 20, 30, 35, 40, 55 au minimum)
- [ ] Les specs pertinentes dans `doc/general_specs/` ont été consultées selon le périmètre
- [ ] Le code existant a été exploré (fichiers similaires, patterns, dépendances)
- [ ] Les fichiers de référence (patterns) sont identifiés pour chaque type de fichier à créer
- [ ] L'analyse de sécurité (phase 2.6) a été effectuée et ses conclusions sont documentées dans le contexte technique
- [ ] Les tâches sont écrites dans la story avec le format détaillé (objectif, fichiers, exigences sécurité, dépendances)
- [ ] Chaque tâche qui crée/modifie un endpoint mentionne explicitement la dépendance auth/RBAC
- [ ] L'état d'avancement technique est aligné avec les tâches
- [ ] La section tests est rédigée avec : cas nominaux, cas d'erreurs, **tests de sécurité obligatoires**, commandes
- [ ] Chaque AC est couvert par au moins une tâche
- [ ] Le statut de la story est resté à `TODO`
- [ ] **Aucun code source n'a été écrit ou modifié**

---

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/stories/STORY-XXX-*.md` | Lecture + Enrichissement (tâches détaillées, tests, contexte sécurité) |
| `.backlog/epics/EPIC-XXX-*.md` | Lecture seule (contexte) |
| `.clinerules/*.md` | Lecture seule (règles de dev — **à consulter avant de rédiger**) |
| `doc/general_specs/*.md` | Lecture seule (contraintes, specs, rôles RBAC) |
| `backend/**/*.py` | Lecture seule (exploration patterns) |
| `frontend/src/**/*` | Lecture seule (exploration patterns) |
| `backend/tests/**/*.py` | Lecture seule (exploration patterns tests) |
| `frontend/tests/**/*` | Lecture seule (exploration patterns tests) |
