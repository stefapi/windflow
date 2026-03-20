<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? 'Modifier l\'Utilisateur' : 'Ajouter un Utilisateur'"
    width="500px"
    @update:model-value="$emit('update:visible', $event)"
  >
    <el-form
      :model="form"
      label-width="140px"
    >
      <el-form-item
        label="Nom d'utilisateur"
        required
      >
        <el-input
          v-model="form.username"
          :disabled="isEdit"
        />
      </el-form-item>
      <el-form-item
        label="Email"
        required
      >
        <el-input v-model="form.email" />
      </el-form-item>
      <el-form-item label="Nom complet">
        <el-input v-model="form.full_name" />
      </el-form-item>
      <el-form-item
        v-if="!isEdit"
        label="Mot de passe"
        required
      >
        <el-input
          v-model="form.password"
          type="password"
          show-password
        />
      </el-form-item>
      <el-form-item label="Administrateur">
        <el-switch v-model="form.is_superuser" />
      </el-form-item>
      <el-form-item label="Organisation">
        <el-select
          v-model="form.organization_id"
          placeholder="Sélectionner une organisation"
          clearable
          style="width: 100%"
        >
          <el-option
            v-for="org in organizations"
            :key="org.id"
            :label="org.name"
            :value="org.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="Actif">
        <el-switch v-model="form.is_active" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">
        Annuler
      </el-button>
      <el-button
        type="primary"
        @click="handleSave"
      >
        {{ isEdit ? 'Modifier' : 'Créer' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, watch, computed } from 'vue'
import type { User, Organization, UserCreate, UserUpdate } from '@/types/api'

interface Props {
  visible: boolean
  user?: User | null
  organizations: Organization[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'save': [data: UserCreate | UserUpdate, isEdit: boolean, editId?: string]
}>()

interface FormData {
  username: string
  email: string
  full_name: string
  password: string
  is_active: boolean
  is_superuser: boolean
  organization_id: string | null
}

const form = reactive<FormData>({
  username: '',
  email: '',
  full_name: '',
  password: '',
  is_active: true,
  is_superuser: false,
  organization_id: null,
})

const isEdit = computed(() => !!props.user)

// Reset form when dialog opens/closes or user changes
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      if (props.user) {
        form.username = props.user.username
        form.email = props.user.email
        form.full_name = props.user.full_name || ''
        form.is_active = props.user.is_active
        form.is_superuser = props.user.is_superuser
        form.organization_id = props.user.organization_id || null
        form.password = ''
      } else {
        form.username = ''
        form.email = ''
        form.full_name = ''
        form.password = ''
        form.is_active = true
        form.is_superuser = false
        form.organization_id = null
      }
    }
  },
  { immediate: true }
)

function handleSave() {
  if (isEdit.value && props.user) {
    const updateData: UserUpdate = {
      email: form.email,
      full_name: form.full_name || undefined,
      is_active: form.is_active,
      is_superuser: form.is_superuser,
      organization_id: form.organization_id || undefined,
    }
    emit('save', updateData, true, props.user.id)
  } else {
    const createData: UserCreate = {
      username: form.username,
      email: form.email,
      password: form.password,
      full_name: form.full_name || undefined,
      organization_id: form.organization_id || undefined,
    }
    emit('save', createData, false)
  }
}
</script>

<script lang="ts">
export default {
  name: 'UserDialog',
}
</script>
