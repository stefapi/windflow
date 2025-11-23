# Formulaires Dynamiques de Déploiement - WindFlow

## Vue d'Ensemble

Le système de formulaires dynamiques permet de générer automatiquement des interfaces de configuration basées sur les définitions de variables des stacks. Cette approche élimine le besoin de coder manuellement chaque formulaire pour chaque stack.

## Architecture

### 1. Backend - Définition des Variables

Les stacks stockent leurs variables configurables dans le champ JSON `variables` :

```python
# backend/app/models/stack.py
class Stack(Base):
    variables: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Variables configurables au format simple"
    )
```

**Format des variables** (depuis postgresql.yaml) :

```yaml
variables:
  postgres_version:
    type: string
    label: "Version PostgreSQL"
    description: "Version de PostgreSQL à déployer"
    default: "16"
    required: true
    enum: ["14", "15", "16", "17"]
  
  postgres_password:
    type: password
    label: "Mot de passe root"
    description: "Mot de passe super-utilisateur PostgreSQL"
    default: "postgres"
    required: true
  
  postgres_port:
    type: integer
    label: "Port PostgreSQL"
    description: "Port d'écoute de PostgreSQL"
    default: 5432
    min: 1024
    max: 65535
    required: true
```

### 2. Backend - Génération Automatique

**Endpoint API** : `GET /api/v1/stacks/{stack_id}`

Retourne la structure complète incluant les variables :

```json
{
  "id": "stack-uuid",
  "name": "PostgreSQL",
  "variables": {
    "postgres_version": {
      "type": "string",
      "label": "Version PostgreSQL",
      "default": "16",
      "enum": ["14", "15", "16", "17"],
      "required": true
    },
    "postgres_password": {
      "type": "password",
      "label": "Mot de passe root",
      "default": "postgres",
      "required": true
    }
  },
  "template": { /* Docker Compose config */ }
}
```

**Service de Déploiement** (`backend/app/services/deployment_service.py`) :

1. **Merge des variables** : Combine les defaults du stack + overrides utilisateur
2. **Rendu du template** : Remplace les `{{ variable }}` dans le template Docker
3. **Génération du config** : Crée la configuration finale Docker Compose
4. **Auto-génération du nom** : Crée un nom unique si absent

```python
async def create(db, deployment_data, organization_id, user_id):
    stack = await get_stack(db, deployment_data.stack_id)
    
    # 1. Générer le nom si absent
    name = deployment_data.name or f"{stack.name}-{timestamp}"
    
    # 2. Merger variables (defaults + user overrides)
    variables = merge_variables(stack.variables, deployment_data.variables)
    
    # 3. Rendre le template avec les variables
    config = render_template(stack.template, variables)
    
    # 4. Créer le déploiement
    deployment = Deployment(name=name, config=config, variables=variables, ...)
```

### 3. Frontend - Composable useDynamicForm

**Fichier** : `frontend/src/composables/useDynamicForm.ts`

**Responsabilités** :
- Initialiser les valeurs par défaut depuis les définitions
- Générer la configuration des champs pour le rendu
- Valider les champs requis
- Gérer les règles de validation (min, max, pattern)

**Utilisation** :

```typescript
import { useDynamicForm } from '@/composables/useDynamicForm'

const stack = await api.get(`/api/v1/stacks/${stackId}`)

// Créer l'instance du formulaire dynamique
const { formData, fields, validateRequired, getAllValues } = useDynamicForm(
  stack.variables
)

// formData est réactif et pré-rempli avec les defaults
console.log(formData)
// { postgres_version: "16", postgres_password: "postgres", postgres_port: 5432 }

// fields contient la configuration pour le rendu
console.log(fields.value)
// [
//   { key: "postgres_version", type: "string", enum: [...], default: "16", ... },
//   { key: "postgres_password", type: "password", default: "postgres", ... },
//   ...
// ]
```

### 4. Frontend - Composant DynamicFormField

**Fichier** : `frontend/src/components/DynamicFormField.vue`

