<template>
  <div class="splash-screen">
    <div class="splash-content">
      <div class="logo">
        <svg
          class="windflow-icon"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M3 10C3 10 5.5 8 9 8C12.5 8 15 10 15 10M9 16C9 16 11.5 14 15 14C18.5 14 21 16 21 16"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          />
          <circle cx="9" cy="10" r="1.5" fill="currentColor" />
          <circle cx="15" cy="16" r="1.5" fill="currentColor" />
        </svg>
      </div>
      <h1 class="title">WindFlow</h1>
      <div class="loading-container">
        <div class="spinner"></div>
        <p class="loading-text">{{ message }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { defineProps, withDefaults } from 'vue'

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
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  z-index: 9999;
}

.splash-content {
  text-align: center;
  color: white;
}

.logo {
  margin-bottom: 1.5rem;
  display: flex;
  justify-content: center;
}

.windflow-icon {
  width: 80px;
  height: 80px;
  color: white;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}

.title {
  font-size: 2.5rem;
  font-weight: 700;
  margin: 0 0 2rem 0;
  letter-spacing: 0.05em;
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
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
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
  opacity: 0.9;
  margin: 0;
}
</style>
