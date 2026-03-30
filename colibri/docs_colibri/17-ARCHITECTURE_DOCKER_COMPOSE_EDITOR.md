# Architecture : Éditeur Docker Compose avec Python/FastAPI et Vue3/Vite

## Vue d'ensemble

Ce document décrit comment porter l'éditeur Docker Compose `ComposeGraphViewer.svelte` (actuellement implémenté en Svelte 5) vers une architecture Python/FastAPI + Vue3/Vite, tout en préservant toutes les fonctionnalités avancées.

### Fonctionnalités clés à préserver

- **Visualisation graphique** avec Cytoscape.js
- **Édition interactive** : modes connexion et montage
- **Parsing YAML** avec récupération d'erreurs partielles
- **Layouts multiples** : breadthfirst, grid, circle, concentric, cose
- **Thèmes** : clair/obscur avec palettes de couleurs par type de nœud
- **Éditeurs détaillés** : panneaux latéraux pour services, networks, volumes, configs, secrets
- **Synchronisation temps réel** : graph ↔️ YAML
- **Nœuds fantômes** : affichage des dépendances manquantes
- **Support multi-ressources** : services, networks, volumes, configs, secrets

## Architecture Backend (Python/FastAPI)

### Structure du projet

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # Point d'entrée FastAPI
│   ├── config.py                  # Configuration
│   ├── models/
│   │   ├── __init__.py
│   │   ├── compose.py             # Modèles Pydantic pour Docker Compose
│   │   ├── graph.py               # Modèles pour éléments Cytoscape
│   │   └── stack.py               # Modèle Stack
│   ├── services/
│   │   ├── __init__.py
│   │   ├── compose_parser.py     # Parsing YAML avec récupération d'erreurs
│   │   ├── compose_validator.py  # Validation Docker Compose
│   │   ├── graph_builder.py      # Conversion YAML → éléments Cytoscape
│   │   └── yaml_generator.py     # Génération YAML depuis graph
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── stacks.py              # Routes CRUD stacks
│   │   └── compose.py             # Routes manipulation compose
│   └── utils/
│       ├── __init__.py
│       └── error_recovery.py      # Utilitaires récupération erreurs
├── tests/
├── requirements.txt
└── README.md
```

### Dépendances Python

```txt
# requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.9.0
pyyaml==6.0.2
python-multipart==0.0.12
```

### Modèles Pydantic

#### models/compose.py

```python
from typing import Optional, Dict, List, Any, Union
from pydantic import BaseModel, Field


class Service(BaseModel):
    """Service Docker Compose"""
    image: Optional[str] = None
    build: Optional[Union[str, Dict[str, Any]]] = None
    command: Optional[Union[str, List[str]]] = None
    environment: Optional[Union[Dict[str, str], List[str]]] = None
    ports: Optional[List[str]] = None
    volumes: Optional[List[str]] = None
    networks: Optional[Union[List[str], Dict[str, Any]]] = None
    depends_on: Optional[Union[List[str], Dict[str, Any]]] = None
    configs: Optional[List[Union[str, Dict[str, Any]]]] = None
    secrets: Optional[List[Union[str, Dict[str, Any]]]] = None
    # Autres champs Docker Compose...
    extra: Dict[str, Any] = Field(default_factory=dict)


class Network(BaseModel):
    """Network Docker Compose"""
    driver: Optional[str] = None
    driver_opts: Optional[Dict[str, str]] = None
    external: Optional[bool] = None
    name: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class Volume(BaseModel):
    """Volume Docker Compose"""
    driver: Optional[str] = None
    driver_opts: Optional[Dict[str, str]] = None
    external: Optional[bool] = None
    name: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class Config(BaseModel):
    """Config Docker Compose"""
    file: Optional[str] = None
    external: Optional[bool] = None
    name: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class Secret(BaseModel):
    """Secret Docker Compose"""
    file: Optional[str] = None
    external: Optional[bool] = None
    name: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class ComposeFile(BaseModel):
    """Fichier Docker Compose complet"""
    version: Optional[str] = None
    services: Dict[str, Service] = Field(default_factory=dict)
    networks: Dict[str, Network] = Field(default_factory=dict)
    volumes: Dict[str, Volume] = Field(default_factory=dict)
    configs: Dict[str, Config] = Field(default_factory=dict)
    secrets: Dict[str, Secret] = Field(default_factory=dict)
    extra: Dict[str, Any] = Field(default_factory=dict)
```

#### models/graph.py

```python
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel


NodeType = Literal["service", "network", "volume", "config", "secret", "ghost"]


class NodeData(BaseModel):
    """Données d'un nœud Cytoscape"""
    id: str
    label: str
    type: NodeType
    image: Optional[str] = None
    details: Dict[str, Any] = {}


class EdgeData(BaseModel):
    """Données d'une arête Cytoscape"""
    id: str
    source: str
    target: str
    type: str  # depends_on, mount_volume, mount_network, mount_config, mount_secret


class CytoscapeNode(BaseModel):
    """Nœud Cytoscape"""
    group: Literal["nodes"] = "nodes"
    data: NodeData
    position: Optional[Dict[str, float]] = None
    classes: str = ""


class CytoscapeEdge(BaseModel):
    """Arête Cytoscape"""
    group: Literal["edges"] = "edges"
    data: EdgeData
    classes: str = ""


class GraphElements(BaseModel):
    """Éléments du graph Cytoscape"""
    nodes: List[CytoscapeNode]
    edges: List[CytoscapeEdge]
```

### Services Backend

#### services/compose_parser.py

```python
import yaml
from typing import Dict, Any, Tuple, List
from ..models.compose import ComposeFile


