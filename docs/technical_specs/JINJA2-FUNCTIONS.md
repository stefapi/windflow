# Fonctions Jinja2 Disponibles - WindFlow

Ce document liste toutes les fonctions Jinja2 personnalisées disponibles dans les templates de déploiement WindFlow.

## Vue d'Ensemble

Les templates de stack peuvent utiliser des fonctions Jinja2 pour générer dynamiquement des valeurs lors du déploiement. Ces fonctions sont disponibles **pour tous les types de déploiement** (Docker containers, Docker Compose, etc.).

## Architecture

```
backend/app/helper/
├── jinja_functions.py      # Bibliothèque de fonctions Jinja2
└── template_renderer.py    # Renderer centralisé
```

Les services de déploiement (DockerService, DockerComposeService) utilisent tous le `TemplateRenderer` centralisé qui injecte automatiquement toutes les fonctions disponibles.

## Fonctions Disponibles

### 1. `generate_password(length=24, include_special=True)`

Génère un mot de passe sécurisé aléatoire.

**Paramètres:**
- `length` (int, default=24): Longueur du mot de passe
- `include_special` (bool, default=True): Inclure des caractères spéciaux

**Exemple:**
```yaml
environment:
  POSTGRES_PASSWORD: "{{ generate_password(32) }}"
  ADMIN_PASSWORD: "{{ generate_password(16, False) }}"  # Sans caractères spéciaux
```

**Caractères utilisés:**
- Lettres majuscules et minuscules: `A-Z`, `a-z`
- Chiffres: `0-9`
- Caractères spéciaux (si activé): `!@#$%^&*()-_=+`

---

### 2. `generate_secret(length=32)`

Génère un secret hexadécimal aléatoire (cryptographiquement sécurisé).

**Paramètres:**
- `length` (int, default=32): Longueur du secret en bytes

**Exemple:**
```yaml
environment:
  SECRET_KEY: "{{ generate_secret(64) }}"
  JWT_SECRET: "{{ generate_secret() }}"
```

**Output:** Chaîne hexadécimale de `length * 2` caractères

---

### 3. `random_string(length, charset='alphanumeric')`

Génère une chaîne aléatoire avec un jeu de caractères personnalisable.

**Paramètres:**
- `length` (int): Longueur de la chaîne
- `charset` (str): Type de caractères
  - `'alphanumeric'`: Lettres et chiffres
  - `'alpha'`: Lettres uniquement
  - `'numeric'`: Chiffres uniquement
  - `'hex'`: Hexadécimal (0-9, a-f)

**Exemple:**
```yaml
environment:
  SESSION_ID: "{{ random_string(16, 'hex') }}"
  USERNAME: "{{ random_string(8, 'alpha') }}"
```

---

### 4. `generate_uuid()`

Génère un UUID v4 aléatoire.

**Exemple:**
```yaml
labels:
  deployment.uuid: "{{ generate_uuid() }}"
```

**Output:** UUID au format standard (ex: `550e8400-e29b-41d4-a716-446655440000`)

---

### 5. `generate_uuid_short()`

Génère un UUID court (12 premiers caractères).

**Exemple:**
```yaml
container_name: "postgres_{{ generate_uuid_short() }}"
```

**Output:** UUID court (ex: `550e8400e29b`)

---

### 6. `base64_encode(value)`

Encode une valeur en Base64.

**Paramètres:**
- `value` (str): Valeur à encoder

**Exemple:**
```yaml
environment:
  CONFIG_ENCODED: "{{ base64_encode('my-config-data') }}"
```

---

### 7. `base64_decode(value)`

Décode une valeur Base64.

**Paramètres:**
- `value` (str): Valeur encodée à décoder

**Exemple:**
```yaml
environment:
  CONFIG_DECODED: "{{ base64_decode('bXktY29uZmlnLWRhdGE=') }}"
```

---

### 8. `hash_value(value, algorithm='sha256')`

Génère un hash d'une valeur.

**Paramètres:**
- `value` (str): Valeur à hasher
- `algorithm` (str): Algorithme de hash
  - `'md5'`
  - `'sha1'`
  - `'sha256'` (default)
  - `'sha512'`

