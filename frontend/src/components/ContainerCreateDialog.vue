<template>
  <el-dialog
    title="Créer un container"
    :model-value="modelValue"
    width="600px"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="140px"
    >
      <!-- Nom -->
      <el-form-item
        label="Nom"
        prop="name"
      >
        <el-input
          v-model="form.name"
          placeholder="my-container"
        />
      </el-form-item>

      <!-- Image -->
      <el-form-item
        label="Image"
        prop="image"
      >
        <el-input
          v-model="form.image"
          placeholder="nginx:latest"
        />
      </el-form-item>

      <!-- Command -->
      <el-form-item label="Commande">
        <el-input
          v-model="commandInput"
          placeholder="Commande (ex: sleep, 3600)"
        />
        <div class="text-xs text-gray-400 mt-1">
          Arguments séparés par des virgules
        </div>
      </el-form-item>

      <!-- Variables d'environnement -->
      <el-divider content-position="left">
        Variables d'environnement
      </el-divider>
      <div
        v-for="(envVar, index) in envVars"
        :key="'env-' + index"
        class="flex items-center gap-2 mb-2"
      >
        <el-input
          v-model="envVar.key"
          placeholder="KEY"
          style="width: 40%"
        />
        <el-input
          v-model="envVar.value"
          type="password"
          show-password
          placeholder="VALUE"
          style="width: 50%"
        />
        <el-button
          type="danger"
          :icon="Delete"
          circle
          size="small"
          @click="envVars.splice(index, 1)"
        />
      </div>
      <el-button
        size="small"
        @click="envVars.push({ key: '', value: '' })"
      >
        + Ajouter une variable
      </el-button>

      <!-- Ports -->
      <el-divider content-position="left">
        Ports
      </el-divider>
      <div
        v-for="(port, index) in portMappings"
        :key="'port-' + index"
        class="flex items-center gap-2 mb-2"
      >
        <el-input
          v-model="port.host"
          placeholder="Hôte (ex: 8080)"
          style="width: 40%"
        />
        <span class="text-gray-400">:</span>
        <el-input
          v-model="port.container"
          placeholder="Container (ex: 80)"
          style="width: 40%"
        />
        <el-button
          type="danger"
          :icon="Delete"
          circle
          size="small"
          @click="portMappings.splice(index, 1)"
        />
      </div>
      <el-button
        size="small"
        @click="portMappings.push({ host: '', container: '' })"
      >
        + Ajouter un port
      </el-button>

      <!-- Volumes -->
      <el-divider content-position="left">
        Volumes
      </el-divider>
      <div
        v-for="(vol, index) in volumeMappings"
        :key="'vol-' + index"
        class="flex items-center gap-2 mb-2"
      >
        <el-input
          v-model="vol.source"
          placeholder="Source (ex: /data)"
          style="width: 40%"
        />
        <span class="text-gray-400">:</span>
        <el-input
          v-model="vol.destination"
          placeholder="Destination (ex: /app/data)"
          style="width: 40%"
        />
        <el-button
          type="danger"
          :icon="Delete"
          circle
          size="small"
          @click="volumeMappings.splice(index, 1)"
        />
      </div>
      <el-button
        size="small"
        @click="volumeMappings.push({ source: '', destination: '' })"
      >
        + Ajouter un volume
      </el-button>

      <!-- Section avancée -->
      <el-divider content-position="left">
        Avancé
      </el-divider>
      <el-form-item label="Restart policy">
        <el-select
          v-model="form.restart_policy"
          placeholder="Sélectionner"
        >
          <el-option
            label="no"
            value="no"
          />
          <el-option
            label="always"
            value="always"
          />
          <el-option
            label="on-failure"
            value="on-failure"
          />
          <el-option
            label="unless-stopped"
            value="unless-stopped"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="Network mode">
        <el-input
          v-model="form.network_mode"
          placeholder="bridge"
        />
      </el-form-item>

      <el-form-item label="Privileged">
        <el-switch v-model="form.privileged" />
        <el-alert
          v-if="form.privileged"
          type="warning"
          :closable="false"
          show-icon
          class="mt-2"
        >
          Attention : le mode privileged donne un accès complet au système hôte.
          Utilisez cette option uniquement si vous savez ce que vous faites.
        </el-alert>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">
        Annuler
      </el-button>
      <el-button
        type="primary"
        :loading="creating"
        @click="handleSubmit"
      >
        Créer
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * ContainerCreateDialog — Formulaire de création manuelle de container Docker.
 *
 * STORY-019 : Création manuelle de containers Docker.
 * Appelle POST /docker/containers via containersApi.create().
 */
