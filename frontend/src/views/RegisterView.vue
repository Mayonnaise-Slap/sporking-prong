<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { extractErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'

type Role = 'student' | 'ta' | 'supervisor'

const email = ref('')
const fullName = ref('')
const password = ref('')
const confirmPassword = ref('')
const role = ref<Role>('student')
const error = ref('')
const submitting = ref(false)

const auth = useAuthStore()
const router = useRouter()

const validationError = computed(() => {
  if (password.value.length > 0 && password.value.length < 8) {
    return 'Password must be at least 8 characters.'
  }
  if (confirmPassword.value.length > 0 && password.value !== confirmPassword.value) {
    return 'Passwords do not match.'
  }
  return ''
})

async function onSubmit() {
  error.value = ''
  if (validationError.value) {
    error.value = validationError.value
    return
  }

  submitting.value = true
  try {
    await auth.register({
      email: email.value,
      password: password.value,
      full_name: fullName.value.trim() || undefined,
      is_ta: role.value === 'ta',
      is_supervisor: role.value === 'supervisor',
    })
    router.push('/assignments')
  } catch (err) {
    error.value = extractErrorMessage(err, 'Could not create your account.')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="container auth-page">
    <form class="card card-pad auth-card" @submit.prevent="onSubmit">
      <p class="card-label">Register</p>
      <h1 class="auth-card__title">Create an account</h1>

      <p v-if="error" class="form-banner form-banner-error">{{ error }}</p>

      <div class="field">
        <label for="register-email">Email</label>
        <input id="register-email" v-model="email" type="email" class="input" required autocomplete="email" />
      </div>

      <div class="field">
        <label for="register-full-name">Full name</label>
        <input id="register-full-name" v-model="fullName" type="text" class="input" autocomplete="name" />
      </div>

      <div class="field">
        <label for="register-password">Password</label>
        <input
          id="register-password"
          v-model="password"
          type="password"
          class="input"
          required
          minlength="8"
          autocomplete="new-password"
        />
        <span class="field-hint">At least 8 characters.</span>
      </div>

      <div class="field">
        <label for="register-confirm-password">Confirm password</label>
        <input
          id="register-confirm-password"
          v-model="confirmPassword"
          type="password"
          class="input"
          required
          autocomplete="new-password"
        />
      </div>

      <fieldset class="role-field">
        <legend class="role-field__legend">Role</legend>

        <label class="checkbox-field">
          <input v-model="role" type="radio" name="role" value="student" />
          <span class="checkbox-field__text">
            <span class="checkbox-field__label">Student</span>
            <span class="checkbox-field__hint">Submits work for review.</span>
          </span>
        </label>

        <label class="checkbox-field">
          <input v-model="role" type="radio" name="role" value="ta" />
          <span class="checkbox-field__text">
            <span class="checkbox-field__label">TA</span>
            <span class="checkbox-field__hint">Reviews submissions and leaves comments.</span>
          </span>
        </label>

        <label class="checkbox-field">
          <input v-model="role" type="radio" name="role" value="supervisor" />
          <span class="checkbox-field__text">
            <span class="checkbox-field__label">Supervisor</span>
            <span class="checkbox-field__hint">Creates assignments and rubrics.</span>
          </span>
        </label>
      </fieldset>

      <div class="form-actions">
        <button type="submit" class="btn btn-primary" :disabled="submitting">
          {{ submitting ? 'Creating account…' : 'Register' }}
        </button>
      </div>

      <p class="auth-card__links text-muted">
        <RouterLink to="/login">Already have an account? Log in</RouterLink>
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
  max-width: 420px;
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

.role-field {
  border: none;
  padding: 0;
  margin: 0 0 var(--space-3);
  min-width: 0;
}

.role-field__legend {
  padding: 0;
  margin-bottom: var(--space-2);
  font-size: var(--text-sm);
  font-weight: 600;
}
</style>