**Exemple:**
```yaml
labels:
  config.hash: "{{ hash_value('my-config', 'sha256') }}"
```

---

### 9. `random_port(min_port=10000, max_port=65535)`

Génère un numéro de port aléatoire.

**Paramètres:**
- `min_port` (int, default=10000): Port minimum
- `max_port` (int, default=65535): Port maximum

**Exemple:**
```yaml
ports:
  - "{{ random_port(8000, 9000) }}:8080"
```

---

### 10. `env(var_name, default='')`

Récupère une variable d'environnement du système.

**Paramètres:**
- `var_name` (str): Nom de la variable d'environnement
- `default` (str, default=''): Valeur par défaut si non trouvée

**Exemple:**
```yaml
environment:
  DEPLOYMENT_ENV: "{{ env('WINDFLOW_ENV', 'production') }}"
  HOME_DIR: "{{ env('HOME') }}"
```

---

### 11. `now(format='%Y-%m-%d %H:%M:%S')`

Retourne la date/heure actuelle formatée.

**Paramètres:**
- `format` (str): Format de date Python strftime

**Exemple:**
```yaml
labels:
  deployed.at: "{{ now('%Y-%m-%d') }}"
  timestamp: "{{ now('%s') }}"  # Unix timestamp
```

**Formats courants:**
- `'%Y-%m-%d'`: 2024-01-15
- `'%Y-%m-%d %H:%M:%S'`: 2024-01-15 14:30:00
- `'%s'`: 1705329000 (Unix timestamp)

---

### 12. `random_choice(*choices)`

Choisit aléatoirement parmi plusieurs valeurs.

**Paramètres:**
- `*choices`: Liste de valeurs possibles

**Exemple:**
```yaml
environment:
  LOG_LEVEL: "{{ random_choice('INFO', 'DEBUG', 'WARNING') }}"
  REGION: "{{ random_choice('eu-west-1', 'us-east-1') }}"
```

---

## Exemples Complets

### Stack PostgreSQL avec Docker Container

```yaml
name: PostgreSQL Database
version: "1.0"
description: PostgreSQL standalone container
target_type: docker

template:
  image: postgres:16-alpine
  container_name: "postgres_{{ generate_uuid_short() }}"
  
  environment:
    POSTGRES_USER: admin
    POSTGRES_PASSWORD: "{{ generate_password(32) }}"
    POSTGRES_DB: windflow_db
    
  ports:
    - "5432:5432"
    
  volumes:
    - "postgres_data:/var/lib/postgresql/data"
    
  labels:
    app: postgres
    deployment.id: "{{ generate_uuid() }}"
    deployed.at: "{{ now('%Y-%m-%d %H:%M:%S') }}"
    config.hash: "{{ hash_value('postgres-v1', 'sha256') }}"
    
  restart_policy: unless-stopped
  
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U admin"]
    interval: 10s
    timeout: 5s
    retries: 5
```

### Stack Application Web avec Docker Compose

```yaml
name: Web Application Stack
version: "1.0"
description: Full web application with database
target_type: docker-compose

template:
  version: "3.8"
  
  services:
    web:
      image: nginx:alpine
      container_name: "web_{{ generate_uuid_short() }}"
      environment:
        APP_SECRET: "{{ generate_secret(64) }}"
        SESSION_KEY: "{{ random_string(32, 'hex') }}"
        DATABASE_URL: "postgresql://admin:{{ generate_password(24) }}@db:5432/appdb"
      ports:
        - "80:80"
      labels:
        deployment.env: "{{ env('WINDFLOW_ENV', 'production') }}"
        build.timestamp: "{{ now('%s') }}"
    
    db:
      image: postgres:16-alpine
      environment:
        POSTGRES_USER: admin
        POSTGRES_PASSWORD: "{{ generate_password(32) }}"
        POSTGRES_DB: appdb
      volumes:
        - db_data:/var/lib/postgresql/data
  
  volumes:
    db_data:
```

### Combinaison de Fonctions

