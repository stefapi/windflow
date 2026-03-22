<template>
  <div class="splash-screen">
    <div class="splash-content">
      <WindFlowLogo
        size="large"
        :animate="true"
      />
      <h1 class="title">
        WindFlow
      </h1>
      <div class="loading-container">
        <div class="spinner" />
        <p class="loading-text">
          {{ message }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { withDefaults, defineProps } from 'vue'
import WindFlowLogo from '@/components/WindFlowLogo.vue'

interface Props {
  message?: string
}

withDefaults(defineProps<Props>(), {
  message: 'Initialisation...'
})
</script>

<style scoped>
.splash-screen {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--color-bg-primary);
  background-image: radial-gradient(ellipse at 50% 40%, var(--color-accent-light) 0%, transparent 60%);
  z-index: 9999;
}

.splash-content {
  text-align: center;
  color: var(--color-text-primary);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.title {
  font-size: 2.5rem;
  font-weight: 700;
  margin: 16px 0 2rem;
  letter-spacing: 0.05em;
  color: var(--color-text-primary);
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--color-accent-light);
  border-top-color: var(--color-border-focus);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-text {
  font-size: 0.95rem;
  opacity: 0.7;
  margin: 0;
  color: var(--color-text-secondary);
}
</style>
