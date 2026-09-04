<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { extractErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'

type Step = 'request' | 'confirm' | 'done'

const step = ref<Step>('request')
const email = ref('')
const code = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const submitting = ref(false)

const auth = useAuthStore()
const router = useRouter()

const validationError = computed(() => {
  if (newPassword.value.length > 0 && newPassword.value.length < 8) {
    return 'Password must be at least 8 characters.'
  }
  if (confirmPassword.value.length > 0 && newPassword.value !== confirmPassword.value) {
    return 'Passwords do not match.'
  }
  return ''
})

async function onRequest() {
  error.value = ''
  submitting.value = true
  try {
    await auth.restoreRequest({ email: email.value })
    step.value = 'confirm'
  } catch (err) {
    error.value = extractErrorMessage(err, 'Could not request a restoration code.')
  } finally {
    submitting.value = false
  }
}

async function onConfirm() {
  error.value = ''
  if (validationError.value) {
    error.value = validationError.value
    return
  }

  submitting.value = true
  try {
    await auth.restoreConfirm({ email: email.value, code: code.value, new_password: newPassword.value })
    step.value = 'done'
  } catch (err) {
    error.value = extractErrorMessage(err, 'Invalid or expired restoration code.')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="container auth-page">
    <div class="card card-pad auth-card">
      <p class="card-label">Restore access</p>

      <template v-if="step === 'request'">
        <h1 class="auth-card__title">Request a reset code</h1>
        <p v-if="error" class="form-banner form-banner-error">{{ error }}</p>
        <form @submit.prevent="onRequest">
          <div class="field">
            <label for="restore-email">Email</label>
            <input id="restore-email" v-model="email" type="email" class="input" required autocomplete="email" />
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary" :disabled="submitting">
              {{ submitting ? 'Sending…' : 'Send reset code' }}
            </button>
          </div>
        </form>
      </template>

      <template v-else-if="step === 'confirm'">
        <h1 class="auth-card__title">Enter the reset code</h1>
        <p class="form-banner form-banner-success">
          If {{ email }} is registered, a code has been generated. There's no email provider wired
          up yet — ask whoever is running the server to read it from the server logs.
        </p>
        <p v-if="error" class="form-banner form-banner-error">{{ error }}</p>
        <form @submit.prevent="onConfirm">
          <div class="field">
            <label for="restore-code">Reset code</label>
            <input id="restore-code" v-model="code" type="text" class="input text-mono" required />
          </div>
          <div class="field">
            <label for="restore-new-password">New password</label>
            <input
              id="restore-new-password"
              v-model="newPassword"
              type="password"
              class="input"
              required
              minlength="8"
              autocomplete="new-password"
            />
          </div>
          <div class="field">
            <label for="restore-confirm-password">Confirm new password</label>
            <input
              id="restore-confirm-password"
              v-model="confirmPassword"
              type="password"
              class="input"
              required
              autocomplete="new-password"
            />
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary" :disabled="submitting">
              {{ submitting ? 'Resetting…' : 'Reset password' }}
            </button>
            <button type="button" class="btn btn-outline" @click="step = 'request'">Back</button>
          </div>
        </form>
      </template>

      <template v-else>
        <h1 class="auth-card__title">Password reset</h1>
        <p class="form-banner form-banner-success">Your password has been reset.</p>
        <button type="button" class="btn btn-primary" @click="router.push('/login')">Continue to log in</button>
      </template>
    </div>
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
  max-width: 420px;
}

.auth-card__title {
  font-size: var(--text-xl);
  font-weight: 700;
  margin: var(--space-1) 0 var(--space-4);
}
</style>