class ComposeParser:
    """Parser YAML Docker Compose avec récupération d'erreurs"""
    
    def parse(self, content: str) -> Tuple[ComposeFile, List[str]]:
        """
        Parse le contenu YAML avec récupération d'erreurs
        
        Returns:
            Tuple[ComposeFile, List[str]]: (fichier parsé, erreurs)
        """
        errors = []
        
        try:
            # Tentative de parsing standard
            data = yaml.safe_load(content)
            
            if not isinstance(data, dict):
                errors.append("Le fichier doit contenir un objet YAML")
                return ComposeFile(), errors
            
            # Validation et conversion en modèle Pydantic
            compose = self._parse_compose_data(data, errors)
            
            return compose, errors
            
        except yaml.YAMLError as e:
            # Récupération partielle en cas d'erreur
            errors.append(f"Erreur YAML: {str(e)}")
            return self._partial_parse(content, errors)
    
    def _parse_compose_data(self, data: Dict[str, Any], errors: List[str]) -> ComposeFile:
        """Parse les données YAML en modèle ComposeFile"""
        try:
            # Extraction des sections principales
            services = self._parse_services(data.get('services', {}), errors)
            networks = self._parse_networks(data.get('networks', {}), errors)
            volumes = self._parse_volumes(data.get('volumes', {}), errors)
            configs = self._parse_configs(data.get('configs', {}), errors)
            secrets = self._parse_secrets(data.get('secrets', {}), errors)
            
            return ComposeFile(
                version=data.get('version'),
                services=services,
                networks=networks,
                volumes=volumes,
                configs=configs,
                secrets=secrets,
                extra={k: v for k, v in data.items() 
                       if k not in ['version', 'services', 'networks', 'volumes', 'configs', 'secrets']}
            )
        except Exception as e:
            errors.append(f"Erreur de parsing: {str(e)}")
            return ComposeFile()
    
    def _parse_services(self, services_data: Dict[str, Any], errors: List[str]) -> Dict[str, Any]:
        """Parse la section services"""
        services = {}
        
        for name, service_data in services_data.items():
            if not isinstance(service_data, dict):
                errors.append(f"Service '{name}': données invalides")
                continue
            
            try:
                # Normaliser depends_on
                depends_on = service_data.get('depends_on')
                if isinstance(depends_on, dict):
                    # Format étendu: {"db": {"condition": "service_healthy"}}
                    service_data['depends_on'] = list(depends_on.keys())
                
                services[name] = service_data
                
            except Exception as e:
                errors.append(f"Service '{name}': {str(e)}")
        
        return services
    
    def _parse_networks(self, networks_data: Any, errors: List[str]) -> Dict[str, Any]:
        """Parse la section networks"""
        if networks_data is None:
            return {}
        
        if not isinstance(networks_data, dict):
            errors.append("Networks doit être un objet")
            return {}
        
        networks = {}
        for name, network_data in networks_data.items():
            # Gestion du format court (null) et étendu
            networks[name] = network_data if isinstance(network_data, dict) else {}
        
        return networks
    
    def _parse_volumes(self, volumes_data: Any, errors: List[str]) -> Dict[str, Any]:
        """Parse la section volumes"""
        if volumes_data is None:
            return {}
        
        if not isinstance(volumes_data, dict):
            errors.append("Volumes doit être un objet")
            return {}
        
        volumes = {}
        for name, volume_data in volumes_data.items():
            volumes[name] = volume_data if isinstance(volume_data, dict) else {}
        
        return volumes
    
    def _parse_configs(self, configs_data: Any, errors: List[str]) -> Dict[str, Any]:
        """Parse la section configs"""
        if configs_data is None:
            return {}
        
        if not isinstance(configs_data, dict):
            errors.append("Configs doit être un objet")
            return {}
        
        return configs_data
    
    def _parse_secrets(self, secrets_data: Any, errors: List[str]) -> Dict[str, Any]:
        """Parse la section secrets"""
        if secrets_data is None:
            return {}
        
        if not isinstance(secrets_data, dict):
            errors.append("Secrets doit être un objet")
            return {}
        
        return secrets_data
    
    def _partial_parse(self, content: str, errors: List[str]) -> ComposeFile:
        """
        Tentative de récupération partielle en cas d'erreur YAML
        Extrait ce qui est parsable du contenu
        """
        # Stratégie: parser ligne par ligne pour identifier les sections valides
        lines = content.split('\n')
        partial_data = {
            'services': {},
            'networks': {},
            'volumes': {},
            'configs': {},
            'secrets': {}
        }
        
        current_section = None
        
        for line in lines:
            stripped = line.strip()
            
            # Détection des sections principales
            if stripped in ['services:', 'networks:', 'volumes:', 'configs:', 'secrets:']:
                current_section = stripped[:-1]
                continue
            
            # Tentative d'extraction des noms de ressources
            if current_section and stripped and not stripped.startswith('#'):
                if ':' in stripped:
                    name = stripped.split(':')[0].strip()
                    if name and not name.startswith('-'):
                        partial_data[current_section][name] = {}
        
        errors.append("Parsing partiel effectué suite à des erreurs YAML")
        return self._parse_compose_data(partial_data, errors)
```

#### services/graph_builder.py

```python
from typing import List, Set
from ..models.compose import ComposeFile
from ..models.graph import (
    GraphElements, CytoscapeNode, CytoscapeEdge,
    NodeData, EdgeData
)