**Responsabilités** :
- Rendre le bon composant Element Plus selon le type
- Gérer la validation et les contraintes
- Afficher les descriptions contextuelles

**Types supportés** :

| Type Variable | Composant Element Plus | Options |
|--------------|----------------------|---------|
| `string` + `enum` | `<el-select>` | Dropdown avec options |
| `number`/`integer` + `enum` | `<el-select>` | Dropdown numérique |
| `password` | `<el-input type="password">` | Champ masqué avec toggle |
| `number`/`integer` | `<el-input-number>` | Input numérique avec min/max |
| `boolean` | `<el-switch>` | Switch on/off |
| `string` (défaut) | `<el-input>` | Input texte standard |

**Exemple de rendu** :

```vue
<template>
  <!-- String avec enum → Select -->
  <el-select v-if="field.enum && field.type === 'string'">
    <el-option v-for="opt in field.enum" :value="opt" />
  </el-select>
  
  <!-- Password → Input password -->
  <el-input v-else-if="field.type === 'password'" type="password" show-password />
  
  <!-- Number → Input number -->
  <el-input-number v-else-if="field.type === 'number'" :min="field.min" :max="field.max" />
  
  <!-- Boolean → Switch -->
  <el-switch v-else-if="field.type === 'boolean'" />
  
  <!-- String par défaut → Input text -->
  <el-input v-else />
</template>
```

### 5. Frontend - Vue Deployments

**Fichier** : `frontend/src/views/Deployments.vue`

**Flux de création de déploiement** :

1. **Ouverture du dialog** → Reset du formulaire
2. **Sélection du stack** → `onStackChange()` :
   - Récupère les variables du stack sélectionné
   - Initialise le formulaire dynamique avec `useDynamicForm(stack.variables)`
   - Pré-remplit les champs avec les valeurs par défaut
3. **Modification des valeurs** → Formulaire réactif via v-model
4. **Validation** :
   - Validation du formulaire de base (stack_id, target_id)
   - Validation des champs requis du formulaire dynamique
5. **Soumission** :
   ```typescript
   const payload = {
     stack_id: form.stack_id,
     target_id: form.target_id,
     name: form.name || undefined,  // Optionnel
     variables: dynamicFormInstance.getAllValues()
   }
   await api.post('/api/v1/deployments', payload)
   ```

## Exemple Complet : PostgreSQL

### 1. Définition dans postgresql.yaml

```yaml
metadata:
  name: PostgreSQL
  version: "1.0.0"
  
template:
  version: "3.8"
  services:
    postgres:
      image: "postgres:{{ postgres_version }}"
      environment:
        POSTGRES_PASSWORD: "{{ postgres_password }}"
        POSTGRES_DB: "{{ postgres_db }}"
      ports:
        - "{{ postgres_port }}:5432"

variables:
  postgres_version:
    type: string
    label: "Version PostgreSQL"
    default: "16"
    enum: ["14", "15", "16", "17"]
    required: true
  
  postgres_password:
    type: password
    label: "Mot de passe root"
    default: "postgres"
    required: true
  
  postgres_db:
    type: string
    label: "Nom de la base de données"
    default: "windflow"
    required: true
  
  postgres_port:
    type: integer
    label: "Port PostgreSQL"
    default: 5432
    min: 1024
    max: 65535
    required: true
```

### 2. Formulaire généré automatiquement

Le frontend génère automatiquement ce formulaire :

```
┌─────────────────────────────────────────────────┐
│ Stack             [PostgreSQL ▼]                │
│ Target            [Docker Local ▼]              │
│ Nom (optionnel)   [                         ]   │
│                                                  │
│ ──────── Configuration des variables ────────   │
│                                                  │
│ Version PostgreSQL [16 ▼]                       │
│   ℹ️ Version de PostgreSQL à déployer           │
│                                                  │
│ Mot de passe root [••••••••] 👁                 │
│   ℹ️ Mot de passe super-utilisateur PostgreSQL  │
│                                                  │
│ Nom de la BD      [windflow              ]      │
│   ℹ️ Nom de la base de données                  │
│                                                  │
│ Port PostgreSQL   [5432] ▲▼                     │
│   ℹ️ Port d'écoute de PostgreSQL                │
│                                                  │
│               [Annuler]    [Déployer]            │
└─────────────────────────────────────────────────┘
```

