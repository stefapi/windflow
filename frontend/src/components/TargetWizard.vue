<template>
  <BaseWizard
    ref="wizardRef"
    v-model="dialogVisible"
    v-model:error="error"
    :title="isEditing ? 'Modifier la cible' : 'Nouvelle cible'"
    :steps="wizardSteps"
    :loading="targetsStore.loading"
    :confirm-label="isEditing ? 'Enregistrer' : 'Créer'"
    :confirm-loading="targetsStore.loading"
    :validate-next="validateCurrentStep"
    @confirm="handleSave"
    @close="handleClose"
  >
    <!-- STEP 0: Basic Info -->
    <template #step-0>
      <el-form
        :model="form"
        :rules="infoRules"
        label-position="top"
        ref="infoFormRef"
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

        <!-- Reachability test -->
        <el-form-item label="Connectivité">
          <div class="w-full">
            <el-button
              :disabled="!form.host"
              :loading="testingReachability"
              @click="testReachability"
            >
              <el-icon class="mr-1"><Promotion /></el-icon>
              Tester la connectivité
            </el-button>

            <div
              v-if="reachabilityResult"
              class="mt-3 w-full"
            >
              <div class="flex flex-col gap-2">
                <div
                  v-for="step in reachabilityResult.steps"
                  :key="step.step"
                  class="flex items-center gap-2"
                >
                  <el-icon
                    :color="step.success ? '#67c23a' : '#f56c6c'"
                    :size="18"
                  >
                    <CircleCheck v-if="step.success" />
                    <CircleClose v-else />
                  </el-icon>
                  <el-tag
                    :type="step.success ? 'success' : 'danger'"
                    size="small"
                    class="w-16 text-center"
                  >
                    {{ step.step.toUpperCase() }}
                  </el-tag>
                  <span class="text-sm text-gray-600">{{ step.message }}</span>
                  <span
                    v-if="step.duration_ms !== null"
                    class="text-xs text-gray-400 ml-auto"
                  >
                    {{ step.duration_ms.toFixed(1) }}ms
                  </span>
                </div>
              </div>

              <el-alert
                :type="reachabilityResult.reachable ? 'success' : 'error'"
                :title="reachabilityResult.reachable
                  ? `${form.host}:${form.port} est joignable`
                  : `${form.host}:${form.port} n'est pas joignable`"
                show-icon
                :closable="false"
                class="mt-3"
              />
            </div>
          </div>
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
    </template>

    <!-- STEP 1: SSH Credentials -->
    <template #step-1>
      <el-form
        :model="credentialsForm"
        :rules="credRules"
        label-position="top"
        ref="credFormRef"
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
          Escalade sudo
        </el-divider>

        <el-form-item label="Activer sudo">
          <el-switch
            v-model="credentialsForm.sudo_enabled"
            active-text="Activé"
            inactive-text="Désactivé"
          />
        </el-form-item>

        <template v-if="credentialsForm.sudo_enabled">
          <el-form-item label="Utilisateur sudo">
            <el-input
              v-model="credentialsForm.sudo_user"
              placeholder="ex: root (défaut: root)"
            />
          </el-form-item>
          <el-form-item label="Mot de passe sudo">
            <el-input
              v-model="credentialsForm.sudo_password"
              type="password"
              show-password
              placeholder="Mot de passe sudo (laisser vide si passwordless)"
            />
          </el-form-item>
          <el-alert
            v-if="!credentialsForm.sudo_password"
            type="info"
            :closable="false"
            show-icon
            class="mb-4"
          >
            <template #title>
              Sans mot de passe sudo, le système tentera un sudo passwordless (sudo -n).
            </template>
          </el-alert>
        </template>
      </el-form>
    </template>

    <!-- STEP 2: Test Connection + Summary -->
    <template #step-2>
      <div class="flex flex-col items-center gap-4">
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
          class="w-full"
        />

        <div
          v-if="connectionTestResult?.os_info"
          class="mt-2"
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
          class="w-full"
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
          <el-descriptions-item label="Sudo">
            <el-tag
              v-if="credentialsForm.sudo_enabled"
              type="success"
              size="small"
            >
              Activé{{ credentialsForm.sudo_user ? ` (${credentialsForm.sudo_user})` : ' (root)' }}
            </el-tag>
            <el-tag
              v-else
              type="info"
              size="small"
            >
              Désactivé
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="form.description"
            label="Description"
          >
            {{ form.description }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </template>
  </BaseWizard>
</template>

<script setup lang="ts">
/**
 * TargetWizard — Create / Edit target dialog
 *
 * Uses BaseWizard for the step engine. Three steps:
 *   0: Basic info (name, host, port, description)
 *   1: SSH credentials (auth method, user, key/password, sudo)
 *   2: Validation (test connection + summary)
 */
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Connection, Promotion, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { useTargetsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import BaseWizard from '@/components/BaseWizard.vue'
import type { Target, TargetCreate, TargetUpdate, ConnectionTestResponse, HostReachabilityResponse, SSHAuthMethod } from '@/types/api'

// ─── Props & Emits ────────────────────────────────────────────

const props = defineProps<{
  modelValue: boolean
  /** Target to edit — null for create mode */
  editTarget: Target | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'saved': [targetId: string]
}>()

// ─── Stores ───────────────────────────────────────────────────

const targetsStore = useTargetsStore()
const authStore = useAuthStore()

// ─── Wizard ref & steps ───────────────────────────────────────

const wizardRef = ref<InstanceType<typeof BaseWizard>>()

const wizardSteps = [
  { title: 'Informations', description: 'Identification' },
  { title: 'Connexion SSH', description: 'Authentification' },
  { title: 'Validation', description: 'Vérifier' },
]

const error = ref('')

// ─── Visibility ───────────────────────────────────────────────

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

const isEditing = computed(() => props.editTarget !== null)

// ─── Form refs ────────────────────────────────────────────────

const infoFormRef = ref<FormInstance>()
const credFormRef = ref<FormInstance>()

// ─── Form state ───────────────────────────────────────────────

const form = reactive({
  name: '',
  host: '',
  port: 22,
  description: '',
})

const credentialsForm = reactive({
  auth_method: 'password' as SSHAuthMethod,
  username: '',
  password: '',
  ssh_private_key: '',
  ssh_private_key_passphrase: '',
  sudo_enabled: false,
  sudo_user: '',
  sudo_password: '',
})

const testingConnection = ref(false)
const connectionTestResult = ref<ConnectionTestResponse | null>(null)
const testingReachability = ref(false)
const reachabilityResult = ref<HostReachabilityResponse | null>(null)

// ─── Validation rules ─────────────────────────────────────────

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

// ─── Step validation ──────────────────────────────────────────

async function validateCurrentStep(): Promise<boolean> {
  const step = wizardRef.value?.currentStep ?? 0

  if (step === 0) {
    const valid = await infoFormRef.value?.validate().catch(() => false)
    return !!valid
  }

  if (step === 1) {
    const valid = await credFormRef.value?.validate().catch(() => false)
    if (valid) {
      // Reset test result when credentials change
      connectionTestResult.value = null
    }
    return !!valid
  }

  return true
}

// ─── Init forms from edit target ──────────────────────────────

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
  credentialsForm.sudo_enabled = false
  credentialsForm.sudo_user = ''
  credentialsForm.sudo_password = ''
  reachabilityResult.value = null
  connectionTestResult.value = null
  error.value = ''
}

function populateFromTarget(target: Target): void {
  form.name = target.name
  form.host = target.host
  form.port = target.port
  form.description = target.description || ''
  // Credentials are not returned from API for security
  credentialsForm.auth_method = (target.auth_method as SSHAuthMethod) || 'password'
  credentialsForm.username = target.username || ''
  // Restore sudo_enabled from target (has_sudo is derived from sudo_enabled && sudo_user)
  credentialsForm.sudo_enabled = target.has_sudo
}

// ─── Watch for open ───────────────────────────────────────────

import { watch } from 'vue'

watch(() => props.modelValue, (open) => {
  if (open) {
    resetForms()
    if (props.editTarget) {
      populateFromTarget(props.editTarget)
    }
  }
})

// ─── Test Reachability ────────────────────────────────────────

async function testReachability(): Promise<void> {
  if (!form.host) return
  testingReachability.value = true
  reachabilityResult.value = null
  try {
    reachabilityResult.value = await targetsStore.testReachability({
      host: form.host,
      port: form.port,
    })
  } catch {
    reachabilityResult.value = {
      host: form.host,
      port: form.port,
      steps: [
        { step: 'dns', success: false, message: 'Erreur lors du test de connectivité', duration_ms: null },
        { step: 'ssh', success: false, message: 'Erreur lors du test de connectivité', duration_ms: null },
      ],
      reachable: false,
    }
  } finally {
    testingReachability.value = false
  }
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
        sudo_enabled: credentialsForm.sudo_enabled,
        sudo_user: credentialsForm.sudo_enabled ? (credentialsForm.sudo_user || undefined) : undefined,
        sudo_password: credentialsForm.sudo_enabled ? (credentialsForm.sudo_password || undefined) : undefined,
      },
    })
    connectionTestResult.value = result
  } catch {
    connectionTestResult.value = { success: false, message: 'Erreur lors du test de connexion' }
  } finally {
    testingConnection.value = false
  }
}

