# System Patterns - WindFlow

## Core Architecture Patterns

### Event-Driven Architecture
WindFlow uses Redis Streams for asynchronous communication between services:

```python
# Event publishing pattern
class EventPublisher:
    def __init__(self, redis_client):
        self.redis = redis_client
        
    async def publish_event(self, stream: str, event_type: str, data: dict):
        event = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        await self.redis.xadd(stream, event)

# Event consumption pattern
class EventConsumer:
    async def consume_events(self, stream: str, group: str, consumer: str):
        while True:
            messages = await self.redis.xreadgroup(
                group, consumer, {stream: ">"}, count=10, block=5000
            )
            for message in messages:
                await self.process_event(message)
```

**Key Benefits:**
- Loose coupling between services
- Scalable message processing
- Reliable event delivery with Redis persistence
- Easy debugging with stream inspection

### Repository Pattern with SQLAlchemy 2.0
All data access goes through repository interfaces:

```python
class TargetRepository(ABC):
    @abstractmethod
    async def create(self, target: TargetCreate) -> Target:
        pass
    
    @abstractmethod
    async def get_by_id(self, target_id: UUID) -> Optional[Target]:
        pass
    
    @abstractmethod
    async def get_by_organization(self, org_id: UUID) -> List[Target]:
        pass

class SQLTargetRepository(TargetRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, target: TargetCreate) -> Target:
        db_target = Target(**target.model_dump())
        self.db.add(db_target)
        await self.db.commit()
        await self.db.refresh(db_target)
        return db_target
```

**Benefits:**
- Testable data access layer
- Consistent API across different storage backends
- Easy mocking for unit tests
- Separation of concerns

### Dependency Injection with Container Pattern
Service dependencies are managed through a central container:

```python
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    # Database
    db = providers.Singleton(get_db_session)
    
    # Repositories
    target_repository = providers.Factory(
        SQLTargetRepository,
        db=db
    )
    
    # Services
    target_service = providers.Factory(
        TargetService,
        repository=target_repository,
        scanner=target_scanner
    )
    
    # API routes
    target_router = providers.Factory(
        TargetRouter,
        service=target_service
    )
```

**Advantages:**
- Clear dependency graph
- Easy testing with mocked dependencies
- Configuration management
- Singleton management for shared resources

## Frontend Architecture Patterns

### Pinia Store Composition Pattern
State management uses Pinia's composition API:

```typescript
export const useTargetsStore = defineStore('targets', () => {
  // Reactive state
  const targets = ref<Target[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  
  // Computed properties
  const activeTargets = computed(() =>
    targets.value.filter(t => t.status === 'active')
  )
  
  // Actions
  async function fetchTargets(): Promise<void> {
    loading.value = true
    try {
      const response = await targetsApi.list()
      targets.value = response.data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
    } finally {
      loading.value = false
    }
  }
  
  return {
    // State
    targets: readonly(targets),
    loading: readonly(loading),
    error: readonly(error),
    
    // Computed
    activeTargets,
    
    // Actions
    fetchTargets
  }
})
```

**Key Features:**
- Type-safe state management
- Reactive computed properties
- Async action handling
- Readonly state exposure

### API Service Layer Pattern
Centralized API communication with interceptors:

```typescript
class ApiService {
  constructor(private client: AxiosInstance) {
    this.setupInterceptors()
  }
  
  private setupInterceptors(): void {
    // Request interceptor for auth
    this.client.interceptors.request.use((config) => {
      const token = useAuthStore().token
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })
    
    // Response interceptor for token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401) {
          await useAuthStore().refreshToken()
          return this.client.request(error.config)
        }
        return Promise.reject(error)
      }
    )
  }
  
  async getTargets(params?: TargetListParams): Promise<ApiResponse<Target[]>> {
    const response = await this.client.get('/targets', { params })
    return response.data
  }
  
  async createTarget(data: TargetCreate): Promise<ApiResponse<Target>> {
    const response = await this.client.post('/targets', data)
    return response.data
  }
}
```

**Benefits:**
- Centralized error handling
- Automatic token management
- Consistent response transformation
- Easy mocking for tests

## Component Design Patterns

