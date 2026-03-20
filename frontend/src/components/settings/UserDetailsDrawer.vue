<template>
  <el-drawer
    :model-value="visible"
    title="Détails de l'utilisateur"
    direction="rtl"
    size="400px"
    @update:model-value="$emit('update:visible', $event)"
  >
    <el-descriptions
      :column="1"
      border
    >
      <el-descriptions-item label="Nom d'utilisateur">
        {{ user?.username }}
      </el-descriptions-item>
      <el-descriptions-item label="Email">
        {{ user?.email }}
      </el-descriptions-item>
      <el-descriptions-item label="Nom complet">
        {{ user?.full_name || '—' }}
      </el-descriptions-item>
      <el-descriptions-item label="Statut">
        <el-tag
          :type="user?.is_active ? 'success' : 'danger'"
          size="small"
        >
          {{ user?.is_active ? 'Actif' : 'Inactif' }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="Administrateur">
        <el-tag
          :type="user?.is_superuser ? 'warning' : 'info'"
          size="small"
        >
          {{ user?.is_superuser ? 'Oui' : 'Non' }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="Organisation">
        {{ organizationName }}
      </el-descriptions-item>
      <el-descriptions-item label="Date de création">
        {{ formatDateTime(user?.created_at) }}
      </el-descriptions-item>
      <el-descriptions-item label="Dernière modification">
        {{ formatDateTime(user?.updated_at) }}
      </el-descriptions-item>
      <el-descriptions-item label="Dernière connexion">
        {{ user?.last_login ? formatDateTime(user?.last_login) : 'Jamais' }}
      </el-descriptions-item>
    </el-descriptions>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">
        Fermer
      </el-button>
      <el-button
        v-if="user"
        type="primary"
        @click="handleEdit"
      >
        Modifier
      </el-button>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { User, Organization } from '@/types/api'

interface Props {
  visible: boolean
  user?: User | null
  organizations: Organization[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'edit': [user: User]
}>()

const organizationName = computed(() => {
  if (!props.user?.organization_id) return '—'
  const org = props.organizations.find(o => o.id === props.user?.organization_id)
  return org?.name || props.user.organization_id
})

function formatDateTime(dateStr: string | undefined | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function handleEdit() {
  if (props.user) {
    emit('edit', props.user)
    emit('update:visible', false)
  }
}
</script>

<script lang="ts">
export default {
  name: 'UserDetailsDrawer',
}
</script>
