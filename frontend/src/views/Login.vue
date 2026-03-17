<template>
  <div class="login-page">
    <!-- Background particles effect -->
    <div class="login-page__bg">
      <div class="login-page__particle login-page__particle--1" />
      <div class="login-page__particle login-page__particle--2" />
      <div class="login-page__particle login-page__particle--3" />
    </div>

    <!-- Login card -->
    <div class="login-card">
      <!-- Logo section -->
      <div class="login-card__header">
        <WindFlowLogo
          size="large"
          :animate="true"
        />
        <h1 class="login-card__title">
          WindFlow
        </h1>
        <p class="login-card__subtitle">
          Container Deployment Platform
        </p>
      </div>

      <!-- Form -->
      <el-form
        ref="formRef"
        :model="loginForm"
        :rules="loginRules"
        class="login-card__form"
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
            class="login-card__btn"
            :class="{ 'login-card__btn--loading': authStore.loading }"
            :disabled="authStore.loading"
          >
            <span v-if="!authStore.loading">Sign In</span>
            <span
              v-else
              class="login-card__btn-loading"
            >
              <span class="login-card__spinner" />
              Connecting...
            </span>
          </button>
        </el-form-item>
      </el-form>

      <!-- Footer -->
      <div class="login-card__footer">
        <span class="login-card__version">v1.0</span>
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
/* ============================================
   Login Page — Dark theme aligned with app
   ============================================ */
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #0c0e14;
  background-image: radial-gradient(ellipse at 30% 20%, rgba(79, 143, 247, 0.08) 0%, transparent 50%),
                    radial-gradient(ellipse at 70% 80%, rgba(56, 189, 248, 0.05) 0%, transparent 50%);
  position: relative;
  overflow: hidden;
}

/* ---- Background particles ---- */
.login-page__bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.login-page__particle {
  position: absolute;
  border-radius: 50%;
  background: rgba(79, 143, 247, 0.15);
  filter: blur(40px);
}

.login-page__particle--1 {
  width: 300px;
  height: 300px;
  top: -80px;
  left: -60px;
  animation: particle-float 12s ease-in-out infinite;
}

.login-page__particle--2 {
  width: 200px;
  height: 200px;
  bottom: -40px;
  right: -40px;
  background: rgba(56, 189, 248, 0.1);
  animation: particle-float 16s ease-in-out infinite reverse;
}

.login-page__particle--3 {
  width: 150px;
  height: 150px;
  top: 50%;
  right: 20%;
  background: rgba(96, 165, 250, 0.08);
  animation: particle-float 10s ease-in-out infinite 2s;
}

@keyframes particle-float {
  0%, 100% { transform: translate(0, 0); }
  25% { transform: translate(20px, -30px); }
  50% { transform: translate(-10px, 20px); }
  75% { transform: translate(15px, 10px); }
}

/* ---- Login Card ---- */
.login-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: 48px 40px 36px;
  background-color: rgba(21, 24, 33, 0.85);
  border: 1px solid #252838;
  border-radius: 16px;
  backdrop-filter: blur(12px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 80px rgba(79, 143, 247, 0.06);
  animation: card-enter 0.6s ease-out;
}

@keyframes card-enter {
  from {
    opacity: 0;
    transform: translateY(24px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* ---- Header / Logo section ---- */
.login-card__header {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 36px;
}

.login-card__title {
  margin: 16px 0 4px;
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.04em;
}

.login-card__subtitle {
  margin: 0;
  font-size: 13px;
  color: #7c8098;
  letter-spacing: 0.02em;
}

/* ---- Form ---- */
.login-card__form {
  width: 100%;
}

/* Override Element Plus input styles for dark theme */
.login-card__form :deep(.el-input__wrapper) {
  background-color: #1c1f2b;
  border: 1px solid #252838;
  border-radius: 10px !important;
  box-shadow: none !important;
  transition: all 0.25s ease;
  overflow: hidden;
}

.login-card__form :deep(.el-input__wrapper:hover) {
  border-color: #3a3f54;
  box-shadow: none !important;
}

.login-card__form :deep(.el-input__wrapper.is-focus) {
  border-color: #4f8ff7;
  box-shadow: 0 0 0 3px rgba(79, 143, 247, 0.15) !important;
}

.login-card__form :deep(.el-input__inner) {
  color: #e2e5f0;
  font-size: 14px;
  border-radius: 10px !important;
  background-color: transparent !important;
}

.login-card__form :deep(.el-input__inner::placeholder) {
  color: #5a5f78;
}

/* Handle browser autofill styles */
.login-card__form :deep(.el-input__inner:-webkit-autofill),
.login-card__form :deep(.el-input__inner:-webkit-autofill:hover),
.login-card__form :deep(.el-input__inner:-webkit-autofill:focus),
.login-card__form :deep(.el-input__inner:-webkit-autofill:active) {
  -webkit-box-shadow: 0 0 0 30px #1c1f2b inset !important;
  -webkit-text-fill-color: #e2e5f0 !important;
  border-radius: 10px !important;
  transition: background-color 5000s ease-in-out 0s;
}

.login-card__form :deep(.el-input__prefix .el-icon) {
  color: #7c8098;
}

.login-card__form :deep(.el-input__suffix .el-icon) {
  color: #7c8098;
}

.login-card__form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.login-card__form :deep(.el-form-item__error) {
  color: #f56c6c;
  font-size: 12px;
}

/* ---- Submit Button ---- */
.login-card__btn {
  width: 100%;
  padding: 14px 24px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #4f8ff7 0%, #3b82f6 50%, #2563eb 100%);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.03em;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.login-card__btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, transparent 50%);
  opacity: 0;
  transition: opacity 0.3s;
}

.login-card__btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 20px rgba(79, 143, 247, 0.4);
}

.login-card__btn:hover:not(:disabled)::before {
  opacity: 1;
}

.login-card__btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(79, 143, 247, 0.3);
}

.login-card__btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.login-card__btn--loading {
  background: linear-gradient(135deg, #3b73d4 0%, #2d6bc7 100%);
}

.login-card__btn-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.login-card__spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ---- Footer ---- */
.login-card__footer {
  display: flex;
  justify-content: center;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #252838;
}

.login-card__version {
  font-size: 11px;
  color: #5a5f78;
  letter-spacing: 0.02em;
}

/* ---- Responsive ---- */
@media (max-width: 767px) {
  .login-page {
    padding: 16px;
  }

  .login-card {
    padding: 36px 24px 28px;
    border-radius: 12px;
    max-width: 100%;
  }

  .login-card__title {
    font-size: 24px;
  }

  .login-card__particle--1,
  .login-card__particle--3 {
    display: none;
  }
}

@media (max-width: 380px) {
  .login-card {
    padding: 28px 20px 24px;
  }
}
</style>
