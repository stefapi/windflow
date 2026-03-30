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
import { Connection } from '@element-plus/icons-vue'
import { useTargetsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import BaseWizard from '@/components/BaseWizard.vue'
import type { Target, TargetCreate, TargetUpdate, ConnectionTestResponse, SSHAuthMethod } from '@/types/api'

// ─── Props & Emits ────────────────────────────────────────────

const props = defineProps<{
  modelValue: boolean
  /** Target to edit — null for create mode */
  editTarget: Target | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'saved': []
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
  sudo_user: '',
  sudo_password: '',
})

const testingConnection = ref(false)
const connectionTestResult = ref<ConnectionTestResponse | null>(null)

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
  credentialsForm.sudo_user = ''
  credentialsForm.sudo_password = ''
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

// ─── Save ─────────────────────────────────────────────────────

async function handleSave(): Promise<void> {
  try {
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
          sudo_user: credentialsForm.sudo_user || undefined,
          sudo_password: credentialsForm.sudo_password || undefined,
        },
      }
      await targetsStore.updateTarget(props.editTarget.id, updateData)
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
    emit('saved')
  } catch {
    error.value = isEditing.value ? 'Échec de la mise à jour' : 'Échec de la création'
  }
}

// ─── Close ────────────────────────────────────────────────────

function handleClose(): void {
  dialogVisible.value = false
}
</script>
