# Workflow de Test - WindFlow

## Vue d'Ensemble

Ce document décrit la stratégie et les processus de test pour WindFlow, basés sur les bonnes pratiques observées et adaptés aux spécificités du projet de déploiement de containers.

## Stratégie de Test

### Pyramide des Tests
```
                    E2E Tests
                   (Playwright)
                  /            \
            API Tests         UI Tests
           (FastAPI)         (Vitest)
          /        |          |        \
   Unit Tests   Integration  Component   Visual
   (pytest)     Tests        Tests      Tests
               (pytest)     (Vitest)   (Chromatic)
```

### Niveaux de Validation
1. **Unit Tests** (85%+) : Logique métier isolée
2. **Integration Tests** (80%+) : Interaction entre composants
3. **API Tests** (90%+) : Endpoints complets
4. **E2E Tests** (70%+) : Workflows utilisateur critiques
5. **Performance Tests** : Non-régression des performances

### Objectifs de Couverture
- **Global** : 85% minimum
- **Backend Core** : 90% minimum
- **Frontend Components** : 80% minimum
- **API Endpoints** : 95% minimum
- **Critical Paths** : 100% requis

## Tests Backend (pytest)

### Structure et Organisation
```
tests/
├── unit/                      # Tests unitaires
│   ├── test_services/        # Services métier
│   ├── test_models/          # Modèles SQLAlchemy
│   ├── test_schemas/         # Validation Pydantic
│   └── test_utils/           # Fonctions utilitaires
├── integration/              # Tests d'intégration
│   ├── test_api/            # Endpoints API
│   ├── test_database/       # Interactions DB
│   └── test_external/       # Services externes
├── e2e/                     # Tests end-to-end
│   └── test_workflows/      # Workflows complets
├── fixtures/                # Données de test partagées
├── mocks/                   # Mocks et stubs
└── conftest.py             # Configuration pytest globale
```

### Configuration pytest
```python
# pytest.ini
[tool:pytest]
minversion = 7.0
addopts = 
    -ra
    --strict-markers
    --strict-config
    --cov=windflow
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=85
    --cov-branch
    --asyncio-mode=auto
testpaths = tests
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
    auth: Authentication tests
    deployment: Deployment tests
    llm: LLM integration tests
```

### Tests Unitaires
```python
# tests/unit/test_services/test_deployment_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from windflow.services.deployment_service import DeploymentService
from windflow.schemas.deployment import DeploymentCreate
from windflow.exceptions import DeploymentError

@pytest.mark.unit
@pytest.mark.asyncio
class TestDeploymentService:
    """Tests unitaires pour DeploymentService."""
    
    @pytest.fixture
    def deployment_service(self):
        return DeploymentService()
    
    @pytest.fixture
    def mock_repository(self):
        return AsyncMock()
    
    @pytest.fixture
    def sample_deployment_data(self):
        return {
            "name": "test-deployment",
            "target_type": "docker",
            "configuration": {"image": "nginx:latest"}
        }
    
    async def test_create_deployment_success(
        self, 
        deployment_service,
        mock_repository,
        sample_deployment_data
    ):
        # Arrange
        user_id = uuid4()
        deployment_data = DeploymentCreate(**sample_deployment_data)
        
        mock_deployment = MagicMock()
        mock_deployment.id = uuid4()
        mock_deployment.status = "pending"
        mock_repository.create.return_value = mock_deployment
        
        # Act
        result = await deployment_service.create_deployment(
            deployment_data, user_id, mock_repository
        )
        
        # Assert
        assert result.status == "pending"
        mock_repository.create.assert_called_once()
    
    async def test_create_deployment_validation_error(
        self, deployment_service, mock_repository
    ):
        # Arrange
        invalid_data = DeploymentCreate(
            name="", target_type="invalid", configuration={}
        )
        
        # Act & Assert
        with pytest.raises(DeploymentError):
            await deployment_service.create_deployment(
                invalid_data, uuid4(), mock_repository
            )
```

