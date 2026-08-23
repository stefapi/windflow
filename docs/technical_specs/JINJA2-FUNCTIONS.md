# Fonctions Jinja2 des templates de stack

> **Statut** : Spécification technique · Implémenté — **refondu (vague 2) — 2026-08-23**
> **Périmètre** : Catalogue exhaustif des fonctions Jinja2 personnalisées injectées dans les templates de stack (signatures, sorties exactes, exemples réels, debug, extensibilité).
> **Référence de fond** : [general_specs — 05 Stack technologique](../general_specs/05-stack-technologique.md) · [12 Marketplace](../general_specs/12-marketplace.md)
> **Dernière mise à jour** : 2026-08-23 — refonte pilotée par [PLAN-REFONTE-TECHNICAL-SPECS.md](../../PLAN-REFONTE-TECHNICAL-SPECS.md)

> **Terminologie** : ce document emploie le vocabulaire canonique du glossaire
> ([19-glossaire.md](../general_specs/19-glossaire.md)). Les identifiants du code historique
> (`target_id`, `TargetType`…) sont cités entre backticks et mis en correspondance à la première occurrence.

## Vue d'ensemble

Les templates de stack (YAML de `stacks_definitions/` — format détaillé dans [STACK-DEFINITIONS.md](STACK-DEFINITIONS.md)) peuvent utiliser des fonctions Jinja2 pour générer dynamiquement des valeurs lors du déploiement : secrets, identifiants, ports, horodatage. Ce catalogue couvre les **16 fonctions** enregistrées dans le dictionnaire `JINJA_FUNCTIONS` de `backend/app/helper/jinja_functions.py` — exhaustif, vérifié ligne à ligne contre le code. Les fonctions s'utilisent dans `template` mais aussi dans les valeurs `default` des variables et dans `deployment_name`/`deployment_notes`.

Les deux emplacements d'usage réels :

- **Dans le `template`** — substitution au moment du déploiement, avec les valeurs finales des variables :

  ```yaml
  # stacks_definitions/postgresql.yaml (réel) — template (extrait)
  template:
    image: "postgres:{{ postgres_version }}"
    container_name: "{{ deployment_name }}"
    environment:
      POSTGRES_PASSWORD: "{{ postgres_password }}"
    ports:
      - "{{ host_port }}:5432"
  ```

