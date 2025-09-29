# Système de Workflows - WindFlow

## Vue d'Ensemble

WindFlow intègre un système de workflows visuels inspiré de n8n et ActivePieces, permettant l'automatisation avancée des déploiements et l'orchestration intelligente des tâches.

### Vision des Workflows

**Objectifs :**
- **Automatisation Complète** : Workflows de déploiement end-to-end
- **Flexibilité Maximale** : Éditeur visuel drag-and-drop
- **Intégration Transparente** : Connexion native avec tous les services WindFlow
- **Intelligence Intégrée** : Optimisation et suggestions automatiques par IA
- **Réutilisabilité** : Bibliothèque de workflows partagés

## Architecture du Workflow Engine

### Composants Principaux

**Workflow Engine Core :**
- **WorkflowEngine** : Moteur d'exécution des workflows
- **NodeRegistry** : Registre des nœuds disponibles
- **ExecutionEngine** : Exécution asynchrone des tâches
- **SchedulerService** : Planification et déclenchement automatique
- **StateManager** : Gestion d'état persistante

```python
class WorkflowEngine:
    """Moteur d'exécution des workflows WindFlow."""
    
    def __init__(self):
        self.node_registry = NodeRegistry()
        self.execution_engine = ExecutionEngine()
        self.state_manager = StateManager()
        self.scheduler = SchedulerService()
        
    async def execute_workflow(self, workflow: Workflow, context: Dict = None) -> WorkflowResult:
        """Exécute un workflow complet."""
        
        # Initialisation du contexte d'exécution
        execution_context = ExecutionContext(
            workflow_id=workflow.id,
            user_context=context or {},
            variables={},
            state=WorkflowState.RUNNING
        )
        
        try:
            # Validation du workflow
            validation_result = await self._validate_workflow(workflow)
            if not validation_result.is_valid:
                raise WorkflowValidationError(validation_result.errors)
            
            # Résolution des dépendances entre nœuds
            execution_order = await self._resolve_execution_order(workflow)
            
            # Exécution séquentielle des nœuds
            for node_id in execution_order:
                node = workflow.get_node(node_id)
                
                # Exécution du nœud
                node_result = await self._execute_node(node, execution_context)
                
                # Mise à jour du contexte avec les résultats
                execution_context.variables.update(node_result.output_data)
                
                # Gestion des conditions d'arrêt
                if node_result.should_stop_workflow:
                    execution_context.state = WorkflowState.STOPPED
                    break
                    
                # Gestion des erreurs
                if node_result.has_error and node.error_handling == "stop":
                    execution_context.state = WorkflowState.FAILED
                    break
            
            # Finalisation
            execution_context.state = WorkflowState.COMPLETED
            
            return WorkflowResult(
                workflow_id=workflow.id,
                state=execution_context.state,
                output_data=execution_context.variables,
                execution_time=execution_context.get_execution_time(),
                logs=execution_context.logs
            )
            
        except Exception as e:
            execution_context.state = WorkflowState.FAILED
            execution_context.add_error(str(e))
            
            return WorkflowResult(
                workflow_id=workflow.id,
                state=WorkflowState.FAILED,
                error=str(e),
                logs=execution_context.logs
            )
    
    async def _execute_node(self, node: WorkflowNode, context: ExecutionContext) -> NodeResult:
        """Exécute un nœud individuel."""
        
        # Récupération de l'implémentation du nœud
        node_implementation = self.node_registry.get_node(node.type)
        
        # Préparation des données d'entrée
        input_data = await self._prepare_node_input(node, context)
        
        # Exécution avec timeout et retry
        result = await self._execute_with_retry(
            node_implementation.execute,
            input_data=input_data,
            config=node.configuration,
            timeout=node.timeout or 300,  # 5 minutes par défaut
            retry_count=node.retry_count or 0
        )
        
        return result
```

### Types de Nœuds

