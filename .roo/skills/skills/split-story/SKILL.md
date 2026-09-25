---
name: split-story
description: Découpe une story en sous-stories. Deux modes — réactif (story IN_PROGRESS/BLOCKED après des échecs d'implémentation) ou proactif (story TODO détectée trop complexe par analyse-story avant toute implémentation). Utilise cette skill quand une story est trop complexe, bloquée, ou déléguée par analyse-story.
---

# split-story

Cette skill **découpe une story existante en sous-stories**. Elle opère dans deux modes complémentaires :

- **Mode réactif** : la story est `IN_PROGRESS` ou `BLOCKED` — l'implémentation a échoué ou bloqué.
- **Mode proactif** : la story est `TODO` — `analyse-story` a détecté une complexité trop élevée (>5 tâches, >6 fichiers, full-stack, >8 AC) et délègue la découpe avant toute implémentation.

**Aucun code n'est écrit.** Seuls les fichiers du backlog sont modifiés.

## Positionnement dans le pipeline

```
# Chemin réactif (échec d'implémentation)
analyse-story → treat-story → [split-story si échec] → treat-story (sous-stories) → finalise-story → finalise-epic → close-epic

# Chemin proactif (complexité détectée à l'analyse)
analyse-story → [split-story] → treat-story (sous-stories) → finalise-story → finalise-epic → close-epic
```

## Usage

Utilise cette skill quand :
- L'utilisateur signale qu'une story échoue à l'implémentation (après plusieurs tentatives)
- L'utilisateur demande de "découper" ou "splitter" une story qui est trop complexe
- Le modèle IA a échoué 2+ fois sur des tâches d'une story `IN_PROGRESS` ou `BLOCKED`
- L'utilisateur mentionne "split story", "découper story", "story trop grosse", "story bloquée"
- L'utilisateur ou `analyse-story` signale qu'une story est trop complexe pour être traitée en une seule session
- Le modèle IA détecte lors de l'analyse qu'une story dépasse les seuils de complexité (>5 tâches, >6 fichiers, full-stack, >8 AC)

## Quand NE PAS utiliser cette skill

- **Pour implémenter** une story → utiliser `treat-story`
- **Pour finaliser** une story → utiliser `finalise-story`
- **Pour créer** une story depuis zéro → utiliser `create-epic` puis `create-stories`
- **Pour analyser** une story non encore analysée → utiliser `analyse-story` d'abord (sauf si la story est en mode proactif avec tâches déjà détaillées)

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le fichier story existe dans `.backlog/stories/`
- [ ] La story est à l'état `IN_PROGRESS`, `BLOCKED` (mode réactif) ou `TODO` (mode proactif)
- [ ] La story a une section `## Tâches d'implémentation détaillées` (sinon, lancer `analyse-story` d'abord)
- [ ] L'epic parent référencé dans la story existe

## Modes d'exécution

### Mode réactif (défaut)

**Déclencheur :** story `IN_PROGRESS` ou `BLOCKED`, après des échecs ou blocages répétés d'implémentation.

**Caractéristiques :**
- Certaines tâches peuvent déjà être complétées `[x]`
- Le diagnostic analyse les tâches bloquantes et les causes d'échec
- Les tâches complétées `[x]` restent dans la story parente (non redistribuées)
- Le statut de la story parente reste `IN_PROGRESS` (ou repasse de `BLOCKED` à `IN_PROGRESS`)

### Mode proactif

**Déclencheur :** story `TODO` — `analyse-story` a identifié une complexité trop élevée et a délibérément délégué la découpe à cette skill avant toute implémentation.

**Caractéristiques :**
- Aucune tâche n'est encore complétée (toutes `[ ]`)
- Le diagnostic est allégé : la complexité est déjà identifiée, pas d'échecs à analyser
- Toutes les tâches sont redistribuées dans les sous-stories (rien ne reste dans la parente)
- La story parente passe au statut `IN_PROGRESS` après la découpe

**Détection automatique du mode :**
- Lire le champ `**Statut :**` dans le fichier story
- `TODO` → **mode proactif**
- `IN_PROGRESS` ou `BLOCKED` → **mode réactif**

## Résultat attendu

- Fichiers `.backlog/stories/STORY-XXX.N-titre-court.md` créés pour chaque sous-story
- Story parente transformée : section `## Sous-stories` ajoutée, sections détaillées remplacées par des notes
- Kanban mis à jour avec les sous-stories dans la colonne appropriée
- Statut de la story parente mis à jour si nécessaire

---

## Phase 1 : Diagnostic de la story

### 1.1 Sélection de la story

Si l'utilisateur n'a pas spécifié de story, lister les stories disponibles dans `.backlog/stories/` avec les statuts candidats :

```
Quelle story souhaitez-vous découper ?

Stories candidates (IN_PROGRESS / BLOCKED / TODO avec complexité signalée) :
- STORY-XXX : [Titre] (IN_PROGRESS) (EPIC-YYY)
- STORY-XXX : [Titre] (BLOCKED) (EPIC-YYY)
- STORY-XXX : [Titre] (TODO — complexité détectée par analyse-story) (EPIC-YYY)
...
```

**Déterminer le mode dès que la story est choisie :**
- Statut `TODO` → **mode proactif**
- Statut `IN_PROGRESS` ou `BLOCKED` → **mode réactif**

### 1.2 Lecture complète de la story

Lire le fichier `.backlog/stories/STORY-XXX-*.md` et extraire :
- **Titre et numéro**
- **Statut** (`TODO`, `IN_PROGRESS` ou `BLOCKED`) — détermine le mode
- **Epic parent** (numéro + titre)
- **Description** (format "En tant que...")
- **Critères d'acceptation (AC)** — identifier ceux déjà cochés `[x]` et ceux encore ouverts `[ ]`
- **Section `## Tâches d'implémentation détaillées`** — identifier les tâches complétées `[x]` et à faire `[ ]`
- **Section `## État d'avancement technique`** — identifier les tâches cochées `[x]` et non cochées `[ ]`
- **Section `## Tests à écrire`** — si présente
- **Section `## Sous-stories`** — si déjà présente (cas de re-découpe)
- **Section `## Blocage`** — si présente, analyser la cause du blocage (mode réactif uniquement)

### 1.3 Lecture de l'epic parent

Lire le fichier epic dans `.backlog/epics/EPIC-XXX-*.md` pour comprendre :
- La **vision globale** et la valeur business
- Les **autres stories de l'epic** pour le contexte
- Les **notes de conception** et contraintes

### 1.4 Diagnostic adapté au mode

#### Mode réactif (IN_PROGRESS / BLOCKED)

Identifier et documenter les causes possibles de l'échec, puis présenter le diagnostic :

```
### Diagnostic — STORY-XXX (Mode réactif)

**Statut actuel :** [IN_PROGRESS | BLOCKED]

**Tâches complétées :** X/N
- [x] Tâche 1 : [Titre]
- [x] Tâche 2 : [Titre]

**Tâches en échec/bloquées :** Y/N
- [ ] Tâche 3 : [Titre] — [Raison estimée de l'échec]
- [ ] Tâche 4 : [Titre] — [Raison estimée de l'échec]

**Causes identifiées :**
- [Complexité / Périmètre trop large / Dépendances / Ambiguïté / Autre]
- [Détail de la cause]

**AC déjà validés :** [liste des AC cochés ou "Aucun"]
**AC restants :** [liste des AC non cochés]
```

#### Mode proactif (TODO)

Le diagnostic est allégé : pas d'échecs à analyser, la complexité est déjà documentée. Présenter un résumé de la complexité détectée :

```
### Diagnostic — STORY-XXX (Mode proactif)

**Statut actuel :** TODO
**Déclencheur :** Complexité détectée par analyse-story avant implémentation

**Indicateurs de complexité :**
- Nombre de tâches : [N] (seuil : >5)
- Nombre de fichiers estimés : [N] (seuil : >6)
- Composantes : [Backend / Frontend / Full-stack]
- Nombre d'AC : [N] (seuil : >8)

**Tâches à redistribuer :** Toutes ([N] tâches, toutes [ ])

**AC à répartir :** [liste des AC non cochés]
```

---

## Phase 2 : Proposition de découpe

### 2.1 Regroupement par cohésion fonctionnelle

Regrouper les **tâches à redistribuer** par cohésion fonctionnelle :
- Backend API / Services / Models / Schemas
- Frontend Composants / Stores / Composables / Types
- Helpers / Utils / Shared
- Tests & intégration

**Mode réactif — Règle critique :** Les tâches déjà complétées `[x]` dans la story parente **ne sont pas redistribuées**. Elles restent dans la story parente comme travail accompli.

**Mode proactif — Règle critique :** Toutes les tâches (toutes `[ ]`) sont redistribuées. Aucune tâche ne reste dans la story parente.

### 2.2 Répartition des AC

Chaque AC non validé de la story parente doit être couvert par **exactement une** sous-story.
- **Mode réactif :** Les AC déjà validés `[x]` restent dans la story parente (cochés).
- **Mode proactif :** Tous les AC sont à répartir (aucun n'est encore validé).

### 2.3 Présentation du plan de découpe

Présenter la proposition **AVANT toute création de fichier**.

#### Mode réactif

```
## 📋 Proposition de découpe — STORY-XXX (Mode réactif)

**Raison du découpage :** [Causes identifiées en Phase 1]

**Tâches déjà complétées (restent dans la story parente) :**
- [x] Tâche 1 : [Titre]
- [x] Tâche 2 : [Titre]

**Sous-stories proposées :**

### STORY-XXX.1 : [Titre] — [Domaine fonctionnel]
- **Périmètre :** [description]
- **AC couverts :** AC 3, AC 4
- **Tâches redistribuées :** Tâche 3, Tâche 4
- **Fichiers concernés :** [liste]
- **Dépendances :** Aucune

### STORY-XXX.2 : [Titre] — [Domaine fonctionnel]
- **Périmètre :** [description]
- **AC couverts :** AC 5, AC 6
- **Tâches redistribuées :** Tâche 5, Tâche 6
- **Fichiers concernés :** [liste]
- **Dépendances :** STORY-XXX.1

**Ordre d'implémentation recommandé :** STORY-XXX.1 → STORY-XXX.2

Validez-vous ce découpage ? (oui / modifications souhaitées / annuler)
```

#### Mode proactif

```
## 📋 Proposition de découpe — STORY-XXX (Mode proactif)

**Raison du découpage :** Complexité trop élevée détectée par analyse-story
  ([N] tâches / [N] fichiers / [composantes] / [N] AC)

**Toutes les tâches sont redistribuées** (aucune tâche complétée à conserver) :

### STORY-XXX.1 : [Titre] — [Domaine fonctionnel]
- **Périmètre :** [description]
- **AC couverts :** AC 1, AC 2
- **Tâches redistribuées :** Tâche 1, Tâche 2
- **Fichiers concernés :** [liste]
- **Dépendances :** Aucune

### STORY-XXX.2 : [Titre] — [Domaine fonctionnel]
- **Périmètre :** [description]
- **AC couverts :** AC 3, AC 4
- **Tâches redistribuées :** Tâche 3, Tâche 4
- **Fichiers concernés :** [liste]
- **Dépendances :** STORY-XXX.1

**Ordre d'implémentation recommandé :** STORY-XXX.1 → STORY-XXX.2

Validez-vous ce découpage ? (oui / modifications souhaitées / annuler)
```

### 2.4 Itérations avec l'utilisateur

Si l'utilisateur propose des modifications :
- Ajuster le regroupement des tâches
- Ajuster la répartition des AC
- Ajuster les dépendances
- Re-présenter le plan modifié pour validation

**Si l'utilisateur annule** : ne rien modifier et terminer la skill sans créer de fichier.

---

## Phase 3 : Création des sous-stories

Après validation explicite de l'utilisateur, créer les fichiers de sous-stories.

### 3.1 Format de fichier de sous-story

Pour chaque sous-story, créer un fichier `.backlog/stories/STORY-XXX.N-titre-court.md` avec le format suivant :

````markdown
# STORY-XXX.N : [Titre de la sous-story]

**Statut :** TODO
**Story Parente :** STORY-XXX — [Titre de la Story]
**Epic Parent :** EPIC-YYY — [Titre de l'Epic]

## Description
[Sous-ensemble de la description parente, spécifique à cette sous-story. Inclure le contexte
nécessaire pour comprendre le périmètre de cette sous-story sans avoir à relire la story parente.]

## Critères d'acceptation (AC)
- [ ] AC X : [Critère hérité de la story parente — texte exact]
- [ ] AC Y : [Critère hérité de la story parente — texte exact]

## Contexte technique
[Fichiers concernés, patterns, prérequis — hérités de la story parente et filtrés
pour ne garder que les éléments pertinents pour cette sous-story]

## Dépendances
- STORY-XXX.(N-1) : [Titre de la sous-story précédente] (ou "Aucune" si première sous-story)

## Tâches d'implémentation détaillées

### Tâche 1 : [Titre descriptif et concis]
**Objectif :** [Description claire en 1-2 phrases de ce que cette tâche accomplit]
**Fichiers :**
- `chemin/vers/fichier.ext` — [Créer | Modifier | Supprimer] — [Description précise]
**Exigences sécurité :** [Si applicable, ou "Aucune exigence spécifique"]
**Dépend de :** [Tâche précédente ou "Aucune"]

### Tâche 2 : [Titre descriptif et concis]
...

## Tests à écrire

### Backend
- `backend/tests/unit/test_xxx.py`
  - `test_cas_nominal` — [Description du cas de test]
  - `test_cas_erreur` — [Description du cas de test]

### Frontend
- `frontend/tests/unit/xxx.spec.ts`
  - `[description du test]` — [Comportement attendu]

### Commandes de validation
```bash
# Backend
pytest backend/tests/unit/test_xxx.py -v

# Frontend
pnpm test -- tests/unit/xxx
```

## État d'avancement technique
- [ ] Tâche 1 : [Titre]
- [ ] Tâche 2 : [Titre]

## Notes d'implémentation
<!-- Ajoutées à la clôture par treat-story -->
````

### 3.2 Règles de rédaction des sous-stories

- **Description** : Reprendre le sous-ensemble pertinent de la description parente, adapté au périmètre de cette sous-story. La sous-story doit être compréhensible indépendamment.
- **AC** : Reprendre **exactement** le texte des AC de la story parente (ne pas reformuler). Un AC ne peut appartenir qu'à une seule sous-story.
- **Contexte technique** : Filtrer pour ne garder que les éléments pertinents pour cette sous-story (fichiers, patterns, prérequis liés aux tâches redistribuées).
- **Tâches** : Reprendre les tâches de la story parente qui sont redistribuées, en conservant le format détaillé complet (objectif, fichiers, exigences sécurité, dépendances). Ne pas résumer — copier et adapter fidèlement.
- **Tests** : Filtrer les tests pour ne garder que ceux pertinents pour cette sous-story.
- **Dépendances** : Indiquer explicitement les dépendances entre sous-stories.

### 3.3 Numérotation et nommage des fichiers

- Numérotation séquentielle : `.1`, `.2`, `.3`, etc.
- L'ordre suit l'ordre logique d'implémentation (dépendances respectées)
- Nom de fichier : `STORY-XXX.N-titre-court.md` où `titre-court` est un slug dérivé du titre (kebab-case, max 5-6 mots)

---

## Phase 4 : Transformation de la story parente

### 4.1 Ajout de la section Sous-stories

Ajouter une section `## Sous-stories` à la story parente, **après** la section `## Critères d'acceptation (AC)` :

```markdown
## Sous-stories
- [ ] STORY-XXX.1 : [Titre sous-story 1] — Couvre AC 3, AC 4
- [ ] STORY-XXX.2 : [Titre sous-story 2] — Couvre AC 5, AC 6
```

### 4.2 Remplacement de la section Tâches d'implémentation détaillées

Le contenu de remplacement dépend du mode.

#### Mode réactif

Remplacer par une note explicative et les tâches déjà complétées :

```markdown
## Tâches d'implémentation détaillées

> ⚠️ Cette story a été découpée en sous-stories suite à des difficultés d'implémentation.
> Les tâches restantes ont été redistribuées dans les sous-stories listées ci-dessus.
> Les tâches complétées avant la découpe sont conservées ci-dessous pour référence.

### Tâches complétées avant découpe
- [x] Tâche 1 : [Titre] ✅
- [x] Tâche 2 : [Titre] ✅
```

Si aucune tâche n'était complétée avant la découpe (rare en mode réactif), indiquer :

```markdown
> (Aucune tâche n'avait été complétée avant la découpe.)
```

#### Mode proactif

Remplacer entièrement la section — aucune tâche complétée à préserver :

```markdown
## Tâches d'implémentation détaillées

> ⚠️ Cette story a été découpée en sous-stories avant implémentation (complexité détectée par analyse-story).
> Toutes les tâches ont été redistribuées dans les sous-stories listées ci-dessus.
> Consulter chaque sous-story pour les tâches détaillées.
```

### 4.3 Remplacement de la section État d'avancement technique

Remplacer le **contenu** de la section `## État d'avancement technique` :

```markdown
## État d'avancement technique

> ⚠️ L'avancement technique est désormais suivi dans les sous-stories individuelles.

**Progression :** 0/2 sous-stories terminées
- [ ] STORY-XXX.1 : [Titre]
- [ ] STORY-XXX.2 : [Titre]
```

### 4.4 Remplacement de la section Tests à écrire

Si la section `## Tests à écrire` existe, la remplacer par une note :

```markdown
## Tests à écrire

> ⚠️ Les tests sont désormais définis dans les sous-stories individuelles.
```

### 4.5 Mise à jour du statut

Mettre à jour le champ `**Statut :**` dans la story parente :
- **Mode réactif :** Si la story était `BLOCKED` → passer à `IN_PROGRESS` (la découpe lève le blocage). Si la story était `IN_PROGRESS` → conserver `IN_PROGRESS`.
- **Mode proactif :** La story était `TODO` → passer à `IN_PROGRESS` (la découpe a démarré le traitement).
- La story parente passera à `DONE` automatiquement quand toutes les sous-stories seront `DONE` (géré par `treat-story`)

### 4.6 Gestion de la section Blocage

Si la story parente contient une section `## Blocage` :
- Annoter la section comme résolue par la découpe :

```markdown
## Blocage

> ✅ Résolu par découpe en sous-stories le [date]. Voir section `## Sous-stories`.
```

### 4.7 Sections à conserver sans modification

- `# Titre` (ne jamais changer le titre ni le numéro de la story parente)
- `**Epic Parent :**`
- `## Description`
- `## Critères d'acceptation (AC)` — les cases `[x]` restent cochées, les `[ ]` restent ouvertes
- `## Dépendances` (section existante — ne pas modifier)
- `## Contexte technique` (section existante — ne pas modifier)
- `## Notes` (si présente)
- `## Notes d'implémentation` (si présente)

---

## Phase 5 : Mise à jour du Kanban

### 5.1 Localisation de la story parente dans le Kanban

Localiser la story parente dans `.backlog/kanban.md` :
- **Mode réactif :** colonne `🔄 IN PROGRESS` ou `📋 BACKLOG`
- **Mode proactif :** colonne `📋 BACKLOG` (statut `TODO`)

### 5.2 Ajout des sous-stories dans le Kanban

Ajouter les sous-stories dans la **même section de groupe** que la story parente, dans la colonne `📋 BACKLOG`. Format :

```markdown
| [STORY-XXX.1](.backlog/stories/STORY-XXX.1-titre-court.md) | [Titre sous-story 1] | [Type hérité] |
| [STORY-XXX.2](.backlog/stories/STORY-XXX.2-titre-court.md) | [Titre sous-story 2] | [Type hérité] |
```

Le type est hérité de la story parente (Analyse, Conception, Implémentation, etc.).

### 5.3 Mise à jour du marqueur de la story parente

- **Mode réactif :** Si la story parente était `BLOCKED` (marqueur `- [!]`) → passer à `- [~]` (IN_PROGRESS). Si déjà `IN_PROGRESS` (`- [~]`) → conserver.
- **Mode proactif :** La story parente était `TODO` (marqueur `- [ ]`) → passer à `- [~]` (IN_PROGRESS).

### 5.4 Non-ajout dans l'epic parent

Les sous-stories **ne sont pas listées dans l'epic parent** (`.backlog/epics/EPIC-XXX-*.md`). Elles sont uniquement référencées dans la section `## Sous-stories` de la story parente.

---

## Phase 6 : Récapitulatif final

Présenter un récapitulatif à l'utilisateur :

```
✅ Story STORY-XXX découpée avec succès.

**Sous-stories créées :**
- .backlog/stories/STORY-XXX.1-[titre].md → TODO
- .backlog/stories/STORY-XXX.2-[titre].md → TODO

**Fichiers mis à jour :**
- .backlog/stories/STORY-XXX-*.md → Transformée (section Sous-stories ajoutée, statut [IN_PROGRESS])
- .backlog/kanban.md → Sous-stories ajoutées au backlog

**Prochaine étape :** Lancer `treat-story` sur STORY-XXX.1 pour commencer l'implémentation.
```

---

## Gestion des cas particuliers

### Story avec sous-stories existantes (re-découpe)

Si la story contient déjà une section `## Sous-stories` :

1. Lire chaque fichier de sous-story existant
2. Identifier les sous-stories déjà `DONE` (ne pas les re-découper)
3. Identifier les sous-stories encore `TODO` ou `IN_PROGRESS` ou `BLOCKED`
4. Proposer à l'utilisateur :

```
⚠️ STORY-XXX contient déjà des sous-stories :
- [x] STORY-XXX.1 : [Titre] — DONE ✅
- [ ] STORY-XXX.2 : [Titre] — BLOCKED ❌

Options :
1. Découper STORY-XXX.2 en sous-sous-stories (STORY-XXX.2.1, STORY-XXX.2.2...)
2. Re-découper toutes les sous-stories non terminées
3. Annuler

Que préférez-vous ?
```

### Story en statut TODO (mode proactif)

- Confirmer que la story a bien une section `## Tâches d'implémentation détaillées` (ajoutée par `analyse-story`)
- Activer le mode proactif : toutes les tâches sont à redistribuer, aucune tâche complétée à préserver
- Passer le statut de la story parente à `IN_PROGRESS` après la découpe
- Ne pas chercher de section `## Blocage` (inapplicable en mode proactif)

### Story BLOCKED

- Appliquer la découpe normalement (mode réactif)
- Remettre le statut à `IN_PROGRESS` après la découpe
- Annoter la section `## Blocage` comme résolue (voir §4.6)

### Story sans section Tâches d'implémentation détaillées

Interrompre la skill et informer l'utilisateur :

```
⚠️ STORY-XXX n'a pas de section "Tâches d'implémentation détaillées".

Cette story n'a pas encore été analysée par `analyse-story`.
La skill `split-story` nécessite que les tâches soient déjà détaillées pour pouvoir les redistribuer.

Recommandation : Lancer `analyse-story` sur STORY-XXX d'abord.

Souhaitez-vous tout de même procéder à une découpe basée uniquement sur les AC ? (oui/non)
```

Si l'utilisateur accepte une découpe basée sur les AC uniquement :
- Créer les sous-stories avec les AC répartis mais sans tâches détaillées
- Indiquer dans chaque sous-story qu'il faut lancer `analyse-story` pour détailler les tâches

### Story avec très peu de tâches restantes (≤ 2 tâches non complétées)

Informer l'utilisateur et déconseiller la découpe :

```
⚠️ STORY-XXX n'a que [N] tâche(s) restante(s) non complétée(s).

Découper pour si peu de tâches est contre-productif.

Recommandation : Continuer l'implémentation avec `treat-story`.
Si la tâche spécifique est bloquée, identifiez le blocage précis et résolvez-le.

Souhaitez-vous quand même découper ? (oui/non)
```

### Story DONE

Informer l'utilisateur et terminer :

```
ℹ️ STORY-XXX est déjà à l'état DONE.
Il n'y a rien à découper. La story est terminée.
```

---

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Story non trouvée | Demander un numéro valide parmi les stories existantes |
| Story à état `TODO` sans section tâches détaillées | Lancer d'abord `analyse-story` pour analyser la story avant la découpe |
| Story à état `TODO` avec tâches détaillées | Activer le mode proactif — découpe normale, toutes les tâches redistribuées |
| Story déjà `DONE` | Informer l'utilisateur — la story est terminée |
| Story sans section `## Tâches d'implémentation détaillées` | Proposer de lancer `analyse-story` d'abord ou mode dégradé (AC uniquement) |
| Epic parent introuvable | Signaler l'incohérence, demander correction manuelle |
| Sous-stories déjà existantes | Proposer de découper une sous-story spécifique ou de re-découper |
| ≤ 2 tâches restantes (mode réactif) | Déconseiller la découpe, proposer de continuer avec `treat-story` |
| Utilisateur annule | Ne rien modifier, terminer la skill sans créer de fichier |
| Conflit de numérotation (fichier sous-story déjà existant) | Signaler le conflit, proposer une numérotation alternative (.N+1) |
| AC ambigus — difficile de les répartir | Présenter les options à l'utilisateur et demander un arbitrage |

---

## Checklist de fin

Avant de conclure l'exécution de cette skill, vérifier :

- [ ] Le mode d'exécution a été déterminé automatiquement (statut `TODO` → proactif ; `IN_PROGRESS`/`BLOCKED` → réactif)
- [ ] La story a été lue et diagnostiquée (mode réactif : tâches bloquantes et causes d'échec ; mode proactif : indicateurs de complexité)
- [ ] L'epic parent a été consulté pour le contexte
- [ ] Le diagnostic a été présenté à l'utilisateur
- [ ] Le plan de découpe a été présenté et **validé explicitement** par l'utilisateur (ou annulé)
- [ ] Si annulé : aucun fichier n'a été créé ou modifié
- [ ] Chaque sous-story a un fichier `.backlog/stories/STORY-XXX.N-*.md` créé
- [ ] Chaque sous-story hérite des AC pertinents de la story parente (texte exact)
- [ ] Chaque AC non validé de la story parente est couvert par **exactement une** sous-story
- [ ] **Mode réactif :** Les tâches déjà complétées `[x]` restent dans la story parente (non redistribuées)
- [ ] **Mode proactif :** Toutes les tâches sont redistribuées (aucune conservée dans la parente)
- [ ] Les tâches non complétées `[ ]` sont redistribuées dans les sous-stories
- [ ] Chaque sous-story a 2-4 tâches d'implémentation détaillées
- [ ] Les dépendances entre sous-stories sont explicites dans chaque fichier
- [ ] La story parente a une section `## Sous-stories` ajoutée après les AC
- [ ] La section `## Tâches d'implémentation détaillées` de la story parente est remplacée par une note adaptée au mode
- [ ] La section `## État d'avancement technique` de la story parente est remplacée par une note
- [ ] La section `## Tests à écrire` de la story parente est remplacée par une note (si existait)
- [ ] Le statut de la story parente est mis à jour (`IN_PROGRESS` — qu'elle était `TODO`, `BLOCKED` ou `IN_PROGRESS`)
- [ ] **Mode réactif :** La section `## Blocage` de la story parente est annotée si elle existait
- [ ] Le Kanban est mis à jour : sous-stories ajoutées, marqueur story parente mis à jour
- [ ] Les sous-stories ne sont **pas** listées dans l'epic parent
- [ ] Un récapitulatif final a été présenté à l'utilisateur avec la prochaine étape
- [ ] **Aucun code source n'a été écrit ou modifié**

---

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/stories/STORY-XXX-*.md` | Lecture (diagnostic) + Modification (transformation en story parente avec sous-stories) |
| `.backlog/stories/STORY-XXX.N-*.md` | Création (nouveaux fichiers de sous-stories) |
| `.backlog/kanban.md` | Modification (ajout des sous-stories au backlog, mise à jour du marqueur story parente) |
| `.backlog/epics/EPIC-XXX-*.md` | Lecture seule (contexte) — les sous-stories **ne sont pas ajoutées** à l'epic |
