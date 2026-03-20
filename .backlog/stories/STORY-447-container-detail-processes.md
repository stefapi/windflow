# STORY-447 : Vue ContainerDetail — Onglet Processus

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace
**Type :** Amélioration

## Description
En tant qu'utilisateur WindFlow, je veux voir la liste des processus running dans un container Docker afin de pouvoir surveiller et diagnostiquer l'activité du container.

### Contexte
Cette story améliore la vue `ContainerDetail.vue` en ajoutant un onglet "Processus" après l'onglet "Stats". Le container detail a déjà 4 onglets (Infos, Logs, Terminal, Stats), cette amélioration ajoute un 5ème onglet.

### Comportement actuel
La vue ContainerDetail affiche 4 onglets : Infos, Logs, Terminal, Stats. Il n'y a pas de visibilité sur les processus running dans le container.

### Comportement attendu
Un nouvel onglet "Processus" affiche un tableau des processus avec :
- PID (Process ID)
- USER (Utilisateur)
- %CPU (Utilisation CPU)
- %MEM (Utilisation mémoire)
- TIME (Temps CPU)
- COMMAND (Commande)

## Critères d'acceptation (AC)
- [ ] AC 1 : L'onglet "Processus" apparaît à droite de l'onglet "Stats" dans ContainerDetail
- [ ] AC 2 : L'onglet affiche un tableau avec les colonnes PID, USER, CPU, MEM, TIME, COMMAND
- [ ] AC 3 : L'onglet est désactivé si le container n'est pas en état "running"
- [ ] AC 4 : Un bouton "Rafraîchir" permet de recharger la liste des processus
- [ ] AC 5 : Un toggle "Auto-refresh" permet de rafraîchir automatiquement toutes les 3 secondes
- [ ] AC 6 : L'API backend expose `GET /api/v1/docker/containers/{id}/top`
- [ ] AC 7 : Les tests unitaires backend et frontend passent
- [ ] AC 8 : L'amélioration ne casse pas les onglets existants (Infos, Logs, Terminal, Stats)

## État d'avancement technique
- [ ] Analyse du code existant (faite)
- [ ] Implémentation backend (schémas, service, endpoint)
- [ ] Implémentation frontend (composable, composant, intégration)
- [ ] Tests unitaires backend
- [ ] Tests unitaires frontend
- [ ] Vérification de non-régression

## Risques de régression

### Fichiers impactés
| Fichier | Impact | Action requise |
|---------|--------|----------------|
| `backend/app/schemas/docker.py` | Ajout de nouveaux schémas Pydantic | Aucun risque |
| `backend/app/services/docker_client_service.py` | Ajout méthode `list_processes()` | Aucun risque |
| `backend/app/api/v1/docker.py` | Ajout endpoint `GET /containers/{id}/top` | Aucun risque |
| `frontend/src/types/api.ts` | Ajout types TypeScript | Aucun risque |
| `frontend/src/composables/useContainerProcesses.ts` | Nouveau fichier | Aucun risque |
| `frontend/src/components/ContainerProcesses.vue` | Nouveau fichier | Aucun risque |
| `frontend/src/views/ContainerDetail.vue` | Ajout d'un onglet | Vérifier que les autres onglets fonctionnent |

### Fonctionnalités annexes à vérifier
- [ ] Onglet Infos : Vérifier l'affichage des informations générales
- [ ] Onglet Logs : Vérifier le streaming des logs
- [ ] Onglet Terminal : Vérifier la connexion WebSocket
- [ ] Onglet Stats : Vérifier le streaming des stats

### Tests existants à maintenir
- [ ] `backend/tests/unit/test_docker/test_docker_client_service.py` : Tests du service Docker
- [ ] `frontend/tests/unit/views/ContainerDetail.spec.ts` : Tests de la vue ContainerDetail

## Plan de non-régression

### Tests à exécuter avant modification
```bash
# Tests backend
pytest backend/tests/unit/test_docker/ -v

# Tests frontend
cd frontend && pnpm test ContainerDetail.spec.ts
```

### Tests à exécuter après modification
```bash
# Tests backend
pytest backend/tests/unit/test_docker/ -v
pytest backend/tests/unit/test_docker/test_container_processes.py -v

# Tests frontend
cd frontend && pnpm test

# Build et lint
cd frontend && pnpm build
cd frontend && pnpm lint
```

### Vérifications manuelles
- [ ] Ouvrir la page ContainerDetail d'un container running et vérifier l'onglet Processus
- [ ] Vérifier que le tableau se rafraîchit avec le bouton et l'auto-refresh
- [ ] Vérifier que l'onglet est désactivé pour un container stopped
- [ ] Vérifier que les autres onglets fonctionnent normalement

## Implémentation technique

### Backend

#### 1. Schémas Pydantic (`backend/app/schemas/docker.py`)
```python
class ContainerProcessResponse(BaseModel):
    """Processus d'un container."""
    pid: int
    user: str = ""
    cpu: float = 0.0
    mem: float = 0.0
    time: str = ""
    command: str = ""

class ContainerProcessListResponse(BaseModel):
    """Liste des processus d'un container."""
    container_id: str
    titles: list[str]  # En-têtes du tableau (PID, USER, %CPU, etc.)
    processes: list[ContainerProcessResponse]
    timestamp: datetime
```

#### 2. Service Docker (`backend/app/services/docker_client_service.py`)
```python
async def list_processes(self, container_id: str, ps_args: str = "aux") -> dict[str, Any]:
    """
    Liste les processus d'un container.
    GET /containers/{id}/top?ps_args=aux
    """
    response = await self._request(
        "GET", 
        f"/containers/{container_id}/top",
        params={"ps_args": ps_args}
    )
    return await response.json()
```

#### 3. Endpoint API (`backend/app/api/v1/docker.py`)
```python
@router.get(
    "/containers/{container_id}/top",
    response_model=ContainerProcessListResponse,
    summary="List container processes",
    description="Get the list of processes running in a container.",
    tags=["docker"],
)
async def get_container_processes(request: Request, container_id: str):
    """Liste les processus d'un container."""
    # Implementation
```

### Frontend

#### 1. Types TypeScript (`frontend/src/types/api.ts`)
```typescript
export interface ContainerProcess {
  pid: number
  user: string
  cpu: number
  mem: number
  time: string
  command: string
}

export interface ContainerProcessListResponse {
  container_id: string
  titles: string[]
  processes: ContainerProcess[]
  timestamp: string
}
```

#### 2. Composable (`frontend/src/composables/useContainerProcesses.ts`)
- Gestion de l'état (loading, error, processes)
- Fetch des processus via API
- Auto-refresh avec intervalle configurable

#### 3. Composant (`frontend/src/components/ContainerProcesses.vue`)
- Tableau Element Plus avec les colonnes requises
- Header avec statut et contrôles (refresh, auto-refresh toggle)
- États loading/error/empty
