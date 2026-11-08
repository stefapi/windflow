# Gabarit de rapport de revue

Reproduire cette structure. Supprimer les sections vides plutôt que d'y écrire du remplissage — sauf les catégories A à F, où « RAS » est la mention attendue.

---

## Revue de code — `<BASE>..HEAD`

### 1. Résumé des changements

- **Plage analysée** : `<BASE>..HEAD` (+ mention si le working tree ou l'index a été inclus)
- **Commits** : N — lister les messages
- **Fichiers** : N modifiés, N ajoutés, N supprimés (+X / −Y lignes)
- **Répartition** : `backend/app` (N), `backend/alembic/versions` (N), `backend/tests` (N), `frontend/src` (N), `frontend/tests` (N), `cli` (N), infra/config (N), ignorés (N : lockfiles, code généré, etc.)
- **Nature des modifications** : 2 à 4 phrases factuelles décrivant ce que fait la PR. Pas d'interprétation d'intention non étayée.

### 2. Périmètre

Indiquer le périmètre des changements identifié à l'étape 1 de la skill :

- **Backend uniquement** — diff limité à `backend/**` (routers FastAPI, services, modèles SQLAlchemy, schémas Pydantic, migrations Alembic, tests pytest).
- **Frontend uniquement** — diff limité à `frontend/**` (vues, composants, composables, stores Pinia, services, types, styles UnoCSS).
- **Full-stack** — diff touchant à la fois `backend/` et `frontend/` ; préciser les points de cohérence à vérifier : schémas Pydantic ↔ types TypeScript (client régénéré via `make generate-api`), endpoints REST ↔ services frontend, canaux WebSocket, migrations ↔ modèles.

Préciser, le cas échéant, les zones sensibles couvertes : contrat API (client généré), migrations de schéma, authentification/autorisation (JWT, RBAC 4 rôles, WebSocket), bus d'événements `Bus`, appels LLM (LiteLLM), métriques `windflow_`.

### 3. Tableau de synthèse

| Sévérité | Nombre |
|---|---|
| Critique | N |
| Majeur | N |
| Mineur | N |
| Info | N |

Si des findings Critiques existent, les rappeler ici en une ligne chacun.

### 4. Findings

Trier par sévérité décroissante à l'intérieur de chaque catégorie. Chaque finding référence la catégorie correspondante de [`checklist.md`](checklist.md) (A à F). Format d'un finding :

> **[Sévérité] `chemin/du/fichier.ext:~ligne`** — Titre court du problème
>
> *Constat* : ce qui est observé dans le code, avec l'extrait pertinent si utile (≤ 5 lignes).
> *Impact* : conséquence concrète (fuite de données, bug, dette, illisibilité).
> *Recommandation* : action précise et applicable.

#### A. Code mort
#### B. Complexité et code inutile
#### C. Non-respect des règles de codage
#### D. Nettoyage
#### E. Sécurité
#### F. Fiabilité (migrations, tests, performances, erreurs, contrats)

### 5. Points positifs

Ce qui est correctement fait et mérite d'être conservé (structure respectée, tests sécurité 401/403/422 ajoutés, schémas Pydantic validés, client API régénéré via `make generate-api`, RBAC `require_role(...)` en place, métriques `windflow_` correctement étiquetées…). 2 à 5 points maximum, uniquement s'ils sont réels.

### 6. Points à confirmer

Éléments qui semblent problématiques mais que l'analyse statique ne permet pas de trancher (usage dynamique possible, auto-import unplugin, intention non documentée). Un point = une hypothèse + ce qui permettrait de la lever.

### 7. Questions pour l'utilisateur

Questions numérotées, chacune rattachée à un fichier ou un finding. Uniquement des questions dont la réponse change la conclusion de la revue.

### 8. Verdict

Une des trois formulations, justifiée en une phrase :

- **Bloquant** — au moins un finding Critique, ou plusieurs Majeurs sur le même chemin critique.
- **Corrections demandées** — findings Majeurs à traiter avant merge.
- **Mergeable** — uniquement des points Mineurs / Info.

Rappeler en dernière ligne qu'aucun fichier n'a été modifié et qu'aucun commit n'a été créé.
