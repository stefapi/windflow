---
name: finalise-story
description: Finalise une story en vérifiant que toutes les tâches sont complètes, que les tests sont écrits et passent, qu'il ne manque rien, puis applique le workflow de clôture du backlog
---

# finalise-story

Cette skill est un **quality gate au niveau story** : elle vérifie exhaustivement qu'une story est réellement terminée (tâches, AC, tests, livrables, oublis) avant d'appliquer le workflow de clôture (passage à DONE, mise à jour kanban + epic).

Elle se positionne **après `treat-story` et avant `finalise-epic`** dans le pipeline de développement.

## Positionnement dans le pipeline

```
analyse-story → treat-story → [finalise-story] → finalise-epic → close-epic
```

## Usage

Utilise cette skill quand :
- L'utilisateur demande de "finaliser une story", "clôturer une story" ou "valider une story"
- L'implémentation d'une story est terminée et on veut s'assurer qu'il ne manque rien avant DONE
- L'utilisateur veut vérifier qu'une story est vraiment prête à être fermée
- L'utilisateur mentionne "quality gate story", "valider les tests", "finaliser STORY-XXX"

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le fichier story existe dans `.backlog/stories/`
- [ ] La story est à l'état `REVIEW` ou `IN_PROGRESS` (pas encore DONE)
- [ ] La section `## Tâches d'implémentation détaillées` est présente (analyse-story a été lancé)
- [ ] L'environnement de développement est opérationnel (pour lancer les tests)

---

## Phase 1 : Lecture et sélection de la story

### 1.1 Sélection de la story

Si l'utilisateur n'a pas spécifié de story, lister les stories disponibles dans `.backlog/stories/` avec statut `REVIEW` ou `IN_PROGRESS` :

```
Quelle story souhaitez-vous finaliser ?

Stories en cours ou en review :
- STORY-XXX : [Titre] (REVIEW) (EPIC-YYY)
- STORY-XXX : [Titre] (IN_PROGRESS) (EPIC-YYY)
...
```

### 1.2 Lecture de la story

Lire le fichier `.backlog/stories/STORY-XXX-*.md` et extraire :
- **Titre, numéro, statut, epic parent**
- **Critères d'acceptation (AC)** et leur état coché/non coché
- **Section `## Tâches d'implémentation détaillées`** — tâches avec objectifs et fichiers
- **Section `## Tests à écrire`** — fichiers et cas de test décrits
- **Section `## État d'avancement technique`** — cases cochées/non cochées
- **Section `## Notes d'implémentation`** — présente/absente, fichiers listés
- **Section `## Sous-stories`** — présente/absente

### 1.3 Cas sous-stories

Si la story contient une section `## Sous-stories` :
1. Lire chaque fichier sous-story listée dans `.backlog/stories/STORY-XXX.N-*.md`
2. Vérifier le statut de chaque sous-story
3. Appliquer les vérifications des phases 2 à 4 à chaque sous-story individuellement
4. La story parente est DONE seulement quand **toutes** les sous-stories sont DONE

---

## Phase 2 : Vérification de la complétude de la story

### 2.1 Tâches d'implémentation

Pour chaque item dans `## État d'avancement technique` :
- `[x]` → ✅ Complété
- `[ ]` → ❌ **Bloquant** — tâche non terminée

Si des tâches sont incomplètes, les lister explicitement et interrompre la clôture.

### 2.2 Critères d'acceptation (AC)

Pour chaque AC de la story :
- `[x]` → ✅ Validé
- `[ ]` → ❌ **Bloquant** — AC non validé

> Si un AC n'est pas coché mais que le code l'implémente visiblement (vérification rapide), le signaler comme ⚠️ **mineur** (oubli de coche probable).

### 2.3 Notes d'implémentation

Vérifier que la section `## Notes d'implémentation` est présente :
- Présente → ✅
- Absente → ❌ **Bloquant** — section obligatoire à la clôture (cf. `.clinerules/01-Project-management.md` §5.4)

### 2.4 Rapport Phase 2

