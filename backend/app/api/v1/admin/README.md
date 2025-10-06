# API d'Administration - WindFlow

## Vue d'Ensemble

L'API d'administration fournit des endpoints pour gérer les stacks marketplace de WindFlow. Ces endpoints **remplacent** les anciens scripts `seed_stacks.py` et `check_stacks.py` en offrant une interface REST complète et sécurisée.

### 🔒 Sécurité

**Tous les endpoints nécessitent l'authentification en tant que superadmin.**

```bash
# Obtenir un token d'authentification
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# Utiliser le token dans les requêtes
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/admin/stacks-management/definitions
```

## Endpoints Disponibles

### 📦 1. Gestion des Définitions YAML

#### GET `/api/v1/admin/stacks-management/definitions`

Liste toutes les définitions YAML de stacks disponibles dans `backend/app/stacks_definitions/`.

**Équivalent à :** `python -m app.scripts.seed_stacks --list`

**Réponse :**
```json
[
  {
    "filename": "nginx-stack.yaml",
    "name": "NGINX Web Server",
    "version": "1.0.0",
    "category": "web",
    "description": "Stack NGINX pour serveur web",
    "is_public": true,
    "tags": ["web", "nginx", "proxy"],
    "variables_count": 5,
    "is_valid": true,
    "validation_errors": null
  }
]
```

#### POST `/api/v1/admin/stacks-management/validate`

Valide toutes les définitions YAML sans les importer.

**Équivalent à :** `python -m app.scripts.seed_stacks --dry-run`

**Réponse :**
```json
{
  "total_files": 10,
  "valid": 9,
  "invalid": 1,
  "all_valid": false,
  "errors": [
    {
      "file": "invalid-stack.yaml",
      "error": "Missing required field: metadata.version"
    }
  ]
}
```

#### POST `/api/v1/admin/stacks-management/import`

Importe un ou tous les stacks depuis les définitions YAML.

**Équivalent à :** 
- `python -m app.scripts.seed_stacks` (tous les stacks)
- `python -m app.scripts.seed_stacks --stack NAME` (stack spécifique)
- `python -m app.scripts.seed_stacks --force` (avec force_update)

**Requête :**
```json
{
  "stack_name": "nginx-stack",  // optionnel, null = tous les stacks
  "force_update": false          // optionnel, forcer la mise à jour
}
```

**Réponse :**
```json
{
  "total": 10,
  "created": 5,
  "updated": 2,
  "skipped": 2,
  "errors": 1,
  "results": [
    {
      "stack_id": "uuid-here",
      "stack_name": "NGINX Web Server",
      "status": "created",
      "message": "Stack created successfully"
    }
  ]
}
```

#### GET `/api/v1/admin/stacks-management/imported`

Liste tous les stacks actuellement importés en base de données.

**Équivalent à :** `python -m app.scripts.check_stacks`

**Query Parameters :**
- `skip` (int): Nombre d'éléments à sauter (pagination)
- `limit` (int): Nombre max d'éléments (1-1000)
- `category` (string): Filtrer par catégorie
- `is_public` (bool): Filtrer par visibilité

**Réponse :**
```json
[
  {
    "id": "uuid-here",
    "name": "NGINX Web Server",
    "version": "1.0.0",
    "category": "web",
    "description": "Stack NGINX pour serveur web",
    "is_public": true,
    "tags": ["web", "nginx"],
    "variables": {...},
    "created_at": "2024-01-15T10:00:00Z"
  }
]
```

---

### 🔄 2. Synchronisation et Comparaison

#### GET `/api/v1/admin/stacks-management/sync/status`

Compare les définitions YAML avec les stacks en base de données.

**Réponse :**
```json
{
  "total_definitions": 15,
  "total_imported": 12,
  "new_stacks": ["new-stack-1", "new-stack-2"],
  "modified_stacks": ["updated-stack"],
  "up_to_date": ["stack-1", "stack-2"],
  "obsolete_stacks": ["old-stack"]
}
```

#### POST `/api/v1/admin/stacks-management/sync/auto`

Synchronisation automatique des stacks.

**Requête :**
```json
{
  "update_modified": true,    // Mettre à jour les stacks modifiés
  "import_new": true,         // Importer les nouveaux stacks
  "delete_obsolete": false    // ⚠️ Supprimer les stacks obsolètes (dangereux)
}
```

**Réponse :** Même format que `/import`

---

### 💾 3. Export et Backup

#### GET `/api/v1/admin/stacks-management/{stack_id}/export`

Exporte un stack en format YAML.

**Réponse :**
```json
{
  "metadata": {
    "name": "NGINX Web Server",
    "version": "1.0.0",
    "description": "...",
    "category": "web",
    "tags": ["web", "nginx"],
    "is_public": true
  },
  "template": "...",
  "variables": {...}
}
```

#### POST `/api/v1/admin/stacks-management/export/bulk`

Exporte plusieurs stacks.

**Requête :**
```json
{
  "stack_ids": ["uuid-1", "uuid-2"],
  "format": "yaml"  // ou "json"
}
```

---

### ⚙️ 4. Administration Avancée

#### PATCH `/api/v1/admin/stacks-management/{stack_id}/toggle-visibility`

Bascule la visibilité d'un stack (public ↔ privé).

#### POST `/api/v1/admin/stacks-management/{stack_id}/duplicate`

Duplique un stack existant.

**Requête :**
```json
{
  "new_name": "NGINX Web Server - Copy",
  "organization_id": "uuid-optional"
}
```

