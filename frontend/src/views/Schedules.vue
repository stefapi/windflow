<template>
  <div class="schedules">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Scheduled Tasks</span>
          <el-button
            type="primary"
            @click="openCreateDialog"
          >
            New Task
          </el-button>
        </div>
      </template>

      <el-table
        v-loading="schedulesStore.loading"
        :data="schedulesStore.tasks"
        stripe
      >
        <el-table-column
          prop="name"
          label="Name"
          min-width="150"
        />
        <el-table-column
          label="Type"
          width="160"
        >
          <template #default="{ row }">
            <el-tag size="small">
              {{ taskTypeLabel(row.task_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="Cron"
          width="150"
        >
          <template #default="{ row }">
            <code>{{ row.cron_expression }}</code>
          </template>
        </el-table-column>
        <el-table-column
          label="Status"
          width="100"
          align="center"
        >
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled"
              active-text=""
              inactive-text=""
              @change="handleToggle(row.id)"
            />
          </template>
        </el-table-column>
        <el-table-column
          label="Last Run"
          width="180"
        >
          <template #default="{ row }">
            <span v-if="row.last_run">{{ formatDate(row.last_run) }}</span>
            <span
              v-else
              class="text-muted"
            >Never</span>
          </template>
        </el-table-column>
        <el-table-column
          label="Last Status"
          width="120"
        >
          <template #default="{ row }">
            <el-tag
              v-if="row.last_status"
              :type="row.last_status === 'success' ? 'success' : 'danger'"
              size="small"
            >
              {{ row.last_status }}
            </el-tag>
            <span
              v-else
              class="text-muted"
            >—</span>
          </template>
        </el-table-column>
        <el-table-column
          label="Runs"
          width="80"
          align="center"
        >
          <template #default="{ row }">
            {{ row.run_count }}
          </template>
        </el-table-column>
        <el-table-column
          label="Actions"
          width="200"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button
              size="small"
              @click="openEditDialog(row)"
            >
              Edit
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="confirmDelete(row.id)"
            >
              Delete
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Tâches prédéfinies -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>Predefined Tasks</span>
      </template>
      <el-descriptions
        :column="1"
        border
        size="small"
      >
        <el-descriptions-item label="Cleanup Logs">
          Daily at 02:00 UTC — Removes deployment logs older than 30 days
          <el-tag
            size="small"
            type="info"
            class="ml-2"
          >
            0 2 * * *
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Health Check Targets">
          Every 5 minutes — Checks connectivity of all targets
          <el-tag
            size="small"
            type="info"
            class="ml-2"
          >
            */5 * * * *
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Retry Pending Deployments">
          Every 10 minutes — Retries stuck pending deployments
          <el-tag
            size="small"
            type="info"
            class="ml-2"
          >
            */10 * * * *
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- Dialog création/édition -->
    <el-dialog
      v-model="showDialog"
      :title="editingTask ? 'Edit Task' : 'Create Task'"
      width="600px"
      destroy-on-close
    >
      <el-form
        :model="form"
        label-width="140px"
      >
        <el-form-item
          label="Name"
          required
        >
          <el-input
            v-model="form.name"
            placeholder="My scheduled task"
          />
        </el-form-item>
        <el-form-item label="Description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
          />
        </el-form-item>
        <el-form-item
          v-if="!editingTask"
          label="Task Type"
          required
        >
          <el-select
            v-model="form.task_type"
            style="width: 100%"
          >
            <el-option
              label="Cleanup Logs"
              value="cleanup_logs"
            />
            <el-option
              label="Health Check"
              value="health_check"
            />
            <el-option
              label="Git Sync"
              value="git_sync"
            />
            <el-option
              label="Retry Deployments"
              value="retry_deployments"
            />
            <el-option
              label="Custom"
              value="custom"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          label="Cron Expression"
          required
        >
          <el-input
            v-model="form.cron_expression"
            placeholder="0 * * * *"
          />
          <div class="cron-help">
            Format: minute hour day month weekday (e.g. <code>0 2 * * *</code> = daily at 2am)
          </div>
        </el-form-item>
        <el-form-item label="Enabled">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">
          Cancel
        </el-button>
        <el-button
          type="primary"
          :loading="saving"
          @click="handleSave"
        >
          {{ editingTask ? 'Update' : 'Create' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useSchedulesStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { ScheduledTask, TaskType } from '@/types/api'

const schedulesStore = useSchedulesStore()
const authStore = useAuthStore()

const showDialog = ref(false)
const saving = ref(false)
const editingTask = ref<ScheduledTask | null>(null)

const form = reactive({
  name: '',
  description: '',
  task_type: 'custom' as TaskType,
  cron_expression: '0 * * * *',
  enabled: true,
})

const taskTypeLabels: Record<TaskType, string> = {
  cleanup_logs: 'Cleanup Logs',
  health_check: 'Health Check',
  git_sync: 'Git Sync',
  retry_deployments: 'Retry Deployments',
  custom: 'Custom',
}

function taskTypeLabel(type: TaskType): string {
  return taskTypeLabels[type] || type
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString()
}

function openCreateDialog(): void {
  editingTask.value = null
  Object.assign(form, {
    name: '',
    description: '',
    task_type: 'custom',
    cron_expression: '0 * * * *',
    enabled: true,
  })
  showDialog.value = true
}

function openEditDialog(task: ScheduledTask): void {
  editingTask.value = task
  Object.assign(form, {
    name: task.name,
    description: task.description || '',
    task_type: task.task_type,
    cron_expression: task.cron_expression,
    enabled: task.enabled,
  })
  showDialog.value = true
}

async function handleSave(): Promise<void> {
  saving.value = true
  try {
    if (editingTask.value) {
      await schedulesStore.updateTask(editingTask.value.id, {
        name: form.name,
        description: form.description,
        cron_expression: form.cron_expression,
        enabled: form.enabled,
      })
      ElMessage.success('Task updated')
    } else {
      await schedulesStore.createTask({
        name: form.name,
        description: form.description,
        task_type: form.task_type,
        cron_expression: form.cron_expression,
        enabled: form.enabled,
        organization_id: authStore.organizationId || '',
      })
      ElMessage.success('Task created')
    }
    showDialog.value = false
  } catch {
    ElMessage.error('Failed to save task')
  } finally {
    saving.value = false
  }
}

async function handleToggle(id: string): Promise<void> {
  try {
    await schedulesStore.toggleTask(id)
  } catch {
    ElMessage.error('Failed to toggle task')
  }
}

async function confirmDelete(id: string): Promise<void> {
  try {
    await ElMessageBox.confirm('Delete this scheduled task?', 'Confirm', { type: 'warning' })
    await schedulesStore.deleteTask(id)
    ElMessage.success('Task deleted')
  } catch {
    // cancelled
  }
}

onMounted(() => {
  const orgId = authStore.organizationId || undefined
  schedulesStore.fetchTasks(orgId)
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.text-muted {
  color: var(--el-text-color-placeholder);
}

.cron-help {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
