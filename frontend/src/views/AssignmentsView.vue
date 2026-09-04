<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { apiClient } from '@/api/client'
import { extractErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import type { AssignmentWithCriteria } from '@/types/api'
import { parseApiDate } from '@/utils/date'

const assignments = ref<AssignmentWithCriteria[]>([])
const loading = ref(true)
const error = ref('')

const auth = useAuthStore()
const route = useRoute()

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function formatDate(value: string) {
  return dateFormatter.format(parseApiDate(value))
}

function totalPoints(assignment: AssignmentWithCriteria) {
  return assignment.criteria.reduce((sum, c) => sum + c.max_points, 0)
}

onMounted(async () => {
  try {
    const { data } = await apiClient.get<AssignmentWithCriteria[]>('/assignments')
    assignments.value = data
  } catch (err) {
    error.value = extractErrorMessage(err, 'Could not load assignments.')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="container assignments-page">
    <header class="assignments-page__header">
      <div>
        <h1 class="assignments-page__title">Assignments</h1>
        <p class="text-muted">Everything published so far, most recent first.</p>
      </div>
      <RouterLink v-if="auth.user?.is_supervisor" to="/assignments/new" class="btn btn-primary">
        New assignment
      </RouterLink>
    </header>

    <p v-if="route.query.created" class="form-banner form-banner-success">Assignment created.</p>
    <p v-if="error" class="form-banner form-banner-error">{{ error }}</p>
    <p v-else-if="loading" class="text-muted">Loading…</p>
    <p v-else-if="assignments.length === 0" class="text-muted">No assignments yet.</p>

    <ul v-else class="assignment-list">
      <li v-for="assignment in assignments" :key="assignment.id">
        <RouterLink :to="`/assignments/${assignment.id}`" class="card card-pad assignment-card">
          <h2 class="assignment-card__title">{{ assignment.title }}</h2>
          <dl class="assignment-card__meta">
            <div>
              <dt class="text-muted">Deadline</dt>
              <dd>{{ formatDate(assignment.deadline_at) }}</dd>
            </div>
            <div>
              <dt class="text-muted">Pass threshold</dt>
              <dd>{{ assignment.pass_threshold_points }} / {{ totalPoints(assignment) }} pts</dd>
            </div>
            <div>
              <dt class="text-muted">Attempts allowed</dt>
              <dd>{{ assignment.max_attempts }}</dd>
            </div>
            <div>
              <dt class="text-muted">Rubric</dt>
              <dd>{{ assignment.criteria.length }} criteria</dd>
            </div>
          </dl>
        </RouterLink>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.assignments-page {
  padding: var(--space-8) var(--space-6) var(--space-12);
}

.assignments-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.assignments-page__title {
  font-size: var(--text-2xl);
  font-weight: 700;
  margin-bottom: var(--space-1);
}

.assignment-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.assignment-card {
  display: block;
  color: inherit;
  transition: border-color 0.12s ease;
}

.assignment-card:hover {
  text-decoration: none;
  border-color: var(--color-border-strong);
}

.assignment-card__title {
  font-size: var(--text-lg);
  font-weight: 700;
  margin-bottom: var(--space-3);
}

.assignment-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-6);
  margin: 0;
  font-size: var(--text-sm);
}

.assignment-card__meta dt {
  font-size: var(--text-xs);
}

.assignment-card__meta dd {
  margin: 0;
  font-weight: 600;
}
</style>
