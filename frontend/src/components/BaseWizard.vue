<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="900px"
    :close-on-click-modal="closeOnClickModal"
    :close-on-press-escape="!loading"
    destroy-on-close
    @close="handleClose"
  >
    <!-- Steps indicator -->
    <el-steps
      :active="currentStep"
      finish-status="success"
      align-center
      class="mb-6"
    >
      <el-step
        v-for="(step, index) in steps"
        :key="index"
        :title="step.title"
        :description="step.description"
      />
    </el-steps>

    <!-- Content area -->
    <div
      v-loading="loading"
      class="min-h-200px"
    >
      <!-- Error alert -->
      <el-alert
        v-if="error"
        :title="error"
        type="error"
        show-icon
        closable
        class="mb-4"
        @close="emit('update:error', '')"
      />

      <!-- Step content via dynamic slot -->
      <div class="px-2">
        <slot :name="`step-${currentStep}`" />
      </div>
    </div>

    <!-- Footer -->
    <template #footer>
      <slot name="footer">
        <div class="flex justify-end gap-2">
          <el-button
            v-if="currentStep > 0 && !completed"
            @click="handlePrev"
          >
            Précédent
          </el-button>
          <el-button @click="handleClose">
            {{ completed ? 'Fermer' : 'Annuler' }}
          </el-button>
          <el-button
            v-if="currentStep < steps.length - 1"
            type="primary"
            :disabled="nextDisabled"
            @click="handleNext"
          >
            Suivant
          </el-button>
          <el-button
            v-if="currentStep === steps.length - 1 && !completed"
            type="success"
            :disabled="confirmDisabled"
            :loading="confirmLoading"
            @click="emit('confirm')"
          >
            {{ confirmLabel }}
          </el-button>
        </div>
      </slot>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * BaseWizard — Generic wizard engine
 *
 * Provides a shared dialog with step navigation, loading, error handling,
 * and a consistent footer. Used by TargetWizard and AdoptionWizard.
 *
 * @slot step-{n}  — Content for step index n
 * @slot footer    — Override the entire footer if needed
 */

import { ref, computed, watch } from 'vue'

export interface WizardStep {
  title: string
  description?: string
}

const props = withDefaults(defineProps<{
  /** v-model for dialog visibility */
  modelValue: boolean
  /** Dialog title */
  title: string
  /** Step definitions */
  steps: WizardStep[]
  /** Show loading overlay */
  loading?: boolean
  /** Error message (two-way bindable) */
  error?: string
  /** Label for the final confirm button */
  confirmLabel?: string
  /** Disable the confirm button */
  confirmDisabled?: boolean
  /** Show loading spinner on confirm button */
  confirmLoading?: boolean
  /** Allow closing by clicking modal backdrop */
  closeOnClickModal?: boolean
  /** Wizard completed — hides confirm, changes cancel to "Fermer" */
  completed?: boolean
  /** Disable the "Suivant" button */
  nextDisabled?: boolean
  /** Async validation before advancing to next step */
  validateNext?: () => Promise<boolean>
}>(), {
  loading: false,
  error: '',
  confirmLabel: 'Confirmer',
  confirmDisabled: false,
  confirmLoading: false,
  closeOnClickModal: false,
  completed: false,
  nextDisabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'update:error': [value: string]
  'next': []
  'prev': []
  'confirm': []
  'close': []
}>()

// ─── Visibility ───────────────────────────────────────────────

const visible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

// ─── Step management ──────────────────────────────────────────

const currentStep = ref(0)

/** Advance to the next step (called after validation passes) */
function advance(): void {
  if (currentStep.value < props.steps.length - 1) {
    currentStep.value++
  }
}

/** Reset to first step */
function reset(): void {
  currentStep.value = 0
}

async function handleNext(): Promise<void> {
  if (props.validateNext) {
    const ok = await props.validateNext()
    if (!ok) return
  }
  advance()
  emit('next')
}

function handlePrev(): void {
  if (currentStep.value > 0) {
    currentStep.value--
    emit('prev')
  }
}

function handleClose(): void {
  visible.value = false
  emit('close')
}

// Reset step when dialog opens
watch(() => props.modelValue, (val) => {
  if (val) {
    currentStep.value = 0
  }
})

// Expose for parent access
defineExpose({ currentStep, advance, reset })
</script>
