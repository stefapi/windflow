# Formulaires dynamiques de configuration des stacks

> **Statut** : Spécification technique · Implémenté — **refondu (vague 2) — 2026-08-23**
> **Périmètre** : Mécanique de génération des formulaires de configuration des stacks (schéma variables → composable `useDynamicForm` → composant `DynamicFormField` → payload de création).
> **Référence de fond** : [general_specs — 03 Modèle compute](../general_specs/03-modele-compute.md) · [09 API](../general_specs/09-api.md) · [11 Plugins](../general_specs/11-plugins.md)
> **Dernière mise à jour** : 2026-08-23 — refonte pilotée par [PLAN-REFONTE-TECHNICAL-SPECS.md](../../PLAN-REFONTE-TECHNICAL-SPECS.md)

> **Terminologie** : ce document emploie le vocabulaire canonique du glossaire
> ([19-glossaire.md](../general_specs/19-glossaire.md)) : Host (ex-*Target*), Machine (ex-*VM*), App, Cluster, profil.
> Les identifiants du code historique (`target_id`, `TargetType`…) sont cités entre backticks
> et mis en correspondance à la première occurrence.

## Vue d'ensemble

Les stacks du catalogue interne exposent leurs variables configurables ; le frontend génère automatiquement le formulaire de configuration à partir de ce schéma — aucun formulaire codé à la main par stack. La chaîne complète :

```
stacks_definitions/*.yaml ──(chargement)──▶ table stacks (variables JSON)
        │
GET /api/v1/stacks/{id} ──▶ variables + default_name
        │
useDynamicForm(stack.variables) ──▶ formData (defaults) + fields (config champs)
        │
DynamicFormField.vue ──▶ composants Element Plus selon le type
        │
POST /api/v1/deployments { stack_id, target_id, name?, variables }
```

Le **format détaillé des variables** (champs, contraintes, types, exemples YAML) est spécifié dans [STACK-DEFINITIONS.md](STACK-DEFINITIONS.md) — ce document décrit la mécanique de rendu et de validation autour de ce schéma.

## État actuel vs cible — payload et terminologie

*État actuel (implémenté)* : la soumission appelle `POST /api/v1/deployments` avec `stack_id` + `target_id` (identifiant du Host, ex-*Target*) + `variables`. La ressource créée est un « deployment ».

*Cible (general_specs ch. 09)* : l'objet manipulé est une **App**, créée via `POST /apps` avec triple XOR `host_id` / `machine_id` / `cluster_id` ([09-api.md](../general_specs/09-api.md)) — ⚠️ **Non implémenté**. « Déploiement » désigne alors l'exécution d'une action d'installation/mise à jour. Table de correspondance complète dans le [README du corpus](README.md).

## Architecture

### 1. Backend — stockage du schéma

Les variables sont stockées en JSON dans la table `stacks`. Extrait réel — `backend/app/models/stack.py` :

```python
    # Variables configurables (format simple pour JSONForms)
    variables: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Variables configurables au format simple",
    )
```

La sérialisation part du schéma Pydantic `StackDefinitionVariable` (via `model_dump(mode="json", exclude_none=True)`, voir `stack_definitions_loader.py`) : les définitions servies à l'API portent donc les clés du schéma — `minimum`/`maximum` pour les bornes numériques, `enum`, `enum_labels`, `pattern`, `visible`, `group`, `variables` (sous-variables)…

### 2. Backend — endpoints de consommation

- `GET /api/v1/stacks/{stack_id}` — retourne le stack avec `variables` et `default_name` (rendu de `metadata.deployment_name` avec les macros des défauts, `backend/app/api/v1/stacks.py`).
- `POST /api/v1/stacks/{stack_id}/regenerate-variable/{variable_name}` — régénère la valeur d'une variable dont le défaut contient une macro (`generate_password`, `get_valid_port`… — catalogue dans [JINJA2-FUNCTIONS.md](JINJA2-FUNCTIONS.md)).

Au déploiement, `DeploymentService.create` fusionne defaults + valeurs utilisateur, **rend toutes les macros Jinja2** (variables, `target_parameters`, template) et persiste la configuration finale — le frontend ne reçoit jamais les macros brutes en retour.

### 3. Frontend — composable `useDynamicForm`

**Fichier** : `frontend/src/composables/useDynamicForm.ts`. Responsabilités : initialiser `formData` depuis les défauts (avec **notation pointée** pour les groupes imbriqués : `performance.shared_buffers`), exposer `fields` (config de rendu, champs `visible: false` filtrés, en-têtes de groupes), les règles de validation Element Plus, et `validateRequired()` / `getChanges()` / `getAllValues()`.