```
### Phase 2 : Complétude de la story

**Tâches d'implémentation :** [N cochées] / [N total]
- [✅/❌] Tâche 1 : [Titre]
- [✅/❌] Tâche 2 : [Titre]
...

**Critères d'acceptation :** [N validés] / [N total]
- [✅/❌/⚠️] AC 1 : [Description]
- [✅/❌/⚠️] AC 2 : [Description]
...

**Notes d'implémentation :** [✅ Présente / ❌ Absente]

**Statut Phase 2 :** ✅ CONFORME / ❌ NON CONFORME ([N] bloquants)
```

---

## Phase 3 : Vérification des tests

### 3.1 Existence des fichiers de test

À partir de la section `## Tests à écrire` de la story, vérifier que chaque fichier de test listé existe sur disque :
- Si le fichier existe → ✅
- Si le fichier est absent → ❌ **Bloquant** — test non écrit

### 3.2 Exécution des tests

Lancer les tests ciblés sur les fichiers de la story.

**Si des commandes de test sont précisées dans la story**, les utiliser en priorité.

**Sinon, utiliser les commandes standards :**

```bash
# Backend — tests unitaires ciblés
poetry run pytest [fichiers de test listés dans la story] -v --tb=short 2>&1

# Backend — tests d'intégration (si mentionnés dans la story)
poetry run pytest backend/tests/integration/ -v --tb=short 2>&1

# Frontend — tests unitaires ciblés
cd frontend && pnpm test [fichier.spec.ts] 2>&1

# Frontend — tests E2E (si mentionnés dans la story)
cd frontend && pnpm test:e2e 2>&1
```

**Résultat attendu :** ✅ tous les tests passent, 0 échec.

Si des tests échouent → ❌ **Bloquant** — reporter les erreurs avec le message exact.

### 3.3 Couverture de code

Lancer la mesure de couverture sur les fichiers produits par la story :

```bash
# Backend — couverture ciblée sur les fichiers de la story
poetry run pytest [fichiers de test] \
  --cov=[module1] --cov=[module2] \
  --cov-report=term-missing 2>&1

# Frontend — couverture globale
cd frontend && pnpm test:coverage 2>&1
```

**Seuils de couverture** (référence `.clinerules/35-testing-quality-gates.md`) :
- Backend : ≥ 85%
- Frontend : ≥ 80%
- Chemins critiques : ≥ 95% si raisonnable

Si couverture insuffisante → ⚠️ **Mineur** (non bloquant mais à signaler).

### 3.4 Rapport Phase 3

```
### Phase 3 : Tests

**Fichiers de test listés dans la story :**
- [✅/❌] `tests/unit/test_xxx.py` — [présent/absent]
- [✅/❌] `tests/xxx.spec.ts` — [présent/absent]

**Exécution des tests :**
- Tests unitaires backend : [✅ N/N passants / ❌ N échecs]
- Tests intégration : [✅ N/N passants / ❌ N échecs / ➖ non applicable]
- Tests E2E : [✅ N/N passants / ❌ N échecs / ➖ non applicable]
- Tests unitaires frontend : [✅ N/N passants / ❌ N échecs / ➖ non applicable]

**Couverture :**
- Backend : [XX%] (seuil ≥ 85%) → [✅/⚠️]
- Frontend : [XX%] (seuil ≥ 80%) → [✅/⚠️]

**Statut Phase 3 :** ✅ CONFORME / ❌ NON CONFORME ([N] bloquants)
```

---

## Phase 4 : Build, Lint & Typecheck

### 4.1 Build

```bash
# Backend (si story backend)
cd backend && poetry build 2>&1

# Frontend (si story frontend)
cd frontend && pnpm build 2>&1
```

### 4.2 Lint

```bash
# Backend
cd backend && ruff check . 2>&1   # ou flake8 selon la config

# Frontend
cd frontend && pnpm lint 2>&1
```

### 4.3 Typecheck

```bash
# Backend
mypy backend/ 2>&1

# Frontend
cd frontend && pnpm typecheck 2>&1
```

Toutes les commandes doivent passer sans erreur/avertissement bloquant.

### 4.4 Rapport Phase 4