- **Dans les `default` des variables** — rendu au chargement du stack (la valeur générée est servie à l'UI, marquée `has_macro`, régénérable via `POST /api/v1/stacks/{id}/regenerate-variable/{name}`) :

  ```yaml
  # stacks_definitions/postgresql.yaml (réel) — defaults à macro (extrait)
  variables:
    container_name:
      default: "{{generate_animalname('postgres')}}"
    volume_name:
      default: "{{generate_cosmicname('postgres-data')}}"
    postgres_password:
      default: "{{ generate_password(24) }}"
    host_port:
      default: "{{get_valid_port(5432)}}"
  ```

**Syntaxe d'appel** : Jinja2 standard — `{{ nom_fonction(args) }}`. Les arguments littéraux présents dans les YAML du dépôt sont des chaînes (guillemets simples ou doubles, ex. `generate_animalname('postgres')`) et des entiers (ex. `generate_password(24)`, `get_valid_port(5432)`) ; les arguments nommés fonctionnent aussi (ex. `get_valid_port(5432, max_attempts=50)`). Une référence de variable (`{{ host_port }}`) n'est **pas** un appel de fonction : elle est substituée par la valeur choisie dans le formulaire (mécanique des formulaires dans [DYNAMIC-FORMS.md](DYNAMIC-FORMS.md)). En cas d'appel à une fonction inconnue ou d'argument invalide, le rendu de la valeur échoue et la macro brute est conservée dans la config (voir § Debug et validation).

## Architecture

```
backend/app/helper/
├── jinja_functions.py      # Bibliothèque JINJA_FUNCTIONS (16 fonctions)
├── animalname.py           # Générateur de noms d'animaux (pour generate_animalname)
├── cosmicname.py           # Générateur de noms d'astres (pour generate_cosmicname)
├── mythologyname.py        # Générateur de noms mythologiques (pour generate_mythologyname)
└── template_renderer.py    # Renderer centralisé (TemplateRenderer + default_renderer)
```

Les services de déploiement n'appellent jamais Jinja2 directement : tous passent par le renderer centralisé (`TemplateRenderer`), qui injecte automatiquement l'ensemble des fonctions (`DeploymentService._render_template` → `renderer.render_string` ; `stacks.py` pour `default_name` et `regenerate-variable`). Le rendu est **récursif** sur les dictionnaires et listes (chaque chaîne est un template Jinja2), et en cas d'erreur (syntaxe, variable non définie) la valeur originale est retournée sans interrompre le déploiement — comportement à connaître lors du debug.

## Catalogue des fonctions

Tableau de synthèse (les sections suivantes détaillent chacune) :

| # | Fonction | Rôle | Sortie |
|---|---|---|---|
| 1 | `generate_password(length=24, include_special=True)` | Mot de passe aléatoire | `length` caractères |
| 2 | `generate_secret(length=32)` | Secret hexadécimal | `length` caractères hex minuscules |
| 3 | `random_string(length, charset='alphanumeric')` | Chaîne aléatoire contrainte | `length` caractères |
| 4 | `generate_uuid()` | UUID v4 | 36 caractères (avec tirets) |
| 5 | `generate_uuid_short()` | UUID v4 compact | 32 caractères (**sans** tirets) |
| 6 | `base64_encode(value)` | Encodage Base64 | str |
| 7 | `base64_decode(value)` | Décodage Base64 | str |
| 8 | `hash_value(value, algorithm='sha256')` | Hash | hex digest |
| 9 | `random_port(min_port=10000, max_port=65535)` | Port aléatoire dans une plage | int |
| 10 | `get_valid_port(start_port=5432, max_attempts=100)` | Premier port réellement libre | int |
| 11 | `env(var_name, default='')` | Variable d'environnement du système | str |
| 12 | `now(format='%Y-%m-%d %H:%M:%S')` | Date/heure courante formatée | str |
| 13 | `random_choice(*choices)` | Choix aléatoire | une des valeurs |
| 14 | `generate_animalname(name='', style=None)` | Nom de code « animaux » | `name-<adjectif>-<animal>[-suffixe]` |
| 15 | `generate_cosmicname(name='', style=None)` | Nom de code « astres » | `name-<adjectif>-<astre>[-suffixe]` |
| 16 | `generate_mythologyname(name='', style=None)` | Nom de code « mythologie » | `name-<adjectif>-<mythologie>[-suffixe]` |

### 1. `generate_password(length=24, include_special=True)`

Mot de passe aléatoire cryptographiquement sûr (`secrets.choice`).

- `length` — longueur **exacte** de la sortie (défaut 24).
- `include_special` — si `True` : lettres + chiffres + `!@#$%^&*()-_=+` ; si `False` : alphanumérique uniquement.

```yaml
# stacks_definitions/postgresql.yaml (réel)
  postgres_password:
    type: password
    default: "{{ generate_password(24) }}"
```

### 2. `generate_secret(length=32)` ⚠️ correction d'une erreur historique de ce document

Secret **hexadécimal** aléatoire (minuscules, `0-9a-f`), cryptographiquement sûr. **`length` est la longueur de la sortie en caractères** : `generate_secret(64)` produit une chaîne de **64 caractères hex**. L'ancienne version de ce document annonçait `length * 2` caractères (« bytes ») — c'était inexact. Implémentation réelle (`backend/app/helper/jinja_functions.py`) :

```python
    @staticmethod
    def generate_secret(length: int = 32) -> str:
        """…"""
        # Génère length/2 bytes puis convertit en hex
        num_bytes = (length + 1) // 2
        random_bytes = secrets.token_bytes(num_bytes)
        hex_string = random_bytes.hex()
        return hex_string[:length]
```

`secrets.token_bytes((length+1)//2)` fournit `ceil(length/2)` octets (64 bits d'entropie pour 16 caractères), convertis en hex puis tronqués à `length` — la sortie fait toujours exactement `length` caractères hex minuscules.

```yaml
environment:
  SECRET_KEY: "{{ generate_secret(64) }}"   # → 64 caractères hex
  JWT_SECRET: "{{ generate_secret() }}"     # → 32 caractères hex
```

### 3. `random_string(length, charset='alphanumeric')`

Chaîne aléatoire selon un charset nommé — contrairement à `generate_secret`, le résultat n'est pas contraint à l'hexa.

- `charset` ∈ `'alphanumeric'` (lettres+chiffres), `'alpha'` (lettres), `'numeric'` (chiffres), `'hex'` (`0-9a-f`).

```yaml
environment:
  SESSION_ID: "{{ random_string(16, 'hex') }}"
  USERNAME: "{{ random_string(8, 'alpha') }}"
```

### 4. `generate_uuid()`

UUID v4 aléatoire, format standard **36 caractères avec tirets** (ex. `550e8400-e29b-41d4-a716-446655440000`).

```yaml
labels:
  deployment.uuid: "{{ generate_uuid() }}"
```

### 5. `generate_uuid_short()` ⚠️ correction d'une erreur historique de ce document

UUID v4 **sans les tirets** : `str(uuid.uuid4()).replace("-", "")` — soit **32 caractères hex**, pas « les 12 premiers caractères » comme indiqué précédemment. Utile pour des noms d'objets où les tirets sont interdits.

```yaml
container_name: "postgres_{{ generate_uuid_short() }}"   # → postgres_<32 hex>
```

### 6. `base64_encode(value)`

Encode une chaîne UTF-8 en Base64 (ex. `base64_encode('hello')` → `aGVsbG8=`).

```yaml
environment:
  CONFIG_ENCODED: "{{ base64_encode('my-config-data') }}"
```

### 7. `base64_decode(value)`

Décode une chaîne Base64 en UTF-8 (réciproque de la précédente).

```yaml
environment:
  CONFIG_DECODED: "{{ base64_decode('bXktY29uZmlnLWRhdGE=') }}"
```

### 8. `hash_value(value, algorithm='sha256')`

Hash hexadécimal d'une valeur UTF-8. `algorithm` ∈ `'md5'`, `'sha1'`, `'sha256'` (défaut), `'sha512'`.

```yaml
labels:
  config.hash: "{{ hash_value('postgres-v1', 'sha256') }}"
```

### 9. `random_port(min_port=10000, max_port=65535)`

Port **aléatoire** (uniforme) dans la plage inclusive `[min_port, max_port]` — sans vérifier s'il est libre : pour un port garanti disponible, utiliser `get_valid_port`.

```yaml
ports:
  - "{{ random_port(8000, 9000) }}:8080"
```

### 10. `get_valid_port(start_port=5432, max_attempts=100)` — nouvelle documentation

Retourne le **premier port réellement disponible** à partir de `start_port` : la fonction tente de binder un socket TCP sur chaque port séquentiellement (`start_port`, `start_port+1`, …) et retourne le premier bind réussi. Lève `RuntimeError` si aucun port libre dans `[start_port, start_port + max_attempts - 1]` ou si la plage dépasse 65535. Extrait réel — `backend/app/helper/jinja_functions.py` :

```python
        for offset in range(max_attempts):
            port = start_port + offset
            if port > 65535:
                raise RuntimeError(
                    "Aucun port disponible trouvé. Dépassement de la plage valide (65535)"
                )
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(("", port))
                    return port
            except OSError:
                continue
```

⚠️ La disponibilité est testée **au moment du rendu, côté backend** — pas au moment où le container écoutera effectivement ; une collision reste possible entre le rendu et le démarrage. Utilisation réelle :

```yaml
# stacks_definitions/postgresql.yaml (réel)
  host_port:
    type: integer
    default: "{{get_valid_port(5432)}}"
```

### 11. `env(var_name, default='')`

Lit une variable d'environnement **du système où tourne le backend** (pas de l'App déployée). Toujours fournir un `default`.

```yaml
environment:
  DEPLOYMENT_ENV: "{{ env('WINDFLOW_ENV', 'production') }}"
```

### 12. `now(format='%Y-%m-%d %H:%M:%S')`

Date/heure courante (UTC, `datetime.utcnow()`) au format strftime fourni.

```yaml
labels:
  deployed.at: "{{ now('%Y-%m-%d') }}"
```

### 13. `random_choice(*choices)`

Choisit uniformément une valeur parmi les arguments (au moins une requise, sinon `ValueError`).

```yaml
environment:
  LOG_LEVEL: "{{ random_choice('INFO', 'DEBUG', 'WARNING') }}"
```

### 14. `generate_animalname(name='', style=None)` — nouvelle documentation

Nom de code mémorable basé sur des animaux, préfixé : `name + "-" + <adjectif>-<animal>` (préfixe vide → nom nu, ex. `bright-dolphin`). Générateur : `backend/app/helper/animalname.py`. Paramètre `style` :

| Style | Format | Exemple |
|---|---|---|
| `None` (défaut) | adjectif-animal | `bright-dolphin` |
| `"ubuntu"` | adjectif-animal-suffixe | `bright-dolphin-a3f` |
| `"docker"` | adverbe-animal-suffixe | `quietly-tiger-b4k2` |
| `"full"` | préverbe-adverbe-adjectif-animal-suffixe | le plus long |

```yaml
# stacks_definitions/postgresql.yaml (réel)
  container_name:
    default: "{{generate_animalname('postgres')}}"   # → postgres-bright-dolphin
    visible: false
```

### 15. `generate_cosmicname(name='', style=None)` — nouvelle documentation

Identique à `generate_animalname` mais sur un vocabulaire d'**astres** (`backend/app/helper/cosmicname.py`) : adjectif-astre (ex. `bright-sun`), mêmes styles `ubuntu`/`docker`/`full`.

```yaml
# stacks_definitions/postgresql.yaml (réel)
  volume_name:
    default: "{{generate_cosmicname('postgres-data')}}"   # → postgres-data-bright-sun
```

### 16. `generate_mythologyname(name='', style=None)` — nouvelle documentation

Identique aux deux précédentes sur un vocabulaire **mythologique** (`backend/app/helper/mythologyname.py`) : adjectif-être mythologique (ex. `bright-zeus`), mêmes styles.

```yaml
environment:
  INSTANCE_NAME: "{{ generate_mythologyname('wf') }}"   # → wf-bright-zeus
```

## Exemples complets

Les exemples complets au format réel (métadonnées complètes `author`/`license` comprises) sont ceux du dépôt — voir `stacks_definitions/postgresql.yaml` (container simple) et `stacks_definitions/baserow.yaml` (Docker Compose multi-services), documentés dans [STACK-DEFINITIONS.md](STACK-DEFINITIONS.md). Combinaisons typiques de fonctions :

```yaml
environment:
  # Mot de passe encodé en Base64
  ENCODED_PASSWORD: "{{ base64_encode(generate_password(24)) }}"

  # Hash du secret pour vérification
  SECRET_HASH: "{{ hash_value(generate_secret(), 'sha512') }}"

  # Nom unique combinant plusieurs fonctions
  INSTANCE_NAME: "app-{{ env('HOSTNAME', 'default') }}-{{ generate_uuid_short() }}"
```

## Debug et validation

Vérifier les fonctions disponibles (le renderer expose le dictionnaire nom → première ligne de docstring) :

```python
from backend.app.helper.template_renderer import default_renderer

functions = default_renderer.get_available_functions()
for name, doc in functions.items():
    print(f"{name}: {doc}")
```

Tester un rendu local (fonction utilitaire du module) :

```python
from backend.app.helper.template_renderer import render_template

template = {
    "environment": {
        "PASSWORD": "{{ generate_password(16) }}",
        "SECRET": "{{ generate_secret(32) }}"   # → 32 caractères hex
    }
}
result = render_template(template, {})
```

Valider la **syntaxe** Jinja2 sans rendre (les erreurs sont listées avec leur chemin dans le dictionnaire) :

```python
from backend.app.helper.template_renderer import default_renderer

is_valid, errors = default_renderer.validate_template(template)
```

⚠️ Rappels de debug : en cas d'erreur de rendu sur une valeur (syntaxe invalide, variable non définie), le renderer retourne **la chaîne originale** (macro visible) et journalise un warning — une macro non substituée dans la config finale est donc le symptôme d'une erreur de rendu, pas d'un crash.

## Extensibilité

1. Ajouter la méthode `@staticmethod` dans la classe `JinjaFunctions` (`backend/app/helper/jinja_functions.py`).
2. L'enregistrer dans le dictionnaire `JINJA_FUNCTIONS` du même fichier — c'est lui qui est copié dans chaque `TemplateRenderer` (le paramètre `additional_functions` du constructeur permet d'ajouter des fonctions ad hoc sans modifier le dictionnaire global).
3. L'utiliser dans les templates YAML.

```python
# Extrait réel — structure du dictionnaire (backend/app/helper/jinja_functions.py)
JINJA_FUNCTIONS = {
    "generate_password": JinjaFunctions.generate_password,
    "generate_secret": JinjaFunctions.generate_secret,
    # … 14 autres entrées …
    "generate_mythologyname": JinjaFunctions.generate_mythologyname,
}
```

## Limitations

Les fonctions sont stateless, sans accès réseau ni système de fichiers ; les substitutions ne portent que sur des chaînes (les valeurs non-chaînes des templates sont conservées telles quelles). `get_valid_port` est la seule à ouvrir un socket (test de disponibilité) ; aucune fonction ne modifie l'état du système.

## Voir aussi

- [05-stack-technologique.md](../general_specs/05-stack-technologique.md) — socle des templates de déploiement
- [12-marketplace.md](../general_specs/12-marketplace.md) — entrées marketplace embarquant un template Jinja2
- [STACK-DEFINITIONS.md](STACK-DEFINITIONS.md) — format YAML des stacks, macros dans les valeurs par défaut · [DYNAMIC-FORMS.md](DYNAMIC-FORMS.md) — régénération des macros côté formulaire