### Tests d'Intégration
```python
# tests/integration/test_api/test_deployment_endpoints.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.integration
@pytest.mark.asyncio
class TestDeploymentAPI:
    """Tests d'intégration pour l'API de déploiement."""
    
    async def test_create_deployment_endpoint(
        self, client: TestClient, auth_headers: dict, db: AsyncSession
    ):
        # Arrange
        deployment_data = {
            "name": "integration-test-deployment",
            "target_type": "docker",
            "configuration": {"image": "nginx:latest"}
        }
        
        # Act
        response = client.post(
            "/api/v1/deployments",
            json=deployment_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == deployment_data["name"]
        assert "id" in data
        
        # Vérification en base
        deployment = await db.get(Deployment, data["id"])
        assert deployment is not None
    
    async def test_deployment_workflow_complete(
        self, client: TestClient, auth_headers: dict
    ):
        # Create → Read → Update → Delete
        
        # Create
        create_response = client.post(
            "/api/v1/deployments",
            json={"name": "workflow-test", "target_type": "docker"},
            headers=auth_headers
        )
        deployment_id = create_response.json()["id"]
        
        # Read
        get_response = client.get(
            f"/api/v1/deployments/{deployment_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        
        # Update
        update_response = client.put(
            f"/api/v1/deployments/{deployment_id}",
            json={"status": "running"},
            headers=auth_headers
        )
        assert update_response.status_code == 200
        
        # Delete
        delete_response = client.delete(
            f"/api/v1/deployments/{deployment_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 204
```

### Tests avec Base de Données
```python
# tests/conftest.py
@pytest_asyncio.fixture
async def async_db():
    """Base de données de test isolée."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///./test.db",
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
def sample_user(async_db):
    """Utilisateur de test."""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@windflow.local"
    )
    async_db.add(user)
    await async_db.commit()
    return user
```

## Tests Frontend (Vitest)

### Configuration Vitest
```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json'],
      exclude: ['node_modules/', 'tests/', '**/*.d.ts'],
      thresholds: {
        statements: 85,
        branches: 80,
        functions: 85,
        lines: 85
      }
    }
  },
  resolve: {
    alias: { '@': resolve(__dirname, 'src') }
  }
})
```

### Tests de Composants
```typescript
// tests/unit/components/DeploymentCard.test.ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import DeploymentCard from '@/components/features/DeploymentCard.vue'

describe('DeploymentCard', () => {
  const mockDeployment = {
    id: 'test-123',
    name: 'Test Deployment',
    status: 'running',
    targetType: 'docker',
    createdAt: '2024-01-15T10:00:00Z'
  }

  it('renders deployment information correctly', () => {
    const wrapper = mount(DeploymentCard, {
      props: { deployment: mockDeployment },
      global: {
        plugins: [createTestingPinia({ createSpy: vi.fn })]
      }
    })

    expect(wrapper.text()).toContain('Test Deployment')
    expect(wrapper.text()).toContain('docker')
    expect(wrapper.find('[data-test="status"]').text()).toBe('running')
  })

  it('emits view-logs event when logs button clicked', async () => {
    const wrapper = mount(DeploymentCard, {
      props: { deployment: mockDeployment },
      global: {
        plugins: [createTestingPinia()]
      }
    })

    await wrapper.find('[data-test="logs-btn"]').trigger('click')
    
    expect(wrapper.emitted('view-logs')).toEqual([['test-123']])
  })

  it('shows correct actions based on status', () => {
    const runningWrapper = mount(DeploymentCard, {
      props: { deployment: { ...mockDeployment, status: 'running' } }
    })
    expect(runningWrapper.find('[data-test="stop-btn"]').exists()).toBe(true)

    const stoppedWrapper = mount(DeploymentCard, {
      props: { deployment: { ...mockDeployment, status: 'stopped' } }
    })
    expect(stoppedWrapper.find('[data-test="start-btn"]').exists()).toBe(true)
  })
})
```

### Tests de Stores Pinia
```typescript
// tests/unit/stores/deployments.test.ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDeploymentsStore } from '@/stores/deployments'

// Mock du service API
vi.mock('@/services/deployments', () => ({
  deploymentService: {
    getAll: vi.fn(),
    create: vi.fn(),
    delete: vi.fn()
  }
}))

describe('Deployments Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('fetches deployments successfully', async () => {
    const store = useDeploymentsStore()
    const mockDeployments = [
      { id: '1', name: 'dep1', status: 'running' },
      { id: '2', name: 'dep2', status: 'stopped' }
    ]

    deploymentService.getAll.mockResolvedValue({ data: mockDeployments })

    await store.fetchDeployments()

    expect(store.deployments).toEqual(mockDeployments)
    expect(store.loading).toBe(false)
    expect(store.error).toBe(null)
  })

  it('handles fetch error correctly', async () => {
    const store = useDeploymentsStore()
    const errorMessage = 'Network error'

    deploymentService.getAll.mockRejectedValue(new Error(errorMessage))

    await store.fetchDeployments()

    expect(store.deployments).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.error).toBe(errorMessage)
  })

  it('computes active deployments correctly', () => {
    const store = useDeploymentsStore()
    store.deployments = [
      { id: '1', status: 'running' },
      { id: '2', status: 'stopped' },
      { id: '3', status: 'running' }
    ]

    expect(store.activeDeployments).toHaveLength(2)
    expect(store.activeDeployments.every(d => d.status === 'running')).toBe(true)
  })
})
```