```
### Phase 4 : Build, Lint & Typecheck

| Vérification    | Backend       | Frontend      |
|-----------------|---------------|---------------|
| Build           | [✅/❌]         | [✅/❌/➖]     |
| Lint            | [✅/❌ N err.] | [✅/❌ N err.] |
| Typecheck       | [✅/❌]         | [✅/❌]         |

**Statut Phase 4 :** ✅ CONFORME / ❌ NON CONFORME
```

---

## Phase 5 : Vérification des oublis

### 5.1 Existence des fichiers sur disque

À partir de la section `## Notes d'implémentation` (liste "Fichiers modifiés/créés"), vérifier que chaque fichier existe sur disque :
- Si le fichier existe → ✅
- Si le fichier est absent → ❌ **Bloquant** — fichier annoncé mais non créé

### 5.2 Détection des TODO/FIXME dans le code

Rechercher des marqueurs de code incomplet dans les fichiers produits par la story :

```bash
# Recherche dans les fichiers backend
grep -rn "TODO\|FIXME\|HACK\|XXX\|NotImplementedError" [fichiers backend de la story] 2>&1

# Recherche dans les fichiers frontend
grep -rn "TODO\|FIXME\|console\.log\|debugger" [fichiers frontend de la story] 2>&1
```

- `TODO` / `FIXME` laissés → ⚠️ **Mineur** — signaler avec emplacement exact
- `console.log` / `debugger` en frontend → ⚠️ **Mineur** — artefacts de debugging à supprimer

### 5.3 Cohérence backlog

Vérifier :
- La story est bien dans la bonne colonne du kanban (`REVIEW` → colonne `🚧 REVIEW`)
- Le statut dans le fichier story correspond à l'état réel
- Les AC cochés dans la story correspondent aux AC de la story dans l'epic parent

### 5.4 Rapport Phase 5

```
### Phase 5 : Oublis & cohérence

**Fichiers sur disque :**
- [✅/❌] `chemin/fichier1.py` → [présent/absent]
- [✅/❌] `chemin/fichier2.vue` → [présent/absent]

**Code incomplet (TODO/FIXME) :**
- [✅ Aucun / ⚠️ N marqueurs trouvés]
  - `fichier.py:42` — TODO: [message]
  - `composant.vue:88` — console.log(...)

**Cohérence backlog :**
- Kanban : [✅ story dans bonne colonne / ❌ mauvaise colonne]
- Statut story : [✅ cohérent / ❌ incohérent]

**Statut Phase 5 :** ✅ CONFORME / ⚠️ MINEUR / ❌ NON CONFORME
```

---

## Phase 6 : Verdict et workflow de clôture

### 6.1 Rapport consolidé

Assembler les résultats des phases 2 à 5 :

```
================================================================================
  ✅/❌ RAPPORT DE FINALISATION — STORY-XXX : [Titre]
================================================================================

**Date :** [Date]
**Epic :** EPIC-XXX — [Titre]

| Phase                   | Statut              | Bloquants |
|-------------------------|---------------------|-----------|
| Phase 2 : Complétude    | ✅/❌               | [N]       |
| Phase 3 : Tests         | ✅/❌               | [N]       |
| Phase 4 : Build/Lint    | ✅/❌               | [N]       |
| Phase 5 : Oublis        | ✅/⚠️/❌           | [N]       |

**Anomalies critiques (bloquantes) :** [N]
**Anomalies mineures (non bloquantes) :** [N]

================================================================================
  VERDICT : [✅ STORY PRÊTE POUR CLÔTURE] / [❌ CORRECTIONS NÉCESSAIRES]
================================================================================
```

### 6.2 Cas ✅ CONFORME — Clôture de la story

Si toutes les phases passent (0 bloquant) :

**Appliquer le workflow de clôture :**

1. **Dans le fichier story** — passer le statut à `DONE` :
   ```markdown
   **Statut :** DONE
   ```

2. **Dans le Kanban** (`.backlog/kanban.md`) :
   - Déplacer la story vers la colonne `✅ DONE`
   - Marqueur `- [x]`

