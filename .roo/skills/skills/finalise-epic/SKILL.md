---
name: finalise-epic
description: Vérifie qu'une epic respecte toutes les attentes en terme de qualité, règles de codage, architecture et critères d'acceptation avant clôture
---

# finalise-epic

Cette skill est un **quality gate** en lecture seule : elle audite exhaustivement une epic, ses stories, le code produit et sa conformité aux règles du projet, puis produit un **rapport de conformité** détaillé. Aucune modification de code n'est effectuée.

## Usage

Utilise cette skill quand :
- L'utilisateur demande de "finaliser une epic", "vérifier une epic" ou "valider une epic"
- Toutes (ou la plupart) des stories d'une epic sont DONE et on veut un quality gate
- L'utilisateur veut un bilan qualité avant de lancer `close-epic`
- L'utilisateur mentionne "quality gate", "review epic", "audit epic", "conformité epic"

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le dossier `.backlog/epics/` existe et contient au moins une epic
- [ ] Le dossier `.backlog/stories/` existe
- [ ] Le fichier `.backlog/kanban.md` existe
- [ ] Au moins une story de l'epic ciblée est à `DONE`
- [ ] L'environnement de développement est opérationnel (pour les commandes de vérification build/lint/tests)

---

## Phase 1 : Collecte des données

### 1.1 Sélection de l'epic

Si l'utilisateur n'a pas spécifié d'epic, lister les fichiers dans `.backlog/epics/` et proposer les epics disponibles :

```
Quelle epic souhaitez-vous finaliser ?

Epics disponibles :
- EPIC-XXX : [Titre] ([statut]) — [N] stories
- EPIC-YYY : [Titre] ([statut]) — [N] stories
...

Indiquez le numéro de l'epic (ex: EPIC-009) ou son titre.
```

### 1.2 Lecture de l'epic

Lire le fichier epic sélectionné et extraire :
- **Titre, statut, priorité**
- **Vision et Description** (contexte fonctionnel)
- **Liste des Stories liées** (numéros et titres)
- **Critères de succès (Definition of Done)** de l'epic
- **Notes de conception** (contraintes techniques, références)

### 1.3 Lecture de toutes les stories

Pour **chaque story** référencée dans l'epic :
1. Trouver le fichier correspondant dans `.backlog/stories/` (pattern : `STORY-XXX-*.md`)
2. Si le fichier n'existe pas → signaler comme **anomalie**
3. Lire le fichier story et extraire :
   - **Statut**
   - **Tous les critères d'acceptation (AC)** et leur état (coché `[x]` / non coché `[ ]`)
   - **État d'avancement technique** (tâches cochées / non cochées)
   - **Section "Notes d'implémentation"** (présente/absente, fichiers listés)
   - **Section "Sous-stories"** (si présente → lire aussi les sous-stories)
   - **Section "Tests à écrire"** (présente/absente)
   - **Section "Tâches d'implémentation détaillées"** (présente/absente)

### 1.4 Lecture du kanban

Lire `.backlog/kanban.md` et vérifier la présence et le positionnement de chaque story.

### 1.5 Inventaire des fichiers de code

À partir des sections "Notes d'implémentation" de chaque story, compiler la liste de **tous les fichiers modifiés/créés** par l'epic. Vérifier l'existence de chaque fichier sur disque.

---

## Phase 2 : Rapport détaillé par story

Pour **chaque story** de l'epic, produire un rapport individuel complet :

### 2.1 Vérification des critères d'acceptation (AC)

Pour chaque AC de la story :
- Si `[x]` → ✅ Validé
- Si `[ ]` → ❌ Non validé — **anomalie critique**
- Si l'AC n'est pas coché mais que le code semble l'implémenter → ⚠️ AC probablement valide mais case non cochée — **anomalie mineure**

### 2.2 Vérification des tâches d'implémentation

Pour chaque tâche dans "État d'avancement technique" :
- Si `[x]` → ✅ Complétée
- Si `[ ]` → ❌ Incomplète — **anomalie critique**

Si la section "Tâches d'implémentation détaillées" est absente → ⚠️ Story non analysée par `analyse-story`