class GraphBuilder:
    """Construit les éléments Cytoscape depuis un fichier Compose"""
    
    def build(self, compose: ComposeFile) -> GraphElements:
        """Construit le graph complet"""
        nodes: List[CytoscapeNode] = []
        edges: List[CytoscapeEdge] = []
        
        # Collecter tous les noms de services/réseaux/volumes définis
        defined_services = set(compose.services.keys())
        defined_networks = set(compose.networks.keys())
        defined_volumes = set(compose.volumes.keys())
        defined_configs = set(compose.configs.keys())
        defined_secrets = set(compose.secrets.keys())
        
        # Créer les nœuds pour les services
        for name, service in compose.services.items():
            nodes.append(self._create_service_node(name, service))
        
        # Créer les nœuds pour les networks
        for name, network in compose.networks.items():
            nodes.append(self._create_network_node(name, network))
        
        # Créer les nœuds pour les volumes
        for name, volume in compose.volumes.items():
            nodes.append(self._create_volume_node(name, volume))
        
        # Créer les nœuds pour les configs
        for name, config in compose.configs.items():
            nodes.append(self._create_config_node(name, config))
        
        # Créer les nœuds pour les secrets
        for name, secret in compose.secrets.items():
            nodes.append(self._create_secret_node(name, secret))
        
        # Traquer les dépendances manquantes
        ghost_services: Set[str] = set()
        
        # Créer les arêtes pour les dépendances entre services
        for service_name, service in compose.services.items():
            depends_on = service.depends_on or []
            
            if isinstance(depends_on, dict):
                depends_on = list(depends_on.keys())
            
            for dep in depends_on:
                # Créer un nœud fantôme si la dépendance n'existe pas
                if dep not in defined_services and dep not in ghost_services:
                    ghost_services.add(dep)
                    nodes.append(self._create_ghost_node(dep))
                
                edges.append(self._create_dependency_edge(service_name, dep))
            
            # Arêtes pour les volumes
            volumes = service.volumes or []
            for volume_spec in volumes:
                volume_name = self._extract_volume_name(volume_spec)
                if volume_name and volume_name in defined_volumes:
                    edges.append(self._create_mount_edge(
                        volume_name, service_name, "mount_volume"
                    ))
            
            # Arêtes pour les networks
            networks = service.networks or []
            if isinstance(networks, list):
                for network in networks:
                    if network in defined_networks:
                        edges.append(self._create_mount_edge(
                            network, service_name, "mount_network"
                        ))
            elif isinstance(networks, dict):
                for network in networks.keys():
                    if network in defined_networks:
                        edges.append(self._create_mount_edge(
                            network, service_name, "mount_network"
                        ))
            
            # Arêtes pour les configs
            configs = service.configs or []
            for config_spec in configs:
                config_name = self._extract_resource_name(config_spec)
                if config_name and config_name in defined_configs:
                    edges.append(self._create_mount_edge(
                        config_name, service_name, "mount_config"
                    ))
            
            # Arêtes pour les secrets
            secrets = service.secrets or []
            for secret_spec in secrets:
                secret_name = self._extract_resource_name(secret_spec)
                if secret_name and secret_name in defined_secrets:
                    edges.append(self._create_mount_edge(
                        secret_name, service_name, "mount_secret"
                    ))
        
        return GraphElements(nodes=nodes, edges=edges)
    
    def _create_service_node(self, name: str, service: Any) -> CytoscapeNode:
        """Crée un nœud service"""
        return CytoscapeNode(
            data=NodeData(
                id=f"service-{name}",
                label=name,
                type="service",
                image=service.image if hasattr(service, 'image') else None,
                details=service.dict() if hasattr(service, 'dict') else {}
            ),
            classes="service"
        )
    
    def _create_network_node(self, name: str, network: Any) -> CytoscapeNode:
        """Crée un nœud network"""
        return CytoscapeNode(
            data=NodeData(
                id=f"network-{name}",
                label=name,
                type="network",
                details=network.dict() if hasattr(network, 'dict') else {}
            ),
            classes="network"
        )
    
    def _create_volume_node(self, name: str, volume: Any) -> CytoscapeNode:
        """Crée un nœud volume"""
        return CytoscapeNode(
            data=NodeData(
                id=f"volume-{name}",
                label=name,
                type="volume",
                details=volume.dict() if hasattr(volume, 'dict') else {}
            ),
            classes="volume"
        )
    
    def _create_config_node(self, name: str, config: Any) -> CytoscapeNode:
        """Crée un nœud config"""
        return CytoscapeNode(
            data=NodeData(
                id=f"config-{name}",
                label=name,
                type="config",
                details=config.dict() if hasattr(config, 'dict') else {}
            ),
            classes="config"
        )
    
    def _create_secret_node(self, name: str, secret: Any) -> CytoscapeNode:
        """Crée un nœud secret"""
        return CytoscapeNode(
            data=NodeData(
                id=f"secret-{name}",
                label=name,
                type="secret",
                details=secret.dict() if hasattr(secret, 'dict') else {}
            ),
            classes="secret"
        )
    
    def _create_ghost_node(self, name: str) -> CytoscapeNode:
        """Crée un nœud fantôme pour une dépendance manquante"""
        return CytoscapeNode(
            data=NodeData(
                id=f"service-{name}",
                label=f"{name} (manquant)",
                type="ghost",
                details={}
            ),
            classes="ghost"
        )
    
    def _create_dependency_edge(self, source: str, target: str) -> CytoscapeEdge:
        """Crée une arête de dépendance"""
        return CytoscapeEdge(
            data=EdgeData(
                id=f"dep-{source}-{target}",
                source=f"service-{source}",
                target=f"service-{target}",
                type="depends_on"
            ),
            classes="dependency"
        )
    
    def _create_mount_edge(self, source: str, target: str, edge_type: str) -> CytoscapeEdge:
        """Crée une arête de montage (volume/network/config/secret)"""
        source_prefix = edge_type.replace("mount_", "")
        return CytoscapeEdge(
            data=EdgeData(
                id=f"{edge_type}-{source}-{target}",
                source=f"{source_prefix}-{source}",
                target=f"service-{target}",
                type=edge_type
            ),
            classes=edge_type
        )
    
    def _extract_volume_name(self, volume_spec: str) -> str:
        """Extrait le nom du volume depuis une spécification"""
        # Format: "volume_name:/path" ou "./path:/path"
        if ':' in volume_spec:
            parts = volume_spec.split(':')
            source = parts[0]
            # Ignorer les bind mounts (chemins relatifs/absolus)
            if not source.startswith('.') and not source.startswith('/'):
                return source
        return ""
    
    def _extract_resource_name(self, resource_spec: Any) -> str:
        """Extrait le nom d'une ressource (config/secret)"""
        if isinstance(resource_spec, str):
            return resource_spec
        elif isinstance(resource_spec, dict) and 'source' in resource_spec:
            return resource_spec['source']
        return ""
```

#### services/yaml_generator.py

```python
import yaml
from typing import Dict, Any, List
from ..models.graph import GraphElements


class YAMLGenerator:
    """Génère du YAML Docker Compose depuis des éléments Cytoscape"""
    
    def generate(self, elements: GraphElements) -> str:
        """
        Génère le contenu YAML depuis le graph
        
        Args:
            elements: Éléments Cytoscape (nodes + edges)
        
        Returns:
            str: Contenu YAML généré
        """
        compose_data: Dict[str, Any] = {
            'version': '3.8',
            'services': {},
            'networks': {},
            'volumes': {},
            'configs': {},
            'secrets': {}
        }
        
        # Reconstruire les services, networks, volumes, etc. depuis les nœuds
        for node in elements.nodes:
            node_type = node.data.type
            node_id = node.data.id
            name = node_id.split('-', 1)[1]  # Retirer le préfixe "service-", "network-", etc.
            
            if node_type == "service":
                compose_data['services'][name] = node.data.details
            elif node_type == "network":
                compose_data['networks'][name] = node.data.details
            elif node_type == "volume":
                compose_data['volumes'][name] = node.data.details
            elif node_type == "config":
                compose_data['configs'][name] = node.data.details
            elif node_type == "secret":
                compose_data['secrets'][name] = node.data.details
            # Ignorer les nœuds fantômes
        
        # Reconstruire les dépendances et montages depuis les arêtes
        for edge in elements.edges:
            edge_type = edge.data.type
            source_id = edge.data.source
            target_id = edge.data.target
            
            # Extraire les noms
            target_name = target_id.split('-', 1)[1]
            
            if edge_type == "depends_on":
                source_name = source_id.split('-', 1)[1]
                
                # Ajouter à depends_on du service source
                if target_name not in compose_data['services']:
                    continue
                
                service = compose_data['services'][target_name]
                if 'depends_on' not in service:
                    service['depends_on'] = []
                
                if isinstance(service['depends_on'], list):
                    if source_name not in service['depends_on']:
                        service['depends_on'].append(source_name)
            
            elif edge_type == "mount_volume":
                source_name = source_id.split('-', 1)[1]
                
                if target_name not in compose_data['services']:
                    continue
                
                service = compose_data['services'][target_name]
                if 'volumes' not in service:
                    service['volumes'] = []
                
                # Format simplifié: "volume_name:/data"
                volume_mount = f"{source_name}:/data"
                if volume_mount not in service['volumes']:
                    service['volumes'].append(volume_mount)
            
            elif edge_type == "mount_network":
                source_name = source_id.split('-', 1)[1]
                
                if target_name not in compose_data['services']:
                    continue
                
                service = compose_data['services'][target_name]
                if 'networks' not in service:
                    service['networks'] = []
                
                if isinstance(service['networks'], list):
                    if source_name not in service['networks']:
                        service['networks'].append(source_name)
            
            elif edge_type == "mount_config":
                source_name = source_id.split('-', 1)[1]
                
                if target_name not in compose_data['services']:
                    continue
                
                service = compose_data['services'][target_name]
                if 'configs' not in service:
                    service['configs'] = []
                
                if source_name not in service['configs']:
                    service['configs'].append(source_name)
            
            elif edge_type == "mount_secret":
                source_name = source_id.split('-', 1)[1]
                
                if target_name not in compose_data['services']:
                    continue
                
                service = compose_data['services'][target_name]
                if 'secrets' not in service:
                    service['secrets'] = []
                
                if source_name not in service['secrets']:
                    service['secrets'].append(source_name)
        
        # Supprimer les sections vides
        for section in ['networks', 'volumes', 'configs', 'secrets']:
            if not compose_data[section]:
                del compose_data[section]
        
        # Générer le YAML
        return yaml.dump(compose_data, default_flow_style=False, sort_keys=False)
