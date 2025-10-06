<template>
  <el-form-item
    v-if="control.visible"
    :label="computedLabel"
    :required="control.required"
    :error="control.errors"
    class="jsonforms-control"
  >
    <el-input
      :model-value="control.data"
      @update:model-value="onChange"
      :placeholder="placeholder"
      :disabled="!control.enabled"
      :clearable="true"
      :size="size"
    />
    <div v-if="control.description" class="el-form-item__description">
      {{ control.description }}
    </div>
  </el-form-item>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { rendererProps, useJsonFormsControl } from '@jsonforms/vue'
import { rankWith, isStringControl } from '@jsonforms/core'

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

const onChange = (value: string) => {
  control.value.handleChange(control.value.path, value)
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'StringControlRenderer'
})

// Tester pour déterminer quand utiliser ce renderer
export const stringControlRendererEntry = {
  renderer: defineComponent({
    name: 'StringControlRenderer'
  }),
  tester: rankWith(2, isStringControl)
}
</script>

<style scoped>
.el-form-item__description {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.4;
}
</style>
