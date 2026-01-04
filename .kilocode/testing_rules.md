## Vue d'Ensemble des Tests

WindFlow adopte une stratégie de tests complète avec plusieurs niveaux de validation pour assurer la qualité et la fiabilité du système.

### Pyramide des Tests
```
        E2E Tests (Playwright)
       /                    \
    API Tests (pytest)   Frontend E2E (Playwright)
   /           |              |            \
Unit Tests   Integration   Component    Visual
(pytest)     Tests        Tests         Tests
            (pytest)     (Vitest)    (Chromatic)
```

### Couverture de Code Minimale
- **Tests unitaires** : 90% minimum
- **Tests d'intégration** : 80% minimum  
- **Tests E2E** : 70% des workflows critiques
- **Couverture globale** : 85% minimum

## Structure des Répertoires de Tests

### Backend Python
```
tests/
├── unit/                   # Tests unitaires
│   ├── test_services/     # Tests des services métier
│   ├── test_models/       # Tests des modèles SQLAlchemy
│   ├── test_schemas/      # Tests des schémas Pydantic
│   └── test_utils/        # Tests des utilitaires
├── integration/           # Tests d'intégration
│   ├── test_api/         # Tests des endpoints API
│   ├── test_database/    # Tests avec base de données
│   └── test_external/    # Tests avec services externes
├── e2e/                   # Tests end-to-end
│   ├── test_workflows/   # Workflows complets
│   └── test_scenarios/   # Scénarios utilisateur
├── fixtures/              # Fixtures partagées
├── mocks/                # Mocks et stubs
├── conftest.py           # Configuration pytest
└── pytest.ini           # Configuration pytest globale
```

### Frontend
```
tests/
├── unit/                  # Tests unitaires composants
│   ├── components/       # Tests composants Vue
│   ├── composables/      # Tests composables
│   ├── services/         # Tests services API
│   └── utils/            # Tests utilitaires
├── integration/           # Tests d'intégration
│   ├── stores/           # Tests stores Pinia
│   └── router/           # Tests routing
├── e2e/                   # Tests end-to-end
│   ├── workflows/        # Workflows utilisateur
│   └── pages/            # Tests par page
├── fixtures/              # Données de test
├── mocks/                # Mocks MSW
├── setup.ts              # Configuration Vitest
└── playwright.config.ts  # Configuration Playwright
```

### CLI/TUI
```
tests/
├── unit/                  # Tests unitaires CLI
│   ├── test_commands/    # Tests commandes individuelles
│   ├── test_services/    # Tests services CLI
│   └── test_config/      # Tests configuration
├── integration/           # Tests d'intégration CLI
│   ├── test_workflows/   # Tests workflows CLI
│   └── test_tui/         # Tests interface TUI
├── e2e/                   # Tests end-to-end CLI
│   └── test_scenarios/   # Scénarios complets
├── fixtures/              # Fixtures CLI
└── mocks/                # Mocks pour CLI
```