### Composition API Component Pattern
All Vue components use the Composition API:

```vue
<template>
  <div class="target-list">
    <div v-for="target in targets" :key="target.id" class="target-item">
      <TargetCard 
        :target="target"
        @edit="handleEdit"
        @delete="handleDelete"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useTargetsStore } from '@/stores/targets'
import TargetCard from './TargetCard.vue'

interface Props {
  organizationId?: string
}

interface Emits {
  'target-selected': [target: Target]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const targetsStore = useTargetsStore()

const targets = computed(() =>
  props.organizationId
    ? targetsStore.targets.filter(t => t.organizationId === props.organizationId)
    : targetsStore.targets
)

onMounted(async () => {
  await targetsStore.fetchTargets(props.organizationId)
})

function handleEdit(target: Target): void {
  emit('target-selected', target)
}

function handleDelete(targetId: string): void {
  // Handle deletion with confirmation
}
</script>
```

**Advantages:**
- Better TypeScript integration
- Improved code organization
- Easier testing
- Better performance with tree-shaking

## Error Handling Patterns

### Backend Error Hierarchy
Structured error handling with custom exceptions:

```python
class WindFlowException(Exception):
    """Base exception for all WindFlow errors."""
    
    def __init__(self, message: str, code: str = "WINDFLOW_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)

class ValidationError(WindFlowException):
    """Validation errors."""
    def __init__(self, message: str, field: str = None):
        super().__init__(message, "VALIDATION_ERROR", 400)
        self.field = field

class NotFoundError(WindFlowException):
    """Resource not found errors."""
    def __init__(self, resource: str, resource_id: str):
        message = f"{resource} with id {resource_id} not found"
        super().__init__(message, "NOT_FOUND", 404)
        self.resource = resource
        self.resource_id = resource_id

# Global exception handler
@app.exception_handler(WindFlowException)
async def windflow_exception_handler(request: Request, exc: WindFlowException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )
```

### Frontend Error Boundaries
Error boundaries for graceful error handling:

```vue
<template>
  <div>
    <slot v-if="!hasError" />
    <div v-else class="error-boundary">
      <h3>Oops! Something went wrong</h3>
      <p>{{ error?.message || 'An unexpected error occurred' }}</p>
      <el-button @click="retry">Try Again</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'

const hasError = ref(false)
const error = ref<Error | null>(null)

onErrorCaptured((err, instance, info) => {
  hasError.value = true
  error.value = err as Error
  
  // Log error for monitoring
  console.error('Error captured:', err, info)
  
  // Prevent error from propagating
  return false
})

function retry(): void {
  hasError.value = false
  error.value = null
  // Trigger component re-render
  location.reload()
}
</script>
```

## Testing Patterns

### Backend Testing with pytest
Comprehensive testing strategy:

```python
@pytest.mark.asyncio
class TestTargetService:
    @pytest.fixture
    def service(self):
        return TargetService()
    
    @pytest.fixture
    def mock_repository(self):
        return AsyncMock(spec=TargetRepository)
    
    async def test_create_target_success(
        self, service: TargetService, mock_repository: AsyncMock
    ):
        # Arrange
        target_data = TargetCreate(name="test", host="localhost", type="docker")
        expected_target = Target(id=uuid4(), **target_data.model_dump())
        
        mock_repository.create.return_value = expected_target
        
        # Act
        with patch.object(service, 'repository', mock_repository):
            result = await service.create_target(target_data)
        
        # Assert
        assert result == expected_target
        mock_repository.create.assert_called_once_with(target_data)
    
    async def test_create_target_validation_error(
        self, service: TargetService, mock_repository: AsyncMock
    ):
        # Arrange
        invalid_data = TargetCreate(name="", host="localhost", type="invalid")
        
        # Act & Assert
        with pytest.raises(ValidationError):
            await service.create_target(invalid_data)
```

### Frontend Testing with Vitest
Component and store testing:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TargetList from './TargetList.vue'

