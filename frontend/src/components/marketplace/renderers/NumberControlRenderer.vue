<template>
  <el-form-item
    v-if="control.visible"
    :label="computedLabel"
    :required="control.required"
    :error="control.errors"
    class="jsonforms-control"
  >
    <el-input-number
      :model-value="control.data"
      @update:model-value="onChange"
      :placeholder="placeholder"
      :disabled="!control.enabled"
      :min="min"
      :max="max"
      :step="step"
      :precision="precision"
      :size="size"
      controls-position="right"
      class="w-full"
    />
    <div v-if="control.description" class="el-form-item__description">
      {{ control.description }}
    </div>
  </el-form-item>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { rendererProps, useJsonFormsControl } from '@jsonforms/vue'
import { rankWith, isNumberControl } from '@jsonforms/core'

const props = defineProps(rendererProps())

const control = useJsonFormsControl(props)

const computedLabel = computed(() => {
  return control.value.label || props.schema?.title || props.uischema?.label
})

const placeholder = computed(() => {
  return props.uischema?.options?.placeholder || `Entrez ${computedLabel.value.toLowerCase()}`
})

const size = computed(() => {
  return props.uischema?.options?.size || 'default'
})

const min = computed(() => {
  return props.schema?.minimum !== undefined ? props.schema.minimum : -Infinity
})

const max = computed(() => {
  return props.schema?.maximum !== undefined ? props.schema.maximum : Infinity
})

const step = computed(() => {
  return props.uischema?.options?.step || props.schema?.multipleOf || 1
})

const precision = computed(() => {
  const precisionOption = props.uischema?.options?.precision
  if (precisionOption !== undefined) return precisionOption

  // Pour les nombres à virgule, précision par défaut 2
  if (props.schema?.type === 'number') return 2
  return 0
})

const onChange = (value: number | null) => {
  control.value.handleChange(control.value.path, value)
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'NumberControlRenderer'
})

export const numberControlRendererEntry = {
  renderer: defineComponent({
    name: 'NumberControlRenderer'
  }),
  tester: rankWith(2, isNumberControl)
}
</script>

<style scoped>
.el-form-item__description {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.4;
}

:deep(.el-input-number) {
  width: 100%;
}
</style>
