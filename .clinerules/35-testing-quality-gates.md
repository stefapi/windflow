# Tests, couverture & quality gates

## Pyramide des tests
Unitaires > Intégration > E2E (peu, sur workflows critiques).

## Couverture minimale
- Minimum : 80% pour tout nouveau composant
- Cible backend : 85%+
- Cible frontend : 80%+
- Chemins critiques : viser 95% quand raisonnable

## Backend
- pytest + pytest-asyncio pour async
- Mock des dépendances externes
- Tests exhaustifs pour API critiques (auth, RBAC, déploiements)

## Frontend
- Vitest pour unitaires
- Playwright pour E2E (workflows critiques)

## Avant de conclure une étape
- lancer tests ciblés si possible
- sinon : dire exactement ce qui n’a pas été exécuté + proposer commande/alternative