```typescript
import { useDynamicForm } from '@/composables/useDynamicForm'

const stack = await api.get(`/api/v1/stacks/${stackId}`)

const { formData, fields, validateRequired, getAllValues } = useDynamicForm(
  stack.variables
)
// formData — réactif, pré-rempli : { postgres_version: "16", host_port: 5432, … }
// fields   — config de rendu : [{ key: "postgres_version", type: "string", enum: […], … }]
```

### 4. Frontend — composant `DynamicFormField`

**Fichier** : `frontend/src/components/DynamicFormField.vue`. Rend le composant Element Plus selon le type (tableau ci-dessous), affiche la description en aide contextuelle, un bouton de régénération pour les champs à macro (`has_macro` → emit `regenerate`), et les libellés `enum_labels` dans les listes déroulantes.

### 5. Frontend — vue `Deployments.vue`

**Fichier** : `frontend/src/views/Deployments.vue`. Flux du dialog de création :

1. Sélection du stack → `onStackChange()` : `GET /stacks/{id}`, pré-remplissage du nom avec `default_name`, instanciation `useDynamicForm(data.variables)`.
2. Champs dynamiques v-model → `form`.
3. Validation (formulaire de base + règles dynamiques).
4. Soumission — extrait réel de la construction du payload (`Deployments.vue`, `handleCreate`) :

```typescript
    const payload: any = {
      stack_id: form.stack_id,
      target_id: form.target_id
    }

    // Ajouter le nom si fourni
    if (form.name && form.name.trim()) {
      payload.name = form.name.trim()
    }

    // Extraire les champs dynamiques pour les variables
    const dynamicVariables: Record<string, any> = {}
    Object.entries(form).forEach(([key, value]) => {
      if (!staticKeys.includes(key)) {
        dynamicVariables[key] = value
      }
    })
```

## Mapping type → composant Element Plus

| Type de variable | Composant | Notes |
|---|---|---|
| `string` + `enum` | `<el-select>` | libellés `enum_labels` si présents |
| `number`/`integer` + `enum` | `<el-select>` | choix numérique |
| `password` | `<el-input type="password">` | masqué + toggle + régénération si macro |
| `number` / `integer` | `<el-input-number>` | `precision=0` pour `integer` (heures : `number` à défaut/min/max entiers) |
| `boolean` | `<el-switch>` | |
| `textarea` | champ multi-lignes | rendu texte long (certains types de configuration) |
| `group` | en-tête de section | sous-champs aplatis en notation pointée |
| `string` (défaut) | `<el-input>` | |

## Exemple complet — PostgreSQL

Définition réelle (extraits de `stacks_definitions/postgresql.yaml`) — noter les bornes en `minimum`/`maximum` :

```yaml
variables:
  postgres_version:
    type: string
    label: "Version PostgreSQL"
    description: "Version de PostgreSQL à déployer"
    default: "16"
    enum:
      - "16"
      - "15"
      - "14"
    required: true
    group: "Configuration générale"

  postgres_password:
    type: password
    label: "Mot de passe PostgreSQL"
    default: "{{ generate_password(24) }}"
    required: true
    min_length: 12
    group: "Sécurité"

  host_port:
    type: integer
    label: "Port hôte"
    default: "{{get_valid_port(5432)}}"
    minimum: 1
    maximum: 65535
    required: true
    group: "Configuration réseau"
```

Formulaire généré :

```
┌─────────────────────────────────────────────────┐
│ Stack             [PostgreSQL ▼]                │
│ Host              [Docker Local ▼]              │
│ Nom (optionnel)   [bright-dolphin        ]      │
│                                                  │
│ ──────── Configuration des variables ────────   │
│ Version PostgreSQL [16 ▼]                       │
│   ℹ️ Version de PostgreSQL à déployer           │
│ Mot de passe PostgreSQL [••••••••] 👁 ↻         │
│ Port hôte   [5432] ▲▼                           │
│               [Annuler]    [Déployer]            │
└─────────────────────────────────────────────────┘
```

Payload réellement envoyée :

```json
{
  "stack_id": "stack-postgresql-uuid",
  "target_id": "target-docker-local-uuid",
  "name": "my-postgres-prod",
  "variables": {
    "postgres_version": "16",
    "postgres_password": "super_secure_password",
    "host_port": 5432
  }
}
```

## Validation

### Frontend (`useDynamicForm.getValidationRules`)

- `required` — bloquant à la soumission.
- `integer` — vérifie `Number.isInteger`.
- Bornes numériques et `pattern` (regex) sur les chaînes — voir l'écart ci-dessous.
- `enum` — le rendu en `el-select` limite de fait aux valeurs proposées.

### Backend

Validation stricte au chargement du YAML (Pydantic, voir [STACK-DEFINITIONS.md](STACK-DEFINITIONS.md)) ; au déploiement, fusion defaults + overrides utilisateur puis rendu Jinja2 des macros (erreurs de rendu = valeur originale conservée, voir [JINJA2-FUNCTIONS.md](JINJA2-FUNCTIONS.md)).

