<template>
  <div class="workflow-editor">
    <el-card>
      <template #header>
        <div class="card-header">
          <el-input v-model="workflowName" placeholder="Workflow Name" style="width: 300px" />
          <div>
            <el-button @click="$router.back()">Cancel</el-button>
            <el-button type="primary" @click="saveWorkflow">Save</el-button>
          </div>
        </div>
      </template>
      <div class="workflow-canvas">
        <VueFlow
          v-model="elements"
          :default-zoom="1"
          :min-zoom="0.2"
          :max-zoom="4"
          @connect="onConnect"
        >
          <Background />
          <Controls />
          <MiniMap />
        </VueFlow>
      </div>
      <div class="node-palette">
        <h4>Node Types</h4>
        <el-button @click="addNode('deploy')" size="small">Deploy Node</el-button>
        <el-button @click="addNode('condition')" size="small">Condition Node</el-button>
        <el-button @click="addNode('notification')" size="small">Notification Node</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VueFlow } from '@vue-flow/core'
import { Controls } from '@vue-flow/controls'
import { Background } from '@vue-flow/background'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import { useWorkflowsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import type { WorkflowNode, WorkflowEdge } from '@/types/api'

const route = useRoute()
const router = useRouter()
const workflowsStore = useWorkflowsStore()
const authStore = useAuthStore()

const workflowName = ref('New Workflow')
const elements = ref<Array<WorkflowNode | WorkflowEdge>>([])
const nodeIdCounter = ref(0)

const addNode = (type: string) => {
  const id = `node_${++nodeIdCounter.value}`
  const newNode = {
    id,
    type: 'default',
    position: { x: Math.random() * 400, y: Math.random() * 400 },
    data: { label: `${type} Node`, type },
  }
  elements.value.push(newNode)
}

const onConnect = (params: any) => {
  elements.value.push({
    id: `edge_${params.source}_${params.target}`,
    source: params.source,
    target: params.target,
    type: 'default',
  })
}

const saveWorkflow = async () => {
  const nodes: WorkflowNode[] = elements.value
    .filter(el => !el.source)
    .map(el => ({
      id: el.id,
      type: el.data?.type || 'default',
      position: el.position,
      data: el.data || {},
    }))

  const edges: WorkflowEdge[] = elements.value
    .filter(el => el.source)
    .map(el => ({
      id: el.id,
      source: el.source,
      target: el.target,
      type: el.type,
    }))

  try {
    const workflowId = route.params.id as string
    if (workflowId && workflowId !== 'new') {
      await workflowsStore.updateWorkflow(workflowId, {
        name: workflowName.value,
        nodes,
        edges,
      })
      ElMessage.success('Workflow updated successfully')
    } else {
      await workflowsStore.createWorkflow({
        name: workflowName.value,
        description: '',
        nodes,
        edges,
        organization_id: authStore.organizationId || '',
      })
      ElMessage.success('Workflow created successfully')
    }
    router.push('/workflows')
  } catch {
    ElMessage.error('Failed to save workflow')
  }
}

onMounted(async () => {
  const workflowId = route.params.id as string
  if (workflowId && workflowId !== 'new') {
    await workflowsStore.fetchWorkflow(workflowId)
    if (workflowsStore.currentWorkflow) {
      workflowName.value = workflowsStore.currentWorkflow.name
      elements.value = [
        ...workflowsStore.currentWorkflow.nodes,
        ...workflowsStore.currentWorkflow.edges,
      ]
    }
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.workflow-canvas {
  height: 500px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.node-palette {
  margin-top: 20px;
  padding: 10px;
  background-color: #f5f5f5;
  border-radius: 4px;
}

.node-palette h4 {
  margin-top: 0;
}
</style>