## Tests End-to-End (Playwright)

### Configuration Playwright
```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html'],
    ['json', { outputFile: 'test-results/results.json' }]
  ],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } }
  ],
  webServer: {
    command: 'make dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI
  }
})
```

### Tests E2E Critiques
```typescript
// tests/e2e/deployment-workflow.test.ts
import { test, expect } from '@playwright/test'

test.describe('Deployment Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto('/login')
    await page.fill('[data-test="username"]', 'admin@windflow.local')
    await page.fill('[data-test="password"]', 'admin123')
    await page.click('[data-test="login-btn"]')
    await expect(page).toHaveURL('/dashboard')
  })

  test('complete deployment creation workflow', async ({ page }) => {
    // Navigate to deployments
    await page.click('[data-test="nav-deployments"]')
    await expect(page).toHaveURL('/deployments')

    // Create new deployment
    await page.click('[data-test="create-deployment-btn"]')
    
    // Fill form
    await page.fill('[data-test="deployment-name"]', 'E2E Test Deployment')
    await page.selectOption('[data-test="stack-select"]', 'web-app')
    await page.selectOption('[data-test="environment"]', 'staging')
    await page.selectOption('[data-test="target-type"]', 'docker')

    // Submit
    await page.click('[data-test="submit-btn"]')

    // Verify creation
    await expect(page.locator('[data-test="deployment-card"]')).toContainText('E2E Test Deployment')
    await expect(page.locator('[data-test="status-badge"]')).toContainText('pending')

    // View details
    await page.click('[data-test="deployment-card"]:first-child')
    await expect(page).toHaveURL(/\/deployments\/.*/)

    // Check logs
    await page.click('[data-test="logs-tab"]')
    await expect(page.locator('[data-test="logs-container"]')).toBeVisible()
  })

  test('deployment error handling', async ({ page }) => {
    await page.goto('/deployments')
    await page.click('[data-test="create-deployment-btn"]')
    
    // Submit empty form
    await page.click('[data-test="submit-btn"]')
    
    // Check validation errors
    await expect(page.locator('[data-test="error-message"]')).toBeVisible()
    await expect(page.locator('[data-test="error-message"]')).toContainText('Name is required')
  })

  test('deployment monitoring and actions', async ({ page }) => {
    await page.goto('/deployments')
    
    // Assume deployment exists
    const deploymentCard = page.locator('[data-test="deployment-card"]').first()
    await expect(deploymentCard).toBeVisible()

    // Stop deployment
    await deploymentCard.locator('[data-test="stop-btn"]').click()
    await page.click('[data-test="confirm-stop"]')
    
    // Verify status change
    await expect(deploymentCard.locator('[data-test="status"]')).toContainText('stopping')
  })
})
```

## Mocks et Stubs

### Backend Mocking
```python
# tests/mocks/external_services.py
class MockDockerService:
    """Mock pour les opérations Docker."""
    
    def __init__(self):
        self.containers = {}
        self.images = {}
    
    async def deploy_container(self, config: dict):
        container_id = f"container-{len(self.containers) + 1}"
        self.containers[container_id] = {
            "id": container_id,
            "status": "running",
            "config": config
        }
        return self.containers[container_id]
    
    async def stop_container(self, container_id: str):
        if container_id in self.containers:
            self.containers[container_id]["status"] = "stopped"
            return True
        return False

class MockLLMService:
    """Mock pour les services LLM."""
    
    async def optimize_deployment(self, config: dict):
        # Simulation d'optimisation
        optimized = config.copy()
        optimized["optimized"] = True
        optimized["cpu_limit"] = "500m"
        optimized["memory_limit"] = "512Mi"
        return optimized, None
```

### Frontend Mocking (MSW)
```typescript
// tests/mocks/handlers.ts
import { rest } from 'msw'

export const handlers = [
  // Deployments
  rest.get('/api/v1/deployments', (req, res, ctx) => {
    return res(
      ctx.json({
        data: [
          {
            id: '1',
            name: 'Mock Deployment 1',
            status: 'running',
            targetType: 'docker'
          },
          {
            id: '2', 
            name: 'Mock Deployment 2',
            status: 'stopped',
            targetType: 'kubernetes'
          }
        ],
        total: 2
      })
    )
  }),

  rest.post('/api/v1/deployments', (req, res, ctx) => {
    return res(
      ctx.status(201),
      ctx.json({
        id: 'new-deployment-id',
        name: 'New Deployment',
        status: 'pending'
      })
    )
  }),

  // Auth
  rest.post('/api/v1/auth/login', (req, res, ctx) => {
    return res(
      ctx.json({
        access_token: 'mock-token',
        user: {
          id: 'user-1',
          username: 'testuser',
          email: 'test@windflow.local'
        }
      })
    )
  })
]
```