### ⚠️ Écart connu — bornes numériques `minimum`/`maximum` vs `min`/`max`

La sérialisation backend sert `minimum`/`maximum` (clés du schéma Pydantic), mais le composable lit `variable.min`/`variable.max` (`VariableDefinition` de `useDynamicForm.ts`) et `DynamicFormField.vue` bind `:min="field.min" :max="field.max"`. En l'état, **les bornes numériques ne s'appliquent pas au rendu ni à la validation frontend** pour les variables servies par l'API stacks. Le correctif (aligner le composable sur `minimum`/`maximum`, ou convertir à la frontière API) est à inscrire au backlog. Règle de rédaction des YAML en attendant : écrire `minimum`/`maximum` (validés par le schéma) — jamais `min:`/`max:`, ignorés silencieusement par Pydantic (constats R3/G15 de l'audit).

## Champs avancés du schéma

Le détail complet des champs vit dans [STACK-DEFINITIONS.md](STACK-DEFINITIONS.md) ; rappel de leur effet côté formulaire :

- **`group` + sous-variables récursives** (`type: group`) — en-tête de section + champs aplatis en notation pointée (`performance.shared_buffers`) ; groupes imbriqués supportés à tous niveaux.
- **`visible: false`** — variable technique exclue du rendu mais présente dans `formData` et le payload (ex. `container_name` généré par macro).
- **`enum_labels`** — libellés affichés dans les `el-select` à la place des valeurs brutes.
- **`depends_on`** — conditions d'affichage basées sur d'autres variables (déclaratif côté schéma ; non exploité par le composable actuel).
- **`has_macro` / `macro_template`** — remplis au rendu des défauts ; activent le bouton de régénération (`regenerate-variable`).
- **`target_parameters`** — paramètres spécifiques à la cible (ex. volumes à supprimer), rendus côté backend, hors formulaire.
- **`deployment_notes`** (markdown rendu) et **`deployment_name`**/`default_name` — affichés autour du formulaire (documentation, pré-remplissage du nom).

## Correspondance nomenclature — variables de stack ↔ configuration de plugin

Les champs de configuration des **plugins** (manifest, [ch. 11](../general_specs/11-plugins.md)) répondent aux mêmes besoins sous une nomenclature différente :

| Variables de stack (YAML `stacks_definitions/`) | Configuration de plugin (manifest ch. 11) |
|---|---|
| `enum` (champ) | type `select` |
| `textarea` | type `multiline` |
| `pattern` | `validation` (regex) |
| `default: "{{ generate_password(…) }}"` | `generate: true` (bouton « Générer ») |
| `visible: false` / `depends_on` | `visible_if` (conditionne à une capability/plugin) |

Deux mécanismes distincts : les variables de stack configurent un déploiement ; la configuration de plugin paramètre un Plugin installé (manifest/hooks, système du [ch. 11](../general_specs/11-plugins.md)).

## Ajout d'un nouveau stack

1. Créer `stacks_definitions/mon-stack.yaml` avec `metadata` (7 champs requis), `template` (macros Jinja2) et `variables` — guide complet dans [STACK-DEFINITIONS.md](STACK-DEFINITIONS.md) :

   ```yaml
   metadata:
     name: MonNouveauStack
     version: "1.0.0"
     category: "…"
     author: "…"
     license: "MIT"
     description: "…"
     target_type: "docker"

   template:
     image: "app:{{ app_version }}"

   variables:
     app_version:
       type: string
       label: "Version"
       default: "latest"
       required: true
   ```

2. Redémarrer le backend (seed automatique) — le formulaire est généré, **sans aucune modification du frontend**.

## Performances & sécurité

Rendu paresseux (formulaire instancié à la sélection du stack), réactivité Vue 3 ; côté sécurité : validation serveur systématique (jamais de confiance au client), secrets masqués (`password`), RBAC sur les endpoints — principes détaillés au [ch. 15 Sécurité](../general_specs/15-securite.md).

## Voir aussi

- [03-modele-compute.md](../general_specs/03-modele-compute.md) — fonctionnel des stacks/templates
- [09-api.md](../general_specs/09-api.md) — cible App (`POST /apps`, triple XOR)
- [11-plugins.md](../general_specs/11-plugins.md) — nomenclature de configuration des plugins
- [13-ui-principes.md](../general_specs/13-ui-principes.md) — principes UX des formulaires
- [STACK-DEFINITIONS.md](STACK-DEFINITIONS.md) — format YAML complet · [JINJA2-FUNCTIONS.md](JINJA2-FUNCTIONS.md) — fonctions des macros