describe('TargetList', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  
  it('renders target list correctly', async () => {
    const mockTargets = [
      { id: '1', name: 'Target 1', status: 'active' },
      { id: '2', name: 'Target 2', status: 'inactive' }
    ]
    
    const wrapper = mount(TargetList, {
      props: { targets: mockTargets }
    })
    
    expect(wrapper.text()).toContain('Target 1')
    expect(wrapper.text()).toContain('Target 2')
  })
  
  it('emits target-selected event on item click', async () => {
    const mockTarget = { id: '1', name: 'Target 1', status: 'active' }
    
    const wrapper = mount(TargetList, {
      props: { targets: [mockTarget] }
    })
    
    await wrapper.find('.target-item').trigger('click')
    
    expect(wrapper.emitted('target-selected')).toEqual([[mockTarget]])
  })
})
```

## Security Patterns

### Authentication Flow
JWT-based authentication with refresh tokens:

```python
class AuthService:
    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    def create_refresh_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    async def refresh_access_token(self, refresh_token: str) -> tuple[str, str]:
        try:
            payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("type") != "refresh":
                raise JWTError("Invalid token type")
                
            user_id = payload.get("sub")
            new_access = self.create_access_token({"sub": user_id})
            new_refresh = self.create_refresh_token({"sub": user_id})
            
            return new_access, new_refresh
        except JWTError:
            raise AuthenticationError("Invalid refresh token")
```

### Authorization with RBAC
Role-based access control with permissions:

```python
class PermissionChecker:
    def __init__(self, user_permissions: list[str]):
        self.permissions = set(user_permissions)
    
    def has_permission(self, required_permission: str) -> bool:
        return required_permission in self.permissions
    
    def has_any_permission(self, permissions: list[str]) -> bool:
        return bool(self.permissions & set(permissions))
    
    def require_permission(self, permission: str) -> None:
        if not self.has_permission(permission):
            raise PermissionDeniedError(f"Missing permission: {permission}")

# Usage in API endpoints
@router.get("/targets/{target_id}")
async def get_target(
    target_id: str,
    current_user: User = Depends(get_current_user),
    checker: PermissionChecker = Depends(get_permission_checker)
):
    checker.require_permission("targets:read")
    
    # Check organization access
    target = await target_service.get_target(target_id)
    if target.organization_id != current_user.organization_id:
        checker.require_permission("targets:read_all")
    
    return target
```

## Performance Patterns

### Caching Strategy
Multi-layer caching with Redis:

```python
class CacheManager:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def get_or_set(self, key: str, getter: Callable, ttl: int = 300):
        # Try cache first
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        
        # Get fresh data
        data = await getter()
        
        # Cache result
        await self.redis.setex(key, ttl, json.dumps(data))
        
        return data
    
    async def invalidate_pattern(self, pattern: str):
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

# Usage in services
class TargetService:
    async def get_targets(self, organization_id: str):
        cache_key = f"targets:org:{organization_id}"
        
        return await self.cache.get_or_set(
            cache_key,
            lambda: self.repository.get_by_organization(organization_id),
            ttl=600  # 10 minutes
        )
    
    async def create_target(self, target_data):
        target = await self.repository.create(target_data)
        
        # Invalidate related caches
        await self.cache.invalidate_pattern(f"targets:org:{target.organization_id}")
        
        return target
```

### Database Optimization
Efficient queries with proper indexing:

```python
# Optimized queries with joins and selects
class OptimizedTargetRepository(SQLTargetRepository):
    async def get_targets_with_capabilities(self, organization_id: UUID):
        stmt = (
            select(Target)
            .options(
                selectinload(Target.capabilities),
                selectinload(Target.deployments).limit(5)
            )
            .where(Target.organization_id == organization_id)
            .order_by(Target.created_at.desc())
        )
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def search_targets(self, query: str, organization_id: UUID):
        # Full-text search with ts_vector
        search_vector = func.to_tsvector('english', Target.name + ' ' + Target.host)
        search_query = func.plainto_tsquery('english', query)
        
        stmt = (
            select(Target)
            .where(
                and_(
                    Target.organization_id == organization_id,
                    search_vector.op('@@')(search_query)
                )
            )
            .order_by(func.ts_rank(search_vector, search_query).desc())
        )
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
```

These patterns form the foundation of WindFlow's architecture, ensuring scalability, maintainability, and consistent development practices across the entire codebase.
