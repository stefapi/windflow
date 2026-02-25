# Workflow dev, commits, dépendances

## Commits
Conventional commits :
<type>(<scope>): <description>
Types: feat, fix, docs, style, refactor, test, chore

## Dépendances
- Python : Poetry uniquement, versions épinglées
- Front : pnpm
- Pas d’ajout de dépendance sans justification + impact sécurité

## Pre-commit / CI
Doit passer :
- format (black / prettier)
- lint (flake8 / eslint)
- typecheck (mypy / tsc)
- sécurité (bandit / semgrep / npm audit)
- tests + couverture

## Memory bank
Si le projet utilise un "memory-bank/" (docs vivantes), le mettre à jour lors de changements significatifs (archi, conventions, API, risques).
