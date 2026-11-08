# 30 — Standards de code et gestion des erreurs

## 1. Langues

Identifiants, noms de fichiers, base de données, API et messages de journal : anglais (glossaire `03`). Commentaires, docstrings, textes destinés à l'utilisateur et documentation : français.

## 2. Typage

- Python : type hints complets sur tout ce qui est public ; mypy (`ignore_missing_imports=false`) en CI.
- TypeScript : `strict` + options additionnelles (`06` §2) ; pas de `any` sauf exception justifiée.
- Validation : mypy + tsc strict au minimum en CI (`make typecheck`).

## 3. Code propre

- Fonctions courtes (≈ 30-40 lignes), noms explicites, un seul niveau d'abstraction par fonction ; SOLID / DRY / KISS / YAGNI / SoC.
- Dépendances injectées par paramètres ; pas d'état global modifiable caché.
- Refactoring local nécessaire au résultat autorisé dans le contrat courant : extraire une responsabilité, simplifier ou supprimer une duplication en préservant les comportements et contrats publics (`01` §12). Un changement structurant ou transversal fait l'objet d'options et d'un arbitrage avant réalisation dépendante.
- Ne pas reproduire un patron existant sans vérifier sa pertinence ; pas de code mort ni de code commenté ; pas de `print` en backend livré.

## 4. Nommage

| Élément | Python | TypeScript / Vue |
| --- | --- | --- |
| Variables, fonctions | `snake_case` | `camelCase` |
| Classes, composants, types | `PascalCase` | `PascalCase` |
| Constantes | `UPPER_SNAKE_CASE` | `UPPER_SNAKE_CASE` |
| Fichiers | `snake_case.py` | Composants kebab-case (`.vue`), autres `camelCase.ts` |
| Tests | `test_<sujet>.py`, fonctions `test_<cas>_<attendu>` | `<Nom>.spec.ts` |

Base et API : `snake_case` + UUID PK + `created_at`/`updated_at` (`55` §2).

## 5. Gestion d'erreurs

Backend :
- exceptions personnalisées héritant de `WindFlowException` (`core/exceptions.py`), jamais d'exception Python brute dans un endpoint ;
- codes HTTP appropriés (401/403/404/409/422…) ;
- logs structurés avec contexte (`request_id`, `user_id`…) ;
- **interdit** : `try/except` qui avale l'erreur sans la relancer ni la journaliser.

Frontend :
- gestion centralisée via store Pinia + notifications Element Plus ;
- fallback gracieux + retry sur erreurs temporaires ; aucun `catch` silencieux.

## 6. Fonctionnalité non implémentée

- Marque unique : `# TODO(STORY-0123): description` (ou `// TODO(STORY-0123): …`) ; l'élément de backlog existe.
- **Interdit** : code fictif, données simulées présentées comme réelles, fonction renvoyant une valeur en dur « provisoirement », endpoint qui répond sans traitement réel.
- Une fonctionnalité inachevée n'est pas exposée : ni route, ni entrée de menu.

## 7. Outils

| Outil | Rôle | Configuration |
| --- | --- | --- |
| black | Formatage backend | — |
| isort | Tri des imports | `profile=black` |
| flake8 | Lint backend | `.flake8` |
| mypy | Types backend | `07` §5 |
| bandit | Sécurité | niveau `low` minimum |
| pylint | Qualité | `.pylintrc` |
| ESLint v9 / Prettier / Stylelint | Frontend | flat config |

`make lint` et `make format` en local (`50` §1) ; la CI vérifie sans corriger.
