# Règles de Test - WindFlow

## Tests Backend avec pytest

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
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
    auth: Authentication related tests
    deployment: Deployment related tests
```

### Configuration conftest.py
```python
# tests/conftest.py
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, MagicMock
import asyncio
from typing import AsyncGenerator, Generator

from windflow.main import app
from windflow.core.database import get_db
from windflow.models.base import Base
from windflow.core.config import settings

# Configuration de base pour tous les tests
@pytest.fixture(scope="session")
def event_loop():
    """Crée une event loop pour tous les tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# Base de données de test
@pytest_asyncio.fixture
async def async_db() -> AsyncGenerator[AsyncSession, None]:
    """Fixture de base de données de test."""
    
    # Moteur de test en mémoire
    engine = create_async_engine(
        "sqlite+aiosqlite:///./test.db",
        echo=False,
        connect_args={"check_same_thread": False}
    )
    
    # Création des tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Session de test
    async_session = sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    # Nettoyage
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

# Client de test
@pytest.fixture
def client(async_db: AsyncSession) -> Generator[TestClient, None, None]:
    """Client de test FastAPI."""
    
    def override_get_db():
        return async_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()

# Fixtures d'authentification
@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    """Headers d'authentification pour les tests."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "test@windflow.local", "password": "testpass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# Fixtures de données
@pytest.fixture
def sample_user_data():
    """Données d'exemple pour un utilisateur."""
    return {
        "username": "testuser",
        "email": "test@windflow.local",
        "password": "testpass123",
        "is_superadmin": False
    }

@pytest.fixture
def sample_deployment_data():
    """Données d'exemple pour un déploiement."""
    return {
        "name": "test-deployment",
        "target_type": "docker",
        "configuration": {
            "image": "nginx:latest",
            "ports": [80, 443],
            "environment": {"ENV": "test"}
        }
    }
```

### Tests Unitaires
```python
# tests/unit/test_services/test_deployment_service.py
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from windflow.services.deployment_service import DeploymentService
from windflow.schemas.deployment import DeploymentCreate, DeploymentResponse
from windflow.exceptions import DeploymentError

@pytest.mark.unit
class TestDeploymentService:
    """Tests unitaires pour DeploymentService."""
    
    @pytest.fixture
    def deployment_service(self):
        """Instance du service de déploiement."""
        return DeploymentService()
    
    @pytest.fixture
    def mock_repository(self):
        """Mock du repository de déploiement."""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_create_deployment_success(
        self, 
        deployment_service: DeploymentService,
        mock_repository: AsyncMock,
        sample_deployment_data: dict
    ):
        """Test de création de déploiement avec succès."""
        
        # Arrange
        user_id = uuid4()
        deployment_data = DeploymentCreate(**sample_deployment_data)
        
        mock_deployment = AsyncMock()
        mock_deployment.id = uuid4()
        mock_deployment.name = "test-deployment"
        mock_deployment.status = "pending"
        
        mock_repository.create.return_value = mock_deployment
        
        # Act
        with patch.object(deployment_service, '_validate_deployment_config'):
            with patch.object(deployment_service, '_trigger_deployment_task'):
                result = await deployment_service.create_deployment(
                    deployment_data,
                    user_id,
                    repository=mock_repository
                )
        
        # Assert
        assert isinstance(result, DeploymentResponse)
        assert result.name == "test-deployment"
        assert result.status == "pending"
        mock_repository.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_deployment_validation_error(
        self,
        deployment_service: DeploymentService,
        mock_repository: AsyncMock,
        sample_deployment_data: dict
    ):
        """Test de création avec erreur de validation."""
        
        # Arrange
        user_id = uuid4()
        deployment_data = DeploymentCreate(**sample_deployment_data)
        
        # Act & Assert
        with patch.object(
            deployment_service, 
            '_validate_deployment_config',
            side_effect=DeploymentError("Configuration invalide")
        ):
            with pytest.raises(DeploymentError, match="Configuration invalide"):
                await deployment_service.create_deployment(
                    deployment_data,
                    user_id,
                    repository=mock_repository
                )
