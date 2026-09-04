<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { extractErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'

const email = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

const auth = useAuthStore()
const router = useRouter()

async function onSubmit() {
  error.value = ''
  submitting.value = true
  try {
    await auth.login({ email: email.value, password: password.value })
    router.push('/assignments')
  } catch (err) {
    error.value = extractErrorMessage(err, 'Invalid email or password.')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="container auth-page">
    <form class="card card-pad auth-card" @submit.prevent="onSubmit">
      <p class="card-label">Log in</p>
      <h1 class="auth-card__title">Welcome back</h1>

      <p v-if="error" class="form-banner form-banner-error">{{ error }}</p>

      <div class="field">
        <label for="login-email">Email</label>
        <input id="login-email" v-model="email" type="email" class="input" required autocomplete="email" />
      </div>

      <div class="field">
        <label for="login-password">Password</label>
        <input
          id="login-password"
          v-model="password"
          type="password"
          class="input"
          required
          autocomplete="current-password"
        />
      </div>

      <div class="form-actions">
        <button type="submit" class="btn btn-primary" :disabled="submitting">
          {{ submitting ? 'Logging in…' : 'Log in' }}
        </button>
      </div>

      <p class="auth-card__links text-muted">
        <RouterLink to="/restore">Forgot your password?</RouterLink>
        &middot;
        <RouterLink to="/register">Need an account? Register</RouterLink>
      </p>
    </form>
  </section>
</template>

<style scoped>
.auth-page {
  display: flex;
  justify-content: center;
  padding: var(--space-12) var(--space-6);
}

.auth-card {
  width: 100%;
  max-width: 380px;
}

.auth-card__title {
  font-size: var(--text-xl);
  font-weight: 700;
  margin: var(--space-1) 0 var(--space-4);
}

.auth-card__links {
  font-size: var(--text-sm);
  margin-top: var(--space-4);
}
</style>