### 2.3 Vérification des livrables (fichiers)

Pour chaque fichier listé dans "Notes d'implémentation" :
- Si le fichier existe → ✅
- Si le fichier n'existe pas → ❌ Fichier manquant — **anomalie majeure**

Si la section "Notes d'implémentation" est absente → ❌ **anomalie majeure**

### 2.4 Vérification des sous-stories (si applicable)

Si la story contient une section `## Sous-stories` :
- Vérifier que chaque sous-story est à `DONE`
- Vérifier que les AC couverts par chaque sous-story sont cochés dans la story parente
- Signaler toute sous-story non terminée

### 2.5 Format du rapport par story

```
### STORY-XXX : [Titre de la Story]

**Statut :** [DONE/REVIEW/IN_PROGRESS/TODO/BLOCKED]
**Conformité :** ✅ CONFORME / ⚠️ MINEUR / ❌ NON CONFORME

#### Critères d'acceptation ([N validés]/[N total])
- [✅/❌/⚠️] AC 1 : [Description]
- [✅/❌/⚠️] AC 2 : [Description]
...

#### Tâches d'implémentation ([N complétées]/[N total])
- [✅/❌] Tâche 1 : [Description]
- [✅/❌] Tâche 2 : [Description]
...

#### Livrables (fichiers)
- [✅/❌] `chemin/fichier1.py` — [Description]
- [✅/❌] `chemin/fichier2.vue` — [Description]
...

#### Tests & Couverture
- [✅/❌/⚠️] Fichiers de test : [présents/absents]
- [✅/⚠️] Couverture : [XX%] (seuil : ≥ 80%)

#### Documentation
- [✅/❌] Section "Notes d'implémentation" : [présente/absente]
- [✅/❌] Section "Tâches d'implémentation détaillées" : [présente/absente]
- [✅/❌] Section "Tests à écrire" : [présente/absente]

#### Anomalies détectées
- [❌/⚠️] [Description de chaque anomalie]
```

### 2.6 Tableau récapitulatif des anomalies par story

Après le rapport individuel de chaque story, produire un tableau synthétique :

```
### Résumé des anomalies par story

| Story | Statut | AC | Tâches | Fichiers | Tests | Notes impl. | Conformité |
|-------|--------|----|--------|----------|-------|-------------|------------|
| STORY-024 | DONE | 8/8 ✅ | 5/5 ✅ | ✅ | ✅ 100% | ✅ | ✅ CONFORME |
| STORY-025 | DONE | 5/6 ⚠️ | 4/4 ✅ | ✅ | ⚠️ 72% | ✅ | ⚠️ MINEUR |
| STORY-026 | REVIEW | 6/7 ❌ | 3/4 ❌ | ❌ 1 absent | ✅ | ❌ Absente | ❌ NON CONFORME |
...
```

---

## Phase 3 : Vérification des critères d'acceptation de l'epic

Lire les **Critères de succès (Definition of Done)** de l'epic. Pour chaque critère, **vérifier dans le code** que la promesse est tenue :

### 3.1 Vérification par analyse de code

Pour chaque critère de l'epic, identifier la vérification appropriée :

| Type de critère | Méthode de vérification |
|-----------------|------------------------|
| "Pas de `dict[str, Any]`" | `grep -r "dict\[str, Any\]"` sur les fichiers backend concernés |
| "Schémas typés / Pydantic" | Vérifier les modèles Pydantic dans les fichiers schema |
| "Structure des onglets correspond à la maquette" | Lire le composant Vue et comparer avec `doc/general_specs/11-UI-mockups.md` |
| "Actions disponibles" | Vérifier la présence des boutons/actions dans les composants frontend |
| "Health checks visibles" | Vérifier le composant d'affichage du health check |
| "Limite ressources affichées" | Vérifier la présence des champs dans le composant |
| "API documentée (OpenAPI)" | Vérifier les docstrings et descriptions Pydantic |
| "Pas de régression" | Exécuter les tests existants |

### 3.2 Format du rapport par critère

