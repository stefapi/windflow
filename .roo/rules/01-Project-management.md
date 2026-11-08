# 01 — Gestion de projet et backlog

## 1. Emplacements

| Élément | Emplacement |
| --- | --- |
| Spécification fonctionnelle | `docs/general_specs/` (index `00-index.md`) et `docs/technical_specs/` |
| Feuille de route | `docs/Roadmap.md` (jamais recopiée ailleurs) |
| Backlog | `.backlog/` — epics, stories, bugs, registre, kanban |
| Epics | `.backlog/epics/EPIC-XXX-slug.md` |
| Stories et sous-stories | `.backlog/stories/STORY-XXX-slug.md` et `STORY-XXX.N-slug.md` |
| Bugs | `.backlog/bugs/BUG-XXX-slug.md` |
| Registre des identifiants | `.backlog/identifiants.md` — attributions et réservations conservées |
| Kanban | `.backlog/kanban.md`, vue générée par `make backlog` depuis les contrats |
| Modèles | `.backlog/_models/` : `epic.md`, `story.md`, `sub-story.md`, `bug.md` |

## 2. Hiérarchie et choix de l'unité

Les stories sont facultatives. La chaîne est **roadmap → epic → story si nécessaire**.

- **Epic** : chantier de la roadmap ; sa métadonnée `**Mode de réalisation :** directe | découpée` indique où se trouve le contrat exécutable.
- **Directe** : l'epic constitue une livraison cohérente, bornée, vérifiable et révisable ; ses prérequis et décisions sont disponibles, les risques et la reprise maîtrisés. Elle porte ses AC, analyse, plan, tests, notes et preuves dans sa section « Exécution directe » ; aucune story miroir n'est créée. Sa liste des stories indique « Sans objet — réalisation directe ».
- **Découpée** : plusieurs résultats indépendants, dépendances/validations distinctes ou une revue trop large justifient des stories verticales. La justification est consignée ; le nombre de fichiers, tâches, couches ou AC n'impose jamais seul une découpe.
- **Story** : tranche verticale livrable rattachée à une epic découpée. Une **sous-story** (`STORY-XXX.N`) est un volet justifié d'une story ; sa parente suit l'ensemble.
- **Tâche** : étape du plan dans le contrat exécutable (epic directe, story ou bug), sans nouveau fichier.
- **Bug** : écart à une exigence livrée, rattaché à l'epic d'origine.

Choisir et justifier le mode à la création/analyse ; une epic sans mode n'est pas prête à exécuter. Une epic qui possède déjà des stories reste découpée par défaut : aucune fusion ou suppression implicite de contrats. Si une epic directe devient trop large, passer en mode découpé avec motif, conserver son identifiant, son travail et ses preuves, puis répartir le reste dans des stories avec matrice de couverture. Ne pas maintenir deux suivis exécutables concurrents du même périmètre.

## 3. Identifiants

- Formats : `EPIC-XXX`, `STORY-XXX`, sous-story `STORY-XXX.N`, `BUG-XXX`.
- Registre durable : `.backlog/identifiants.md`. Toute attribution ou réservation est inscrite avec son chemin de contrat, sa date et son motif **dans le même changement** que la création ; une entrée n'est jamais retirée et un numéro n'est jamais réutilisé, même après abandon.
- Numéro suivant = maximum des identifiants du même type du registre et des fichiers conservés + 1 ; les sous-stories ont un compteur par parent. Avant attribution, réconcilier tout fichier non inscrit et toute réservation ; un contrat inscrit mais manquant est une anomalie à restaurer, pas un numéro libre.
- Une réservation sans contrat emploie explicitement le statut « Réservation sans contrat » ; son annulation est consignée, jamais effacée.
- Slug : minuscules sans accents, kebab-case, 5 à 6 mots au plus (ex. `STORY-401-import-stacks-yaml.md`).

## 4. Format des fichiers de backlog

- Un élément est créé en copiant le gabarit correspondant de `.backlog/_models/` vers son dossier cible ; les gabarits font foi et ne sont jamais remplis directement.
- En-tête : titre `# IDENTIFIANT : Titre`, puis métadonnées en lignes en gras (`**Statut :**`, `**Priorité :**`, `**Epic Parent :**`, `**Gravité :**`, `**Mode de réalisation :**` pour une epic… selon le gabarit).
- Les commentaires `<!-- … -->` des gabarits expliquent le rôle de chaque section ; ils sont supprimés une fois le document renseigné.
- Une exigence de métadonnée posée par une règle s'ajoute à cet en-tête.

## 5. Sections obligatoires

Gabarits de référence : `.backlog/_models/`. Les clauses déjà présentes dans la spécification sont référencées, pas recopiées.

