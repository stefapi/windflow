<template>
  <div class="login-page">
    <!-- Background gradient -->
    <div class="absolute inset-0 bg-gradient-to-br from-accent-light/30 via-transparent to-accent-light/20" />

    <!-- Background particles effect -->
    <div class="absolute inset-0 pointer-events-none overflow-hidden">
      <div class="login-particle w-300px h-300px -top-80px -left-60px animate-pulse animate-float-1" />
      <div class="login-particle w-200px h-200px -bottom-40px -right-40px animate-pulse animate-float-2" />
      <div class="login-particle w-150px h-150px top-50% right-20% animate-pulse animate-float-3" />
    </div>

    <!-- Login card -->
    <div class="login-card animate-fade-in">
      <!-- Logo section -->
      <div class="login-card-header">
        <WindFlowLogo
          size="large"
          :animate="true"
        />
        <h1 class="login-card-title">
          WindFlow
        </h1>
        <p class="login-card-subtitle">
          Container Deployment Platform
        </p>
      </div>

      <!-- Form -->
      <el-form
        ref="formRef"
        :model="loginForm"
        :rules="loginRules"
        class="login-card-form"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="Username"
            prefix-icon="User"
            size="large"
            :disabled="authStore.loading"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="Password"
            prefix-icon="Lock"
            size="large"
            show-password
            :disabled="authStore.loading"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item>
          <button
            type="submit"
            class="login-btn"
            :class="authStore.loading ? 'login-btn-loading' : 'login-btn-hover'"
            :disabled="authStore.loading"
          >
            <span v-if="!authStore.loading">Sign In</span>
            <span
              v-else
              class="flex items-center justify-center gap-2"
            >
              <span class="login-spinner" />
              Connecting...
            </span>
          </button>
        </el-form-item>
      </el-form>

      <!-- Footer -->
      <div class="login-card-footer">
        <span class="login-card-version">v1.0</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import type { FormRules } from 'element-plus'
import WindFlowLogo from '@/components/WindFlowLogo.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loginForm = reactive({
  username: '',
  password: '',
})

const loginRules: FormRules = {
  username: [
    { required: true, message: 'Username is required', trigger: 'blur' },
  ],
  password: [
    { required: true, message: 'Password is required', trigger: 'blur' },
  ],
}

const handleLogin = async () => {
  try {
    await authStore.login(loginForm)
    ElMessage.success('Login successful')

    // Wait for Vue's reactivity system to update before navigation
    await nextTick()

    // Navigate to the redirect path or dashboard
    const redirect = (route.query['redirect'] as string) || '/'
    await router.replace(redirect)
  } catch {
    ElMessage.error('Login failed. Please check your credentials.')
  }
}
</script>

<style scoped>
/* Custom animations not supported by UnoCSS utilities */
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(24px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.animate-fade-in {
  animation: fade-in 0.6s ease-out;
}

/* Floating animations for particles */
@keyframes float-1 {
  0%, 100% {
    transform: translate(0, 0);
  }
  25% {
    transform: translate(30px, 20px);
  }
  50% {
    transform: translate(20px, 40px);
  }
  75% {
    transform: translate(-10px, 25px);
  }
}

@keyframes float-2 {
  0%, 100% {
    transform: translate(0, 0);
  }
  25% {
    transform: translate(-25px, -15px);
  }
  50% {
    transform: translate(-40px, 10px);
  }
  75% {
    transform: translate(-15px, 30px);
  }
}

@keyframes float-3 {
  0%, 100% {
    transform: translate(0, 0);
  }
  25% {
    transform: translate(15px, -30px);
  }
  50% {
    transform: translate(-20px, -20px);
  }
  75% {
    transform: translate(25px, 10px);
  }
}

.animate-float-1 {
  animation: float-1 16s ease-in-out infinite;
}

.animate-float-2 {
  animation: float-2 14s ease-in-out infinite;
  animation-delay: 1s;
}

.animate-float-3 {
  animation: float-3 18s ease-in-out infinite;
  animation-delay: 2s;
}

/* Login form Element Plus overrides for theme support */
.login-card-form :deep(.el-input__wrapper) {
  background-color: var(--color-bg-input);
  border: 1px solid var(--color-border-light);
  border-radius: 10px !important;
  box-shadow: none !important;
  transition: all 0.25s ease;
  overflow: hidden;
}

.login-card-form :deep(.el-input__wrapper:hover) {
  border-color: var(--color-border);
  box-shadow: none !important;
}

.login-card-form :deep(.el-input__wrapper.is-focus) {
  border-color: var(--color-border-focus);
  box-shadow: 0 0 0 3px var(--color-accent-light) !important;
}

.login-card-form :deep(.el-input__inner) {
  color: var(--color-text-primary);
  font-size: 14px;
  border-radius: 10px !important;
  background-color: transparent !important;
}

.login-card-form :deep(.el-input__inner::placeholder) {
  color: var(--color-text-placeholder);
}

/* Handle browser autofill styles */
.login-card-form :deep(.el-input__inner:-webkit-autofill),
.login-card-form :deep(.el-input__inner:-webkit-autofill:hover),
.login-card-form :deep(.el-input__inner:-webkit-autofill:focus),
.login-card-form :deep(.el-input__inner:-webkit-autofill:active) {
  -webkit-box-shadow: 0 0 0 30px var(--color-bg-input) inset !important;
  -webkit-text-fill-color: var(--color-text-primary) !important;
  border-radius: 10px !important;
  transition: background-color 5000s ease-in-out 0s;
}

.login-card-form :deep(.el-input__prefix .el-icon) {
  color: var(--color-text-secondary);
}

.login-card-form :deep(.el-input__suffix .el-icon) {
  color: var(--color-text-secondary);
}

.login-card-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.login-card-form :deep(.el-form-item__error) {
  color: var(--color-error);
  font-size: 12px;
}

/* Responsive adjustments */
@media (max-width: 767px) {
  .login-page {
    padding: 16px;
  }

  .login-card {
    padding: 36px 24px 28px;
    border-radius: 12px;
    max-width: 100%;
  }

  .login-card-title {
    font-size: 24px;
  }
}

@media (max-width: 380px) {
  .login-card {
    padding: 28px 20px 24px;
  }
}
</style>