```

### Routes API

#### routers/compose.py

```python
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel

from ..services.compose_parser import ComposeParser
from ..services.graph_builder import GraphBuilder
from ..services.yaml_generator import YAMLGenerator
from ..models.graph import GraphElements


router = APIRouter(prefix="/api/compose", tags=["compose"])

parser = ComposeParser()
graph_builder = GraphBuilder()
yaml_generator = YAMLGenerator()


class ParseRequest(BaseModel):
    content: str


class ParseResponse(BaseModel):
    compose: Dict[str, Any]
    graph_elements: GraphElements
    errors: list[str]


class GenerateYAMLRequest(BaseModel):
    graph_elements: GraphElements


class GenerateYAMLResponse(BaseModel):
    yaml_content: str


@router.post("/parse", response_model=ParseResponse)
async def parse_compose(request: ParseRequest):
    """
    Parse un fichier Docker Compose et retourne le modèle + éléments graph
    """
    # Parser le YAML
    compose, errors = parser.parse(request.content)
    
    # Générer les éléments du graph
    graph_elements = graph_builder.build(compose)
    
    return ParseResponse(
        compose=compose.dict(),
        graph_elements=graph_elements,
        errors=errors
    )


@router.post("/generate-yaml", response_model=GenerateYAMLResponse)
async def generate_yaml(request: GenerateYAMLRequest):
    """
    Génère du YAML Docker Compose depuis des éléments Cytoscape
    """
    yaml_content = yaml_generator.generate(request.graph_elements)
    
    return GenerateYAMLResponse(yaml_content=yaml_content)


@router.post("/validate")
async def validate_compose(request: ParseRequest):
    """
    Valide un fichier Docker Compose
    """
    compose, errors = parser.parse(request.content)
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }
```

### Point d'entrée FastAPI

#### main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import compose

app = FastAPI(
    title="Docker Compose Editor API",
    description="API pour l'éditeur Docker Compose",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enregistrement des routers
app.include_router(compose.router)


@app.get("/")
async def root():
    return {"message": "Docker Compose Editor API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Architecture Frontend (Vue3/Vite)

### Structure du projet

```
frontend/
├── src/
│   ├── main.ts                        # Point d'entrée
│   ├── App.vue                        # Composant racine
│   ├── components/
│   │   ├── ComposeGraphViewer.vue    # Éditeur graphique principal
│   │   ├── LayoutSelector.vue        # Sélecteur de layout
│   │   ├── ThemeToggle.vue           # Basculement thème
│   │   ├── AddElementDialog.vue      # Dialog ajout éléments
│   │   └── editors/
│   │       ├── ServiceEditor.vue     # Éditeur service
│   │       ├── NetworkEditor.vue     # Éditeur network
│   │       ├── VolumeEditor.vue      # Éditeur volume
│   │       ├── ConfigEditor.vue      # Éditeur config
│   │       └── SecretEditor.vue      # Éditeur secret
│   ├── composables/
│   │   ├── useCytoscape.ts           # Hook Cytoscape
│   │   ├── useComposeParser.ts       # Hook parsing
│   │   └── useTheme.ts               # Hook thème
│   ├── types/
│   │   ├── compose.ts                # Types Docker Compose
│   │   └── graph.ts                  # Types Cytoscape
│   ├── utils/
│   │   ├── cytoscapeStyles.ts        # Styles Cytoscape
│   │   └── api.ts                    # Client API
│   └── assets/
│       └── styles/
│           └── main.css
├── package.json
├── vite.config.ts
├── tsconfig.json
└── index.html
```

### Dépendances Frontend

```json
{
  "name": "docker-compose-editor-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "cytoscape": "^3.28.1",
    "js-yaml": "^4.1.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vue-tsc": "^1.8.0",
    "@types/cytoscape": "^3.19.0",
    "@types/js-yaml": "^4.0.9"
  }
}
```

### Types TypeScript

#### types/compose.ts

```typescript
export interface Service {
  image?: string;
  build?: string | { context: string; dockerfile?: string };
  command?: string | string[];
  environment?: Record<string, string> | string[];
  ports?: string[];
  volumes?: string[];
  networks?: string[] | Record<string, any>;
  depends_on?: string[] | Record<string, any>;
  configs?: Array<string | { source: string; target: string }>;
  secrets?: Array<string | { source: string; target: string }>;
  [key: string]: any;
}

export interface Network {
  driver?: string;
  driver_opts?: Record<string, string>;
  external?: boolean;
  name?: string;
  [key: string]: any;
}

export interface Volume {
  driver?: string;
  driver_opts?: Record<string, string>;
  external?: boolean;
  name?: string;
  [key: string]: any;
}

export interface Config {
  file?: string;
  external?: boolean;
  name?: string;
  [key: string]: any;
}

export interface Secret {
  file?: string;
  external?: boolean;
  name?: string;
  [key: string]: any;
}

export interface ComposeFile {
  version?: string;
  services: Record<string, Service>;
  networks?: Record<string, Network>;
  volumes?: Record<string, Volume>;
  configs?: Record<string, Config>;
  secrets?: Record<string, Secret>;
}
```

#### types/graph.ts

```typescript
import type { Core, NodeDefinition, EdgeDefinition } from 'cytoscape';

export type NodeType = 'service' | 'network' | 'volume' | 'config' | 'secret' | 'ghost';
export type EdgeType = 'depends_on' | 'mount_volume' | 'mount_network' | 'mount_config' | 'mount_secret';
export type LayoutName = 'breadthfirst' | 'grid' | 'circle' | 'concentric' | 'cose';
export type InteractionMode = 'normal' | 'connection' | 'mount';

export interface GraphNode extends NodeDefinition {
  data: {
    id: string;
    label: string;
    type: NodeType;
    image?: string;
    details: any;
  };
  classes: string;
}

export interface GraphEdge extends EdgeDefinition {
  data: {
    id: string;
    source: string;
    target: string;
    type: EdgeType;
  };
  classes: string;
}