- **Epic** : Mode de réalisation et justification ; Vision (valeur business, utilisateurs cibles) ; Description ; Liste des Stories liées ; Notes de conception ; Critères de succès (Definition of Done) ; Risques ; Dépendances ; Source roadmap ; Historique de clôture.
- **Epic directe, en complément** : AC stables ; section « Exécution directe » (Contexte technique, Tâches d'implémentation détaillées, Tests à écrire, État d'avancement technique, Notes d'implémentation).
- **Story** : Description (format « En tant que… ») ; Contexte technique (rempli par l'analyse) ; Critères d'acceptation (AC) ; Sous-stories (si découpage) ; Dépendances ; Tâches d'implémentation détaillées ; Tests à écrire ; État d'avancement technique ; Notes d'implémentation.
- **Bug** : Reproduction ; Comportement attendu ; Comportement actuel ; Contexte technique (cause racine, réparation cible) ; Tâches d'implémentation détaillées ; Tests à écrire ; État d'avancement technique ; Résolution.

## 6. Cycles de vie

**Unité exécutable** (epic directe, story, sous-story) : `TODO → IN_PROGRESS → REVIEW → DONE`, avec retour `REVIEW → IN_PROGRESS` si correction ; `BLOCKED` avec motif et état de reprise si une dépendance bloque le travail. L'analyse seule ne démarre pas l'implémentation. Une epic directe atteint `REVIEW` quand sa réalisation est prête à relire, `DONE` lors de sa clôture (`close-epic`) après finalisation conforme et validation requise.

**Bug** : `NEW → CONFIRMED → IN_PROGRESS → REVIEW → DONE`, avec sorties `WONT_FIX` (accepté mais non corrigé) et `ABANDONED` (non reproduit, obsolète). Un bug `NEW` passe à `CONFIRMED` une fois reproduit.

**Epic découpée** : statut agrégé, consigné dans son fichier. `TODO` si aucune réalisation n'est commencée ; `IN_PROGRESS` si du travail reste ; `BLOCKED` si aucune travail utile ne peut continuer ; `REVIEW` lorsque les stories sont terminées et que la revue globale reste à accepter ; `DONE` uniquement après finalisation et clôture. Une liste vide ne prouve pas la complétude.

## 7. Définition de terminé

**Unité exécutable** acceptée seulement si :
1. chaque critère d'acceptation est satisfait et relié à un test pertinent, ou à une revue justifiée pour un travail purement documentaire ;
2. pour un changement applicatif, `make check` et les contrôles supplémentaires requis par la tâche passent ; pour un changement purement documentaire, revue et contrôles du corpus (`make check-harness`, `make backlog-check`) peuvent suffire ; pour l'outillage, exécuter les contrôles pertinents (`make harness-test`) sans inventer de preuve applicative. Dans tous les cas, un contrôle absent, vide, ignoré ou non exécuté reste non validé ; une dérogation exceptionnelle exige décideur, justification, périmètre et expiration (`35-testing-quality-gates.md` §8) ;
3. les seuils de couverture sont respectés sur les périmètres applicables (`35` §3) ; une modification documentaire seule ne requiert pas de mesure de couverture ;
4. si le contrat d'API a changé : le client TypeScript est régénéré dans le même changement (`make generate-api`) ;
5. si le schéma a changé : migration Alembic relue et testée (`20-architecture-and-api.md`) ;
6. la documentation et les règles touchées sont à jour ;
7. une entrée est ajoutée dans `CHANGELOG.md`, section « Unreleased » ;
8. le kanban, la « Liste des Stories liées » de l'epic et les statuts sont synchronisés (`make backlog`, `make backlog-check`) ;
9. aucun `TODO`/`FIXME` sans référence d'élément de backlog (`30-code-standards.md` §6).

**Bug** résolu : un test reproduit le bug (en échec avant le correctif, vert après) et la section « Résolution » est renseignée ; la vérification finale appartient au propriétaire.

**Epic** `DONE` : une epic directe satisfait les critères de son propre contrat et la définition commune ci-dessus ; une epic découpée exige aussi toutes ses stories et sous-stories terminées, sans exigence restante perdue. Dans les deux modes, ses critères de succès sont vérifiés et consignés à l'« Historique de clôture ».

## 8. Cohérence croisée

- La métadonnée `**Epic Parent :**` d'une story ou d'un bug désigne un epic existant.
- La « Liste des Stories liées » de l'epic contient chaque story rattachée ; la case est cochée si et seulement si la story est `DONE` ou `ABANDONED`. Après découpe, le parent y est représenté par ses sous-stories.
- Une story parente passe `DONE` seulement quand toutes ses sous-stories sont `DONE`.
- Le kanban est une **vue générée** : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne jamais éditer `.backlog/kanban.md` à la main. Le statut de référence est le champ `**Statut :**` du fichier.

| Statut story/bug | Colonne Kanban | Marqueur case |
| --- | --- | --- |
| `TODO` | 📋 BACKLOG | `- [ ]` |
| `IN_PROGRESS` | 🏗️ IN PROGRESS | `- [~]` |
| `REVIEW` | 🚧 REVIEW | `- [?]` |
| `BLOCKED` | 🏗️ IN PROGRESS (annotation) | `- [!]` |
| `DONE` / `WONT_FIX` | ✅ DONE | `- [x]` |

- Contrôle structurel : `make backlog-check` vérifie identifiants, statuts, registre, liens parent/enfants, cases et vue générée ; il ne valide ni les AC ni une acceptation métier.
- Branches et commits citent l'identifiant (`feat/STORY-401-...`, pied `Refs: STORY-401`) — `50-dev-workflow.md` §5.

## 9. Fin de session

Avant de conclure une session de travail :
1. mettre à jour le statut, les cases et les notes (d'implémentation ou de résolution) du fichier ;
2. actualiser le statut de l'epic selon son mode ; en mode découpé, synchroniser sa liste de stories ;
3. régénérer le kanban par `make backlog` puis vérifier `make backlog-check` ;
4. ajouter l'entrée `CHANGELOG.md` si du code livrable a changé ;
5. déclarer les tests exécutés et non exécutés ;
6. donner la prochaine étape, une seule.

## 10. Clôture et conservation

**Règle d'or : ne jamais supprimer un fichier de backlog.** Les contrats terminés sont conservés à leur chemin, avec leur identifiant, leurs AC, décisions, notes et preuves. Un abandon se traduit par le statut `ABANDONED` + marqueur `[ABANDONED]` dans le titre + note explicative.

- `close-epic` vérifie les conditions de terminé, renseigne l'« Historique de clôture », conserve la liste liée des stories, puis retire seulement les lignes de suivi du kanban actif. Les critères non satisfaits ne sont pas cochés par la clôture. Un bug ouvert empêchant les critères de succès bloque la clôture.
- `clean-epic` répare les liens erronés sans effacer l'historique. Un fichier manquant impose d'examiner registre et Git, puis de restaurer le contrat ou de signaler l'anomalie ; son identifiant reste réservé.
- Le registre garde aussi les identifiants abandonnés. Une réouverture conserve identifiant et chemin, ajoute un événement daté et remet les lignes concernées au kanban ; elle n'efface pas l'acceptation antérieure.
- La clôture d'une epic directe vérifie son contrat et ses preuves ; zéro story est normal dans ce mode. La clôture d'une epic découpée vérifie aussi ses stories, sous-stories et la couverture agrégée.

## 11. Pipeline d'une unité de travail

- **Epic directe** : `create-epic → analyse-story (cible EPIC) → treat-story (cible EPIC) → finalise-epic → close-epic`. `treat-epic` orchestre ce chemin sans appeler `create-stories`.
- **Epic découpée** : `create-epic → create-stories → [analyse-story → treat-story → finalise-story] → finalise-epic → close-epic`, dans l'ordre des dépendances.
- Les skills de création (`create-*`) ne génèrent que la description et les AC — pas de tâches techniques. L'analyse (`analyse-story`) explore le code et écrit les tâches détaillées sans coder. L'implémentation (`treat-story`) exécute le plan avec autonomie locale (§12).
- `split-story` reste réservé aux stories, en mode proactif (story `TODO`, complexité détectée à l'analyse) ou réactif (story `IN_PROGRESS`/`BLOCKED` après échecs répétés) ; une epic devenue trop large est découpée par `create-stories`. La taille d'une session ou le seul nombre de fichiers n'est pas un motif de découpe.

## 12. Autonomie et réexamen de l'approche

Le besoin, les invariants, les critères d'acceptation et les limites sont stables ; le plan technique reste adaptable. L'agent décide des choix locaux réversibles compatibles, y compris les refactorings nécessaires au résultat, sans story supplémentaire ni confirmation pour chaque détail. Il consigne les choix utiles à la reprise. Une dérive du besoin ou des critères est arbitrée, jamais absorbée silencieusement.

L'agent suspend les correctifs concernés et réexamine l'approche lorsqu'une même famille de problèmes revient, qu'un correctif déplace l'erreur, que les hypothèses sont successivement invalidées, ou que règles complexes, exceptions et responsabilités se dispersent. Il étudie la cause à l'échelle du mécanisme et conserve les contraintes approuvées. Il prépare faits, hypothèses, options, recommandation et vérification discriminante avant de proposer un autre modèle. Une nouvelle tentative exige une hypothèse ou une preuve nouvelle ; les limites explicites du contrat restent applicables, sans seuil universel d'essais.

Les changements de frontières, persistance, transactions, modèle d'exécution, contrats publics, sécurité ou dépendance importante sont soumis au propriétaire avant implémentation dépendante. Les investigations réversibles nécessaires pour rendre les options concrètes sont autonomes. Poursuivre les travaux indépendants autorisés ; découper une tâche ne résout pas son défaut de conception.

Protocole partagé des skills et des modes : [exécution](../../docs/dev/protocole-execution.md). La revue distincte et les validations sensibles suivent `02` §7 et `35` ; l'autonomie locale ne vaut ni acceptation ni autorisation de fusion.
