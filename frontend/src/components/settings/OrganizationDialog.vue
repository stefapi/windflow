<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? 'Modifier l\'Organisation' : 'Ajouter une Organisation'"
    width="500px"
    @update:model-value="$emit('update:visible', $event)"
  >
    <el-form
      :model="form"
      label-width="120px"
    >
      <el-form-item
        label="Nom"
        required
      >
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item label="Slug">
        <el-input
          v-model="form.slug"
          placeholder="Laisser vide pour générer automatiquement"
        >
          <template #prepend>
            <el-icon><Link /></el-icon>
          </template>
        </el-input>
        <div class="form-hint">
          Identifiant unique pour l'URL (ex: mon-organisation). Lettres minuscules, chiffres et tirets uniquement.
        </div>
      </el-form-item>
      <el-form-item label="Description">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
        />
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
import { reactive, watch } from 'vue'
import { Link } from '@element-plus/icons-vue'
import type { Organization, OrganizationCreate, OrganizationUpdate } from '@/types/api'

interface Props {
  visible: boolean
  organization?: Organization | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'save': [data: OrganizationCreate | OrganizationUpdate, isEdit: boolean, editId?: string]
}>()

interface FormData {
  name: string
  slug: string
  description: string
}

const form = reactive<FormData>({
  name: '',
  slug: '',
  description: '',
})

const isEdit = computed(() => !!props.organization)

// Reset form when dialog opens/closes or organization changes
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      if (props.organization) {
        form.name = props.organization.name
        form.slug = props.organization.slug || ''
        form.description = props.organization.description || ''
      } else {
        form.name = ''
        form.slug = ''
        form.description = ''
      }
    }
  },
  { immediate: true }
)

function handleSave() {
  if (isEdit.value && props.organization) {
    emit('save', form as OrganizationUpdate, true, props.organization.id)
  } else {
    emit('save', form as OrganizationCreate, false)
  }
}
</script>

<script lang="ts">
import { computed } from 'vue'
export default {
  name: 'OrganizationDialog',
}
</script>

<style scoped>
.form-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.4;
}
</style>
