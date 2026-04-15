# Tests, couverture & quality gates

## Pyramide des tests

Unitaires > Intégration > E2E (peu, sur workflows critiques).

---

## Couverture minimale

- Minimum : 80% pour tout nouveau composant
- Cible backend : 85%+
- Cible frontend : 80%+
- Chemins critiques (auth, déploiement, RBAC) : viser 95%

---

## Outillage (voir `.clinerules/05-tech-stack.md`)

| Niveau | Backend | Frontend |
|--------|---------|----------|
| Unitaires | `pytest` + `pytest-asyncio` | `Vitest` |
| Intégration | `pytest` + DB réelle + Redis | `Vitest` + mocks HTTP |
| E2E | — | `Playwright` (workflows critiques) |

Toutes les commandes de lancement sont dans le `Makefile` (voir `.clinerules/55-project-structure.md`).

---

## Backend — patterns de tests

### Structure d'un test unitaire (service)

```python
# backend/tests/unit/test_services/test_xxx_service.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_docker_client():
    return AsyncMock()

@pytest.mark.asyncio
async def test_get_all_returns_empty_list(mock_docker_client):
    """Cas nominal : liste vide"""
    service = XxxService(docker_client=mock_docker_client)
    mock_docker_client.containers.list.return_value = []
    result = await service.get_all()
    assert result == []

@pytest.mark.asyncio
async def test_create_with_valid_data(mock_docker_client):
    """Cas nominal : création avec données valides"""
    ...

@pytest.mark.asyncio
async def test_create_raises_on_invalid_data(mock_docker_client):
    """Cas d'erreur : données invalides → exception métier"""
    ...
```

### Structure d'un test d'endpoint API

```python
# backend/tests/unit/test_api/test_xxx.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_xxx_list_authenticated(client: AsyncClient, auth_headers):
    """Cas nominal : liste accessible avec auth"""
    response = await client.get("/api/v1/xxx", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_get_xxx_list_unauthenticated(client: AsyncClient):
    """Sécurité : 401 sans token"""
    response = await client.get("/api/v1/xxx")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_create_xxx_forbidden_for_viewer(client: AsyncClient, viewer_headers):
    """Sécurité RBAC : 403 pour rôle insuffisant"""
    response = await client.post("/api/v1/xxx", json={...}, headers=viewer_headers)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_create_xxx_invalid_body(client: AsyncClient, auth_headers):
    """Validation : 422 avec body invalide"""
    response = await client.post("/api/v1/xxx", json={"invalid": "data"}, headers=auth_headers)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_get_xxx_not_found(client: AsyncClient, auth_headers):
    """Cas d'erreur : 404 si ressource inexistante"""
    response = await client.get("/api/v1/xxx/nonexistent-id", headers=auth_headers)
    assert response.status_code == 404
```

### Cas de test obligatoires par type d'endpoint

| Verbe | Cas nominaux | Cas d'erreur obligatoires |
|-------|-------------|--------------------------|
| GET (liste) | retourne liste vide, retourne liste avec éléments, pagination | 401, 403 (RBAC), 400 (paramètres invalides) |
| GET (détail) | retourne ressource complète | 401, 403, 404 |
| POST | crée avec données valides, retourne 201+objet créé | 401, 403, 422 (validation), 409 (conflit si applicable) |
| PUT/PATCH | met à jour partiellement, met à jour complètement | 401, 403, 404, 422 |
| DELETE | supprime, retourne 204 | 401, 403, 404 |

---

## Frontend — patterns de tests

### Structure d'un test composant (Vitest)

