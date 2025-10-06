<template>
  <el-form-item
    v-if="control.visible"
    :label="computedLabel"
    :required="control.required"
    :error="control.errors"
    class="jsonforms-control"
  >
    <div class="password-control">
      <el-input
        :model-value="control.data"
        @update:model-value="onChange"
        type="password"
        :placeholder="placeholder"
        :disabled="!control.enabled"
        :clearable="true"
        :show-password="true"
        :size="size"
        class="password-input"
      />
      <el-button
        v-if="canGenerate"
        @click="generatePassword"
        :size="size"
        class="generate-btn ml-2"
      >
        <el-icon><Refresh /></el-icon>
        Générer
      </el-button>
    </div>
    <div v-if="control.description" class="el-form-item__description">
      {{ control.description }}
    </div>
    <div v-if="passwordStrength" class="password-strength">
      <div class="strength-bar">
        <div
          class="strength-fill"
          :class="`strength-${passwordStrength.level}`"
          :style="{ width: `${passwordStrength.score}%` }"
        />
      </div>
      <span class="strength-label">{{ passwordStrength.label }}</span>
    </div>
  </el-form-item>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { rendererProps, useJsonFormsControl } from '@jsonforms/vue'
import { rankWith, and, schemaMatches } from '@jsonforms/core'
import { generateSecurePassword } from '@/utils/passwordGenerator'

const props = defineProps(rendererProps())

const control = useJsonFormsControl(props)

const computedLabel = computed(() => {
  return control.value.label || props.schema?.title || props.uischema?.label
})

const placeholder = computed(() => {
  return props.uischema?.options?.placeholder || 'Entrez un mot de passe sécurisé'
})

const size = computed(() => {
  return props.uischema?.options?.size || 'default'
})

const canGenerate = computed(() => {
  return props.uischema?.options?.generate !== false
})

const passwordStrength = computed(() => {
  const value = control.value.data as string
  if (!value || value.length === 0) return null

  let score = 0

  // Longueur
  if (value.length >= 8) score += 20
  if (value.length >= 12) score += 20
  if (value.length >= 16) score += 10

  // Complexité
  if (/[a-z]/.test(value)) score += 10
  if (/[A-Z]/.test(value)) score += 10
  if (/[0-9]/.test(value)) score += 15
  if (/[^a-zA-Z0-9]/.test(value)) score += 15

  let level: string
  let label: string

  if (score < 30) {
    level = 'weak'
    label = 'Faible'
  } else if (score < 60) {
    level = 'medium'
    label = 'Moyen'
  } else if (score < 80) {
    level = 'good'
    label = 'Bon'
  } else {
    level = 'strong'
    label = 'Excellent'
  }

  return { score, level, label }
})

const generatePassword = () => {
  const minLength = props.schema?.minLength || 16
  const password = generateSecurePassword({
    length: Math.max(minLength, 16),
    uppercase: true,
    lowercase: true,
    numbers: true,
    symbols: true
  })

  control.value.handleChange(control.value.path, password)
}

const onChange = (value: string) => {
  control.value.handleChange(control.value.path, value)
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'PasswordControlRenderer'
})

// Tester pour format: password ou type avec password dans le nom
export const passwordControlRendererEntry = {
  renderer: defineComponent({
    name: 'PasswordControlRenderer'
  }),
  tester: rankWith(
    3,
    and(
      schemaMatches((schema) =>
        schema.format === 'password' ||
        schema.type === 'password' ||
        (typeof schema.title === 'string' && schema.title.toLowerCase().includes('password'))
      )
    )
  )
}
</script>

<style scoped>
.password-control {
  display: flex;
  align-items: center;
}

.password-input {
  flex: 1;
}

.generate-btn {
  flex-shrink: 0;
}

.el-form-item__description {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.4;
}

.password-strength {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.strength-bar {
  flex: 1;
  height: 4px;
  background: var(--el-fill-color-light);
  border-radius: 2px;
  overflow: hidden;
}

.strength-fill {
  height: 100%;
  transition: all 0.3s ease;
  border-radius: 2px;
}

.strength-weak {
  background: var(--el-color-danger);
}

.strength-medium {
  background: var(--el-color-warning);
}

.strength-good {
  background: var(--el-color-primary);
}

.strength-strong {
  background: var(--el-color-success);
}

.strength-label {
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}
</style>