**Nœuds de Déclenchement (Trigger Nodes) :**
- **Manual Trigger** : Déclenchement manuel
- **Schedule Trigger** : Déclenchement planifié (cron)
- **Webhook Trigger** : Déclenchement via webhook
- **Event Trigger** : Déclenchement sur événement système
- **File Trigger** : Déclenchement sur modification de fichier

**Nœuds d'Action (Action Nodes) :**
- **Deploy Stack** : Déploiement d'un stack
- **Scale Service** : Mise à l'échelle d'un service
- **Backup Data** : Sauvegarde de données
- **Send Notification** : Envoi de notifications
- **Execute Script** : Exécution de scripts personnalisés

**Nœuds de Logique (Logic Nodes) :**
- **Condition** : Branchement conditionnel
- **Loop** : Boucles et itérations
- **Merge** : Fusion de branches
- **Switch** : Aiguillage multiple
- **Wait** : Attente temporelle

**Nœuds d'Intégration (Integration Nodes) :**
- **HTTP Request** : Requêtes HTTP
- **Database Query** : Requêtes de base de données
- **Cloud Service** : Intégration services cloud
- **Monitoring** : Collecte de métriques
- **Git Operations** : Opérations Git

```python
class NodeRegistry:
    """Registre centralisé des types de nœuds."""
    
    def __init__(self):
        self.nodes = {}
        self._register_core_nodes()
    
    def _register_core_nodes(self):
        """Enregistre les nœuds de base."""
        
        # Nœuds de déclenchement
        self.register_node("trigger.manual", ManualTriggerNode)
        self.register_node("trigger.schedule", ScheduleTriggerNode)
        self.register_node("trigger.webhook", WebhookTriggerNode)
        
        # Nœuds d'action WindFlow
        self.register_node("windflow.deploy_stack", DeployStackNode)
        self.register_node("windflow.scale_service", ScaleServiceNode)
        self.register_node("windflow.backup_data", BackupDataNode)
        
        # Nœuds de logique
        self.register_node("logic.condition", ConditionNode)
        self.register_node("logic.loop", LoopNode)
        self.register_node("logic.merge", MergeNode)
        
        # Nœuds d'intégration
        self.register_node("integration.http", HTTPRequestNode)
        self.register_node("integration.notification", NotificationNode)
        self.register_node("integration.script", ScriptExecutionNode)
    
    def register_node(self, node_type: str, node_class: Type[WorkflowNode]):
        """Enregistre un nouveau type de nœud."""
        self.nodes[node_type] = node_class
    
    def get_node(self, node_type: str) -> Type[WorkflowNode]:
        """Récupère une classe de nœud."""
        if node_type not in self.nodes:
            raise NodeNotFoundError(f"Node type '{node_type}' not found")
        return self.nodes[node_type]
```

## Éditeur Visuel de Workflows

### Interface Vue.js avec Vue Flow