```
#### Critères de succès de l'epic ([N validés]/[N total])

- ✅ Critère 1 : "Toutes les informations Docker inspect pertinentes sont affichées"
  → Vérification : analyse de `ContainerDetail.vue` + sous-composants
  → Résultat : champs présents dans les composants État, Config, Aperçu

- ❌ Critère 5 : "Les schémas backend sont typés (pas de dict[str, Any])"
  → Vérification : `grep -r "dict\[str, Any\]" backend/app/schemas/docker.py`
  → Résultat : 2 occurrences trouvées dans `ContainerHostConfigInfo`
  → Action corrective : typer les champs restants

- ⚠️ Critère 8 : "Les erreurs d'état sont visibles"
  → Vérification : composant `ContainerStateTab.vue`
  → Résultat : ExitCode et Error affichés, mais OOMKilled absent de la vue
  → Action corrective : ajouter l'affichage de OOMKilled
```

---

## Phase 4 : Vérification Code Quality (exécution)

Lancer les commandes de vérification et reporter les résultats.

### 4.1 Build

```bash
# Backend
cd backend && poetry build 2>&1

# Frontend
cd frontend && pnpm build 2>&1
```

### 4.2 Lint

```bash
# Backend
cd backend && ruff check . 2>&1   # ou flake8 / pylint selon configuration

# Frontend
cd frontend && pnpm lint 2>&1
```

### 4.3 Type checking

```bash
# Backend
mypy backend/ 2>&1

# Frontend
cd frontend && pnpm typecheck 2>&1
```

### 4.4 Tests

```bash
# Backend
cd backend && poetry run pytest tests/ -v --tb=short 2>&1

# Frontend
cd frontend && pnpm test 2>&1
```

### 4.5 Couverture

```bash
# Backend (fichiers concernés par l'epic)
cd backend && poetry run pytest tests/ --cov=app/schemas/docker --cov=app/api/v1/docker --cov-report=term-missing 2>&1

# Frontend (fichiers concernés par l'epic)
cd frontend && pnpm test:coverage 2>&1
```

**Seuils de couverture** (référence `.clinerules/35-testing-quality-gates.md`) :
- Minimum : 80% pour tout nouveau composant
- Backend : 85%+
- Frontend : 80%+
- Chemins critiques : 95% si raisonnable

### 4.6 Format du rapport Code Quality

```
### Code Quality

| Vérification | Backend | Frontend |
|-------------|---------|----------|
| Build | ✅ Succès | ✅ Succès |
| Lint | ✅ 0 erreurs | ❌ 2 erreurs (eslint) |
| Type Check | ✅ mypy clean | ✅ tsc clean |
| Tests | ✅ 142/142 passants | ✅ 38/38 passants |
| Couverture | ✅ 94% | ⚠️ 76% (seuil 80%) |
```

Si des commandes échouent, reporter les erreurs détaillées et les actions correctives proposées.

---

## Phase 5 : Vérification Architecture & Standards

Vérification par analyse du code produit, basée sur les règles `.clinerules/`.

### 5.1 API-first (`.clinerules/20-architecture-and-api.md`)

- [ ] Endpoints documentés avec OpenAPI (docstrings, descriptions, examples)
- [ ] Schémas Pydantic utilisés pour toutes les requêtes/réponses
- [ ] Pagination présente pour les listes > 20 éléments (si applicable)
- [ ] Pas de logique métier dans les routes (déléguée aux services)

### 5.2 Type safety (`.clinerules/30-code-standards.md`)

- [ ] Python : type hints complets sur tout ce qui est public
- [ ] TypeScript : pas de `any` (sauf exception justifiée)
- [ ] Pas de `dict[str, Any]` non justifié dans les schémas backend

### 5.3 Conventions de nommage (`.clinerules/30-code-standards.md`)

- [ ] Python : snake_case (fonctions, variables, modules), UPPER_SNAKE_CASE (constantes)
- [ ] Frontend : fichiers kebab-case, TS/JS camelCase, composants PascalCase
- [ ] DB : snake_case + UUID PK + created_at/updated_at (si applicable)

### 5.4 Clean code (`.clinerules/30-code-standards.md`)

- [ ] Fonctions courtes (~30 lignes max)
- [ ] Noms explicites
- [ ] Pas de duplication évidente