import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { containersApi } from '@/services/api'
import type { ContainerCreateRequest, ContainerDetail } from '@/types/api'

// ─── Props & Emits ────────────────────────────────────────────────────────────

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'created': [payload: ContainerDetail]
}>()

// ─── Form state ───────────────────────────────────────────────────────────────

const formRef = ref<FormInstance>()
const creating = ref(false)

const form = ref({
  name: '',
  image: '',
  restart_policy: 'no',
  network_mode: 'bridge',
  privileged: false,
})

const commandInput = ref('')

const envVars: Ref<{ key: string; value: string }[]> = ref([])
const portMappings: Ref<{ host: string; container: string }[]> = ref([])
const volumeMappings: Ref<{ source: string; destination: string }[]> = ref([])

// ─── Validation rules ─────────────────────────────────────────────────────────

const rules: FormRules = {
  name: [
    { required: true, message: 'Le nom est requis', trigger: 'blur' },
    {
      pattern: /^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/,
      message: 'Le nom doit commencer par un caractère alphanumérique et ne contenir que des lettres, chiffres, _, ., -',
      trigger: 'blur',
    },
  ],
  image: [
    { required: true, message: "L'image est requise", trigger: 'blur' },
  ],
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function buildRequest(): ContainerCreateRequest {
  const data: ContainerCreateRequest = {
    name: form.value.name,
    image: form.value.image,
  }

  // Command
  if (commandInput.value.trim()) {
    data.command = commandInput.value.split(',').map(s => s.trim()).filter(Boolean)
  }

  // Env vars — format KEY=VALUE
  const envEntries = envVars.value
    .filter(e => e.key.trim())
    .map(e => `${e.key}=${e.value}`)
  if (envEntries.length > 0) {
    data.env = envEntries
  }

  // Ports — format { "80/tcp": { "HostPort": "8080" } }
  const ports: Record<string, Record<string, string>> = {}
  for (const mapping of portMappings.value) {
    if (mapping.container.trim() && mapping.host.trim()) {
      const proto = mapping.container.includes('/') ? '' : '/tcp'
      ports[`${mapping.container}${proto}`] = { HostPort: mapping.host }
    }
  }
  if (Object.keys(ports).length > 0) {
    data.ports = ports
  }

  // Volumes — format { "/host/path": "/container/path" }
  const volumes: Record<string, string> = {}
  for (const vol of volumeMappings.value) {
    if (vol.source.trim() && vol.destination.trim()) {
      volumes[vol.source] = vol.destination
    }
  }
  if (Object.keys(volumes).length > 0) {
    data.volumes = volumes
  }

  // Advanced
  if (form.value.restart_policy && form.value.restart_policy !== 'no') {
    data.restart_policy = form.value.restart_policy
  }
  if (form.value.network_mode && form.value.network_mode !== 'bridge') {
    data.network_mode = form.value.network_mode
  }
  if (form.value.privileged) {
    data.privileged = true
  }

  return data
}

function resetForm(): void {
  form.value = {
    name: '',
    image: '',
    restart_policy: 'no',
    network_mode: 'bridge',
    privileged: false,
  }
  commandInput.value = ''
  envVars.value = []
  portMappings.value = []
  volumeMappings.value = []
  formRef.value?.resetFields()
}

// ─── Actions ──────────────────────────────────────────────────────────────────

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  creating.value = true
  try {
    const requestData = buildRequest()
    const response = await containersApi.create(requestData)
    emit('created', response.data)
    ElMessage.success(`Container "${form.value.name}" créé avec succès`)
    handleClose()
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la création du container'
    ElMessage.error(message)
  } finally {
    creating.value = false
  }
}

function handleClose(): void {
  resetForm()
  emit('update:modelValue', false)
}
</script>