export interface GraphElements {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
```

### Composant Principal : ComposeGraphViewer.vue

```vue
<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import { useCytoscape } from '@/composables/useCytoscape';
import { useComposeParser } from '@/composables/useComposeParser';
import { useTheme } from '@/composables/useTheme';
import LayoutSelector from './LayoutSelector.vue';
import ThemeToggle from './ThemeToggle.vue';
import AddElementDialog from './AddElementDialog.vue';
import ServiceEditor from './editors/ServiceEditor.vue';
import type { LayoutName, InteractionMode, NodeType } from '@/types/graph';

interface Props {
  composeContent: string;
  onContentChange?: (content: string) => void;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  contentChange: [content: string];
}>();

// Container pour Cytoscape
const graphContainer = ref<HTMLElement | null>(null);

// États
const layout = ref<LayoutName>('breadthfirst');
const interactionMode = ref<InteractionMode>('normal');
const selectedNode = ref<any>(null);
const connectionSource = ref<string | null>(null);
const mountSource = ref<{ name: string; type: NodeType } | null>(null);
const showAddDialog = ref(false);
const errors = ref<string[]>([]);

// Composables
const { isDark } = useTheme();
const { parseCompose, generateYAML } = useComposeParser();
const {
  cy,
  initCytoscape,
  updateLayout,
  addNode,
  addEdge,
  removeNode,
  removeEdge,
  updateNodeData,
  getElements,
} = useCytoscape(graphContainer, isDark);

// Parser le contenu initial
onMounted(async () => {
  await loadCompose(props.composeContent);
});

// Synchroniser le contenu
watch(() => props.composeContent, async (newContent) => {
  await loadCompose(newContent);
});

// Changer le layout
watch(layout, (newLayout) => {
  updateLayout(newLayout);
});

// Changer le thème
watch(isDark, () => {
  if (cy.value) {
    // Réappliquer les styles avec le nouveau thème
    initCytoscape(getElements());
  }
});

async function loadCompose(content: string) {
  try {
    const result = await parseCompose(content);
    errors.value = result.errors;
    
    if (result.graph_elements) {
      initCytoscape(result.graph_elements);
    }
  } catch (error) {
    console.error('Erreur parsing:', error);
    errors.value = ['Erreur lors du parsing du fichier'];
  }
}

async function syncToYAML() {
  try {
    const elements = getElements();
    const yamlContent = await generateYAML(elements);
    
    if (props.onContentChange) {
      props.onContentChange(yamlContent);
    }
    emit('contentChange', yamlContent);
  } catch (error) {
    console.error('Erreur génération YAML:', error);
  }
}

// Gestion des modes d'interaction
function enterConnectionMode() {
  interactionMode.value = 'connection';
  connectionSource.value = null;
}

function enterMountMode() {
  interactionMode.value = 'mount';
  mountSource.value = null;
}

function exitSpecialMode() {
  interactionMode.value = 'normal';
  connectionSource.value = null;
  mountSource.value = null;
}

// Gestionnaires d'événements Cytoscape
function setupEventHandlers() {
  if (!cy.value) return;
  
  // Clic sur un nœud
  cy.value.on('tap', 'node', (event) => {
    const node = event.target;
    const nodeData = node.data();
    
    if (interactionMode.value === 'connection') {
      handleConnectionMode(nodeData);
    } else if (interactionMode.value === 'mount') {
      handleMountMode(nodeData);
    } else {
      // Mode normal : sélectionner le nœud pour édition
      selectedNode.value = nodeData;
    }
  });
  
  // Clic sur le fond : désélectionner
  cy.value.on('tap', (event) => {
    if (event.target === cy.value) {
      selectedNode.value = null;
      if (interactionMode.value !== 'normal') {
        exitSpecialMode();
      }
    }
  });
  
  // Double-clic sur un nœud : ouvrir l'éditeur
  cy.value.on('dbltap', 'node', (event) => {
    const node = event.target;
    selectedNode.value = node.data();
  });
}

function handleConnectionMode(nodeData: any) {
  // Mode connexion : créer des dépendances entre services
  if (nodeData.type !== 'service' && nodeData.type !== 'ghost') {
    return;
  }
  
  if (!connectionSource.value) {
    // Premier clic : définir la source
    connectionSource.value = nodeData.id;
  } else {
    // Deuxième clic : créer la dépendance
    const sourceName = connectionSource.value.replace('service-', '');
    const targetName = nodeData.id.replace('service-', '');
    
    addEdge({
      data: {
        id: `dep-${targetName}-${sourceName}`,
        source: connectionSource.value,
        target: nodeData.id,
        type: 'depends_on',
      },
      classes: 'dependency',
    });
    
    // Synchroniser avec le YAML
    syncToYAML();
    
    // Réinitialiser
    connectionSource.value = null;
  }
}

function handleMountMode(nodeData: any) {
  // Mode montage : attacher volumes/networks/configs/secrets aux services
  const validTypes = ['volume', 'network', 'config', 'secret', 'service'];
  
  if (!validTypes.includes(nodeData.type)) {
    return;
  }
  
  if (!mountSource.value) {
    // Premier clic : sélectionner la ressource à monter
    if (nodeData.type === 'service') {
      return; // Les services ne peuvent pas être la source
    }
    
    mountSource.value = {
      name: nodeData.id.replace(`${nodeData.type}-`, ''),
      type: nodeData.type,
    };
  } else {
    // Deuxième clic : monter sur le service
    if (nodeData.type !== 'service') {
      return; // La cible doit être un service
    }
    
    const edgeType = `mount_${mountSource.value.type}`;
    const sourceId = `${mountSource.value.type}-${mountSource.value.name}`;
    
    addEdge({
      data: {
        id: `${edgeType}-${mountSource.value.name}-${nodeData.id}`,
        source: sourceId,
        target: nodeData.id,
        type: edgeType,
      },
      classes: edgeType,
    });
    
    // Synchroniser avec le YAML
    syncToYAML();
    
    // Réinitialiser
    mountSource.value = null;
  }
}

// Ajout d'éléments
function handleAddElement(type: NodeType, name: string, data: any) {
  const nodeId = `${type}-${name}`;
  
  addNode({
    data: {
      id: nodeId,
      label: name,
      type,
      details: data,
    },
    classes: type,
  });
  
  syncToYAML();
  showAddDialog.value = false;
}

// Suppression d'éléments
function deleteSelected() {
  if (!selectedNode.value) return;
  
  removeNode(selectedNode.value.id);
  selectedNode.value = null;
  syncToYAML();
}

// Mise à jour d'un nœud
function updateNode(nodeId: string, newData: any) {
  updateNodeData(nodeId, newData);
  syncToYAML();
}

onMounted(() => {
  setupEventHandlers();
});
</script>

<template>
  <div class="compose-graph-viewer">
    <!-- Barre d'outils -->
    <div class="toolbar">
      <LayoutSelector v-model="layout" />
      