## Tests de Performance

### Backend Performance
```python
# tests/performance/test_api_performance.py
import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

@pytest.mark.performance
class TestAPIPerformance:
    
    async def test_deployment_creation_performance(self, client, auth_headers):
        """Test de performance pour création de déploiements."""
        
        start_time = time.time()
        
        # 100 créations concurrentes
        tasks = []
        for i in range(100):
            task = self.create_deployment(client, auth_headers, f"perf-test-{i}")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Analyse des résultats
        successful = [r for r in results if not isinstance(r, Exception)]
        failed = [r for r in results if isinstance(r, Exception)]
        
        # Assertions
        assert len(successful) >= 95  # 95% de succès minimum
        assert end_time - start_time < 10  # Moins de 10 secondes
        assert len(failed) < 5  # Moins de 5% d'échecs
    
    async def create_deployment(self, client, headers, name):
        response = client.post(
            "/api/v1/deployments",
            json={"name": name, "target_type": "docker"},
            headers=headers
        )
        return response.status_code == 201
```

### Frontend Performance
```typescript
// tests/performance/bundle-size.test.ts
import { describe, it, expect } from 'vitest'
import { analyzeBundle } from '../utils/bundle-analyzer'

describe('Bundle Performance', () => {
  it('should not exceed size limits', async () => {
    const analysis = await analyzeBundle()
    
    expect(analysis.totalSize).toBeLessThan(2 * 1024 * 1024) // 2MB max
    expect(analysis.mainChunk).toBeLessThan(500 * 1024) // 500KB max
    expect(analysis.vendorChunk).toBeLessThan(1 * 1024 * 1024) // 1MB max
  })

  it('should have efficient code splitting', async () => {
    const analysis = await analyzeBundle()
    
    expect(analysis.chunks.length).toBeGreaterThan(3) // Code splitting actif
    expect(analysis.duplicateModules.length).toBe(0) // Pas de duplication
  })
})
```

## Commandes de Test

### Commandes Make
```makefile
# Tests backend
backend-test: ## Run backend unit tests
	$(POETRY) run pytest tests/unit/

backend-test-integration: ## Run backend integration tests
	$(POETRY) run pytest tests/integration/

backend-test-e2e: ## Run backend e2e tests
	$(POETRY) run pytest tests/e2e/

backend-test-all: ## Run all backend tests
	$(POETRY) run pytest

backend-coverage: ## Generate coverage report
	$(POETRY) run pytest --cov-report=html
	$(BROWSER) htmlcov/index.html

# Tests frontend
frontend-test: ## Run frontend unit tests
	cd frontend && pnpm test

frontend-test-ui: ## Run frontend tests with UI
	cd frontend && pnpm test:ui

frontend-test-coverage: ## Generate frontend coverage
	cd frontend && pnpm test:coverage

frontend-test-e2e: ## Run frontend e2e tests
	cd frontend && pnpm test:e2e

frontend-test-e2e-ui: ## Run e2e tests with UI
	cd frontend && pnpm test:e2e:ui

# Tests globaux
test-all: backend-test-all frontend-test frontend-test-e2e ## Run all tests

test-quick: backend-test frontend-test ## Run quick tests only

test-watch: ## Run tests in watch mode
	make -j2 backend-test-watch frontend-test-watch

performance-test: ## Run performance tests
	$(POETRY) run pytest tests/performance/ -m performance
```

### Scripts de Test Automatisés
```bash
#!/bin/bash
# scripts/test-ci.sh

set -e

echo "🧪 Running WindFlow Test Suite"

# Backend tests
echo "📦 Backend Tests"
make backend-test-all

# Frontend tests  
echo "🎨 Frontend Tests"
make frontend-test
make frontend-test-e2e

# Performance tests
echo "⚡ Performance Tests"
make performance-test

# Security tests
echo "🔒 Security Tests"
make security-test

echo "✅ All tests passed!"
```

## Quality Gates et CI/CD

### GitHub Actions Integration
```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install poetry
          poetry install --with dev
          
      - name: Run tests
        run: |
          make backend-test-all
          
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
          cache: 'pnpm'
          
      - name: Install dependencies
        run: cd frontend && pnpm install
        
      - name: Run tests
        run: |
          make frontend-test
          make frontend-test-e2e
```

### Quality Gates
- **Coverage** : 85% minimum pour merge
- **Performance** : Pas de régression > 10%
- **Security** : Aucune vulnérabilité critique
- **E2E** : Tous les workflows critiques passent

---

**Note** : Cette stratégie de test est évolutive et doit être adaptée selon les besoins spécifiques de chaque feature WindFlow.
