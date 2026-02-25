# Standards de code & conventions

## Type safety obligatoire
- Python : type hints complets sur tout ce qui est public
- TypeScript : strict, pas de `any` sauf exception justifiée
- Validation : mypy + tsc strict (au minimum en CI)

## Clean code
- Fonctions courtes (≈30 lignes max si possible)
- Noms explicites
- SOLID / DRY / KISS / YAGNI / SoC
- Refactor minimal utile (éviter refactors massifs non demandés)

## Conventions de nommage
- Classes/Composants : PascalCase
- Python : snake_case (fonctions/variables/modules), constantes UPPER_SNAKE_CASE
- Front : fichiers kebab-case, JS/TS camelCase
- DB : snake_case + UUID PK + created_at/updated_at

## Gestion d’erreurs
Backend :
- exceptions personnalisées héritant de `WindFlowException`
- codes HTTP appropriés
- logs structurés avec contexte
- messages d’erreur internationalisés si la base le prévoit

Frontend :
- gestion centralisée via store Pinia
- notifications via Element Plus
- fallback gracieux + retry sur erreurs temporaires