```yaml
environment:
  # Mot de passe encodé en Base64
  ENCODED_PASSWORD: "{{ base64_encode(generate_password(24)) }}"
  
  # Hash du secret pour vérification
  SECRET_HASH: "{{ hash_value(generate_secret(), 'sha512') }}"
  
  # Nom unique combinant plusieurs fonctions
  INSTANCE_NAME: "app-{{ env('HOSTNAME', 'default') }}-{{ generate_uuid_short() }}"
  
  # Port aléatoire dans une plage spécifique
  APP_PORT: "{{ random_port(3000, 4000) }}"
```

## Bonnes Pratiques

### 1. Sécurité des Mots de Passe

**✅ Bon:**
```yaml
POSTGRES_PASSWORD: "{{ generate_password(32) }}"  # Longueur sécurisée
API_SECRET: "{{ generate_secret(64) }}"           # Secret cryptographique
```

**❌ Mauvais:**
```yaml
POSTGRES_PASSWORD: "{{ generate_password(8) }}"   # Trop court
API_SECRET: "{{ random_string(16) }}"             # Pas assez sécurisé
```

### 2. Nommage des Containers

**✅ Bon:**
```yaml
container_name: "postgres_{{ generate_uuid_short() }}"  # Unique et court
```

**❌ Mauvais:**
```yaml
container_name: "postgres_{{ generate_uuid() }}"  # Trop long pour un nom
```

### 3. Labels et Metadata

**✅ Bon:**
```yaml
labels:
  deployment.id: "{{ generate_uuid() }}"
  deployed.at: "{{ now('%Y-%m-%d %H:%M:%S') }}"
  config.version: "1.0"
```

### 4. Variables d'Environnement

**✅ Bon:**
```yaml
DEPLOYMENT_ENV: "{{ env('WINDFLOW_ENV', 'production') }}"  # Avec fallback
```

**❌ Mauvais:**
```yaml
DEPLOYMENT_ENV: "{{ env('WINDFLOW_ENV') }}"  # Pas de fallback
```

## Debugging et Validation

### Vérifier les Fonctions Disponibles

```python
from backend.app.helper.template_renderer import default_renderer

# Lister toutes les fonctions
functions = default_renderer.get_available_functions()
for name, doc in functions.items():
    print(f"{name}: {doc}")
```

### Tester un Template

```python
from backend.app.helper.template_renderer import render_template

template = {
    "environment": {
        "PASSWORD": "{{ generate_password(16) }}",
        "SECRET": "{{ generate_secret() }}"
    }
}

result = render_template(template, {})
print(result)
# {
#   "environment": {
#     "PASSWORD": "aB3$fG7&kL9@pQ2!",
#     "SECRET": "a1b2c3d4e5f6..."
#   }
# }
```

### Valider un Template

```python
from backend.app.helper.template_renderer import default_renderer

template = {"env": {"KEY": "{{ generate_password(24) }}"}}

is_valid, errors = default_renderer.validate_template(template)
if not is_valid:
    print("Erreurs:", errors)
```

## Extensibilité

### Ajouter une Nouvelle Fonction

1. **Ajouter la fonction dans `jinja_functions.py`:**

```python
class JinjaFunctions:
    @staticmethod
    def my_custom_function(param: str) -> str:
        """Description de ma fonction."""
        return f"processed_{param}"
```

2. **Enregistrer dans `JINJA_FUNCTIONS`:**

```python
JINJA_FUNCTIONS = {
    # ... fonctions existantes
    'my_custom_function': JinjaFunctions.my_custom_function,
}
```

3. **Utiliser dans les templates:**

```yaml
environment:
  VALUE: "{{ my_custom_function('test') }}"
```

## Limitations

1. **Pas de modification d'état**: Les fonctions sont stateless et ne peuvent pas modifier l'état global
2. **Pas d'accès réseau**: Les fonctions ne peuvent pas faire d'appels HTTP/API externes
3. **Performances**: Éviter les boucles complexes dans les templates
4. **Sécurité**: Ne jamais passer de données utilisateur non validées aux fonctions

## Support

Pour toute question ou suggestion de nouvelles fonctions, créer une issue sur le dépôt WindFlow.

---

**Version:** 1.0  
**Dernière mise à jour:** 29/11/2024  
**Auteur:** Équipe WindFlow