```

### Tests d'Intégration
```python
# tests/integration/test_api/test_deployment_endpoints.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.integration
class TestDeploymentEndpoints:
    """Tests d'intégration pour les endpoints de déploiement."""
    
    @pytest.mark.asyncio
    async def test_create_deployment_endpoint(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_deployment_data: dict
    ):
        """Test d'intégration pour la création de déploiement."""
        
        # Act
        response = client.post(
            "/api/v1/deployments",
            json=sample_deployment_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_deployment_data["name"]
        assert data["status"] == "pending"
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_list_deployments_endpoint(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test d'intégration pour la liste des déploiements."""
        
        # Act
        response = client.get(
            "/api/v1/deployments",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data
        assert isinstance(data["data"], list)
    
    @pytest.mark.asyncio
    async def test_get_deployment_not_found(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test d'intégration pour déploiement non trouvé."""
        
        # Act
        response = client.get(
            f"/api/v1/deployments/{uuid4()}",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()
```

## Tests d'API avec Mocks

### Configuration des Mocks
```python
# tests/mocks/external_services.py
from unittest.mock import AsyncMock, MagicMock
import pytest

class MockDockerClient:
    """Mock pour le client Docker."""
    
    def __init__(self):
        self.containers = AsyncMock()
        self.images = AsyncMock()
        self.networks = AsyncMock()
        
    async def deploy_container(self, config: dict):
        """Mock de déploiement de container."""
        return {
            "id": "container-123",
            "status": "running",
            "ports": config.get("ports", [])
        }

class MockKubernetesClient:
    """Mock pour le client Kubernetes."""
    
    def __init__(self):
        self.apps_v1 = AsyncMock()
        self.core_v1 = AsyncMock()
        
    async def deploy_pod(self, manifest: dict):
        """Mock de déploiement de pod."""
        return {
            "metadata": {"name": manifest["metadata"]["name"]},
            "status": {"phase": "Running"}
        }

class MockVaultClient:
    """Mock pour HashiCorp Vault."""
    
    def __init__(self):
        self.secrets = {
            "database/config": {
                "username": "test_user",
                "password": "test_password"
            }
        }
    
    async def read_secret(self, path: str):
        """Mock de lecture de secret."""
        return self.secrets.get(path, {})

# Fixtures pour les mocks
@pytest.fixture
def mock_docker_client():
    """Mock du client Docker."""
    return MockDockerClient()

@pytest.fixture
def mock_k8s_client():
    """Mock du client Kubernetes."""
    return MockKubernetesClient()

@pytest.fixture
def mock_vault_client():
    """Mock du client Vault."""
    return MockVaultClient()
```

### Tests avec Services Externes
```python
# tests/integration/test_external/test_docker_service.py
import pytest
from unittest.mock import patch, AsyncMock

from windflow.services.docker_service import DockerService
from windflow.exceptions import DeploymentError

@pytest.mark.integration
class TestDockerService:
    """Tests d'intégration pour DockerService."""
    
    @pytest.fixture
    def docker_service(self):
        """Instance du service Docker."""
        return DockerService()
    
    @pytest.mark.asyncio
    async def test_deploy_container_success(
        self,
        docker_service: DockerService,
        mock_docker_client: AsyncMock
    ):
        """Test de déploiement de container avec succès."""
        
        # Arrange
        config = {
            "image": "nginx:latest",
            "ports": [80, 443],
            "environment": {"ENV": "test"}
        }
        
        # Act
        with patch.object(docker_service, 'client', mock_docker_client):
            result = await docker_service.deploy_container(config)
        
        # Assert
        assert result["status"] == "running"
        assert result["id"] == "container-123"
        mock_docker_client.deploy_container.assert_called_once_with(config)
    
    @pytest.mark.asyncio
    async def test_deploy_container_failure(
        self,
        docker_service: DockerService,
        mock_docker_client: AsyncMock
    ):
        """Test d'échec de déploiement de container."""
        
        # Arrange
        config = {"image": "invalid:image"}
        mock_docker_client.deploy_container.side_effect = Exception("Image not found")
        
        # Act & Assert
        with patch.object(docker_service, 'client', mock_docker_client):
            with pytest.raises(DeploymentError, match="Image not found"):
                await docker_service.deploy_container(config)
```

## Tests Frontend avec Vitest

### Configuration Vitest
```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'jsdom',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json'],
      exclude: [
        'node_modules/',
        'tests/',
        '**/*.d.ts',
        '**/*.config.*'
      ],
      thresholds: {
        statements: 85,
        branches: 80,
        functions: 85,
        lines: 85
      }
    },
    setupFiles: ['tests/setup.ts']
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  }
})
```

### Setup de Tests Frontend
```typescript
// tests/setup.ts
import { vi } from 'vitest'
import { config } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { ElButton, ElMessage } from 'element-plus'

// Configuration globale des composants
config.global.components = {
  ElButton,
  // Autres composants Element Plus
}

config.global.plugins = [createPinia()]

// Mocks globaux
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    go: vi.fn()
  }),
  useRoute: () => ({
    params: {},
    query: {},
    name: 'test-route'
  })
}))