### 5.5 Sécurité (`.clinerules/40-security.md`)

- [ ] Pas de secrets en dur dans le code
- [ ] Validation inputs côté serveur (Pydantic)
- [ ] Pas de données sensibles dans les logs

### 5.6 Observabilité (`.clinerules/45-observability.md`)

- [ ] Logs structurés (JSON) pour les nouveaux services/routes
- [ ] Pas de données sensibles dans les logs
- [ ] Correlation IDs si applicable

### 5.7 Format du rapport Architecture & Standards

```
### Architecture & Standards

| Catégorie | Statut | Détails |
|-----------|--------|---------|
| API-first | ✅ CONFORME | Endpoints documentés, schémas Pydantic |
| Type safety | ⚠️ MINEUR | 1 `any` dans `helpers.ts` ligne 42 |
| Conventions nommage | ✅ CONFORME | snake_case Python, camelCase TS |
| Clean code | ✅ CONFORME | Fonctions < 30 lignes |
| Sécurité | ✅ CONFORME | Pas de secrets en dur |
| Observabilité | ✅ CONFORME | Logs structurés |
```

---

## Phase 6 : Rapport de finalisation consolidé

### 6.1 Synthèse globale

Assembler les résultats des phases 1 à 5 en un rapport final structuré :

```
================================================================================
  📋 RAPPORT DE FINALISATION — EPIC-XXX : [Titre de l'Epic]
================================================================================

**Date :** [Date du rapport]
**Statut epic :** [IN_PROGRESS/DONE]
**Stories totales :** [N] (DONE: [N], REVIEW: [N], IN_PROGRESS: [N], TODO: [N], ABANDONED: [N])

================================================================================
  PHASE 1 : COHÉRENCE BACKLOG & DOCUMENTATION
================================================================================

[Vérification kanban, epic, statuts, synchronisation]

Statut : ✅ CONFORME / ❌ NON CONFORME

================================================================================
  PHASE 2 : RAPPORT DÉTAILLÉ PAR STORY
================================================================================

### STORY-024 : [Titre] — [Statut]
[Rapport détaillé]

### STORY-025 : [Titre] — [Statut]
[Rapport détaillé]

...

### Résumé des anomalies par story
[Tableau récapitulatif]

================================================================================
  PHASE 3 : CRITÈRES D'ACCEPTATION DE L'EPIC
================================================================================

[Critère par critère avec vérification code]

Statut : ✅ [N]/[N] critères validés

================================================================================
  PHASE 4 : CODE QUALITY
================================================================================

[Build, Lint, TypeCheck, Tests, Couverture]

Statut : ✅ CONFORME / ❌ NON CONFORME

================================================================================
  PHASE 5 : ARCHITECTURE & STANDARDS
================================================================================

[Vérification par catégorie]

Statut : ✅ CONFORME / ⚠️ MINEUR / ❌ NON CONFORME

================================================================================
  VERDICT GLOBAL
================================================================================

  [✅ EPIC PRÊTE POUR CLÔTURE] / [❌ CORRECTIONS NÉCESSAIRES]

  Score de conformité : [N]% ([N] vérifications passées / [N] total)

  Anomalies critiques : [N]    (bloquantes pour la clôture)
  Anomalies mineures : [N]     (non bloquantes mais à adresser)
  Avertissements : [N]         (suggestions d'amélioration)

================================================================================
  ACTIONS CORRECTIVES (si non conforme)
================================================================================

  🔴 [Bloquant] STORY-026 — AC 3 non validé : [description]
     → Action : [correction proposée]
     → Fichier : [chemin/fichier]

  🟡 [Mineur] STORY-025 — Couverture tests 72% < 80%
     → Action : Ajouter des tests sur [fichiers concernés]

  🟢 [Suggestion] Frontend — 1 `any` dans helpers.ts
     → Action : Typer explicitement le paramètre

================================================================================
  PROCHAINE ÉTAPE
================================================================================

  Si ✅ CONFORME :
    → Lancer `close-epic` pour clôturer l'epic
    → Commande : "Ferme l'epic EPIC-XXX"

  Si ❌ NON CONFORME :
    → Corriger les anomalies critiques listées ci-dessus
    → Re-lancer `finalise-epic` après corrections
================================================================================
```