### 3. Payload envoyée au backend

```json
{
  "stack_id": "stack-postgresql-uuid",
  "target_id": "target-docker-local-uuid",
  "name": "my-postgres-prod",
  "variables": {
    "postgres_version": "16",
    "postgres_password": "super_secure_password",
    "postgres_db": "production_db",
    "postgres_port": 5432
  }
}
```

### 4. Backend génère la configuration finale

```yaml
version: "3.8"
services:
  postgres:
    image: "postgres:16"  # ← Variable substituée
    environment:
      POSTGRES_PASSWORD: "super_secure_password"  # ← Variable substituée
      POSTGRES_DB: "production_db"  # ← Variable substituée
    ports:
      - "5432:5432"  # ← Variable substituée
```

## Avantages de l'Approche

### ✅ Pour les Développeurs

- **Zéro code frontend** pour ajouter un nouveau stack
- **Type-safe** : TypeScript strict + validation Pydantic
- **Réutilisable** : Composant et composable génériques
- **Maintenable** : Un seul endroit pour gérer les formulaires

### ✅ Pour les Utilisateurs

- **Interface cohérente** : Tous les stacks utilisent la même UI
- **Valeurs par défaut** : Pré-remplies intelligemment
- **Validation temps réel** : Feedback immédiat sur les erreurs
- **Aide contextuelle** : Descriptions pour chaque champ

### ✅ Pour la Plateforme

- **Scalable** : Ajout facile de nouveaux stacks
- **Flexible** : Supporte tous les types de champs courants
- **Sécurisé** : Validation côté client ET serveur
- **Extensible** : Facile d'ajouter de nouveaux types de champs

## Ajout d'un Nouveau Stack

Pour ajouter un nouveau stack avec formulaire dynamique :

1. **Créer le fichier YAML** dans `stacks_definitions/` :
   ```yaml
   metadata:
     name: MonNouveauStack
   
   template:
     # Votre config Docker Compose avec {{ variables }}
   
   variables:
     ma_variable:
       type: string
       label: "Ma Variable"
       default: "valeur_par_defaut"
       required: true
   ```

2. **Charger le stack** : Le système charge automatiquement tous les `.yaml`

3. **C'est tout !** Le formulaire est généré automatiquement

Aucune modification du frontend nécessaire ! 🎉

## Types de Variables Supportés

| Type | Description | Validation |
|------|-------------|-----------|
| `string` | Texte libre | pattern (regex optionnel) |
| `password` | Texte masqué | pattern (regex optionnel) |
| `number` | Nombre décimal | min, max |
| `integer` | Nombre entier | min, max |
| `boolean` | Vrai/Faux | - |
| `string` + `enum` | Choix dans liste | enum obligatoire |
| `number` + `enum` | Choix numérique | enum obligatoire |

## Validation

### Frontend

- **Champs requis** : Empêche la soumission si vide
- **Min/Max** : Pour les nombres
- **Pattern** : Regex pour les strings
- **Enum** : Limite aux choix disponibles

### Backend

- **Pydantic V2** : Validation stricte des types
- **Merge intelligent** : Combine defaults + overrides
- **Render sécurisé** : Jinja2 avec échappement
- **Validation métier** : Dans DeploymentService

## Performances

- **Lazy loading** : Formulaire créé seulement quand stack sélectionné
- **Réactivité Vue 3** : Updates optimisées
- **Cache côté client** : Stacks chargés une fois
- **Validation progressive** : Feedback temps réel

## Sécurité

- **Secrets masqués** : Type `password` avec show/hide
- **Validation serveur** : Jamais de confiance client seul
- **Échappement Jinja2** : Protection contre injection
- **RBAC** : Vérification des permissions

---

**Documentation mise à jour** : 23/11/2025  
**Version WindFlow** : 1.0.0