3. **Dans l'epic parent** (`.backlog/epics/EPIC-XXX-*.md`) :
   - Cocher la story dans `## Liste des Stories liées` :
     ```markdown
     - [x] STORY-XXX : [Titre]
     ```
   - Si **toutes** les stories de l'epic sont maintenant DONE → mettre le statut epic à `DONE`

4. **Confirmer à l'utilisateur :**
   ```
   ✅ STORY-XXX clôturée avec succès.

   Fichiers mis à jour :
   - .backlog/stories/STORY-XXX-*.md → DONE
   - .backlog/kanban.md → déplacée en ✅ DONE
   - .backlog/epics/EPIC-XXX-*.md → story cochée [x]

   Prochaine étape : implémenter STORY-YYY ou lancer `finalise-epic` si toutes les stories sont terminées.
   ```

### 6.3 Cas ❌ NON CONFORME — Blocage et actions correctives

Si des anomalies critiques sont détectées, **ne pas passer à DONE** mais lister les actions à effectuer :

```
❌ STORY-XXX non clôturée — corrections nécessaires :

🔴 [Bloquant] Tâche 3 non cochée : "[Titre de la tâche]"
   → Vérifier l'implémentation dans [fichier concerné]

🔴 [Bloquant] AC 4 non validé : "[Description de l'AC]"
   → Implémenter ou cocher si l'implémentation est présente

🔴 [Bloquant] Tests unitaires échouent : 2 erreurs
   → [Message d'erreur exact]
   → Fichier : [chemin/test.py] ligne [N]

🟡 [Mineur] Couverture backend 72% < 85%
   → Ajouter des tests sur [modules concernés]

🟡 [Mineur] TODO laissé dans [fichier.py:42]
   → Supprimer ou compléter

Une fois corrigé, relancer `finalise-story` sur STORY-XXX.
```

Mettre la story à `REVIEW` (ou la laisser à `IN_PROGRESS` si corrections majeures).

---

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Story non trouvée | Demander un numéro valide |
| Story déjà DONE | Informer l'utilisateur, demander confirmation si re-run voulu |
| Story à TODO (jamais commencée) | Informer — cette skill s'applique après treat-story |
| Section "Tâches" absente | Signaler — lancer `analyse-story` d'abord |
| Environnement de test non opérationnel | Sauter la Phase 3/4, signaler et lister les commandes manuelles |
| Commande de test échouée | Reporter l'erreur exacte, continuer les autres phases |
| Pas de section "Tests à écrire" | Avertir (mode dégradé), détecter quand même les fichiers de test existants |

---

## Checklist de fin

Avant de conclure l'exécution de cette skill, vérifier que les conditions suivantes sont remplies pour une clôture réussie :

- [ ] Toutes les tâches d'implémentation sont cochées dans "État d'avancement technique"
- [ ] Tous les AC sont cochés dans le fichier story
- [ ] La section "Notes d'implémentation" est présente
- [ ] Tous les fichiers de test listés dans "Tests à écrire" existent sur disque
- [ ] Les tests unitaires passent (0 échec)
- [ ] Les tests d'intégration passent (si applicable)
- [ ] Les tests E2E passent (si applicables)
- [ ] Couverture backend ≥ 85% (ou justification)
- [ ] Couverture frontend ≥ 80% (ou justification)
- [ ] Build passe sans erreur (backend et/ou frontend)
- [ ] Lint passe sans erreur ou avertissement bloquant
- [ ] Typecheck passe sans erreur
- [ ] Aucun TODO/FIXME non intentionnel dans les fichiers produits
- [ ] Aucun `console.log` / `debugger` oublié dans le code frontend
- [ ] Tous les fichiers annoncés dans "Notes d'implémentation" existent sur disque
- [ ] Si ✅ : statut story → DONE, kanban mis à jour, epic parent mis à jour

---

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/stories/STORY-XXX-*.md` | Lecture (audit) + Mise à jour statut → DONE si conforme |
| `.backlog/epics/EPIC-XXX-*.md` | Lecture + Cocher la story si DONE |
| `.backlog/kanban.md` | Mise à jour colonne (REVIEW → DONE si conforme) |
| Fichiers de code (backend + frontend) | Lecture seule (vérification oublis) |
| Fichiers de tests | Vérification existence + exécution |
