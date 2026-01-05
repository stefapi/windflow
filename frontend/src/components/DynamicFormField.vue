<template>
  <!-- Header de groupe -->
  <div v-if="field.isGroupHeader" class="group-header">
    <h4 class="group-title">{{ field.label }}</h4>
    <p v-if="field.description" class="group-description">{{ field.description }}</p>
  </div>

  <!-- Champ de formulaire normal -->
  <el-form-item
    v-else
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
        :label="getOptionLabel(option)"
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
        :label="getOptionLabel(option)"
        :value="option"
      />
    </el-select>

    <!-- Password → Input type password avec bouton show/hide -->
    <div v-else-if="field.type === 'password'" class="input-with-regenerate">
      <el-input
        v-model="localValue"
        type="password"
        :placeholder="`Entrer ${field.label}`"
        show-password
        clearable
      />
      <el-tooltip
        v-if="field.has_macro"
        content="Régénérer une nouvelle valeur"
        placement="top"
      >
        <el-button
          class="regenerate-button"
          :icon="Refresh"
          @click="emit('regenerate')"
          circle
        />
      </el-tooltip>
    </div>

    <!-- Number → Input number avec min/max -->
    <div v-else-if="field.type === 'number' || field.type === 'integer'" class="input-with-regenerate">
      <el-input-number
        v-model="localValue"
        :min="field.min"
        :max="field.max"
        :precision="isIntegerField ? 0 : 2"
        :placeholder="`Entrer ${field.label}`"
        style="width: 100%"
        controls-position="right"
      />
      <el-tooltip
        v-if="field.has_macro"
        content="Régénérer une nouvelle valeur"
        placement="top"
      >
        <el-button
          class="regenerate-button"
          :icon="Refresh"
          @click="emit('regenerate')"
          circle
        />
      </el-tooltip>
    </div>

    <!-- Boolean → Switch -->
    <el-switch
      v-else-if="field.type === 'boolean'"
      v-model="localValue"
      :active-text="field.label"
    />

    <!-- String par défaut → Input text -->
    <div v-else class="input-with-regenerate">
      <el-input
        v-model="localValue"
        :placeholder="`Entrer ${field.label}`"
        clearable
      />
      <el-tooltip
        v-if="field.has_macro"
        content="Régénérer une nouvelle valeur"
        placement="top"
      >
        <el-button
          class="regenerate-button"
          :icon="Refresh"
          @click="emit('regenerate')"
          circle
        />
      </el-tooltip>
    </div>

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
import { InfoFilled, Refresh } from '@element-plus/icons-vue'
import type { FormField } from '@/composables/useDynamicForm'

interface Props {
  field: FormField
  modelValue: any
}

interface Emits {
  (e: 'update:modelValue', value: any): void
  (e: 'regenerate'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Détecte si un champ number doit être affiché comme entier
const isIntegerField = computed(() => {
  // Si le type est explicitement integer, pas de décimales
  if (props.field.type === 'integer') return true

  // Heuristique: certains stacks peuvent déclarer `number` alors que la valeur
  // attendue est un entier (defaults/min/max entiers).
  if (props.field.type !== 'number') return false

  const defaultIsInteger = Number.isInteger(props.field.default)
  const minIsInteger = props.field.min === undefined || Number.isInteger(props.field.min)
  const maxIsInteger = props.field.max === undefined || Number.isInteger(props.field.max)

  return defaultIsInteger && minIsInteger && maxIsInteger
})

// Valeur locale avec v-model bidirectionnel
const localValue = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

/**
 * Retourne le libellé à afficher pour une option d'enum.
 * Si enum_labels est défini et contient la clé, retourne le libellé.
 * Sinon, retourne la valeur convertie en string.
 */
const getOptionLabel = (option: any): string => {
  const optionStr = String(option)
  if (props.field.enum_labels && props.field.enum_labels[optionStr]) {
    return props.field.enum_labels[optionStr]
  }
  return optionStr
}
</script>

<style scoped>
/* Header de groupe */
.group-header {
  margin: 20px 0 12px 0;
  padding: 12px 16px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-left: 4px solid #409eff;
  border-radius: 4px;
}

.group-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.group-description {
  margin: 6px 0 0 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

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

/* Container pour input avec bouton de régénération */
.input-with-regenerate {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.input-with-regenerate > :first-child {
  flex: 1;
}

.regenerate-button {
  flex-shrink: 0;
}
</style>