```typescript
// frontend/tests/unit/components/XxxComponent.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import XxxComponent from '@/components/XxxComponent.vue'

describe('XxxComponent', () => {
  describe('rendu initial', () => {
    it('affiche le loading spinner pendant le chargement', () => {
      const wrapper = mount(XxxComponent, {
        props: { id: '123' },
        global: { plugins: [createTestingPinia({ initialState: { xxx: { loading: true } } })] }
      })
      expect(wrapper.find('[data-testid="loading"]').exists()).toBe(true)
    })

    it('affiche les données quand chargées', async () => {
      const wrapper = mount(XxxComponent, { props: { id: '123' }, ... })
      expect(wrapper.text()).toContain('valeur attendue')
    })
  })

  describe('interactions', () => {
    it('émet un événement au clic sur le bouton', async () => {
      const wrapper = mount(XxxComponent, ...)
      await wrapper.find('button').trigger('click')
      expect(wrapper.emitted('action')).toBeTruthy()
    })
  })

  describe('cas d\'erreur', () => {
    it('affiche un message d\'erreur si l\'API échoue', async () => {
      // mock l'erreur dans le store
      ...
      expect(wrapper.find('[data-testid="error"]').text()).toBe('...')
    })
  })
})
```

### Structure d'un test composable (Vitest)

```typescript
// frontend/tests/unit/composables/useXxx.spec.ts
import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'
import { useXxx } from '@/composables/useXxx'

vi.mock('@/services/xxx', () => ({
  fetchXxx: vi.fn(),
}))

describe('useXxx', () => {
  it('retourne les données initiales vides', () => {
    const { items, loading, error } = useXxx()
    expect(items.value).toEqual([])
    expect(loading.value).toBe(false)
  })

  it('charge les données correctement', async () => {
    fetchXxx.mockResolvedValue([{ id: '1', name: 'test' }])
    const { items, load } = useXxx()
    await load()
    expect(items.value).toHaveLength(1)
  })

  it('gère les erreurs de l\'API', async () => {
    fetchXxx.mockRejectedValue(new Error('Network Error'))
    const { error, load } = useXxx()
    await load()
    expect(error.value).toBeTruthy()
  })
})
```

### Cas de test obligatoires pour les composants/vues

- **Rendu initial** : état vide, état chargement (spinner), état avec données
- **Interactions** : clic bouton, saisie formulaire, navigation
- **États d'erreur** : affichage message d'erreur, retry
- **Props/Emits** : vérifier les props requises, les événements émis
- **Accès conditionnel** : éléments cachés selon rôle/état

---

## Tests de sécurité obligatoires

Ces tests DOIVENT être écrits pour tout endpoint modifiant des données ou exposant des données sensibles.

### Backend

```python
# Toujours tester :
test_xxx_returns_401_when_no_token()         # Pas d'accès sans auth
test_xxx_returns_403_when_insufficient_role() # RBAC respecté
test_xxx_rejects_invalid_input()              # Protection injection (422)
test_xxx_does_not_expose_sensitive_fields()   # Pas de champs sensibles dans la réponse
```

### Frontend

```typescript
// Dans les tests de vues avec routes protégées :
it('redirige vers /login si non authentifié', ...)
it('masque les actions admin pour un rôle viewer', ...)
it('n\'affiche pas les tokens/secrets dans le DOM', ...)
```

---

## Commandes de validation

Se référer au `Makefile` (source de vérité) :

```bash
make test-backend          # pytest backend complet
make test-frontend         # Vitest frontend complet
make lint                  # Lint backend + frontend
make typecheck             # mypy + tsc strict
```

### Commandes ciblées lors du développement

```bash
# Backend — tests d'un module spécifique
poetry run pytest backend/tests/unit/test_services/test_xxx_service.py -v
poetry run pytest backend/tests/unit/test_api/test_xxx.py -v --tb=short

# Frontend — tests d'un fichier spécifique
cd frontend && pnpm test -- tests/unit/components/XxxComponent
cd frontend && pnpm test -- tests/unit/views/XxxView
cd frontend && pnpm build && pnpm lint
```

---

## Avant de conclure une étape

- Lancer les tests ciblés sur les fichiers modifiés/créés
- Vérifier la couverture si possible (`--cov` backend, `--coverage` frontend)
- Si impossible d'exécuter : préciser exactement ce qui n'a pas été lancé et fournir la commande
