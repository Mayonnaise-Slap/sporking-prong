<script setup lang="ts">
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

function onLogout() {
  auth.logout()
  router.push('/')
}
</script>

<template>
  <header class="app-header">
    <div class="container app-header__inner">
      <RouterLink to="/" class="app-header__brand">
        <span class="app-header__brand-ta">(TA)</span>co
      </RouterLink>

      <nav class="app-header__actions">
        <RouterLink to="/assignments" class="btn btn-ghost btn-sm">Assignments</RouterLink>

        <template v-if="auth.isAuthenticated">
          <span class="app-header__user text-mono">{{ auth.user?.email }}</span>
          <button type="button" class="btn btn-ghost btn-sm" @click="onLogout">Log out</button>
        </template>
        <template v-else>
          <RouterLink to="/login" class="btn btn-ghost btn-sm">Log in</RouterLink>
          <RouterLink to="/register" class="btn btn-primary btn-sm">Register</RouterLink>
        </template>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  height: var(--header-height);
  background: var(--color-ink);
  border-bottom: 1px solid var(--color-ink-border);
}

.app-header__inner {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.app-header__brand {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--color-ink-text);
  letter-spacing: -0.01em;
}

.app-header__brand:hover {
  text-decoration: none;
  color: var(--color-ink-text);
}

.app-header__brand-ta {
  color: var(--color-primary);
}

.app-header__actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.app-header__user {
  font-size: var(--text-sm);
  color: var(--color-ink-text-muted);
}
</style>
