<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <h2>WindFlow Login</h2>
      </template>
      <el-form :model="loginForm" @submit.prevent="handleLogin">
        <el-form-item label="Username">
          <el-input v-model="loginForm.username" placeholder="Enter username" />
        </el-form-item>
        <el-form-item label="Password">
          <el-input v-model="loginForm.password" type="password" placeholder="Enter password" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="authStore.loading" style="width: 100%">
            Login
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()

const loginForm = reactive({
  username: '',
  password: '',
})

const handleLogin = async () => {
  try {
    await authStore.login(loginForm)
    ElMessage.success('Login successful')
    router.push('/')
  } catch (error) {
    ElMessage.error('Login failed')
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 400px;
}

h2 {
  text-align: center;
  margin: 0;
}
</style>