#### DELETE `/api/v1/admin/stacks-management/{stack_id}?force=false`

Supprime un stack.

**Query Parameters :**
- `force` (bool): Forcer la suppression même avec déploiements actifs

⚠️ **Attention :** Par défaut, refuse de supprimer si des déploiements existent.

---

### 📊 5. Statistiques et Monitoring

#### GET `/api/v1/admin/stacks-management/stats/overview`

Vue d'ensemble des statistiques des stacks.

**Réponse :**
```json
{
  "total_stacks": 50,
  "public_stacks": 30,
  "private_stacks": 20,
  "stacks_by_category": {
    "web": 15,
    "database": 10,
    "monitoring": 8
  },
  "most_deployed": [
    {
      "stack_id": "uuid",
      "name": "NGINX",
      "deployments": 125
    }
  ],
  "recently_added": [...]
}
```

#### GET `/api/v1/admin/stacks-management/{stack_id}/usage`

Statistiques d'usage d'un stack spécifique.

**Réponse :**
```json
{
  "stack_id": "uuid",
  "stack_name": "NGINX Web Server",
  "total_deployments": 125,
  "successful_deployments": 120,
  "failed_deployments": 5,
  "success_rate": 96.0,
  "organizations_using": 15,
  "last_deployment": "2024-01-20T14:30:00Z"
}
```

---

### 🔍 6. Recherche et Santé

#### GET `/api/v1/admin/stacks-management/health`

Vérifie la santé des stacks et détecte les problèmes.

**Réponse :**
```json
{
  "status": "healthy",  // ou "degraded"
  "total_issues": 0,
  "total_warnings": 2,
  "issues": [],
  "warnings": [
    {
      "type": "orphaned_stack",
      "stack_id": "uuid",
      "stack_name": "Old Stack",
      "message": "Stack en DB sans définition YAML"
    }
  ]
}
```

#### GET `/api/v1/admin/stacks-management/search`

Recherche avancée de stacks.

**Query Parameters :**
- `q` (string): Terme de recherche (nom ou description)
- `category` (string): Filtrer par catégorie
- `tags` (array): Filtrer par tags
- `is_public` (bool): Filtrer par visibilité
- `skip` (int): Pagination offset
- `limit` (int): Nombre max de résultats (1-100)

**Réponse :**
```json
{
  "total": 25,
  "skip": 0,
  "limit": 20,
  "results": [...]
}
```

---

## Exemples d'Utilisation

### Workflow Complet d'Import

```bash
# 1. Vérifier les définitions disponibles
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/stacks-management/definitions

# 2. Valider avant d'importer
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/stacks-management/validate

# 3. Importer tous les stacks
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"force_update": false}' \
  http://localhost:8000/api/v1/admin/stacks-management/import

# 4. Vérifier les stacks importés
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/stacks-management/imported
```

### Synchronisation Régulière

```bash
# 1. Vérifier le statut de synchronisation
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/stacks-management/sync/status

# 2. Synchroniser automatiquement
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"update_modified": true, "import_new": true, "delete_obsolete": false}' \
  http://localhost:8000/api/v1/admin/stacks-management/sync/auto
```

### Monitoring et Maintenance

```bash
# Vérifier la santé des stacks
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/stacks-management/health

# Voir les statistiques globales
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/stacks-management/stats/overview

# Statistiques d'un stack spécifique
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/stacks-management/{stack_id}/usage
```

---

## Migration depuis les Scripts

### Avant (scripts Python)

```bash
# Lister les stacks
python -m app.scripts.seed_stacks --list

# Valider
python -m app.scripts.seed_stacks --dry-run

# Importer
python -m app.scripts.seed_stacks
python -m app.scripts.seed_stacks --force
python -m app.scripts.seed_stacks --stack nginx-stack

# Vérifier
python -m app.scripts.check_stacks
```

### Après (API REST)

```bash
# Lister les stacks
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/stacks-management/definitions

# Valider
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/stacks-management/validate

# Importer
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  http://localhost:8000/api/v1/admin/stacks-management/import

curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"force_update": true}' \
  http://localhost:8000/api/v1/admin/stacks-management/import

curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stack_name": "nginx-stack"}' \
  http://localhost:8000/api/v1/admin/stacks-management/import

# Vérifier
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/admin/stacks-management/imported
```

---

## Codes de Statut HTTP

- `200 OK` - Succès
- `201 Created` - Ressource créée
- `400 Bad Request` - Requête invalide
- `401 Unauthorized` - Non authentifié
- `403 Forbidden` - Pas les permissions (non-superadmin)
- `404 Not Found` - Ressource non trouvée
- `409 Conflict` - Conflit (ex: stack déjà existant)
- `500 Internal Server Error` - Erreur serveur

---

## Intégration Frontend

Ces endpoints peuvent être facilement intégrés dans le frontend Vue.js pour créer une interface d'administration graphique :

- Dashboard de gestion des stacks
- Import/export par glisser-déposer
- Synchronisation en un clic
- Statistiques visuelles
- Monitoring temps réel

---

## Notes Importantes

1. **Sécurité** : Tous les endpoints nécessitent un token superadmin
2. **Performance** : Les endpoints sont optimisés avec pagination
3. **Atomicité** : Les opérations d'import sont transactionnelles
4. **Logging** : Toutes les opérations sont loggées
5. **Validation** : Validation stricte des entrées via Pydantic

---

**Version :** 1.0  
**Date :** 06/01/2025  
**Auteur :** Équipe WindFlow
