<template>
  <el-dialog
    :model-value="visible"
    title="Changer le mot de passe"
    width="450px"
    @update:model-value="$emit('update:visible', $event)"
  >
    <el-form
      :model="form"
      label-width="180px"
      @submit.prevent="handleSave"
    >
      <el-form-item label="Utilisateur">
        <el-input
          :value="user?.username"
          disabled
        />
      </el-form-item>
      <el-form-item
        label="Nouveau mot de passe"
        required
      >
        <el-input
          v-model="form.password"
          type="password"
          show-password
          placeholder="Minimum 8 caractères"
        />
      </el-form-item>
      <el-form-item
        label="Confirmer le mot de passe"
        required
      >
        <el-input
          v-model="form.confirmPassword"
          type="password"
          show-password
          placeholder="Confirmer le mot de passe"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">
        Annuler
      </el-button>
      <el-button
        type="primary"
        :loading="loading"
        @click="handleSave"
      >
        Enregistrer
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { User } from '@/types/api'

interface Props {
  visible: boolean
  user?: User | null
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'save': [password: string]
}>()

interface FormData {
  password: string
  confirmPassword: string
}

const form = reactive<FormData>({
  password: '',
  confirmPassword: '',
})

// Reset form when dialog opens
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      form.password = ''
      form.confirmPassword = ''
    }
  }
)

function handleSave() {
  if (!form.password || form.password.length < 8) {
    ElMessage.error('Le mot de passe doit contenir au moins 8 caractères')
    return
  }

  if (form.password !== form.confirmPassword) {
    ElMessage.error('Les mots de passe ne correspondent pas')
    return
  }

  emit('save', form.password)
}
</script>

<script lang="ts">
export default {
  name: 'PasswordDialog',
}
</script>