      <div class="mode-buttons">
        <button
          :class="{ active: interactionMode === 'normal' }"
          @click="exitSpecialMode"
        >
          Normal
        </button>
        <button
          :class="{ active: interactionMode === 'connection' }"
          @click="enterConnectionMode"
        >
          Mode Connexion
        </button>
        <button
          :class="{ active: interactionMode === 'mount' }"
          @click="enterMountMode"
        >
          Mode Montage
        </button>
      </div>
      
      <button @click="showAddDialog = true">
        Ajouter un élément
      </button>
      
      <button
        @click="deleteSelected"
        :disabled="!selectedNode"
      >
        Supprimer
      </button>
      
      <ThemeToggle />
    </div>
    
    <!-- Messages d'erreur -->
    <div v-if="errors.length > 0" class="errors">
      <div v-for="(error, index) in errors" :key="index" class="error">
        {{ error }}
      </div>
    </div>
    
    <!-- Messages de mode -->
    <div v-if="interactionMode !== 'normal'" class="mode-message">
      <template v-if="interactionMode === 'connection'">
        <span v-if="!connectionSource">
          Cliquez sur un service source
        </span>
        <span v-else>
          Cliquez sur un service cible pour créer une dépendance
        </span>
      </template>
      <template v-if="interactionMode === 'mount'">
        <span v-if="!mountSource">
          Cliquez sur une ressource (volume/network/config/secret)
        </span>
        <span v-else>
          Cliquez sur un service pour monter {{ mountSource.type }} "{{ mountSource.name }}"
        </span>
      </template>
    </div>
    
    <!-- Conteneur du graph -->
    <div ref="graphContainer" class="graph-container"></div>
    
    <!-- Panneau latéral d'édition -->
    <div v-if="selectedNode" class="editor-panel">
      <ServiceEditor
        v-if="selectedNode.type === 'service'"
        :node-id="selectedNode.id"
        :data="selectedNode.details"
        @update="updateNode"
      />
      <!-- Autres éditeurs selon le type... -->
    </div>
    
    <!-- Dialog ajout d'élément -->
    <AddElementDialog
      v-if="showAddDialog"
      @add="handleAddElement"
      @close="showAddDialog = false"
    />
  </div>
</template>

<style scoped>
.compose-graph-viewer {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
}

.toolbar {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  background: var(--toolbar-bg);
  border-bottom: 1px solid var(--border-color);
}

.mode-buttons {
  display: flex;
  gap: 0.5rem;
}

button {
  padding: 0.5rem 1rem;
  border: 1px solid var(--border-color);
  background: var(--button-bg);
  color: var(--text-color);
  cursor: pointer;
  border-radius: 4px;
}

button:hover:not(:disabled) {
  background: var(--button-hover-bg);
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

button.active {
  background: var(--primary-color);
  color: white;
}

.errors {
  padding: 0.5rem 1rem;
  background: var(--error-bg);
  color: var(--error-color);
}

.error {
  margin: 0.25rem 0;
}

.mode-message {
  padding: 0.5rem 1rem;
  background: var(--info-bg);
  color: var(--info-color);
  text-align: center;
}

.graph-container {
  flex: 1;
  width: 100%;
  background: var(--graph-bg);
}

.editor-panel {
  position: fixed;
  right: 0;
  top: 60px;
  bottom: 0;
  width: 400px;
  background: var(--panel-bg);
  border-left: 1px solid var(--border-color);
  overflow-y: auto;
  padding: 1rem;
}
</style>
```

### Composables

#### composables/useCytoscape.ts

```typescript
import { ref, type Ref } from 'vue';
import cytoscape, { type Core } from 'cytoscape';
import type { GraphElements, GraphNode, GraphEdge, LayoutName } from '@/types/graph';
import { getCytoscapeStyles } from '@/utils/cytoscapeStyles';

export function useCytoscape(
  container: Ref<HTMLElement | null>,
  isDark: Ref<boolean>
) {
  const cy = ref<Core | null>(null);
  
  function initCytoscape(elements: GraphElements) {
    if (!container.value) return;
    
    // Détruire l'instance existante
    if (cy.value) {
      cy.value.destroy();
    }
    
    // Créer nouvelle instance
    cy.value = cytoscape({
      container: container.value,
      elements: [...elements.nodes, ...elements.edges],
      style: getCytoscapeStyles(isDark.value),
      layout: {
        name: 'breadthfirst',
        directed: true,
        padding: 50,
      },
      minZoom: 0.1,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    });
  }
  
  function updateLayout(layoutName: LayoutName) {
    if (!cy.value) return;
    
    const layoutOptions = {
      breadthfirst: {
        name: 'breadthfirst',
        directed: true,
        padding: 50,
        spacingFactor: 1.5,
      },
      grid: {
        name: 'grid',
        padding: 50,
        avoidOverlap: true,
      },
      circle: {
        name: 'circle',
        padding: 50,
        avoidOverlap: true,
      },
      concentric: {
        name: 'concentric',
        padding: 50,
        minNodeSpacing: 100,
      },
      cose: {
        name: 'cose',
        padding: 50,
        nodeRepulsion: 8000,
        idealEdgeLength: 100,
      },
    };
    
    const layout = cy.value.layout(layoutOptions[layoutName]);
    layout.run();
  }
  
  function addNode(node: GraphNode) {
    if (!cy.value) return;
    cy.value.add(node);
  }
  
  function addEdge(edge: GraphEdge) {
    if (!cy.value) return;
    cy.value.add(edge);
  }
  
  function removeNode(nodeId: string) {
    if (!cy.value) return;
    cy.value.getElementById(nodeId).remove();
  }
  
  function removeEdge(edgeId: string) {
    if (!cy.value) return;
    cy.value.getElementById(edgeId).remove();
  }
  
  function updateNodeData(nodeId: string, newData: any) {
    if (!cy.value) return;
    const node = cy.value.getElementById(nodeId);
    node.data('details', newData);
  }
  
  function getElements(): GraphElements {
    if (!cy.value) return { nodes: [], edges: [] };
    
    const nodes = cy.value.nodes().map(node => ({
      group: 'nodes' as const,
      data: node.data(),
      classes: node.classes().join(' '),
      position: node.position(),
    }));
    
    const edges = cy.value.edges().map(edge => ({
      group: 'edges' as const,
      data: edge.data(),
      classes: edge.classes().join(' '),
    }));
    
    return { nodes, edges };
  }
  
  return {
    cy,
    initCytoscape,
    updateLayout,
    addNode,
    addEdge,
    removeNode,
    removeEdge,
    updateNodeData,
    getElements,
  };
}
```

#### composables/useComposeParser.ts

```typescript
import { apiClient } from '@/utils/api';
import type { GraphElements } from '@/types/graph';
import type { ComposeFile } from '@/types/compose';

export function useComposeParser() {
  async function parseCompose(content: string) {
    const response = await apiClient.post('/api/compose/parse', { content });
    return {
      compose: response.data.compose as ComposeFile,
      graph_elements: response.data.graph_elements as GraphElements,
      errors: response.data.errors as string[],
    };
  }
  
  async function generateYAML(elements: GraphElements): Promise<string> {
    const response = await apiClient.post('/api/compose/generate-yaml', {
      graph_elements: elements,
    });
    return response.data.yaml_content;
  }
  
  return {
    parseCompose,
    generateYAML,
  };
}
```

#### composables/useTheme.ts

```typescript
import { ref, watch } from 'vue';

export function useTheme() {
  const isDark = ref(false);
  
  // Charger la préférence depuis localStorage
  const stored = localStorage.getItem('theme');
  if (stored) {
    isDark.value = stored === 'dark';
  } else {
    // Détecter la préférence système
    isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  
  // Appliquer le thème
  function applyTheme() {
    document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light');
  }
  
  // Sauvegarder et appliquer lors des changements
  watch(isDark, () => {
    localStorage.setItem('theme', isDark.value ? 'dark' : 'light');
    applyTheme();
  });
  
  applyTheme();
  
  function toggleTheme() {
    isDark.value = !isDark.value;
  }
  
  return {
    isDark,
    toggleTheme,
  };
}
```

### Utilitaires

#### utils/cytoscapeStyles.ts

```typescript
import type { Stylesheet } from 'cytoscape';

export function getCytoscapeStyles(isDark: boolean): Stylesheet[] {
  const colors = isDark ? {
    service: '#3b82f6',
    network: '#10b981',
    volume: '#f59e0b',
    config: '#8b5cf6',
    secret: '#ec4899',
    ghost: '#64748b',
    text: '#f1f5f9',
    edge: '#475569',
    background: '#1e293b',
  } : {
    service: '#2563eb',
    network: '#059669',
    volume: '#d97706',
    config: '#7c3aed',
    secret: '#db2777',
    ghost: '#94a3b8',
    text: '#0f172a',
    edge: '#64748b',
    background: '#f8fafc',
  };
  
  return [
    // Styles de nœuds par type
    {
      selector: 'node',
      style: {
        'label': 'data(label)',
        'text-valign': 'center',
        'text-halign': 'center',
        'color': colors.text,
        'font-size': '12px',
        'width': '60px',
        'height': '60px',
      },
    },
    {
      selector: 'node.service',
      style: {
        'background-color': colors.service,
        'shape': 'rectangle',
      },
    },
    {
      selector: 'node.network',
      style: {
        'background-color': colors.network,
        'shape': 'hexagon',
      },
    },
    {
      selector: 'node.volume',
      style: {
        'background-color': colors.volume,
        'shape': 'barrel',
      },
    },
    {
      selector: 'node.config',
      style: {
        'background-color': colors.config,
        'shape': 'diamond',
      },
    },
    {
      selector: 'node.secret',
      style: {
        'background-color': colors.secret,
        'shape': 'pentagon',
      },
    },
    {
      selector: 'node.ghost',
      style: {
        'background-color': colors.ghost,
        'shape': 'ellipse',
        'border-width': '2px',
        'border-style': 'dashed',
        'border-color': colors.edge,
        'opacity': 0.6,
      },
    },
    // Styles d'arêtes
    {
      selector: 'edge',
      style: {
        'width': 2,
        'line-color': colors.edge,
        'target-arrow-color': colors.edge,
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
      },
    },
    {
      selector: 'edge.dependency',
      style: {
        'line-color': colors.service,
        'target-arrow-color': colors.service,
      },
    },
    {
      selector: 'edge.mount_volume',
      style: {
        'line-color': colors.volume,
        'target-arrow-color': colors.volume,
        'line-style': 'dashed',
      },
    },
    {
      selector: 'edge.mount_network',
      style: {
        'line-color': colors.network,
        'target-arrow-color': colors.network,
        'line-style': 'dotted',
      },
    },
    {
      selector: 'edge.mount_config',
      style: {
        'line-color': colors.config,
        'target-arrow-color': colors.config,
        'line-style': 'dashed',
      },
    },
    {
      selector: 'edge.mount_secret',
      style: {
        'line-color': colors.secret,
        'target-arrow-color': colors.secret,
        'line-style': 'dashed',
      },
    },
    // États interactifs
    {
      selector: ':selected',
      style: {
        'border-width': '3px',
        'border-color': '#fbbf24',
        'background-color': '#fbbf24',
      },
    },
  ];
}
```

#### utils/api.ts

```typescript
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});
```

---

## Déploiement

### Backend (FastAPI)

```bash
# Installation des dépendances
cd backend
pip install -r requirements.txt

# Lancement du serveur
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Vue3/Vite)

