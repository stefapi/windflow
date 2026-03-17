<template>
  <div class="stacks">
    <!-- Liste des stacks -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Stacks Management</span>
          <el-button
            type="primary"
            @click="openCreateDialog"
          >
            Create Stack
          </el-button>
        </div>
      </template>

      <el-table
        v-loading="stacksStore.loading"
        :data="stacksStore.stacks"
        @row-click="selectStack"
      >
        <el-table-column
          prop="name"
          label="Name"
          min-width="150"
        />
        <el-table-column
          prop="description"
          label="Description"
          min-width="200"
          show-overflow-tooltip
        />
        <el-table-column
          label="Created"
          width="180"
        >
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          label="Status"
          width="130"
        >
          <template #default="{ row }">
            <StatusBadge
              :status="getStackStatus(row)"
              size="small"
            />
          </template>
        </el-table-column>
        <el-table-column
          label="Actions"
          width="150"
          fixed="right"
        >
          <template #default="{ row }">
            <ActionButtons
              :actions="['edit', 'deploy', 'delete']"
              @action="(type) => handleStackAction(type, row)"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Panneau de détail / édition du stack sélectionné -->
    <el-card
      v-if="selectedStack"
      style="margin-top: 20px"
    >
      <template #header>
        <div class="card-header">
          <span>{{ isEditing ? 'Edit Stack' : 'Stack Details' }}: {{ selectedStack.name }}</span>
          <div>
            <el-button
              v-if="!isEditing"
              type="primary"
              size="small"
              @click="startEditing"
            >
              Edit
            </el-button>
            <el-button
              v-if="isEditing"
              type="success"
              size="small"
              :loading="saving"
              @click="saveStack"
            >
              Save
            </el-button>
            <el-button
              v-if="isEditing"
              size="small"
              @click="cancelEditing"
            >
              Cancel
            </el-button>
            <el-button
              size="small"
              @click="selectedStack = null"
            >
              Close
            </el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- Onglet Compose -->
        <el-tab-pane
          label="Compose YAML"
          name="compose"
        >
          <div class="compose-editor-section">
            <div
              v-if="isEditing"
              class="editor-toolbar"
            >
              <el-button
                size="small"
                :loading="validating"
                @click="validateCompose"
              >
                Validate YAML
              </el-button>
              <el-tag
                v-if="validationResult !== null"
                :type="validationResult ? 'success' : 'danger'"
                size="small"
              >
                {{ validationResult ? '✓ Valid' : '✗ Invalid' }}
              </el-tag>
            </div>
            <div class="yaml-editor">
              <textarea
                ref="yamlEditorRef"
                v-model="editForm.compose_content"
                :readonly="!isEditing"
                class="yaml-textarea"
                spellcheck="false"
                wrap="off"
              />
            </div>
            <div
              v-if="validationErrors.length > 0"
              class="validation-errors"
            >
              <el-alert
                v-for="(err, idx) in validationErrors"
                :key="idx"
                :title="err"
                type="error"
                :closable="false"
                show-icon
                style="margin-bottom: 4px"
              />
            </div>
          </div>
        </el-tab-pane>

        <!-- Onglet Variables d'environnement -->
        <el-tab-pane
          label="Environment Variables"
          name="env"
        >
          <div class="env-section">
            <div v-if="envVars.length > 0">
              <el-table
                :data="envVars"
                size="small"
              >
                <el-table-column
                  prop="key"
                  label="Variable"
                  min-width="200"
                />
                <el-table-column
                  label="Value"
                  min-width="300"
                >
                  <template #default="{ row }">
                    <div class="env-value-cell">
                      <span v-if="row.hidden && !row.revealed">••••••••</span>
                      <span v-else>{{ row.value }}</span>
                      <el-button
                        v-if="row.hidden"
                        size="small"
                        link
                        @click="row.revealed = !row.revealed"
                      >
                        {{ row.revealed ? 'Hide' : 'Show' }}
                      </el-button>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column
                  prop="service"
                  label="Service"
                  width="150"
                />
              </el-table>
            </div>
            <el-empty
              v-else
              description="No environment variables detected"
              :image-size="60"
            />
          </div>
        </el-tab-pane>

        <!-- Onglet Prévisualisation -->
        <el-tab-pane
          label="Preview"
          name="preview"
        >
          <div class="preview-section">
            <h4>Services detected</h4>
            <el-descriptions
              v-if="parsedServices.length > 0"
              :column="1"
              border
              size="small"
            >
              <el-descriptions-item
                v-for="svc in parsedServices"
                :key="svc.name"
                :label="svc.name"
              >
                <el-tag
                  size="small"
                  class="mr-2"
                >
                  {{ svc.image || 'build' }}
                </el-tag>
                <el-tag
                  v-for="port in svc.ports"
                  :key="port"
                  size="small"
                  type="info"
                  class="mr-1"
                >
                  {{ port }}
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
            <el-empty
              v-else
              description="Unable to parse compose content"
              :image-size="60"
            />
          </div>
        </el-tab-pane>

        <!-- Onglet Historique des versions -->
        <el-tab-pane
          label="History"
          name="history"
        >
          <div class="history-section">
            <div
              class="history-toolbar"
              style="margin-bottom: 12px"
            >
              <el-button
                size="small"
                type="primary"
                :loading="creatingVersion"
                @click="createSnapshot"
              >
                Create Snapshot
              </el-button>
              <el-button
                size="small"
                :loading="loadingVersions"
                @click="loadVersions"
              >
                Refresh
              </el-button>
            </div>
            <el-table
              v-if="versions.length > 0"
              v-loading="loadingVersions"
              :data="versions"
              size="small"
            >
              <el-table-column
                label="Version"
                width="90"
              >
                <template #default="{ row }">
                  <el-tag size="small">
                    v{{ row.version_number }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                prop="change_summary"
                label="Summary"
                min-width="200"
                show-overflow-tooltip
              />
              <el-table-column
                label="Author"
                width="130"
              >
                <template #default="{ row }">
                  {{ row.author_name || '—' }}
                </template>
              </el-table-column>
              <el-table-column
                label="Date"
                width="170"
              >
                <template #default="{ row }">
                  {{ formatDate(row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column
                label="Actions"
                width="180"
                fixed="right"
              >
                <template #default="{ row }">
                  <el-button
                    size="small"
                    link
                    @click="previewVersion(row)"
                  >
                    View
                  </el-button>
                  <el-popconfirm
                    title="Restore this version?"
                    confirm-button-text="Restore"
                    @confirm="restoreVersion(row)"
                  >
                    <template #reference>
                      <el-button
                        size="small"
                        link
                        type="warning"
                      >
                        Restore
                      </el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>
            <el-empty
              v-else
              description="No version history yet"
              :image-size="60"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Dialog de création -->
    <el-dialog
      v-model="showCreateDialog"
      title="Create Stack"
      width="700px"
      destroy-on-close
    >
      <el-form
        :model="createForm"
        label-width="140px"
      >
        <el-form-item
          label="Name"
          required
        >
          <el-input
            v-model="createForm.name"
            placeholder="my-stack"
          />
        </el-form-item>
        <el-form-item label="Description">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="2"
          />
        </el-form-item>
        <el-form-item
          label="Compose Content"
          required
        >
          <textarea
            v-model="createForm.compose_content"
            class="yaml-textarea"
            :rows="15"
            spellcheck="false"
            wrap="off"
            placeholder="version: '3.8'&#10;services:&#10;  web:&#10;    image: nginx:latest&#10;    ports:&#10;      - '80:80'"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">
          Cancel
        </el-button>
        <el-button
          type="primary"
          :loading="stacksStore.loading"
          @click="handleCreate"
        >
          Create
        </el-button>
      </template>
    </el-dialog>

    <!-- Dialog de déploiement -->
    <el-dialog
      v-model="showDeployDialog"
      title="Deploy Stack"
      width="500px"
      destroy-on-close
    >
      <el-form
        :model="deployForm"
        label-width="120px"
      >
        <el-form-item label="Stack">
          <el-input
            :model-value="deployStack?.name"
            disabled
          />
        </el-form-item>
        <el-form-item
          label="Target"
          required
        >
          <el-select
            v-model="deployForm.target_id"
            placeholder="Select target"
            style="width: 100%"
          >
            <el-option
              v-for="target in targetsStore.targets"
              :key="target.id"
              :label="`${target.name} (${target.host})`"
              :value="target.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDeployDialog = false">
          Cancel
        </el-button>
        <el-button
          type="success"
          :loading="deploying"
          @click="handleDeploy"
        >
          Deploy
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useStacksStore, useTargetsStore, useDeploymentsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { stacksApi } from '@/services/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Stack, StackCreate, StackVersion } from '@/types/api'
import ActionButtons from '@/components/ui/ActionButtons.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import type { StatusType } from '@/components/ui/StatusBadge.vue'
import type { ActionType } from '@/components/ui/ActionButtons.vue'

const stacksStore = useStacksStore()
const targetsStore = useTargetsStore()
const deploymentsStore = useDeploymentsStore()
const authStore = useAuthStore()

// State
const selectedStack = ref<Stack | null>(null)
const isEditing = ref(false)
const saving = ref(false)
const validating = ref(false)
const validationResult = ref<boolean | null>(null)
const validationErrors = ref<string[]>([])
const activeTab = ref('compose')
const showCreateDialog = ref(false)
const showDeployDialog = ref(false)
const deployStack = ref<Stack | null>(null)
const deploying = ref(false)
const versions = ref<StackVersion[]>([])
const loadingVersions = ref(false)
const creatingVersion = ref(false)

const editForm = reactive({
  name: '',
  description: '',
  compose_content: '',
})

const createForm = reactive<StackCreate>({
  name: '',
  description: '',
  compose_content: '',
  organization_id: authStore.organizationId || '',
})

const deployForm = reactive({
  target_id: '',
})

const yamlEditorRef = ref<HTMLTextAreaElement | null>(null)

// Get stack status based on metadata
function getStackStatus(stack: Stack): StatusType {
  if (!stack.metadata) return 'draft'
  const metadata = stack.metadata as Record<string, unknown>
  const status = metadata['status']
  if (status === 'deployed') return 'deployed'
  if (status === 'error') return 'error'
  if (status === 'deploying') return 'deploying'
  return 'draft'
}

// Computed: parse env vars from compose content
const envVars = computed(() => {
  const content = selectedStack.value?.compose_content || editForm.compose_content
  if (!content) return []

  const vars: { key: string; value: string; service: string; hidden: boolean; revealed: boolean }[] = []
  const lines = content.split('\n')
  let currentService = ''

  for (const line of lines) {
    const serviceMatch = line.match(/^\s{2}(\w[\w-]*):\s*$/)
    if (serviceMatch?.[1]) {
      currentService = serviceMatch[1]
    }
    const envMatch = line.match(/^\s+-\s*(\w+)=(.*)$/)
    if (envMatch?.[1] && envMatch[2] !== undefined) {
      const key = envMatch[1]
      const value = envMatch[2]
      const isSecret = /password|secret|key|token/i.test(key)
      vars.push({ key, value, service: currentService, hidden: isSecret, revealed: false })
    }
    const envMapMatch = line.match(/^\s{6}(\w+):\s*(.+)$/)
    if (envMapMatch?.[1] && envMapMatch[2]) {
      const key = envMapMatch[1]
      const value = envMapMatch[2]
      const isSecret = /password|secret|key|token/i.test(key)
      vars.push({ key, value, service: currentService, hidden: isSecret, revealed: false })
    }
  }
  return vars
})

// Computed: parse services from compose content
const parsedServices = computed(() => {
  const content = selectedStack.value?.compose_content || editForm.compose_content
  if (!content) return []

  const services: { name: string; image: string; ports: string[] }[] = []
  const lines = content.split('\n')
  let inServices = false
  let currentService = ''
  let currentImage = ''
  let currentPorts: string[] = []
  let inPorts = false

  for (const line of lines) {
    if (/^services:\s*$/.test(line)) {
      inServices = true
      continue
    }
    if (inServices) {
      const svcMatch = line.match(/^\s{2}(\w[\w-]*):\s*$/)
      if (svcMatch?.[1]) {
        if (currentService) {
          services.push({ name: currentService, image: currentImage, ports: currentPorts })
        }
        currentService = svcMatch[1]
        currentImage = ''
        currentPorts = []
        inPorts = false
        continue
      }
      const imgMatch = line.match(/^\s{4}image:\s*(.+)$/)
      if (imgMatch?.[1]) {
        currentImage = imgMatch[1].trim()
        inPorts = false
        continue
      }
      if (/^\s{4}ports:\s*$/.test(line)) {
        inPorts = true
        continue
      }
      if (inPorts) {
        const portMatch = line.match(/^\s{6}-\s*['"]?(.+?)['"]?\s*$/)
        if (portMatch?.[1]) {
          currentPorts.push(portMatch[1])
          continue
        }
        inPorts = false
      }
    }
  }
  if (currentService) {
    services.push({ name: currentService, image: currentImage, ports: currentPorts })
  }
  return services
})

// Methods
function selectStack(stack: Stack): void {
  selectedStack.value = stack
  editForm.name = stack.name
  editForm.description = stack.description || ''
  editForm.compose_content = stack.compose_content
  isEditing.value = false
  validationResult.value = null
  validationErrors.value = []
  activeTab.value = 'compose'
  versions.value = []
  loadVersions()
}

function startEditing(): void {
  isEditing.value = true
}

function cancelEditing(): void {
  if (selectedStack.value) {
    editForm.name = selectedStack.value.name
    editForm.description = selectedStack.value.description || ''
    editForm.compose_content = selectedStack.value.compose_content
  }
  isEditing.value = false
  validationResult.value = null
  validationErrors.value = []
}

async function saveStack(): Promise<void> {
  if (!selectedStack.value) return
  saving.value = true
  try {
    await stacksStore.updateStack(selectedStack.value.id, {
      name: editForm.name,
      description: editForm.description,
      compose_content: editForm.compose_content,
    })
    selectedStack.value = { ...selectedStack.value, ...editForm }
    isEditing.value = false
    ElMessage.success('Stack updated successfully')
  } catch {
    ElMessage.error('Failed to update stack')
  } finally {
    saving.value = false
  }
}

async function validateCompose(): Promise<void> {
  validating.value = true
  validationErrors.value = []
  try {
    const response = await stacksApi.validate({ compose_content: editForm.compose_content })
    validationResult.value = response.data.valid
    validationErrors.value = response.data.errors || []
  } catch {
    validationResult.value = false
    validationErrors.value = ['Failed to validate compose content']
  } finally {
    validating.value = false
  }
}

function openCreateDialog(): void {
  Object.assign(createForm, {
    name: '',
    description: '',
    compose_content: '',
    organization_id: authStore.organizationId || '',
  })
  showCreateDialog.value = true
}

async function handleCreate(): Promise<void> {
  try {
    await stacksStore.createStack({ ...createForm })
    ElMessage.success('Stack created successfully')
    showCreateDialog.value = false
  } catch {
    ElMessage.error('Failed to create stack')
  }
}

function openDeployDialog(stack: Stack): void {
  deployStack.value = stack
  deployForm.target_id = ''
  showDeployDialog.value = true
}

async function handleDeploy(): Promise<void> {
  if (!deployStack.value || !deployForm.target_id) {
    ElMessage.warning('Please select a target')
    return
  }
  deploying.value = true
  try {
    await deploymentsStore.createDeployment({
      stack_id: deployStack.value.id,
      target_id: deployForm.target_id,
    })
    ElMessage.success('Deployment started successfully')
    showDeployDialog.value = false
  } catch {
    ElMessage.error('Failed to start deployment')
  } finally {
    deploying.value = false
  }
}

async function confirmDelete(id: string): Promise<void> {
  try {
    await ElMessageBox.confirm('Are you sure you want to delete this stack?', 'Confirm', {
      type: 'warning',
    })
    await stacksStore.deleteStack(id)
    if (selectedStack.value?.id === id) {
      selectedStack.value = null
    }
    ElMessage.success('Stack deleted successfully')
  } catch {
    // cancelled or error
  }
}

// Handle action button clicks
function handleStackAction(type: ActionType, stack: Stack): void {
  switch (type) {
    case 'edit':
      selectStack(stack)
      break
    case 'deploy':
      openDeployDialog(stack)
      break
    case 'delete':
      confirmDelete(stack.id)
      break
  }
}

// --- Version history methods ---

async function loadVersions(): Promise<void> {
  if (!selectedStack.value) return
  loadingVersions.value = true
  try {
    const response = await stacksApi.listVersions(selectedStack.value.id)
    versions.value = response.data
  } catch {
    ElMessage.error('Failed to load version history')
  } finally {
    loadingVersions.value = false
  }
}

async function createSnapshot(): Promise<void> {
  if (!selectedStack.value) return
  creatingVersion.value = true
  try {
    await stacksApi.createVersion(selectedStack.value.id, { change_summary: 'Manual snapshot' })
    ElMessage.success('Snapshot created')
    await loadVersions()
  } catch {
    ElMessage.error('Failed to create snapshot')
  } finally {
    creatingVersion.value = false
  }
}

function previewVersion(version: StackVersion): void {
  editForm.compose_content = version.compose_content
  activeTab.value = 'compose'
  isEditing.value = false
  ElMessage.info(`Viewing version v${version.version_number}`)
}

async function restoreVersion(version: StackVersion): Promise<void> {
  if (!selectedStack.value) return
  try {
    const response = await stacksApi.restoreVersion(selectedStack.value.id, version.id)
    selectedStack.value = response.data
    editForm.compose_content = response.data.compose_content
    ElMessage.success(`Restored to version v${version.version_number}`)
    await loadVersions()
    await stacksStore.fetchStacks(authStore.organizationId || undefined)
  } catch {
    ElMessage.error('Failed to restore version')
  }
}

function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString()
}

onMounted(() => {
  const orgId = authStore.organizationId || undefined
  stacksStore.fetchStacks(orgId)
  targetsStore.fetchTargets(orgId)
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.yaml-editor {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  overflow: hidden;
}

.yaml-textarea {
  width: 100%;
  min-height: 400px;
  padding: 12px;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  background: #1e1e1e;
  color: #d4d4d4;
  border: none;
  outline: none;
  resize: vertical;
  tab-size: 2;
  white-space: pre;
  overflow: auto;
}

.yaml-textarea:read-only {
  background: #252526;
  cursor: default;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.validation-errors {
  margin-top: 8px;
}

.compose-editor-section {
  padding: 8px 0;
}

.env-section {
  padding: 8px 0;
}

.env-value-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preview-section {
  padding: 8px 0;
}

.preview-section h4 {
  margin-bottom: 12px;
}
</style>