```vue
<template>
  <div class="workflow-editor">
    <div class="editor-toolbar">
      <el-button @click="saveWorkflow" type="primary">
        <i class="el-icon-document"></i> Sauvegarder
      </el-button>
      <el-button @click="executeWorkflow" type="success">
        <i class="el-icon-video-play"></i> Exécuter
      </el-button>
      <el-button @click="validateWorkflow" type="info">
        <i class="el-icon-check"></i> Valider
      </el-button>
    </div>
    
    <div class="editor-content">
      <!-- Palette de nœuds -->
      <div class="node-palette">
        <h3>Nœuds Disponibles</h3>
        <div class="node-categories">
          <div v-for="category in nodeCategories" :key="category.name" class="category">
            <h4>{{ category.name }}</h4>
            <div 
              v-for="node in category.nodes" 
              :key="node.type"
              class="node-item"
              draggable="true"
              @dragstart="onNodeDragStart($event, node)"
            >
              <i :class="node.icon"></i>
              {{ node.name }}
            </div>
          </div>
        </div>
      </div>
      
      <!-- Éditeur de workflow -->
      <div class="workflow-canvas">
        <VueFlow
          v-model="elements"
          class="workflow-flow"
          @connect="onConnect"
          @node-click="onNodeClick"
          @drop="onDrop"
          @dragover="onDragOver"
        >
          <Background pattern="dots" />
          <Controls />
          <MiniMap />
          
          <!-- Templates de nœuds personnalisés -->
          <template #node-trigger="{ data }">
            <TriggerNode :data="data" @configure="onConfigureNode" />
          </template>
          
          <template #node-action="{ data }">
            <ActionNode :data="data" @configure="onConfigureNode" />
          </template>
          
          <template #node-logic="{ data }">
            <LogicNode :data="data" @configure="onConfigureNode" />
          </template>
        </VueFlow>
      </div>
      
      <!-- Panneau de configuration -->
      <div class="config-panel" v-if="selectedNode">
        <h3>Configuration : {{ selectedNode.data.label }}</h3>
        <component 
          :is="getConfigComponent(selectedNode.type)"
          :node="selectedNode"
          @update="onNodeUpdate"
        />
      </div>
    </div>
    
    <!-- Modal d'exécution -->
    <el-dialog v-model="executionDialogVisible" title="Exécution du Workflow">
      <div class="execution-logs">
        <div v-for="log in executionLogs" :key="log.id" class="log-entry">
          <span class="timestamp">{{ formatTime(log.timestamp) }}</span>
          <span :class="['level', log.level]">{{ log.level }}</span>
          <span class="message">{{ log.message }}</span>
        </div>
      </div>
      
      <template #footer>
        <el-button @click="executionDialogVisible = false">Fermer</el-button>
        <el-button @click="stopExecution" type="danger" v-if="workflowRunning">
          Arrêter
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { VueFlow, Background, Controls, MiniMap } from '@vue-flow/core'
import type { Node, Edge, Connection } from '@vue-flow/core'
import { useWorkflowStore } from '@/stores/workflow'
import { useNotificationStore } from '@/stores/notifications'

const workflowStore = useWorkflowStore()
const notificationStore = useNotificationStore()

const elements = ref<(Node | Edge)[]>([])
const selectedNode = ref<Node | null>(null)
const executionDialogVisible = ref(false)
const executionLogs = ref<ExecutionLog[]>([])
const workflowRunning = ref(false)

const nodeCategories = computed(() => [
  {
    name: 'Déclencheurs',
    nodes: [
      { type: 'trigger.manual', name: 'Manuel', icon: 'el-icon-hand' },
      { type: 'trigger.schedule', name: 'Planifié', icon: 'el-icon-time' },
      { type: 'trigger.webhook', name: 'Webhook', icon: 'el-icon-link' }
    ]
  },
  {
    name: 'Actions WindFlow',
    nodes: [
      { type: 'windflow.deploy_stack', name: 'Déployer Stack', icon: 'el-icon-upload' },
      { type: 'windflow.scale_service', name: 'Mettre à l\'échelle', icon: 'el-icon-rank' },
      { type: 'windflow.backup_data', name: 'Sauvegarder', icon: 'el-icon-download' }
    ]
  },
  {
    name: 'Logique',
    nodes: [
      { type: 'logic.condition', name: 'Condition', icon: 'el-icon-question' },
      { type: 'logic.loop', name: 'Boucle', icon: 'el-icon-refresh' },
      { type: 'logic.merge', name: 'Fusion', icon: 'el-icon-connection' }
    ]
  }
])

const onNodeDragStart = (event: DragEvent, node: NodeType) => {
  event.dataTransfer?.setData('application/vueflow', JSON.stringify(node))
}

const onDrop = (event: DragEvent) => {
  const nodeData = JSON.parse(event.dataTransfer?.getData('application/vueflow') || '{}')
  
  // Création d'un nouveau nœud
  const newNode: Node = {
    id: generateNodeId(),
    type: 'custom',
    position: {
      x: event.offsetX,
      y: event.offsetY
    },
    data: {
      label: nodeData.name,
      nodeType: nodeData.type,
      configuration: {}
    }
  }
  
  elements.value.push(newNode)
}

const onConnect = (connection: Connection) => {
  const newEdge: Edge = {
    id: `edge-${connection.source}-${connection.target}`,
    source: connection.source,
    target: connection.target,
    type: 'smoothstep'
  }
  
  elements.value.push(newEdge)
}

const onNodeClick = (node: Node) => {
  selectedNode.value = node
}

const saveWorkflow = async () => {
  try {
    const workflow = {
      name: 'Mon Workflow',
      description: 'Description du workflow',
      nodes: elements.value.filter(el => 'data' in el),
      edges: elements.value.filter(el => 'source' in el),
      configuration: {}
    }
    
    await workflowStore.saveWorkflow(workflow)
    notificationStore.showSuccess('Workflow sauvegardé avec succès')
  } catch (error) {
    notificationStore.showError('Erreur lors de la sauvegarde')
  }
}

const executeWorkflow = async () => {
  try {
    executionDialogVisible.value = true
    workflowRunning.value = true
    executionLogs.value = []
    
    const workflow = buildWorkflowFromElements()
    
    // Execution avec streaming des logs
    const execution = await workflowStore.executeWorkflow(workflow)
    
    // Écoute des logs en temps réel
    execution.onLog((log: ExecutionLog) => {
      executionLogs.value.push(log)
    })
    
    execution.onComplete(() => {
      workflowRunning.value = false
      notificationStore.showSuccess('Workflow exécuté avec succès')
    })
    
    execution.onError((error: string) => {
      workflowRunning.value = false
      notificationStore.showError(`Erreur d'exécution: ${error}`)
    })
    
  } catch (error) {
    workflowRunning.value = false
    notificationStore.showError('Erreur lors du lancement')
  }
}
</script>
```

## Workflows Prédéfinis

### Templates de Workflows Courants

**1. Déploiement Complet avec Tests**
```yaml
workflow:
  name: "Déploiement avec Tests"
  description: "Déploiement automatique avec tests et rollback"
  
  nodes:
    - id: "trigger"
      type: "trigger.webhook"
      configuration:
        webhook_path: "/deploy"
        authentication: "token"
    
    - id: "validate_config"
      type: "windflow.validate_stack"
      configuration:
        stack_id: "{{ trigger.stack_id }}"
        validation_level: "strict"
    
    - id: "run_tests"
      type: "integration.script"
      configuration:
        script_type: "bash"
        script: |
          echo "Running tests..."
          npm test
          pytest
    
    - id: "deploy_staging"
      type: "windflow.deploy_stack"
      configuration:
        stack_id: "{{ trigger.stack_id }}"
        environment: "staging"
        wait_for_healthy: true
    
    - id: "smoke_tests"
      type: "integration.http"
      configuration:
        method: "GET"
        url: "{{ deploy_staging.endpoint }}/health"
        expected_status: 200
        retry_count: 5
    
    - id: "deploy_production"
      type: "windflow.deploy_stack"
      configuration:
        stack_id: "{{ trigger.stack_id }}"
        environment: "production"
        backup_before_deploy: true
    
    - id: "notify_success"
      type: "integration.notification"
      configuration:
        channels: ["slack", "email"]
        message: "Déploiement réussi: {{ trigger.stack_id }}"
        
  edges:
    - source: "trigger"
      target: "validate_config"
    - source: "validate_config"
      target: "run_tests"
    - source: "run_tests"
      target: "deploy_staging"
    - source: "deploy_staging"
      target: "smoke_tests"
    - source: "smoke_tests"
      target: "deploy_production"
    - source: "deploy_production"
      target: "notify_success"