```bash
# Installation des dépendances
cd frontend
npm install

# Développement
npm run dev

# Build production
npm run build
```

---

## Migration depuis Svelte 5

### Équivalences des patterns

| Svelte 5 | Vue 3 Composition API |
|----------|----------------------|
| `let state = $state()` | `const state = ref()` |
| `let derived = $derived()` | `const derived = computed()` |
| `$effect(() => {})` | `watch(() => {}, () => {})` ou `watchEffect()` |
| `$props()` | `defineProps<>()` |
| `export let prop` | `defineProps<{ prop: Type }>()` |
| `{#if condition}` | `<template v-if="condition">` |
| `{#each items as item}` | `<template v-for="item in items">` |
| `{item.property}` | `{{ item.property }}` |
| `on:click={handler}` | `@click="handler"` |
| `bind:value={state}` | `v-model="state"` |

### Points d'attention pour la migration

1. **Réactivité**
   - Svelte 5 : Réactivité automatique sur les variables avec `$state()`
   - Vue 3 : Doit utiliser `ref()` et accéder à `.value` dans le script, mais pas dans le template

2. **Gestion du cycle de vie**
   - Svelte : `onMount()`, `onDestroy()`, `beforeUpdate()`, `afterUpdate()`
   - Vue : `onMounted()`, `onUnmounted()`, `onBeforeUpdate()`, `onUpdated()`

3. **Événements personnalisés**
   - Svelte : `createEventDispatcher()` ou callbacks dans props
   - Vue : `defineEmits<>()`

4. **Slots**
   - Svelte : `<slot />`, `<slot name="header" />`
   - Vue : `<slot />`, `<slot name="header" />`

---

## Fonctionnalités avancées à implémenter

### 1. Éditeurs de ressources détaillés

Chaque type de ressource (service, network, volume, config, secret) doit avoir son propre éditeur dans le panneau latéral avec :

- **ServiceEditor** : image, build, command, environment, ports, volumes, networks, depends_on, restart, deploy, etc.
- **NetworkEditor** : driver, driver_opts, external, name, labels, attachable, etc.
- **VolumeEditor** : driver, driver_opts, external, name, labels, etc.
- **ConfigEditor** : file, external, name, template_driver, etc.
- **SecretEditor** : file, external, name, template_driver, etc.