### 6.2 Écriture du rapport dans l'epic

Ajouter le rapport de finalisation dans le fichier epic, dans une section dédiée :

```markdown
## Rapport de finalisation

**Date :** [Date]
**Verdict :** ✅ CONFORME / ❌ NON CONFORME
**Score :** [N]%

### Résumé
- Stories vérifiées : [N]
- Anomalies critiques : [N]
- Anomalies mineures : [N]
- Critères epic validés : [N]/[N]
- Code quality : ✅/❌

### Détail
[Résumé condensé du rapport]
```

---

## Règles de la skill

### Lecture seule
- Cette skill **ne modifie aucun fichier de code**
- Elle peut uniquement :
  - Mettre à jour le fichier epic avec le rapport de finalisation
  - Mettre à jour le kanban si des incohérences mineures sont détectées (après confirmation utilisateur)

### Non-bloquante
- Si une commande de vérification échoue (ex: environnement non configuré), continuer les autres vérifications et signaler l'échec
- Ne jamais abandonner l'audit complet pour une erreur ponctuelle

### Progressivité
- Les vérifications sont ordonnées de la plus rapide (lecture fichiers) à la plus coûteuse (exécution tests)
- L'utilisateur peut demander d'arrêter le rapport à n'importe quelle phase

---

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Epic non trouvée | Demander un numéro valide |
| Aucune story DONE | Informer l'utilisateur — rapport limité |
| Story file manquant | Signaler l'anomalie, continuer avec les autres stories |
| Commande build/lint/test échouée | Reporter l'erreur, continuer les autres vérifications |
| Environnement non configuré | Sauter la Phase 4 (Code Quality), signaler l'absence |
| Fichier de code manquant | Signaler dans le rapport par story |

---

## Exemple d'utilisation

**Utilisateur :** "Finalise l'epic EPIC-009"

**Actions de la skill :**

1. **Phase 1 — Collecte :**
   - Lire EPIC-009 → 6 stories (STORY-024 à STORY-029)
   - Lire les 6 fichiers stories
   - Lire le kanban
   - Compiler l'inventaire des fichiers de code

2. **Phase 2 — Rapport par story :**
   - STORY-024 : DONE, 8/8 AC, 5/5 tâches, fichiers OK, 100% couverture → ✅
   - STORY-025 : DONE, 6/6 AC, 4/4 tâches, fichiers OK, 88% couverture → ✅
   - STORY-026 : REVIEW, 6/7 AC ❌, 3/4 tâches ❌, 1 fichier manquant → ❌
   - STORY-027 : DONE, 5/5 AC, 3/3 tâches, fichiers OK → ✅
   - STORY-028 : TODO → ⚠️ non commencé
   - STORY-029 : DONE, 4/4 AC, 2/2 tâches → ✅
   - Tableau récapitulatif des anomalies

3. **Phase 3 — Critères epic :**
   - 7/10 critères validés
   - 3 critères non validés (liés à STORY-026 et STORY-028 incomplètes)

4. **Phase 4 — Code Quality :**
   - Build ✅, Lint ✅, TypeCheck ✅, Tests ✅, Couverture ✅

5. **Phase 5 — Architecture :**
   - API-first ✅, Type safety ✅, Conventions ✅, Sécurité ✅

6. **Phase 6 — Verdict :**
   - ❌ CORRECTIONS NÉCESSAIRES
   - 2 anomalies critiques (STORY-026 incomplète, STORY-028 non commencée)
   - Action : traiter STORY-026, puis STORY-028, puis re-lancer finalise-epic

---

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/epics/EPIC-XXX-*.md` | Lecture + Ajout rapport de finalisation |
| `.backlog/stories/STORY-XXX-*.md` | Lecture seule (audit) |
| `.backlog/kanban.md` | Lecture seule (audit) |
| Fichiers de code (backend + frontend) | Lecture seule (vérification conformité) |
| Fichiers de tests | Lecture seule + exécution |