```

**2. Scaling Automatique**
```yaml
workflow:
  name: "Auto-Scaling Intelligent"
  description: "Mise à l'échelle automatique basée sur les métriques"
  
  trigger:
    type: "schedule"
    schedule: "*/5 * * * *"  # Toutes les 5 minutes
    
  nodes:
    - id: "collect_metrics"
      type: "windflow.get_metrics"
      configuration:
        services: ["web-app", "api-service"]
        metrics: ["cpu_usage", "memory_usage", "request_rate"]
        
    - id: "analyze_load"
      type: "logic.condition"
      configuration:
        condition: "{{ collect_metrics.cpu_usage > 80 or collect_metrics.request_rate > 1000 }}"
        
    - id: "scale_up"
      type: "windflow.scale_service"
      configuration:
        service_id: "{{ collect_metrics.service_id }}"
        scale_factor: 1.5
        max_replicas: 10
        
    - id: "wait_stabilization"
      type: "logic.wait"
      configuration:
        duration: 300  # 5 minutes
        
    - id: "verify_scaling"
      type: "windflow.get_metrics"
      configuration:
        services: ["{{ collect_metrics.service_id }}"]
        
    - id: "rollback_if_needed"
      type: "logic.condition"
      configuration:
        condition: "{{ verify_scaling.cpu_usage > 90 }}"
        true_branch: "emergency_rollback"
        false_branch: "notify_scaling_success"
