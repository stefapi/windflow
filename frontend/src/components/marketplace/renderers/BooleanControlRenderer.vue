<template>
  <el-form-item
    v-if="control.visible"
    :label="computedLabel"
    :required="control.required"
    :error="control.errors"
    class="jsonforms-control"
  >
    <el-switch
      :model-value="control.data"
      @update:model-value="onChange"
      :disabled="!control.enabled"
      :size="size"
      :active-text="activeText"
      :inactive-text="inactiveText"
    />
    <div v-if="control.description" class="el-form-item__description">
      {{ control.description }}
    </div>
  </el-form-item>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { rendererProps, useJsonFormsControl } from '@jsonforms/vue'
import { rankWith, isBooleanControl } from '@jsonforms/core'

const props = defineProps(rendererProps())

const control = useJsonFormsControl(props)

const computedLabel = computed(() => {
  return control.value.label || props.schema?.title || props.uischema?.label
})

const size = computed(() => {
  return props.uischema?.options?.size || 'default'
})

const activeText = computed(() => {
  return props.uischema?.options?.activeText || props.schema?.const === true ? 'Oui' : undefined
})

const inactiveText = computed(() => {
  return props.uischema?.options?.inactiveText || props.schema?.const === false ? 'Non' : undefined
})

const onChange = (value: boolean) => {
  control.value.handleChange(control.value.path, value)
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'BooleanControlRenderer'
})

export const booleanControlRendererEntry = {
  renderer: defineComponent({
    name: 'BooleanControlRenderer'
  }),
  tester: rankWith(2, isBooleanControl)
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
