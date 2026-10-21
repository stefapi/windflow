# BUG-002 : Makefile `.ONESHELL:` masque les échecs de lint

**Statut :** DONE
**Gravité :** Majeur (quality gate faussé)

## Reproduction

1. Lancer `make backend-lint` (recette multi-lignes : isort `--check`, black `--check`, flake8, mypy, bandit)
2. La commande retourne **exit 0** alors qu'isort et mypy détectent des non-conformités préexistantes (~37 fichiers isort non conformes et 21 erreurs mypy)

## Comportement attendu

Le gate `make backend-lint` doit échouer (exit ≠ 0) dès qu'une sous-commande de la recette échoue (isort, black, flake8 ou mypy), afin que la CI bloque réellement sur les non-conformités de lint et de typage.

## Comportement actuel

`Makefile` ligne 71 : la directive `.ONESHELL:` fait exécuter chaque recette dans un shell unique ; l'exit code propagé est celui de la **dernière** commande uniquement (bandit, qui passe). Un échec d'isort, black, flake8 ou mypy est donc silencieusement masqué — le quality gate laisse passer du code non conforme.

## Piste de résolution

Retirer `.ONESHELL:` (ligne 71) **ou** ajouter `set -e` en tête de chaque recette multi-lignes.
À traiter dans la foulée : ~37 fichiers isort + 21 erreurs mypy préexistantes à ce jour invisibles pour le gate.

## Contexte

Découvert lors du debug de BUG-001 (correction des 35 échecs de la suite unitaire backend) : le passage `make backend-lint` → exit 0 donnait une illusion de conformité malgré les non-conformités préexistantes.

## Confirmation (2026-10-21)

- `make backend-lint` → **exit 0** alors que la sortie contient des erreurs réelles.
- `poetry run isort --check-only backend/app` → **exit 1** (11 fichiers non conformes sous `backend/app`).
- `cd backend && poetry run mypy app/` → **exit 1** (21 erreurs, conforme au signalement).
- **Anomalie supplémentaire découverte** : avec `.ONESHELL:` le `cd backend` de la ligne mypy persiste pour les lignes suivantes de la recette → `bandit -r backend` s'exécute depuis `backend/` et scanne `backend/backend` (inexistant) → `Files skipped (1): ./backend (No such file or directory)` + exit 0 : **bandit ne scanne en réalité aucun fichier** dans `make backend-lint`.

## Résolution (2026-10-21)

### Cause racine

Directive `.ONESHELL:` (ancienne ligne 71 du `Makefile`) : chaque recette multi-lignes s'exécute dans **un shell unique sans `set -e`**. L'exit code propagé à make est celui de la **dernière** commande uniquement (bandit, qui passait) — tout échec d'isort/black/flake8/mypy était silencieusement masqué. Effet secondaire : le `cd backend` de la ligne mypy persistait pour bandit qui scannait `backend/backend` (inexistant) → bandit ne scannait rien.

### Option retenue : A — suppression de `.ONESHELL:`

Justification (au vu du Makefile réel) :
- **Aucune recette ne dépend du comportement `.ONESHELL:`** : toutes les recettes multi-lignes sont soit des suites de lignes autonomes (chacune préfixée par `cd X && cmd` quand nécessaire), soit des blocs shell uniques via continuations `\` (`dev`, `docker-dev`, `dev-full`, `ci-test-backend`, `enable-*`…) qui fonctionnent à l'identique sans `.ONESHELL:`.
- La persistance du `cd` entre lignes n'était utilisée **nulle part volontairement** — c'était au contraire un bug latent (bandit).
- L'option B (`set -e;` par recette) aurait exigé de modifier ~40 recettes (intrusif, risque d'oubli) et n'aurait **pas** corrigé la persistance du `cd`.

### Fix appliqué

- `Makefile` : suppression de la ligne `.ONESHELL:` (remplacée par un commentaire de garde interdisant sa réintroduction).
- Aucune autre modification de recette nécessaire : le comportement make standard (un shell par ligne, arrêt à la première ligne en échec) restaure le fail-fast pour **toutes** les cibles : `backend-lint`, `backend-format`, `cli-lint`, `cli-format`, `lint`, `format`, `ci-lint-backend`, `ci-lint-frontend`, `ci-full`, `ci-quick`, `backend-all`, `frontend-all`, `cli-all`, `test`, etc.
- Les non-conformités détectées (~11 fichiers isort sous `backend/app` + 21 erreurs mypy) sont **hors périmètre** (cf. consigne) — le gate les détecte désormais honnêtement.

### Preuves de validation

| Vérification | Avant | Après |
|---|---|---|
| `make backend-lint` | **exit 0** (échecs masqués) | **exit 2** (`Makefile:168: backend-lint] Error 1` sur isort — fail-fast) |
| `poetry run isort --check-only backend/app` | exit 1 (masqué) | exit 1 (détecté par le gate) |
| `cd backend && poetry run mypy app/` | exit 1, 21 erreurs (masquées) | exit 1 (détecté par le gate) |
| bandit dans `backend-lint` | `Files skipped: ./backend (No such file)` — ne scannait rien | s'exécute depuis la racine (plus de `Files skipped`) |
| `make help` | exit 0 | exit 0 (non régressé) |
| Sonde fail-fast isolée (make -f probe) | — | échec ligne 1 → exit 2, ligne suivante non exécutée ; cible saine → exit 0 |
| Dry-runs `make -n` : `help`, `backend-lint`, `backend-format`, `frontend-lint`, `cli-lint`, `cli-format`, `lint`, `format`, `ci-lint-backend`, `ci-lint-frontend`, `ci-full`, `ci-quick`, `backend-all`*, `frontend-all`, `cli-all`, `test`*, `ci-test-backend`, `ci-security-backend`, `generate-api`, `docker-dev`, `dev` | — | tous OK sauf (*) voir anomalies préexistantes |

### Anomalies préexistantes relevées (hors périmètre, non corrigées)

- `make typecheck` : cible inexistante (seuls `backend-typecheck`/`frontend-typecheck` existent) — exit 2 **avant comme après** le fix.
- `make backend-all` et `make test` : référencent une cible `backend-test` inexistante (seuls `backend-test-unit/-integration/-coverage/-all` existent) — exit 2 **avant comme après** le fix (vérifié via `git stash`).
- `ci-lint-backend` : `pylint ... || true` et `ci-security-*` : `|| true` — tolérances volontaires préexistantes, non modifiées.
- Non-conformités isort/mypy préexistantes : à traiter séparément (le bug signalait ~37 fichiers isort sur `backend/` complet ; mesure fraîche : 11 sous `backend/app` seul).

### Cibles Makefile modifiées

- Aucune recette modifiée individuellement — la suppression de `.ONESHELL:` (1 ligne) change le mode d'exécution de **toutes** les recettes et restaure le fail-fast standard.