// ─── Save ─────────────────────────────────────────────────────

async function handleSave(): Promise<void> {
  try {
    let savedTargetId: string

    if (isEditing.value && props.editTarget) {
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
          sudo_enabled: credentialsForm.sudo_enabled,
          sudo_user: credentialsForm.sudo_enabled ? (credentialsForm.sudo_user || undefined) : undefined,
          sudo_password: credentialsForm.sudo_enabled ? (credentialsForm.sudo_password || undefined) : undefined,
        },
      }
      await targetsStore.updateTarget(props.editTarget.id, updateData)
      savedTargetId = props.editTarget.id
      ElMessage.success('Cible mise à jour avec succès')
    } else {
      const createData: TargetCreate = {
        name: form.name,
        type: 'physical', // Les cibles créées via wizard sont des machines physiques (SSH)
        host: form.host,
        port: form.port,
        description: form.description || undefined,
        credentials: {
          auth_method: credentialsForm.auth_method,
          username: credentialsForm.username,
          password: credentialsForm.auth_method === 'password' ? credentialsForm.password : undefined,
          ssh_private_key: credentialsForm.auth_method === 'ssh_key' ? credentialsForm.ssh_private_key : undefined,
          ssh_private_key_passphrase: credentialsForm.auth_method === 'ssh_key' ? credentialsForm.ssh_private_key_passphrase : undefined,
          sudo_enabled: credentialsForm.sudo_enabled,
          sudo_user: credentialsForm.sudo_enabled ? (credentialsForm.sudo_user || undefined) : undefined,
          sudo_password: credentialsForm.sudo_enabled ? (credentialsForm.sudo_password || undefined) : undefined,
        },
        organization_id: authStore.organizationId || '',
      }
      const created = await targetsStore.createTarget(createData)
      savedTargetId = created.id
      ElMessage.success('Cible créée avec succès')
    }
    dialogVisible.value = false
    emit('saved', savedTargetId)
  } catch {
    error.value = isEditing.value ? 'Échec de la mise à jour' : 'Échec de la création'
  }
}

// ─── Close ────────────────────────────────────────────────────

function handleClose(): void {
  dialogVisible.value = false
}
</script>
