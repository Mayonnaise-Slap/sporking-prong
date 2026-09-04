<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { apiClient } from '@/api/client'
import { extractErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import type { AssignmentCreatePayload, AssignmentWithCriteria } from '@/types/api'

interface CriterionRow {
  title: string
  max_points: number | null
  min_points: number | null
}

function emptyCriterion(): CriterionRow {
  return { title: '', max_points: null, min_points: null }
}

const auth = useAuthStore()
const router = useRouter()

const title = ref('')
const conditionMarkdown = ref('')
const deadlineAt = ref('')
const maxAttempts = ref(3)
const passThresholdPoints = ref<number | null>(null)
const criteria = reactive<CriterionRow[]>([emptyCriterion()])

const error = ref('')
const submitting = ref(false)

const canSubmit = computed(
  () =>
    title.value.trim().length > 0 &&
    conditionMarkdown.value.trim().length > 0 &&
    deadlineAt.value.length > 0 &&
    passThresholdPoints.value !== null &&
    criteria.every((c) => c.title.trim().length > 0 && c.max_points !== null),
)

function addCriterion() {
  criteria.push(emptyCriterion())
}

function removeCriterion(index: number) {
  if (criteria.length > 1) {
    criteria.splice(index, 1)
  }
}

async function onSubmit() {
  error.value = ''
  if (!canSubmit.value) {
    error.value = 'Fill in the assignment details and at least one rubric criterion.'
    return
  }

  const payload: AssignmentCreatePayload = {
    title: title.value.trim(),
    condition_markdown: conditionMarkdown.value,
    // datetime-local has no timezone; the browser parses it as local time,
    // toISOString() converts to the UTC instant the backend expects.
    deadline_at: new Date(deadlineAt.value).toISOString(),
    max_attempts: maxAttempts.value,
    pass_threshold_points: passThresholdPoints.value as number,
    criteria: criteria.map((c) => ({
      title: c.title.trim(),
      max_points: c.max_points as number,
      min_points: c.min_points,
    })),
  }

  submitting.value = true
  try {
    await apiClient.post<AssignmentWithCriteria>('/assignments', payload)
    router.push({ path: '/assignments', query: { created: '1' } })
  } catch (err) {
    error.value = extractErrorMessage(err, 'Could not create the assignment.')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="container new-assignment-page">
    <div v-if="!auth.user?.is_supervisor" class="card card-pad">
      <p class="card-label">Not authorized</p>
      <h1 class="new-assignment-page__title">Supervisors only</h1>
      <p class="text-muted">Only supervisors can create assignments.</p>
      <RouterLink to="/assignments" class="btn btn-outline" style="margin-top: var(--space-4)">Back to assignments</RouterLink>
    </div>

    <form v-else class="card card-pad" @submit.prevent="onSubmit">
      <p class="card-label">New assignment</p>
      <h1 class="new-assignment-page__title">Create an assignment</h1>

      <p v-if="error" class="form-banner form-banner-error">{{ error }}</p>

      <div class="field">
        <label for="assignment-title">Title</label>
        <input id="assignment-title" v-model="title" type="text" class="input" required />
      </div>

      <div class="field">
        <label for="assignment-condition">Condition (Markdown)</label>
        <textarea
          id="assignment-condition"
          v-model="conditionMarkdown"
          class="textarea"
          required
          placeholder="Goal, functional/non-functional requirements, Definition of Done…"
        ></textarea>
      </div>

      <div class="new-assignment-page__row">
        <div class="field">
          <label for="assignment-deadline">Deadline</label>
          <input id="assignment-deadline" v-model="deadlineAt" type="datetime-local" class="input" required />
        </div>

        <div class="field">
          <label for="assignment-max-attempts">Max attempts</label>
          <input id="assignment-max-attempts" v-model.number="maxAttempts" type="number" min="1" class="input" required />
        </div>

        <div class="field">
          <label for="assignment-pass-threshold">Pass threshold (pts)</label>
          <input
            id="assignment-pass-threshold"
            v-model.number="passThresholdPoints"
            type="number"
            min="0"
            step="0.5"
            class="input"
            required
          />
        </div>
      </div>

      <h2 class="new-assignment-page__section-title">Rubric criteria</h2>
      <p class="field-hint" style="margin-bottom: var(--space-3)">
        Leave "min points" blank for free partial credit, or set it equal to max points for all-or-nothing.
      </p>

      <div v-for="(criterion, index) in criteria" :key="index" class="criterion-row">
        <div class="field criterion-row__title">
          <label :for="`criterion-title-${index}`">Criterion {{ index + 1 }}</label>
          <input :id="`criterion-title-${index}`" v-model="criterion.title" type="text" class="input" required />
        </div>
        <div class="field criterion-row__points">
          <label :for="`criterion-max-${index}`">Max points</label>
          <input
            :id="`criterion-max-${index}`"
            v-model.number="criterion.max_points"
            type="number"
            min="0"
            step="0.5"
            class="input"
            required
          />
        </div>
        <div class="field criterion-row__points">
          <label :for="`criterion-min-${index}`">Min points</label>
          <input
            :id="`criterion-min-${index}`"
            v-model.number="criterion.min_points"
            type="number"
            min="0"
            step="0.5"
            class="input"
          />
        </div>
        <button
          type="button"
          class="btn btn-outline btn-sm criterion-row__remove"
          :disabled="criteria.length === 1"
          @click="removeCriterion(index)"
        >
          Remove
        </button>
      </div>

      <button type="button" class="btn btn-outline btn-sm" @click="addCriterion">Add criterion</button>

      <div class="form-actions" style="margin-top: var(--space-6)">
        <button type="submit" class="btn btn-primary" :disabled="submitting">
          {{ submitting ? 'Creating…' : 'Create assignment' }}
        </button>
        <RouterLink to="/assignments" class="btn btn-outline">Cancel</RouterLink>
      </div>
    </form>
  </section>
</template>

<style scoped>
.new-assignment-page {
  padding: var(--space-8) var(--space-6) var(--space-12);
  max-width: 720px;
}

.new-assignment-page__title {
  font-size: var(--text-xl);
  font-weight: 700;
  margin: var(--space-1) 0 var(--space-4);
}

.new-assignment-page__row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--space-4);
}

.new-assignment-page__section-title {
  font-size: var(--text-lg);
  font-weight: 700;
  margin: var(--space-6) 0 var(--space-1);
}

.criterion-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-top: 1px solid var(--color-border);
}

.criterion-row:first-of-type {
  border-top: none;
}

.criterion-row__title {
  flex: 2;
}

.criterion-row__points {
  flex: 1;
  min-width: 110px;
}

.criterion-row__remove {
  margin-top: calc(var(--text-sm) + var(--space-3));
}
</style>
