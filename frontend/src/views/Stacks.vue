<template>
  <div class="stacks">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Stacks Management</span>
          <el-button type="primary" @click="showDialog = true">Create Stack</el-button>
        </div>
      </template>
      <el-table :data="stacksStore.stacks" v-loading="stacksStore.loading">
        <el-table-column prop="name" label="Name" />
        <el-table-column prop="description" label="Description" />
        <el-table-column label="Actions" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="viewStack(row)">View</el-button>
            <el-button size="small" type="danger" @click="deleteStack(row.id)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" title="Create Stack" width="600px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="Name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="Description">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>
        <el-form-item label="Compose Content">
          <el-input v-model="form.compose_content" type="textarea" :rows="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">Cancel</el-button>
        <el-button type="primary" @click="handleCreate">Create</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useStacksStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import type { StackCreate } from '@/types/api'

const stacksStore = useStacksStore()
const authStore = useAuthStore()
const showDialog = ref(false)

const form = reactive<StackCreate>({
  name: '',
  description: '',
  compose_content: '',
  organization_id: authStore.organizationId || '',
})

const handleCreate = async () => {
  try {
    await stacksStore.createStack({ ...form })
    ElMessage.success('Stack created successfully')
    showDialog.value = false
    Object.assign(form, { name: '', description: '', compose_content: '' })
  } catch (error) {
    ElMessage.error('Failed to create stack')
  }
}

const viewStack = (stack: any) => {
  ElMessage.info('Stack details: ' + stack.name)
}

const deleteStack = async (id: string) => {
  try {
    await stacksStore.deleteStack(id)
    ElMessage.success('Stack deleted successfully')
  } catch (error) {
    ElMessage.error('Failed to delete stack')
  }
}

onMounted(() => {
  stacksStore.fetchStacks(authStore.organizationId || undefined)
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