```

**3. Backup et Maintenance**
```yaml
workflow:
  name: "Maintenance Programmée"
  description: "Backup automatique et maintenance des services"
  
  trigger:
    type: "schedule"
    schedule: "0 2 * * 0"  # Tous les dimanches à 2h
    
  nodes:
    - id: "backup_databases"
      type: "windflow.backup_data"
      configuration:
        backup_type: "full"
        retention_days: 30
        compress: true
        
    - id: "cleanup_old_images"
      type: "integration.script"
      configuration:
        script: |
          docker image prune -f
          docker system prune -f
          
    - id: "update_certificates"
      type: "windflow.renew_certificates"
      configuration:
        auto_renew: true
        notification_days: 30
        
    - id: "health_check_all"
      type: "windflow.health_check"
      configuration:
        scope: "all_services"
        detailed: true
        
    - id: "generate_report"
      type: "integration.notification"
      configuration:
        channels: ["email"]
        template: "maintenance_report"
        attachments: ["{{ backup_databases.backup_file }}", "{{ health_check_all.report_file }}"]
```

## Gestion d'État et Persistance

### Workflow State Management

```python
class WorkflowStateManager:
    """Gestionnaire d'état persistant pour les workflows."""
    
    async def save_execution_state(self, execution_id: str, state: ExecutionState):
        """Sauvegarde l'état d'exécution."""
        
        state_data = {
            "execution_id": execution_id,
            "workflow_id": state.workflow_id,
            "current_node": state.current_node,
            "variables": state.variables,
            "node_states": state.node_states,
            "status": state.status.value,
            "started_at": state.started_at.isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        await self.redis.hset(
            f"workflow_execution:{execution_id}",
            mapping=state_data
        )
        
        # TTL pour nettoyage automatique
        await self.redis.expire(f"workflow_execution:{execution_id}", 86400 * 7)  # 7 jours
    
    async def resume_execution(self, execution_id: str) -> Optional[ExecutionState]:
        """Reprend l'exécution d'un workflow interrompu."""
        
        state_data = await self.redis.hgetall(f"workflow_execution:{execution_id}")
        
        if not state_data:
            return None
            
        return ExecutionState(
            execution_id=execution_id,
            workflow_id=state_data["workflow_id"],
            current_node=state_data["current_node"],
            variables=json.loads(state_data["variables"]),
            node_states=json.loads(state_data["node_states"]),
            status=ExecutionStatus(state_data["status"]),
            started_at=datetime.fromisoformat(state_data["started_at"])
        )
```

---

**Références :**
- [Vue d'Ensemble](01-overview.md) - Contexte du projet
- [Architecture](02-architecture.md) - Architecture générale
- [Fonctionnalités Principales](10-core-features.md) - Fonctionnalités liées aux workflows
- [LLM Integration](17-llm-integration.md) - IA dans les workflows
- [Interface Web](09-web-interface.md) - Éditeur visuel de workflows
- [API Design](07-api-design.md) - APIs des workflows
