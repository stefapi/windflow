# BUG-013 : Docstrings `expires_in: 1800` mensongers dans `auth.py` (valeur réelle 900)

**Statut :** DONE
**Gravité :** Mineur

> Constaté lors de la revue finale de conformité (STORY-254.3, 2026-11-07) ; signalement n°2 de STORY-252, jamais traité.

## Reproduction
1. `grep -n "1800" backend/app/api/v1/auth.py` → 3 docstrings codent en dur `expires_in: 1800`
2. Comparer à [`backend/app/config.py`](../../backend/app/config.py) l.36-38 : `jwt_access_token_expire_minutes = 15` → 900 s

## Comportement attendu
La documentation OpenAPI (servie depuis ces docstrings) doit refléter le contrat réel : `expires_in` calculé = `jwt_access_token_expire_minutes * 60` = **900** (arbitrage F5 — JWT 15 min, STORY-252).

## Comportement actuel
3 docstrings annoncent 1800 s (30 min — l'ancienne durée pré-arbitrage F5) alors que le code émet des tokens de 900 s : documentation de contrat trompeuse pour les consommateurs API.

## Résolution

Corrigé le 2026-11-07 (cycle NEW → CONFIRMED → IN_PROGRESS → REVIEW → DONE parcouru lors de la session de correction).

### Correctifs appliqués

- [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py) : les 3 occurrences `"expires_in": 1800` (exemples OpenAPI login l.150, refresh l.450, register l.731) → **900** ;
- [`backend/app/schemas/user.py`](../../backend/app/schemas/user.py) : dans le même esprit (même champ, même mensonge — signalés par STORY-252 « l.259/318/370 » avec la valeur 3600), les 6 occurrences `3600` des exemples/docstrings (`Token`, `LoginResponse`, `RefreshResponse`) → **900**.

### Vérification

- `grep -rn '"expires_in": 1800\|"expires_in": 3600' backend/app --include="*.py"` → **0 hit** ;
- `black`/`isort` conformes sur les deux fichiers ; suite `test_schemas` + 86 tests `auth` verts (aucune valeur codée en dur dans les tests ne dépendait des exemples) ;
- La valeur réelle émise par le code (`settings.jwt_access_token_expire_minutes * 60`, auth.py l.375/534/865) reste la source de vérité — les exemples documentent désormais le défaut F5 (15 min).
