<template>
  <el-form-item
    v-if="control.visible"
    :label="computedLabel"
    :required="control.required"
    :error="control.errors"
    class="jsonforms-control"
  >
    <el-select
      :model-value="control.data"
      @update:model-value="onChange"
      :placeholder="placeholder"
      :disabled="!control.enabled"
      :clearable="clearable"
      :size="size"
      class="w-full"
    >
      <el-option
        v-for="option in options"
        :key="option.value"
        :label="option.label"
        :value="option.value"
      />
    </el-select>
    <div v-if="control.description" class="el-form-item__description">
      {{ control.description }}
    </div>
  </el-form-item>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { rendererProps, useJsonFormsControl } from '@jsonforms/vue'
import { rankWith, isEnumControl } from '@jsonforms/core'

const props = defineProps(rendererProps())

const control = useJsonFormsControl(props)

const computedLabel = computed(() => {
  return control.value.label || props.schema?.title || props.uischema?.label
})

const placeholder = computed(() => {
  return props.uischema?.options?.placeholder || 'Sélectionnez une option'
})

const size = computed(() => {
  return props.uischema?.options?.size || 'default'
})

const clearable = computed(() => {
  return props.uischema?.options?.clearable !== false && !control.value.required
})

const options = computed(() => {
  const enumValues = props.schema?.enum || []
  const enumLabels = props.schema?.enumNames || props.uischema?.options?.enumLabels || []

  return enumValues.map((value: any, index: number) => ({
    value,
    label: enumLabels[index] || String(value)
  }))
})

const onChange = (value: any) => {
  control.value.handleChange(control.value.path, value)
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'EnumControlRenderer'
})

export const enumControlRendererEntry = {
  renderer: defineComponent({
    name: 'EnumControlRenderer'
  }),
  tester: rankWith(2, isEnumControl)
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