// Mock Element Plus notifications
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn()
    }
  }
})
```

### Tests de Composants Vue
```typescript
// tests/unit/components/DeploymentCard.test.ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ElButton, ElTag } from 'element-plus'
import DeploymentCard from '@/components/features/DeploymentCard.vue'
import type { Deployment } from '@/types'

const mockDeployment: Deployment = {
  id: 'test-123',
  name: 'Test Deployment',
  status: 'running',
  targetType: 'docker',
  createdAt: '2024-01-15T10:00:00Z',
  updatedAt: '2024-01-15T10:30:00Z'
}

describe('DeploymentCard', () => {
  it('renders deployment information correctly', () => {
    const wrapper = mount(DeploymentCard, {
      props: { deployment: mockDeployment },
      global: {
        components: { ElButton, ElTag }
      }
    })

    expect(wrapper.text()).toContain('Test Deployment')
    expect(wrapper.text()).toContain('docker')
    expect(wrapper.text()).toContain('running')
  })

  it('emits view-logs event when logs button is clicked', async () => {
    const wrapper = mount(DeploymentCard, {
      props: { deployment: mockDeployment },
      global: {
        components: { ElButton, ElTag }
      }
    })

    await wrapper.find('[data-test="view-logs-btn"]').trigger('click')
    
    expect(wrapper.emitted('view-logs')).toEqual([['test-123']])
  })

  it('shows stop button for running deployments', () => {
    const wrapper = mount(DeploymentCard, {
      props: { deployment: mockDeployment },
      global: {
        components: { ElButton, ElTag }
      }
    })

    expect(wrapper.find('[data-test="stop-btn"]').exists()).toBe(true)
  })

  it('hides stop button for completed deployments', () => {
    const finishedDeployment = { 
      ...mockDeployment, 
      status: 'success' as const 
    }
    
    const wrapper = mount(DeploymentCard, {
      props: { deployment: finishedDeployment },
      global: {
        components: { ElButton, ElTag }
      }
    })

    expect(wrapper.find('[data-test="stop-btn"]').exists()).toBe(false)
  })
})
```

### Tests de Services API Frontend
```typescript
// tests/unit/services/deployment.service.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { deploymentService } from '@/services/deployment.service'
import type { DeploymentCreateRequest } from '@/types'

// Mock axios
vi.mock('axios')

describe('DeploymentService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('creates deployment successfully', async () => {
    // Arrange
    const mockResponse = {
      data: {
        data: {
          id: 'deploy-123',
          name: 'test-deployment',
          status: 'pending'
        }
      }
    }
    
    vi.mocked(axios.post).mockResolvedValueOnce(mockResponse)
    
    const request: DeploymentCreateRequest = {
      name: 'test-deployment',
      stackId: 'stack-123',
      targetType: 'docker'
    }

    // Act
    const result = await deploymentService.create(request)

    // Assert
    expect(result.data.name).toBe('test-deployment')
    expect(result.data.status).toBe('pending')
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/deployments',
      request
    )
  })

  it('handles API error correctly', async () => {
    // Arrange
    vi.mocked(axios.post).mockRejectedValueOnce(
      new Error('Network error')
    )

    const request: DeploymentCreateRequest = {
      name: 'test-deployment',
      stackId: 'stack-123',
      targetType: 'docker'
    }

    // Act & Assert
    await expect(
      deploymentService.create(request)
    ).rejects.toThrow('Network error')
  })
})
```

## Tests End-to-End avec Playwright

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
    ['json', { outputFile: 'test-results/results.json' }],
    ['junit', { outputFile: 'test-results/results.xml' }]
  ],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] }
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] }
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] }
    }
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI
  }
})
```

