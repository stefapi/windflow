---
name: create-refactoring
description: Crée une story de refactoring technique avec analyse d'architecture, identification des impacts et plan de non-régression complet
---

# create-refactoring

Cette skill guide la création d'une story de **refactoring technique** dans l'application WindFlow. Elle assure une analyse approfondie de l'architecture existante, l'identification des risques de régression, et la planification détaillée des vérifications de non-régression.

## Usage

Utilise cette skill quand :
- L'utilisateur demande de refactorer du code (ex: "Refactor le service de déploiement")
- L'utilisateur veut améliorer la structure/architecture sans changer le comportement
- L'utilisateur identifie de la dette technique à éliminer
- L'utilisateur demande d'appliquer un pattern de conception (SOLID, DRY, etc.)
- L'utilisateur veut réorganiser des modules/composants

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le dossier `.backlog/stories/` existe
- [ ] Le dossier `.backlog/epics/` existe (pour trouver l'epic parent)
- [ ] Le fichier `.backlog/kanban.md` existe
- [ ] Le code à refactorer existe réellement dans le codebase

---

## Phase 1 : Clarification

Si le refactoring n'est pas clairement identifié ou si la demande est vague, poser les questions suivantes :

### Questions obligatoires (si information manquante)

```
## Clarification nécessaire

Pour créer cette story de refactoring, j'ai besoin des informations suivantes :

1. **Code cible** : Quel code/module/composant doit être refactoré ?
   - [ ] Fichier(s) ou module(s) concerné(s)
   - [ ] Localisation dans le codebase (backend/frontend)

2. **Motivation** : Pourquoi ce refactoring est-il nécessaire ?
   - [ ] Dette technique (code difficile à maintenir)
   - [ ] Violation de principes SOLID
   - [ ] Duplication de code (DRY)
   - [ ] Complexité excessive (KISS)
   - [ ] Amélioration de la testabilité
   - [ ] Performance
   - [ ] Préparation à une future fonctionnalité

3. **Type de refactoring** :
   - [ ] Extraction (méthode, classe, module)
   - [ ] Renommage (variables, fonctions, fichiers)
   - [ ] Déplacement (fichier, module, dossier)
   - [ ] Simplification (conditionnelles, méthodes)
   - [ ] Introduction de pattern (Strategy, Factory, etc.)
   - [ ] Suppression de code mort
   - [ ] Réorganisation de structure

4. **Contraintes particulières** :
   - [ ] Y a-t-il une deadline ou une urgence ?
   - [ ] Ce refactoring doit-il être fait de manière incrémentale ?
   - [ ] Y a-t-il des dépendances externes à considérer ?

5. **Périmètre** :
   - [ ] Ce refactoring est-il limité à un module ou impacte-t-il plusieurs parties ?

Merci de fournir ces informations pour que je puisse analyser l'existant et créer une story adaptée.
```

### Questions sur la méthode (si plusieurs approches possibles)

Si plusieurs méthodes de refactoring sont envisageables, présenter les options à l'utilisateur :

```
## Choix de la méthode de refactoring

Pour le refactoring de [description], j'ai identifié plusieurs approches possibles :

### Option A : [Nom de l'approche]
- **Description** : [Description courte]
- **Avantages** : [Avantages]
- **Inconvénients** : [Inconvénients]
- **Effort estimé** : [Faible/Moyen/Élevé]

### Option B : [Nom de l'approche]
- **Description** : [Description courte]
- **Avantages** : [Avantages]
- **Inconvénients** : [Inconvénients]
- **Effort estimé** : [Faible/Moyen/Élevé]

### Ma recommandation : Option X
[Raison de la recommandation basée sur SOLID/DRY/KISS/YAGNI]

Quelle approche préférez-vous ? (A/B/Autre)
```

---

## Phase 2 : Analyse du Code Existant

Une fois le refactoring identifié, explorer le codebase pour comprendre l'implémentation actuelle.

### 2.1 Exploration du code

**Pour un refactoring backend :**
```bash
# Identifier les fichiers liés au module à refactorer
backend/app/api/v1/           # Endpoints
backend/app/models/           # Modèles SQLAlchemy
backend/app/schemas/          # Schémas Pydantic
backend/app/services/         # Services métier
backend/app/core/             # Abstractions et utilitaires
backend/app/tasks/            # Tâches Celery
```

**Pour un refactoring frontend :**
```bash
# Identifier les fichiers liés au composant à refactorer
frontend/src/views/           # Vues
frontend/src/components/      # Composants
frontend/src/composables/     # Composables
frontend/src/stores/          # Stores Pinia
frontend/src/services/        # Services API
frontend/src/types/           # Types TypeScript
```

### 2.2 Recherche des dépendances

Utiliser `grep` ou `search_files` pour identifier :
- Les imports du module/composant
- Les usages dans d'autres fichiers
- Les tests existants

```bash
# Exemple de recherche
grep -r "ServiceName" backend/app/
grep -r "ComponentName" frontend/src/
```

### 2.3 Identification du comportement actuel

**Étape critique** : Documenter le comportement actuel qui doit être préservé :

```markdown
## Comportement à préserver

### Entrées
- [Input 1] : [Description]
- [Input 2] : [Description]

### Sorties
- [Output 1] : [Description]
- [Output 2] : [Description]

### Effets de bord
- [Effet 1] : [Description (ex: écriture DB, appel API)]

### Cas limites (edge cases)
- [Edge case 1] : [Comportement attendu]
- [Edge case 2] : [Comportement attendu]
```

### 2.4 Identification des tests existants

Lister les tests qui couvrent actuellement le code à refactorer :
- `frontend/tests/unit/` - Tests unitaires frontend
- `frontend/tests/e2e/` - Tests E2E
- `backend/tests/unit/` - Tests unitaires backend
- `backend/tests/integration/` - Tests d'intégration

**Si les tests sont insuffisants** :
> ⚠️ **Recommandation** : La couverture de tests actuelle est insuffisante pour garantir une non-régression. Il est recommandé d'ajouter des tests de comportement avant le refactoring.

### 2.5 Vérification des standards de code

Consulter `.clinerules/30-code-standards.md` pour vérifier :
- **Type safety** : Type hints Python / TypeScript strict
- **Clean code** : SOLID, DRY, KISS, YAGNI, SoC
- **Conventions de nommage** : snake_case (Python), camelCase (JS/TS)
- **Gestion d'erreurs** : Exceptions personnalisées, logs structurés

---

## Phase 3 : Choix de la Méthode de Refactoring

### 3.1 Types de refactoring courants

| Type | Description | Quand l'utiliser |
|------|-------------|------------------|
| **Extraction de méthode** | Extraire une partie de code dans une nouvelle méthode | Code dupliqué, méthode trop longue |
| **Extraction de classe** | Créer une nouvelle classe à partir d'une existante | Violation SRP, classe trop grosse |
| **Extraction de module** | Séparer un module en plusieurs | Couplage fort, responsabilités multiples |
| **Renommage** | Changer les noms de variables/fonctions/fichiers | Noms peu explicites |
| **Déplacement** | Déplacer une méthode/classe vers un autre module | Mauvaise localisation |
| **Simplification conditionnelle** | Simplifier les structures conditionnelles | Logique complexe |
| **Introduction de pattern** | Appliquer un pattern de conception | Besoin de flexibilité/extensibilité |
| **Suppression de code mort** | Supprimer le code inutilisé | Code obsolète |

### 3.2 Principes directeurs

Basés sur `.clinerules/30-code-standards.md` :

- **SOLID** :
  - Single Responsibility Principle (SRP)
  - Open/Closed Principle (OCP)
  - Liskov Substitution Principle (LSP)
  - Interface Segregation Principle (ISP)
  - Dependency Inversion Principle (DIP)

- **Autres principes** :
  - **DRY** (Don't Repeat Yourself) : Éliminer la duplication
  - **KISS** (Keep It Simple, Stupid) : Privilégier la simplicité
  - **YAGNI** (You Aren't Gonna Need It) : Ne pas anticiper les besoins futurs
  - **SoC** (Separation of Concerns) : Séparer les responsabilités

### 3.3 Validation de la méthode

Présenter la méthode choisie à l'utilisateur :

```
## Méthode de refactoring proposée

### Approche
[Description de la méthode choisie]

### Justification (principes appliqués)
- [Principe 1] : [Comment il est respecté]
- [Principe 2] : [Comment il est respecté]

### Étapes prévues
1. [Étape 1]
2. [Étape 2]
3. [Étape 3]

### Fichiers impactés
| Fichier | Action | Impact |
|---------|--------|--------|
| [Fichier 1] | [Création/Modification/Suppression] | [Description] |

Confirmez-vous cette approche ? (oui/non/modifications)
```

---

## Phase 4 : Identification des Risques

### 4.1 Mapping des dépendances

Créer un tableau des dépendances :

| Fichier | Type de dépendance | Impact | Risque |
|---------|-------------------|--------|--------|
| Module A | Import direct | Élevé | Appels à vérifier |
| Service B | Injection | Moyen | Interface à maintenir |
| Test C | Test unitaire | Faible | Mise à jour possible |

### 4.2 Identification des risques de régression

Lister les risques potentiels :

```markdown
## Risques de régression identifiés

### Risques élevés
- [ ] Le module X est utilisé par Y composants : vérifier tous les appelants
- [ ] L'interface publique change : assurer la rétrocompatibilité ou versionner

### Risques moyens
- [ ] Le comportement dans les edge cases peut changer : tester explicitement
- [ ] Les performances peuvent être impactées : mesurer avant/après

### Risques faibles
- [ ] Code interne non exposé : refactorer librement
```

### 4.3 Fonctionnalités à vérifier post-implémentation

Identifier les fonctionnalités qui devront être testées après le refactoring :
- Fonctionnalités utilisant directement le module refactoré
- Fonctionnalités avec des flux de données similaires
- Fonctionnalités critiques (auth, déploiements, etc.)

---

## Phase 5 : Création de la Story

### 5.1 Détermination du numéro de story

Lister les fichiers existants dans `.backlog/stories/` pour déterminer le prochain numéro disponible.
- Format : `STORY-XXX` (numérotation séquentielle globale)
- Exemple : si STORY-422 est le dernier, le prochain est STORY-423

### 5.2 Identification de l'epic parent

Chercher l'epic la plus pertinente dans `.backlog/epics/` :
- Si le refactoring concerne une epic existante, l'utiliser
- Sinon, créer une epic "Refactoring technique" ou demander à l'utilisateur

### 5.3 Génération du slug

Créer un slug kebab-case à partir du titre :
- "Refactoring service deployment" → `refactoring-service-deployment`
- "Extraction composant auth" → `extraction-composant-auth`

### 5.4 Création du fichier story

Créer le fichier `.backlog/stories/STORY-XXX-[slug].md` avec la structure suivante :

```markdown
# STORY-XXX : [Titre du refactoring]

**Statut :** TODO
**Epic Parent :** EPIC-XXX — [Titre de l'Epic]
**Type :** Refactoring

## Description
En tant que développeur, je veux [Description du refactoring] afin de [Bénéfice attendu].

### Motivation
[Pourquoi ce refactoring est nécessaire - référence aux principes SOLID/DRY/KISS]

### Comportement à préserver
Ce refactoring ne doit **pas** changer le comportement externe :

**Entrées :**
- [Input 1] : [Description]
- [Input 2] : [Description]

**Sorties :**
- [Output 1] : [Description]

**Effets de bord :**
- [Effet 1] : [Description]

### Méthode choisie
[Description de l'approche de refactoring]

## Critères d'acceptation (AC)
- [ ] AC 1 : Le code refactoré respecte les principes [SOLID/DRY/KISS]
- [ ] AC 2 : Le comportement externe est inchangé
- [ ] AC 3 : Tous les tests existants passent
- [ ] AC 4 : La couverture de tests est maintenue ou améliorée (≥ 80%)
- [ ] AC 5 : Le type checking passe (mypy/tsc strict)
- [ ] AC 6 : Le linting passe sans erreur
- [ ] AC 7 : [Critère spécifique au refactoring]

## État d'avancement technique
- [ ] Analyse du code existant
- [ ] Ajout de tests de comportement (si nécessaire)
- [ ] Implémentation du refactoring
- [ ] Vérification de non-régression
- [ ] Mise à jour de la documentation (si nécessaire)

## Risques de régression

### Fichiers impactés
| Fichier | Impact | Action requise |
|---------|--------|----------------|
| [Fichier 1] | [Description] | [Vérification/Mise à jour] |

### Dépendances à vérifier
- [ ] [Dépendance 1] : Vérifier que [comportement attendu]
- [ ] [Dépendance 2] : Vérifier que [comportement attendu]

### Tests existants à maintenir
- [ ] `[Fichier de test 1]` : Tests liés à [fonctionnalité]
- [ ] `[Fichier de test 2]` : Tests liés à [fonctionnalité]

## Plan de non-régression

### Tests à exécuter avant modification (baseline)
```bash
# Commandes pour capturer l'état initial
[Commande de test backend]
[Commande de test frontend]
[Commande de type checking]
```

### Tests à exécuter après modification
```bash
# Commandes pour vérifier la non-régression
[Commande de test backend]
[Commande de test frontend]
[Commande de build]
[Commande de lint]
[Commande de type checking]
```

### Points de vérification post-implémentation
- [ ] [Vérification 1] : [Description de ce qu'il faut vérifier]
- [ ] [Vérification 2] : [Description de ce qu'il faut vérifier]
- [ ] [Vérification 3] : [Description de ce qu'il faut vérifier]

### Vérifications manuelles (si applicables)
- [ ] [Vérification manuelle 1]
- [ ] [Vérification manuelle 2]
```

---

## Phase 6 : Mise à jour du Backlog

### 6.1 Mise à jour du Kanban

Ajouter la story dans la colonne **📋 BACKLOG** du fichier `.backlog/kanban.md` :

```markdown
### EPIC-XXX : [Titre de l'Epic]
- [ ] STORY-XXX : [Titre de la story de refactoring]
```

### 6.2 Mise à jour de l'epic parent

Ajouter la story dans la section `## Liste des Stories liées` de l'epic parent :

```markdown
- [ ] STORY-XXX : [Titre de la story de refactoring]
```

---

## Résumé de la Skill

### Checklist de fin

Avant de conclure l'exécution de cette skill, vérifier :

- [ ] Le code à refactorer a été clairement identifié
- [ ] La motivation du refactoring est documentée (SOLID/DRY/KISS)
- [ ] Le comportement à préserver est documenté
- [ ] La méthode de refactoring a été choisie et validée
- [ ] Les risques de régression ont été identifiés
- [ ] Le fichier story a été créé avec le template standard
- [ ] La section "Plan de non-régression" est renseignée
- [ ] Les points de vérification post-implémentation sont définis
- [ ] Le Kanban est à jour
- [ ] L'epic parent est à jour

### Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/stories/STORY-XXX-*.md` | Création |
| `.backlog/epics/EPIC-XXX-*.md` | Mise à jour (ajout story) |
| `.backlog/kanban.md` | Mise à jour (ajout dans BACKLOG) |
| Fichiers de code | Lecture seule (analyse) |
| Fichiers de tests | Lecture seule (identification) |

---

## Gestion des Erreurs

| Erreur | Action |
|--------|--------|
| Code non trouvé | Demander des précisions à l'utilisateur |
| Impossible d'identifier l'epic parent | Demander à l'utilisateur de spécifier une epic |
| Numéro de story déjà utilisé | Incrémenter jusqu'au prochain numéro libre |
| Plusieurs méthodes possibles | Présenter les options et demander à l'utilisateur |
| Risques de régression trop élevés | Alerter l'utilisateur et proposer un refactoring incrémental |
| Tests existants insuffisants | Recommander d'ajouter des tests avant le refactoring |
| Comportement mal défini | Demander des clarifications sur les edge cases |

---

## Exemple d'utilisation

**Utilisateur :** "Refactor le service de déploiement pour respecter SRP"

**Actions de la skill :**

1. **Phase 1 - Clarification** :
   - Identifier le service : `backend/app/services/deployment_service.py`
   - Motivation : SRP (Single Responsibility Principle)
   - Type : Extraction de classes

2. **Phase 2 - Analyse** :
   - Explorer `deployment_service.py` (500+ lignes)
   - Identifier les responsabilités : validation, orchestration, notification
   - Lister les dépendances et tests existants
   - Documenter le comportement à préserver

3. **Phase 3 - Choix de la méthode** :
   - Proposer l'extraction en 3 services : `DeploymentValidator`, `DeploymentOrchestrator`, `DeploymentNotifier`
   - Justifier avec SRP
   - Valider avec l'utilisateur

4. **Phase 4 - Risques** :
   - Identifier les appelants du service
   - Identifier les risques de régression
   - Définir les points de vérification

5. **Phase 5 - Création** :
   - Créer `STORY-423-refactoring-deployment-service-srp.md`
   - Inclure le plan de non-régression détaillé

6. **Phase 6 - Backlog** :
   - Ajouter dans le Kanban
   - Lier à l'epic parent

**Résultat :**
```
Story créée : STORY-423 - Refactoring du service de déploiement pour respecter SRP

Méthode choisie : Extraction en 3 services
- DeploymentValidator : Validation des paramètres
- DeploymentOrchestrator : Orchestration du déploiement
- DeploymentNotifier : Gestion des notifications

Fichiers analysés :
- backend/app/services/deployment_service.py
- backend/tests/unit/test_deployment_service.py

Risques de régression identifiés :
- Interface publique à maintenir (rétrocompatibilité)
- 5 appelants directs à vérifier

Plan de non-régression :
- Tests avant : pytest backend/tests/unit/test_deployment_service.py -v
- Tests après : pytest backend/tests/ -v --cov
- Type checking : mypy backend/app/services/
- Build : poetry build

La story est prête dans le backlog. Utilise la skill `treat-story` pour l'implémenter.