### 2. Validation en temps réel

```typescript
// composables/useComposeValidator.ts
export function useComposeValidator() {
  async function validateService(service: Service): Promise<string[]> {
    const errors: string[] = [];
    
    // Vérifier image ou build
    if (!service.image && !service.build) {
      errors.push('Un service doit avoir soit "image" soit "build"');
    }
    
    // Vérifier les ports
    if (service.ports) {
      for (const port of service.ports) {
        if (!isValidPortMapping(port)) {
          errors.push(`Port mapping invalide: ${port}`);
        }
      }
    }
    
    // Vérifier les variables d'environnement
    if (service.environment) {
      // Validation des formats
    }
    
    return errors;
  }
  
  return {
    validateService,
  };
}
```

### 3. Auto-complétion et suggestions

Le frontend peut proposer :
- Suggestions d'images Docker populaires lors de la création de services
- Auto-complétion des noms de services pour `depends_on`
- Suggestions de ports communs (80, 443, 3000, 5432, 27017, etc.)
- Détection des volumes nommés vs bind mounts

### 4. Export/Import de configurations

```typescript
// Exporter le graph en PNG
async function exportGraphAsPNG() {
  if (!cy.value) return;
  const png = cy.value.png({ 
    output: 'blob',
    bg: 'white',
    full: true,
    scale: 2
  });
  // Télécharger le blob
}

// Exporter en JSON
function exportAsJSON() {
  const elements = getElements();
  const json = JSON.stringify(elements, null, 2);
  downloadFile(json, 'compose-graph.json', 'application/json');
}
```

### 5. Undo/Redo

```typescript
// composables/useHistory.ts
export function useHistory() {
  const history = ref<GraphElements[]>([]);
  const currentIndex = ref(-1);
  
  function pushState(elements: GraphElements) {
    // Supprimer les états futurs si on est au milieu de l'historique
    history.value = history.value.slice(0, currentIndex.value + 1);
    history.value.push(elements);
    currentIndex.value++;
    
    // Limiter la taille de l'historique
    if (history.value.length > 50) {
      history.value.shift();
      currentIndex.value--;
    }
  }
  
  function undo(): GraphElements | null {
    if (currentIndex.value > 0) {
      currentIndex.value--;
      return history.value[currentIndex.value];
    }
    return null;
  }
  
  function redo(): GraphElements | null {
    if (currentIndex.value < history.value.length - 1) {
      currentIndex.value++;
      return history.value[currentIndex.value];
    }
    return null;
  }
  
  return {
    pushState,
    undo,
    redo,
    canUndo: computed(() => currentIndex.value > 0),
    canRedo: computed(() => currentIndex.value < history.value.length - 1),
  };
}
```

---

## Optimisations de performance

### Backend

1. **Caching** : Mettre en cache le parsing des fichiers identiques
2. **Validation asynchrone** : Valider en arrière-plan pendant l'édition
3. **Compression** : Compresser les réponses API avec gzip

### Frontend

1. **Debouncing** : Limiter la fréquence de génération YAML pendant l'édition
2. **Virtualisation** : Pour les très grands graphes (> 100 nœuds)
3. **Lazy loading** : Charger les éditeurs de ressources à la demande
4. **Memoization** : Mettre en cache les calculs coûteux

```typescript
// Debounce pour la génération YAML
import { debounce } from 'lodash-es';

const debouncedSyncToYAML = debounce(syncToYAML, 500);
```

---

## Tests

### Backend (pytest)

```python
# tests/test_compose_parser.py
import pytest
from app.services.compose_parser import ComposeParser

def test_parse_simple_compose():
    parser = ComposeParser()
    content = """
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
    """
    
    compose, errors = parser.parse(content)
    assert len(errors) == 0
    assert 'web' in compose.services
    assert compose.services['web'].image == 'nginx:latest'

def test_parse_with_depends_on():
    parser = ComposeParser()
    content = """
version: '3.8'
services:
  web:
    image: nginx:latest
    depends_on:
      - db
  db:
    image: postgres:13
    """
    
    compose, errors = parser.parse(content)
    assert len(errors) == 0
    assert compose.services['web'].depends_on == ['db']
```

### Frontend (Vitest + Vue Test Utils)

```typescript
// tests/ComposeGraphViewer.test.ts
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import ComposeGraphViewer from '@/components/ComposeGraphViewer.vue';

describe('ComposeGraphViewer', () => {
  it('devrait parser et afficher un compose simple', async () => {
    const composeContent = `
version: '3.8'
services:
  web:
    image: nginx:latest
    `;
    
    const wrapper = mount(ComposeGraphViewer, {
      props: {
        composeContent
      }
    });
    
    // Attendre le parsing
    await wrapper.vm.$nextTick();
    
    expect(wrapper.find('.graph-container').exists()).toBe(true);
  });
  
  it('devrait changer de mode d\'interaction', async () => {
    const wrapper = mount(ComposeGraphViewer, {
      props: {
        composeContent: 'version: "3.8"\nservices: {}'
      }
    });
    
    const connectionButton = wrapper.find('button:contains("Mode Connexion")');
    await connectionButton.trigger('click');
    
    expect(wrapper.vm.interactionMode).toBe('connection');
  });
});
```

---

## Sécurité

### Backend

1. **Validation stricte** : Valider tous les inputs avec Pydantic
2. **Limite de taille** : Limiter la taille des fichiers YAML (max 10 MB)
3. **Timeout** : Limiter le temps de parsing (max 5 secondes)
4. **Sanitization** : Échapper les caractères spéciaux dans le YAML généré

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MAX_YAML_SIZE: int = 10 * 1024 * 1024  # 10 MB
    PARSE_TIMEOUT: int = 5  # secondes
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### Frontend

1. **CSP** : Configurer Content Security Policy
2. **Validation côté client** : Valider avant d'envoyer au backend
3. **XSS Protection** : Échapper le contenu utilisateur affiché

---

## Conclusion

Ce document décrit l'architecture complète pour porter l'éditeur Docker Compose de Svelte 5 vers Python/FastAPI + Vue3/Vite. Les points clés sont :

✅ **Architecture backend robuste** avec FastAPI, Pydantic et services modulaires  
✅ **Frontend moderne** avec Vue 3 Composition API et Cytoscape.js  
✅ **Préservation de toutes les fonctionnalités** de l'éditeur original  
✅ **Parsing YAML avec récupération d'erreurs** pour une meilleur UX  
✅ **Modes d'interaction avancés** (connexion, montage)  
✅ **Support multi-ressources** (services, networks, volumes, configs, secrets)  
✅ **Thèmes clair/obscur** avec palettes de couleurs personnalisées  
✅ **Tests et optimisations** pour la production

L'implémentation suit les meilleures pratiques et patterns modernes pour assurer maintenabilité et extensibilité du code.
