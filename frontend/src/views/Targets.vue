<template>
  <div class="targets">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ t('targets.title', 'Cibles de déploiement') }}</span>
          <el-button
            type="primary"
            @click="openCreateDialog"
          >
            <el-icon class="mr-1"><Plus /></el-icon>
            {{ t('targets.add', 'Ajouter une cible') }}
          </el-button>
        </div>
      </template>

      <el-table
        v-loading="targetsStore.loading"
        :data="targetsStore.targets"
        :expand-row-keys="expandedRowId ? [expandedRowId] : []"
        row-key="id"
        stripe
        @expand-change="handleExpandChange"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div
              v-loading="loadingCapabilities.has(row.id)"
              class="capabilities-section"
            >
              <h4 class="capabilities-title">
                {{ t('targets.capabilities', 'Capacités détectées') }}
              </h4>

              <!-- Scan info -->
              <div
                v-if="row.scan_date"
                class="scan-info"
              >
                <el-tag
                  :type="row.scan_success ? 'success' : 'danger'"
                  size="small"
                >
                  {{ row.scan_success ? '✓ Scan OK' : '✗ Scan échoué' }}
                </el-tag>
                <span class="scan-date">{{ formatDate(row.scan_date) }}</span>
                <el-button
                  size="small"
                  :loading="scanningTargets.has(row.id)"
                  @click="refreshCapabilities(row.id)"
                >
                  Rescan
                </el-button>
              </div>

              <!-- OS / Platform info -->
              <div
                v-if="row.os_info || row.platform_info"
                class="system-info"
              >
                <el-descriptions
                  :column="2"
                  size="small"
                  border
                >
                  <el-descriptions-item
                    v-if="row.os_info && row.os_info['distribution']"
                    label="OS"
                  >
                    {{ row.os_info['distribution'] }}
                    {{ row.os_info['version'] || '' }}
                  </el-descriptions-item>
                  <el-descriptions-item
                    v-if="row.platform_info && row.platform_info['architecture']"
                    label="Architecture"
                  >
                    {{ row.platform_info['architecture'] }}
                  </el-descriptions-item>
                  <el-descriptions-item
                    v-if="row.platform_info && row.platform_info['cpu_cores']"
                    label="CPU cores"
                  >
                    {{ row.platform_info['cpu_cores'] }}
                  </el-descriptions-item>
                  <el-descriptions-item
                    v-if="row.platform_info && row.platform_info['total_memory_gb']"
                    label="Mémoire"
                  >
                    {{ row.platform_info['total_memory_gb'] }} Go
                  </el-descriptions-item>
                </el-descriptions>
              </div>

              <!-- Capabilities table -->
              <el-table
                v-if="row.capabilities && row.capabilities.length > 0"
                :data="row.capabilities"
                stripe
                class="capabilities-table"
              >
                <el-table-column
                  prop="capability_type"
                  :label="t('targets.capabilityType', 'Type')"
                  width="250"
                >
                  <template #default="{ row: capRow }">
                    <el-tag size="small">
                      {{ formatCapabilityType(capRow.capability_type) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column
                  prop="version"
                  label="Version"
                >
                  <template #default="{ row: capRow }">
                    {{ capRow.version || '—' }}
                  </template>
                </el-table-column>
                <el-table-column
                  prop="is_available"
                  label="Disponible"
                  width="120"
                >
                  <template #default="{ row: capRow }">
                    <el-tag
                      :type="capRow.is_available ? 'success' : 'info'"
                      size="small"
                    >
                      {{ capRow.is_available ? 'Oui' : 'Non' }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
              <div
                v-else-if="!loadingCapabilities.has(row.id)"
                class="no-capabilities"
              >
                <el-empty :description="t('targets.noCapabilities', 'Aucune capacité détectée. Cliquez sur le bouton Scan pour détecter.')" />
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column
          prop="name"
          label="Nom"
          min-width="140"
        />
        <el-table-column
          prop="host"
          label="Hôte"
          min-width="160"
        />
        <el-table-column
          prop="port"
          label="Port"
          width="80"
        />
        <el-table-column
          label="Connexion"
          width="130"
        >
          <template #default="{ row }">
            <div class="connection-info">
              <el-tag
                size="small"
                type="info"
              >
                {{ row.auth_method === 'local' ? 'Local' : row.auth_method === 'ssh_key' ? 'SSH Key' : 'Password' }}
              </el-tag>
              <span
                v-if="row.username"
                class="username"
              >{{ row.username }}</span>
              <el-tag
                v-if="row.has_sudo"
                size="small"
                type="warning"
              >
                sudo
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          label="Statut"
          width="120"
        >
          <template #default="{ row }">
            <StatusBadge :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column
          label="Actions"
          width="200"
          align="right"
        >
          <template #default="{ row }">
            <el-button-group>
              <el-button
                size="small"
                title="Scanner"
                :loading="scanningTargets.has(row.id)"
                @click="refreshCapabilities(row.id)"
              >
                <el-icon><Refresh /></el-icon>
              </el-button>
              <el-button
                size="small"
                title="Modifier"
                @click="openEditDialog(row)"
              >
                <el-icon><Edit /></el-icon>
              </el-button>
              <el-button
                size="small"
                type="danger"
                title="Supprimer"
                @click="confirmDelete(row)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- ===================== CREATE / EDIT DIALOG ===================== -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? t('targets.editTitle', 'Modifier la cible') : t('targets.createTitle', 'Nouvelle cible')"
      width="640px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-steps
        :active="currentStep"
        finish-status="success"
        simple
        class="wizard-steps"
      >
        <el-step title="Informations" />
        <el-step title="Connexion SSH" />
        <el-step title="Validation" />
      </el-steps>

      <!-- STEP 0: Basic Info -->
      <div v-show="currentStep === 0">
        <el-form
          :model="form"
          :rules="infoRules"
          label-width="140px"
          ref="infoFormRef"
          class="step-form"
        >
          <el-form-item
            label="Nom"
            prop="name"
          >
            <el-input
              v-model="form.name"
              placeholder="ex: production-server"
            />
          </el-form-item>
          <el-form-item
            label="Hôte"
            prop="host"
          >
            <el-input
              v-model="form.host"
              placeholder="IP ou nom de domaine"
            />
          </el-form-item>
          <el-form-item label="Port SSH">
            <el-input-number
              v-model="form.port"
              :min="1"
              :max="65535"
            />
          </el-form-item>
          <el-form-item label="Description">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="2"
              placeholder="Description optionnelle"
            />
          </el-form-item>
        </el-form>
      </div>

      <!-- STEP 1: SSH Credentials -->
      <div v-show="currentStep === 1">
        <el-form
          :model="credentialsForm"
          :rules="credRules"
          label-width="180px"
          ref="credFormRef"
          class="step-form"
        >
          <el-form-item label="Méthode d'authentification">
            <el-radio-group v-model="credentialsForm.auth_method">
              <el-radio value="local">
                Local (sans SSH)
              </el-radio>
              <el-radio value="password">
                Mot de passe
              </el-radio>
              <el-radio value="ssh_key">
                Clé SSH
              </el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item
            v-if="credentialsForm.auth_method !== 'local'"
            label="Utilisateur"
            prop="username"
          >
            <el-input
              v-model="credentialsForm.username"
              placeholder="ex: deploy, root"
            />
          </el-form-item>

          <!-- Password auth -->
          <el-form-item
            v-if="credentialsForm.auth_method === 'password'"
            label="Mot de passe"
            prop="password"
          >
            <el-input
              v-model="credentialsForm.password"
              type="password"
              show-password
              placeholder="Mot de passe SSH"
            />
          </el-form-item>

          <!-- SSH Key auth -->
          <el-form-item
            v-if="credentialsForm.auth_method === 'ssh_key'"
            label="Clé privée SSH"
            prop="ssh_private_key"
          >
            <el-input
              v-model="credentialsForm.ssh_private_key"
              type="textarea"
              :rows="5"
              placeholder="Paste your SSH private key here"
            />
          </el-form-item>
          <el-form-item
            v-if="credentialsForm.auth_method === 'ssh_key'"
            label="Phrase de passe (optionnel)"
          >
            <el-input
              v-model="credentialsForm.ssh_private_key_passphrase"
              type="password"
              show-password
              placeholder="Passphrase de la clé"
            />
          </el-form-item>

          <el-divider content-position="left">
            Escalade sudo (optionnel)
          </el-divider>

          <el-form-item label="Utilisateur sudo">
            <el-input
              v-model="credentialsForm.sudo_user"
              placeholder="ex: root"
            />
          </el-form-item>
          <el-form-item label="Mot de passe sudo">
            <el-input
              v-model="credentialsForm.sudo_password"
              type="password"
              show-password
              placeholder="Mot de passe sudo"
            />
          </el-form-item>
        </el-form>
      </div>

      <!-- STEP 2: Test Connection + Summary -->
      <div v-show="currentStep === 2">
        <div class="validation-step">
          <el-button
            type="primary"
            :loading="testingConnection"
            @click="testSSHConnection"
          >
            <el-icon class="mr-1"><Connection /></el-icon>
            Tester la connexion
          </el-button>

          <el-alert
            v-if="connectionTestResult"
            :type="connectionTestResult.success ? 'success' : 'error'"
            :title="connectionTestResult.message"
            show-icon
            :closable="false"
            class="test-result"
          />

          <div
            v-if="connectionTestResult?.os_info"
            class="os-info"
          >
            <el-tag type="info">
              {{ connectionTestResult.os_info['distribution'] || connectionTestResult.os_info['uname'] || 'OS détecté' }}
            </el-tag>
          </div>

          <el-divider />

          <el-descriptions
            :column="1"
            border
            size="small"
            title="Résumé"
          >
            <el-descriptions-item label="Nom">
              {{ form.name }}
            </el-descriptions-item>
            <el-descriptions-item label="Hôte">
              {{ form.host }}:{{ form.port }}
            </el-descriptions-item>
            <el-descriptions-item
              v-if="credentialsForm.auth_method !== 'local'"
              label="Utilisateur"
            >
              {{ credentialsForm.username }}
            </el-descriptions-item>
            <el-descriptions-item label="Authentification">
              {{ credentialsForm.auth_method === 'local' ? 'Local (sans SSH)' : credentialsForm.auth_method === 'ssh_key' ? 'Clé SSH' : 'Mot de passe' }}
            </el-descriptions-item>
            <el-descriptions-item
              v-if="credentialsForm.sudo_user"
              label="Sudo"
            >
              {{ credentialsForm.sudo_user }}
            </el-descriptions-item>
            <el-descriptions-item
              v-if="form.description"
              label="Description"
            >
              {{ form.description }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">
            Annuler
          </el-button>
          <el-button
            v-if="currentStep > 0"
            @click="currentStep--"
          >
            Précédent
          </el-button>
          <el-button
            v-if="currentStep < 2"
            type="primary"
            @click="nextStep"
          >
            Suivant
          </el-button>
          <el-button
            v-if="currentStep === 2"
            type="success"
            :loading="targetsStore.loading"
            @click="handleSave"
          >
            {{ isEditing ? 'Enregistrer' : 'Créer' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useTargetsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Plus, Edit, Delete, Refresh, Connection } from '@element-plus/icons-vue'
import { targetsApi } from '@/services/api'
import type { Target, TargetCreate, TargetUpdate, ConnectionTestResponse, SSHAuthMethod } from '@/types/api'
import StatusBadge from '@/components/ui/StatusBadge.vue'

const targetsStore = useTargetsStore()
const authStore = useAuthStore()

// UI state
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingTargetId = ref<string | null>(null)
const currentStep = ref(0)
const scanningTargets = ref<Set<string>>(new Set())
const expandedRowId = ref<string | null>(null)
const loadingCapabilities = ref<Set<string>>(new Set())
const testingConnection = ref(false)
const connectionTestResult = ref<ConnectionTestResponse | null>(null)

// Form refs
const infoFormRef = ref<FormInstance>()
const credFormRef = ref<FormInstance>()

// Basic info form
const form = reactive({
  name: '',
  host: '',
  port: 22,
  description: '',
})

// Credentials form
const credentialsForm = reactive({
  auth_method: 'password' as SSHAuthMethod,
  username: '',
  password: '',
  ssh_private_key: '',
  ssh_private_key_passphrase: '',
  sudo_user: '',
  sudo_password: '',
})

// Validation rules
const infoRules: FormRules = {
  name: [{ required: true, message: 'Le nom est requis', trigger: 'blur' }],
  host: [{ required: true, message: "L'hôte est requis", trigger: 'blur' }],
}

const credRules: FormRules = {
  username: [{
    validator: (_rule: unknown, value: string, callback: (err?: Error) => void) => {
      if (credentialsForm.auth_method !== 'local' && !value) {
        callback(new Error("L'utilisateur est requis"))
      } else {
        callback()
      }
    },
    trigger: 'blur',
  }],
  password: [{
    validator: (_rule: unknown, value: string, callback: (err?: Error) => void) => {
      if (credentialsForm.auth_method === 'password' && !value) {
        callback(new Error('Le mot de passe est requis'))
      } else {
        callback()
      }
    },
    trigger: 'blur',
  }],
  ssh_private_key: [{
    validator: (_rule: unknown, value: string, callback: (err?: Error) => void) => {
      if (credentialsForm.auth_method === 'ssh_key' && !value) {
        callback(new Error('La clé privée SSH est requise'))
      } else {
        callback()
      }
    },
    trigger: 'blur',
  }],
}

// ─── Helpers ──────────────────────────────────────────────────

const t = (_key: string, fallback: string) => fallback // i18n placeholder

function formatDate(date: string | null): string {
  if (!date) return '—'
  return new Date(date).toLocaleString('fr-FR')
}

function formatCapabilityType(type: string): string {
  const map: Record<string, string> = {
    docker: 'Docker',
    docker_compose: 'Docker Compose',
    docker_swarm: 'Docker Swarm',
    kubernetes: 'Kubernetes',
    kubectl: 'kubectl',
    helm: 'Helm',
    libvirt: 'Libvirt',
    virtualbox: 'VirtualBox',
    vagrant: 'Vagrant',
    proxmox: 'Proxmox',
    qemu_kvm: 'QEMU/KVM',
    podman: 'Podman',
    lxc: 'LXC',
    lxd: 'LXD',
    incus: 'Incus',
    containerd: 'containerd',
  }
  return map[type] || type
}

function resetForms(): void {
  form.name = ''
  form.host = ''
  form.port = 22
  form.description = ''
  credentialsForm.auth_method = 'password'
  credentialsForm.username = ''
  credentialsForm.password = ''
  credentialsForm.ssh_private_key = ''
  credentialsForm.ssh_private_key_passphrase = ''
  credentialsForm.sudo_user = ''
  credentialsForm.sudo_password = ''
  connectionTestResult.value = null
  currentStep.value = 0
}

// ─── Dialog management ────────────────────────────────────────

function openCreateDialog(): void {
  isEditing.value = false
  editingTargetId.value = null
  resetForms()
  dialogVisible.value = true
}

function openEditDialog(target: Target): void {
  isEditing.value = true
  editingTargetId.value = target.id
  resetForms()

  form.name = target.name
  form.host = target.host
  form.port = target.port
  form.description = target.description || ''

  // Credentials are not returned from API for security
  // User must re-enter them to change
  credentialsForm.auth_method = (target.auth_method as SSHAuthMethod) || 'password'
  credentialsForm.username = target.username || ''

  currentStep.value = 0
  dialogVisible.value = true
}

async function nextStep(): Promise<void> {
  if (currentStep.value === 0) {
    const valid = await infoFormRef.value?.validate().catch(() => false)
    if (!valid) return
  }
  if (currentStep.value === 1) {
    const valid = await credFormRef.value?.validate().catch(() => false)
    if (!valid) return
    // Reset test result when credentials change
    connectionTestResult.value = null
  }
  currentStep.value++
}

// ─── Test Connection ──────────────────────────────────────────

async function testSSHConnection(): Promise<void> {
  testingConnection.value = true
  connectionTestResult.value = null
  try {
    const result = await targetsStore.testConnection({
      host: form.host,
      port: form.port,
      credentials: {
        auth_method: credentialsForm.auth_method,
        username: credentialsForm.username,
        password: credentialsForm.auth_method === 'password' ? credentialsForm.password : undefined,
        ssh_private_key: credentialsForm.auth_method === 'ssh_key' ? credentialsForm.ssh_private_key : undefined,
        ssh_private_key_passphrase: credentialsForm.auth_method === 'ssh_key' ? credentialsForm.ssh_private_key_passphrase : undefined,
      },
    })
    connectionTestResult.value = result
  } catch {
    connectionTestResult.value = { success: false, message: 'Erreur lors du test de connexion' }
  } finally {
    testingConnection.value = false
  }
}

// ─── Save (Create / Update) ───────────────────────────────────

async function handleSave(): Promise<void> {
  try {
    if (isEditing.value && editingTargetId.value) {
      const updateData: TargetUpdate = {
        name: form.name,
        host: form.host,
        port: form.port,
        description: form.description,
        credentials: {
          auth_method: credentialsForm.auth_method,
          username: credentialsForm.username,
          password: credentialsForm.auth_method === 'password' ? credentialsForm.password : undefined,
          ssh_private_key: credentialsForm.auth_method === 'ssh_key' ? credentialsForm.ssh_private_key : undefined,
          ssh_private_key_passphrase: credentialsForm.auth_method === 'ssh_key' ? credentialsForm.ssh_private_key_passphrase : undefined,
          sudo_user: credentialsForm.sudo_user || undefined,
          sudo_password: credentialsForm.sudo_password || undefined,
        },
      }
      await targetsStore.updateTarget(editingTargetId.value, updateData)
      ElMessage.success('Cible mise à jour avec succès')
    } else {
      const createData: TargetCreate = {
        name: form.name,
        type: 'docker', // default, will be updated by scan
        host: form.host,
        port: form.port,
        description: form.description || undefined,
        credentials: {
          auth_method: credentialsForm.auth_method,
          username: credentialsForm.username,
          password: credentialsForm.auth_method === 'password' ? credentialsForm.password : undefined,
          ssh_private_key: credentialsForm.auth_method === 'ssh_key' ? credentialsForm.ssh_private_key : undefined,
          ssh_private_key_passphrase: credentialsForm.auth_method === 'ssh_key' ? credentialsForm.ssh_private_key_passphrase : undefined,
          sudo_user: credentialsForm.sudo_user || undefined,
          sudo_password: credentialsForm.sudo_password || undefined,
        },
        organization_id: authStore.organizationId || '',
      }
      await targetsStore.createTarget(createData)
      ElMessage.success('Cible créée avec succès')
    }
    dialogVisible.value = false
  } catch {
    ElMessage.error(isEditing.value ? 'Échec de la mise à jour' : 'Échec de la création')
  }
}

// ─── Delete ───────────────────────────────────────────────────

async function confirmDelete(target: Target): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `Supprimer la cible "${target.name}" (${target.host}) ? Cette action est irréversible.`,
      'Confirmer la suppression',
      {
        confirmButtonText: 'Supprimer',
        cancelButtonText: 'Annuler',
        type: 'warning',
      },
    )
    await targetsStore.deleteTarget(target.id)
    ElMessage.success('Cible supprimée')
  } catch {
    // User cancelled or delete failed
  }
}

// ─── Scan / Capabilities ──────────────────────────────────────

const handleExpandChange = async (row: Target, expandedRows: Target[]): Promise<void> => {
  if (expandedRows.length === 0) {
    expandedRowId.value = null
  } else {
    expandedRowId.value = row.id
    if (!row.capabilities || row.capabilities.length === 0) {
      await loadCapabilities(row.id)
    }
  }
}

const loadCapabilities = async (targetId: string): Promise<void> => {
  loadingCapabilities.value.add(targetId)
  try {
    const response = await targetsApi.getCapabilities(targetId)
    const targetIndex = targetsStore.targets.findIndex(t => t.id === targetId)
    if (targetIndex !== -1 && targetsStore.targets[targetIndex]) {
      targetsStore.targets[targetIndex].capabilities = response.data.capabilities
    }
  } catch {
    ElMessage.error('Impossible de charger les capacités')
  } finally {
    loadingCapabilities.value.delete(targetId)
  }
}

const refreshCapabilities = async (targetId: string): Promise<void> => {
  try {
    scanningTargets.value.add(targetId)
    await targetsStore.scanTarget(targetId)
    await loadCapabilities(targetId)
    ElMessage.success('Scan terminé avec succès')
  } catch {
    ElMessage.error('Échec du scan')
  } finally {
    scanningTargets.value.delete(targetId)
  }
}

// ─── Init ─────────────────────────────────────────────────────

onMounted(() => {
  targetsStore.fetchTargets(authStore.organizationId || undefined)
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.wizard-steps {
  margin-bottom: 24px;
}

.step-form {
  max-width: 520px;
  margin: 16px auto 0;
}

.validation-step {
  padding: 16px;
  text-align: center;
}

.test-result {
  margin-top: 16px;
  text-align: left;
}

.os-info {
  margin-top: 12px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.capabilities-section {
  padding: 20px;
  margin: 10px 0;
  background-color: var(--color-bg-secondary, #f5f7fa);
  border-radius: 4px;
}

.capabilities-title {
  margin: 0 0 15px;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
}

.capabilities-table {
  background-color: var(--color-bg-card, #fff);
  border-radius: 4px;
}

.no-capabilities {
  padding: 20px;
  text-align: center;
}

.scan-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.scan-date {
  color: var(--color-text-secondary, #909399);
  font-size: 13px;
}

.system-info {
  margin-bottom: 16px;
}

.connection-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}

.connection-info .username {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}

.mr-1 {
  margin-right: 4px;
}
</style>