### Tests E2E Complets
```typescript
// tests/e2e/workflows/deployment-workflow.test.ts
import { test, expect, Page } from '@playwright/test'

test.describe('Deployment Workflow', () => {
  let page: Page

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage()
    
    // Authentification
    await page.goto('/login')
    await page.fill('[data-test="username"]', 'admin@windflow.local')
    await page.fill('[data-test="password"]', 'admin123')
    await page.click('[data-test="login-btn"]')
    
    await expect(page).toHaveURL('/dashboard')
  })

  test('complete deployment workflow', async () => {
    // Navigation vers déploiements
    await page.click('[data-test="nav-deployments"]')
    await expect(page).toHaveURL('/dashboard/deployments')

    // Création d'un nouveau déploiement
    await page.click('[data-test="create-deployment-btn"]')
    
    // Remplissage du formulaire
    await page.fill('[data-test="deployment-name"]', 'E2E Test Deployment')
    await page.selectOption('[data-test="stack-select"]', 'web-app')
    await page.selectOption('[data-test="environment-select"]', 'staging')
    await page.selectOption('[data-test="target-select"]', 'docker')
    
    // Soumission
    await page.click('[data-test="submit-btn"]')
    
    // Vérification de la création
    await expect(page.locator('[data-test="deployment-card"]')).toContainText('E2E Test Deployment')
    await expect(page.locator('[data-test="status-badge"]')).toContainText('pending')

    // Visualisation des détails
    await page.click('[data-test="deployment-card"]:first-child')
    await expect(page).toHaveURL(/\/dashboard\/deployments\/.*/)
    
    // Vérification des logs
    await page.click('[data-test="logs-tab"]')
    await expect(page.locator('[data-test="logs-container"]')).toBeVisible()
  })

  test('deployment error handling', async () => {
    // Création d'un déploiement avec configuration invalide
    await page.goto('/dashboard/deployments')
    await page.click('[data-test="create-deployment-btn"]')
    
    await page.fill('[data-test="deployment-name"]', 'Invalid Deployment')
    await page.selectOption('[data-test="stack-select"]', 'invalid-stack')
    
    await page.click('[data-test="submit-btn"]')
    
    // Vérification de l'erreur
    await expect(page.locator('[data-test="error-message"]')).toBeVisible()
    await expect(page.locator('[data-test="error-message"]')).toContainText('Stack not found')
  })
})
```

### Tests CLI avec Playwright
```python
# tests/e2e/test_cli_workflows.py
import pytest
import subprocess
import json
from pathlib import Path

@pytest.mark.e2e
class TestCLIWorkflows:
    """Tests end-to-end pour les workflows CLI."""
    
    def test_deployment_cli_workflow(self):
        """Test complet du workflow de déploiement CLI."""
        
        # Authentification
        result = subprocess.run([
            "windflow", "auth", "login",
            "--username", "admin@windflow.local",
            "--password", "admin123"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "Successfully authenticated" in result.stdout
        
        # Création de déploiement
        result = subprocess.run([
            "windflow", "deploy", "create",
            "--stack", "web-app",
            "--environment", "staging",
            "--target", "docker"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        
        # Extraction de l'ID du déploiement
        output_lines = result.stdout.split('\n')
        deployment_id = None
        for line in output_lines:
            if "Deployment ID:" in line:
                deployment_id = line.split(":")[1].strip()
                break
        
        assert deployment_id is not None
        
        # Vérification du statut
        result = subprocess.run([
            "windflow", "deploy", "status", deployment_id
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "Status:" in result.stdout
        
        # Nettoyage
        subprocess.run([
            "windflow", "deploy", "delete", deployment_id, "--confirm"
        ], capture_output=True, text=True)
```

## Tests de Performance

### Configuration des Tests de Performance
```python
# tests/performance/test_api_performance.py
import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
import statistics

@pytest.mark.performance
class TestAPIPerformance:
    """Tests de performance pour l'API."""
    
    @pytest.mark.asyncio
    async def test_concurrent_deployment_creation(self, client, auth_headers):
        """Test de création de déploiements concurrents."""
        
        async def create_deployment(index: int):
            """Crée un déploiement et mesure le temps."""
            start_time = time.time()
            
            response = client.post(
                "/api/v1/deployments",
                json={
                    "name": f"perf-test-{index}",
                    "target_type": "docker",
                    "configuration": {"image": "nginx"}
                },
                headers=auth_headers
            )
            
            end_time = time.time()
            return response.status_code == 201, end_time - start_time
        
        # Exécution de 100 créations concurrentes
        tasks = [create_deployment(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        
        # Analyse des résultats
        success_count = sum(1 for success, _ in results if success)
        response_times = [duration for _, duration in results]
        
        # Assertions de performance
        assert success_count >= 95  # 95% de succès minimum
        assert statistics.mean(response_times) < 1.0  # Temps moyen < 1s
        assert max(response_times) < 5.0  # Temps max < 5s
```

## Continuous Integration

### Configuration GitHub Actions
```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
