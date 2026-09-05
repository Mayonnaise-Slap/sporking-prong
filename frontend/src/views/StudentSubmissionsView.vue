<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { apiClient } from '@/api/client'
import { extractErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import type { AssignmentWithCriteria, SubmissionPublic } from '@/types/api'
import { parseApiDate } from '@/utils/date'

// studentId absent -> "my submissions" (self); present -> a TA/supervisor
// looking up one student's history (linked from SubmissionView.vue).
const props = defineProps<{ studentId?: number }>()

const auth = useAuthStore()
const route = useRoute()

const loading = ref(true)
const loadError = ref('')
const submissions = ref<SubmissionPublic[]>([])
const assignmentTitleById = ref<Record<number, string>>({})

const dateFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
function formatDate(value: string) {
  return dateFormatter.format(parseApiDate(value))
}

const displayName = computed(() => {
  if (!props.studentId) return null
  // Prefer the authoritative name once loaded; the query hint (carried from
  // the link that sent us here) covers the instant before that resolves.
  const fromData = submissions.value[0]?.student_full_name
  if (fromData) return fromData
  const hinted = route.query.name
  return typeof hinted === 'string' && hinted ? hinted : `Student #${props.studentId}`
})

function assignmentTitle(assignmentId: number) {
  return assignmentTitleById.value[assignmentId] ?? `Assignment #${assignmentId}`
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const params = props.studentId ? { student_id: props.studentId } : undefined
    const { data } = await apiClient.get<SubmissionPublic[]>('/submissions', { params })
    submissions.value = data

    const { data: assignments } = await apiClient.get<AssignmentWithCriteria[]>('/assignments')
    assignmentTitleById.value = Object.fromEntries(assignments.map((a) => [a.id, a.title]))
  } catch (err) {
    loadError.value = extractErrorMessage(err, 'Could not load submissions.')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (!props.studentId && !auth.isAuthenticated) {
    loading.value = false
    return
  }
  load()
})
</script>

<template>
  <section class="container submissions-page">
    <h1 class="submissions-page__title">
      {{ displayName ? `${displayName}'s submissions` : 'My submissions' }}
    </h1>

    <p v-if="!props.studentId && !auth.isAuthenticated" class="text-muted">
      <RouterLink to="/login">Log in</RouterLink> to see your submissions.
    </p>

    <p v-else-if="loading" class="text-muted">Loading…</p>
    <p v-else-if="loadError" class="form-banner form-banner-error">{{ loadError }}</p>
    <p v-else-if="submissions.length === 0" class="text-muted">No submissions yet.</p>

    <ul v-else class="submissions-page__list">
      <li v-for="submission in submissions" :key="submission.id">
        <RouterLink :to="`/submissions/${submission.id}`" class="submission-row">
          <span class="submission-row__title">{{ assignmentTitle(submission.assignment_id) }}</span>
          <span class="text-muted">attempt {{ submission.attempt_number }}</span>
          <span class="text-muted">{{ formatDate(submission.submitted_at) }}</span>
          <span class="badge" :class="submission.processed_status === 'done' ? 'badge-success' : 'badge-neutral'">
            {{ submission.processed_status }}
          </span>
          <span class="badge badge-neutral">{{ submission.review_status }}</span>
        </RouterLink>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.submissions-page {
  padding: var(--space-8) var(--space-6) var(--space-12);
}

.submissions-page__title {
  font-size: var(--text-2xl);
  font-weight: 700;
  margin-bottom: var(--space-6);
}

.submissions-page__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.submissions-page__list li {
  border-top: 1px solid var(--color-border);
}

.submissions-page__list li:first-child {
  border-top: none;
}

.submission-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  font-size: var(--text-sm);
  color: inherit;
}

.submission-row:hover {
  text-decoration: none;
}

.submission-row:hover .submission-row__title {
  text-decoration: underline;
}

.submission-row__title {
  font-weight: 600;
}
</style>
