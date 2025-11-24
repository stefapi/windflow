<template>
  <el-form-item
    :label="field.label"
    :required="field.required"
    :prop="field.key"
    :rules="field.validationRules"
  >
    <!-- String avec enum → Select dropdown -->
    <el-select
      v-if="field.enum && field.type === 'string'"
      v-model="localValue"
      :placeholder="`Sélectionner ${field.label}`"
      style="width: 100%"
      clearable
    >
      <el-option
        v-for="option in field.enum"
        :key="option"
        :label="option"
        :value="option"
      />
    </el-select>

    <!-- Number avec enum → Select dropdown -->
    <el-select
      v-else-if="field.enum && (field.type === 'number' || field.type === 'integer')"
      v-model="localValue"
      :placeholder="`Sélectionner ${field.label}`"
      style="width: 100%"
      clearable
    >
      <el-option
        v-for="option in field.enum"
        :key="option"
        :label="String(option)"
        :value="option"
      />
    </el-select>

    <!-- Password → Input type password avec bouton show/hide -->
    <el-input
      v-else-if="field.type === 'password'"
      v-model="localValue"
      type="password"
      :placeholder="`Entrer ${field.label}`"
      show-password
      clearable
    />

    <!-- Number → Input number avec min/max -->
    <el-input-number
      v-else-if="field.type === 'number' || field.type === 'integer'"
      v-model="localValue"
      :min="field.min"
      :max="field.max"
      :precision="isIntegerField ? 0 : 2"
      :placeholder="`Entrer ${field.label}`"
      style="width: 100%"
      controls-position="right"
    />

    <!-- Boolean → Switch -->
    <el-switch
      v-else-if="field.type === 'boolean'"
      v-model="localValue"
      :active-text="field.label"
    />

    <!-- String par défaut → Input text -->
    <el-input
      v-else
      v-model="localValue"
      :placeholder="`Entrer ${field.label}`"
      clearable
    />

    <!-- Description (aide contextuelle) -->
    <template v-if="field.description" #extra>
      <div class="field-description">
        <el-icon class="description-icon"><InfoFilled /></el-icon>
        <span>{{ field.description }}</span>
      </div>
    </template>
  </el-form-item>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import type { FormField } from '@/composables/useDynamicForm'

interface Props {
  field: FormField
  modelValue: any
}

interface Emits {
  (e: 'update:modelValue', value: any): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Détecte si un champ number doit être affiché comme entier
const isIntegerField = computed(() => {
  if (props.field.type !== 'number') return false

  // Si la valeur par défaut est un entier
  const defaultIsInteger = Number.isInteger(props.field.default)

  // Si min et max sont des entiers (ou undefined)
  const minIsInteger = props.field.min === undefined || Number.isInteger(props.field.min)
  const maxIsInteger = props.field.max === undefined || Number.isInteger(props.field.max)

  // Considérer comme entier si toutes les valeurs sont entières
  return defaultIsInteger && minIsInteger && maxIsInteger
})

// Valeur locale avec v-model bidirectionnel
const localValue = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})
</script>

<style scoped>
.field-description {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #909399;
  font-size: 13px;
  margin-top: 4px;
}

.description-icon {
  font-size: 14px;
  flex-shrink: 0;
}

/* Style pour le switch avec label */
:deep(.el-switch__label) {
  margin-left: 8px;
}
</style>
