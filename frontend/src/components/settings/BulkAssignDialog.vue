<template>
  <el-dialog
    :model-value="visible"
    title="Affecter à une organisation"
    width="500px"
    @update:model-value="$emit('update:visible', $event)"
  >
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="bulk-assign-alert"
    >
      <template #title>
        <strong>{{ userIds.length }}</strong> utilisateur{{ userIds.length > 1 ? 's' : '' }} seront affectés.
      </template>
    </el-alert>
    <el-form
      :model="form"
      label-width="140px"
      class="bulk-assign-form"
    >
      <el-form-item
        label="Organisation"
        required
      >
        <el-select
          v-model="form.organization_id"
          placeholder="Sélectionner une organisation"
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
    </el-form>
    <div class="bulk-assign-list">
      <p>Utilisateurs concernés :</p>
      <ul>
        <li
          v-for="(label, index) in displayedUserLabels"
          :key="index"
        >
          {{ label }}
        </li>
        <li
          v-if="userLabels.length > maxDisplayed"
          class="more-items"
        >
          ... et {{ userLabels.length - maxDisplayed }} autre{{ userLabels.length - maxDisplayed > 1 ? 's' : '' }}
        </li>
      </ul>
    </div>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">
        Annuler
      </el-button>
      <el-button
        type="primary"
        :loading="loading"
        :disabled="!form.organization_id"
        @click="handleConfirm"
      >
        Affecter {{ userIds.length }} utilisateur{{ userIds.length > 1 ? 's' : '' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, computed, watch } from 'vue'
import type { Organization } from '@/types/api'

interface Props {
  visible: boolean
  userIds: string[]
  userLabels: string[]
  organizations: Organization[]
  maxDisplayed?: number
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  maxDisplayed: 5,
  loading: false,
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'confirm': [organizationId: string]
}>()

const form = reactive({
  organization_id: '' as string,
})

const displayedUserLabels = computed(() => props.userLabels.slice(0, props.maxDisplayed))

// Reset form when dialog opens
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      form.organization_id = ''
    }
  }
)

function handleConfirm() {
  if (form.organization_id) {
    emit('confirm', form.organization_id)
  }
}
</script>

<script lang="ts">
export default {
  name: 'BulkAssignDialog',
}
</script>

<style scoped>
.bulk-assign-alert {
  margin-bottom: 16px;
}

.bulk-assign-form {
  margin-bottom: 16px;
}

.bulk-assign-list p {
  font-weight: 500;
  margin-bottom: 8px;
}

.bulk-assign-list ul {
  margin: 0;
  padding-left: 20px;
  max-height: 150px;
  overflow-y: auto;
}

.bulk-assign-list li {
  margin-bottom: 4px;
}

.bulk-assign-list .more-items {
  font-style: italic;
  color: var(--el-text-color-secondary);
}
</style>
