<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { apiClient } from '@/api/client'
import { extractErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import type {
  AssignmentWithCriteria,
  RubricCriterionCreatePayload,
  RubricCriterionUpdatePayload,
  SubmissionPublic,
} from '@/types/api'
import type { RubricCriterion } from '@/types/models'
import { parseApiDate } from '@/utils/date'

const props = defineProps<{ id: number }>()

const auth = useAuthStore()

// Roles are informal per the product doc (no strict access control) — these
// just pick which section renders; the backend is what actually enforces
// the boundary (403 on the write endpoints, require_staff on the list).
const isSupervisor = computed(() => auth.user?.is_supervisor ?? false)
const isStaff = computed(() => (auth.user?.is_ta || auth.user?.is_supervisor) ?? false)

const dateFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
function formatDate(value: string) {
  return dateFormatter.format(parseApiDate(value))
}

const assignment = ref<AssignmentWithCriteria | null>(null)
const loading = ref(true)
const loadError = ref('')

const totalPoints = computed(() => assignment.value?.criteria.reduce((sum, c) => sum + c.max_points, 0) ?? 0)

// There's no GET /assignments/{id} endpoint yet, only the list — reuse it
// and find the one we want, same as the assignments list page does.
async function loadAssignment() {
  loading.value = true
  loadError.value = ''
  try {
    const { data } = await apiClient.get<AssignmentWithCriteria[]>('/assignments')
    const found = data.find((a) => a.id === props.id) ?? null
    assignment.value = found
    if (!found) loadError.value = 'Assignment not found.'
  } catch (err) {
    loadError.value = extractErrorMessage(err, 'Could not load this assignment.')
  } finally {
    loading.value = false
  }
}

// ---- Grading rules (supervisor only) ----
const editingCriterionId = ref<number | null>(null)
const editDraft = reactive({ title: '', max_points: 0, min_points: null as number | null })
const criteriaError = ref('')
const savingCriterion = ref(false)

function startEdit(criterion: RubricCriterion) {
  editingCriterionId.value = criterion.id
  editDraft.title = criterion.title
  editDraft.max_points = criterion.max_points
  editDraft.min_points = criterion.min_points
}

function cancelEdit() {
  editingCriterionId.value = null
}

async function saveEdit(criterion: RubricCriterion) {
  if (!assignment.value) return

  const payload: RubricCriterionUpdatePayload = {}
  if (editDraft.title !== criterion.title) payload.title = editDraft.title
  if (editDraft.max_points !== criterion.max_points) payload.max_points = editDraft.max_points
  if (editDraft.min_points !== criterion.min_points) payload.min_points = editDraft.min_points

  if (Object.keys(payload).length === 0) {
    editingCriterionId.value = null
    return
  }

  criteriaError.value = ''
  savingCriterion.value = true
  try {
    const { data } = await apiClient.patch<RubricCriterion>(
      `/assignments/${assignment.value.id}/criteria/${criterion.id}`,
      payload,
    )
    const index = assignment.value.criteria.findIndex((c) => c.id === criterion.id)
    if (index !== -1) assignment.value.criteria[index] = data
    editingCriterionId.value = null
  } catch (err) {
    criteriaError.value = extractErrorMessage(err, 'Could not save this criterion.')
  } finally {
    savingCriterion.value = false
  }
}

async function removeCriterion(criterion: RubricCriterion) {
  if (!assignment.value) return
  criteriaError.value = ''
  try {
    await apiClient.delete(`/assignments/${assignment.value.id}/criteria/${criterion.id}`)
    assignment.value.criteria = assignment.value.criteria.filter((c) => c.id !== criterion.id)
  } catch (err) {
    criteriaError.value = extractErrorMessage(err, 'Could not delete this criterion.')
  }
}

const newCriterion = reactive({ title: '', max_points: null as number | null, min_points: null as number | null })
const addingCriterion = ref(false)

async function addCriterion() {
  if (!assignment.value || !newCriterion.title.trim() || newCriterion.max_points === null) return

  const payload: RubricCriterionCreatePayload = {
    title: newCriterion.title.trim(),
    max_points: newCriterion.max_points,
    min_points: newCriterion.min_points,
  }

  criteriaError.value = ''
  addingCriterion.value = true
  try {
    const { data } = await apiClient.post<RubricCriterion>(`/assignments/${assignment.value.id}/criteria`, payload)
    assignment.value.criteria.push(data)
    newCriterion.title = ''
    newCriterion.max_points = null
    newCriterion.min_points = null
  } catch (err) {
    criteriaError.value = extractErrorMessage(err, 'Could not add this criterion.')
  } finally {
    addingCriterion.value = false
  }
}

// ---- Submissions (TA or supervisor) ----
const submissions = ref<SubmissionPublic[]>([])
const submissionsLoading = ref(false)
const submissionsError = ref('')

async function loadSubmissions() {
  if (!assignment.value) return
  submissionsLoading.value = true
  submissionsError.value = ''
  try {
    const { data } = await apiClient.get<SubmissionPublic[]>(`/assignments/${assignment.value.id}/submissions`)
    submissions.value = data
  } catch (err) {
    submissionsError.value = extractErrorMessage(err, 'Could not load submissions.')
  } finally {
    submissionsLoading.value = false
  }
}

// ---- Submit a file (everyone else) ----
const selectedFile = ref<File | null>(null)
const submitting = ref(false)
const submitError = ref('')
const lastSubmission = ref<SubmissionPublic | null>(null)

function onFileChange(event: Event) {
  selectedFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
}

async function submitFile() {
  if (!assignment.value || !selectedFile.value) return

  const formData = new FormData()
  formData.append('file', selectedFile.value)

  submitError.value = ''
  submitting.value = true
  try {
    const { data } = await apiClient.post<SubmissionPublic>(
      `/assignments/${assignment.value.id}/submissions`,
      formData,
    )
    lastSubmission.value = data
    selectedFile.value = null
  } catch (err) {
    submitError.value = extractErrorMessage(err, 'Could not submit your file.')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await loadAssignment()
  if (assignment.value && isStaff.value) {
    await loadSubmissions()
  }
})
</script>

<template>
  <section class="container detail-page">
    <p v-if="loading" class="text-muted">Loading…</p>
    <p v-else-if="loadError" class="form-banner form-banner-error">{{ loadError }}</p>

    <template v-else-if="assignment">
      <RouterLink to="/assignments" class="text-muted detail-back">&larr; All assignments</RouterLink>

      <header class="detail-header">
        <h1 class="detail-header__title">{{ assignment.title }}</h1>
        <dl class="detail-header__meta">
          <div>
            <dt class="text-muted">Deadline</dt>
            <dd>{{ formatDate(assignment.deadline_at) }}</dd>
          </div>
          <div>
            <dt class="text-muted">Pass threshold</dt>
            <dd>{{ assignment.pass_threshold_points }} / {{ totalPoints }} pts</dd>
          </div>
          <div>
            <dt class="text-muted">Attempts allowed</dt>
            <dd>{{ assignment.max_attempts }}</dd>
          </div>
        </dl>
      </header>

      <div class="detail-grid">
        <section class="card card-pad">
          <p class="card-label">Condition</p>
          <pre class="detail-condition text-mono">{{ assignment.condition_markdown }}</pre>
        </section>

        <section class="card card-pad">
          <p class="card-label">Rubric</p>

          <ul class="criteria-list">
            <li v-for="criterion in assignment.criteria" :key="criterion.id" class="criteria-row">
              <div v-if="isSupervisor && editingCriterionId === criterion.id" class="criteria-row__edit">
                <input v-model="editDraft.title" type="text" class="input" />
                <input v-model.number="editDraft.max_points" type="number" min="0" step="0.5" class="input" />
                <input
                  v-model.number="editDraft.min_points"
                  type="number"
                  min="0"
                  step="0.5"
                  class="input"
                  placeholder="optional"
                />
                <div class="criteria-row__actions">
                  <button type="button" class="btn btn-primary btn-sm" :disabled="savingCriterion" @click="saveEdit(criterion)">
                    Save
                  </button>
                  <button type="button" class="btn btn-outline btn-sm" @click="cancelEdit">Cancel</button>
                </div>
              </div>

              <template v-else>
                <div class="criteria-row__info">
                  <p class="criteria-row__title">{{ criterion.title }}</p>
                  <p class="text-muted criteria-row__points">{{ criterion.min_points ?? 0 }}&ndash;{{ criterion.max_points }} pts</p>
                </div>
                <div v-if="isSupervisor" class="criteria-row__actions">
                  <button type="button" class="btn btn-outline btn-sm" @click="startEdit(criterion)">Edit</button>
                  <button type="button" class="btn btn-outline btn-sm" @click="removeCriterion(criterion)">Delete</button>
                </div>
              </template>
            </li>
            <li v-if="assignment.criteria.length === 0" class="text-muted">No grading rules yet.</li>
          </ul>

          <p v-if="criteriaError" class="form-banner form-banner-error">{{ criteriaError }}</p>

          <form v-if="isSupervisor" class="criteria-add" @submit.prevent="addCriterion">
            <p class="card-label criteria-add__label">Add grading rule</p>
            <div class="criteria-add__row">
              <input v-model="newCriterion.title" type="text" class="input" placeholder="Criterion title" required />
              <input v-model.number="newCriterion.max_points" type="number" min="0" step="0.5" class="input" placeholder="Max pts" required />
              <input
                v-model.number="newCriterion.min_points"
                type="number"
                min="0"
                step="0.5"
                class="input"
                placeholder="Min pts (optional)"
              />
              <button type="submit" class="btn btn-primary btn-sm" :disabled="addingCriterion">Add</button>
            </div>
          </form>
        </section>
      </div>

      <section v-if="isStaff" class="card card-pad">
        <p class="card-label">Submissions</p>
        <p v-if="submissionsError" class="form-banner form-banner-error">{{ submissionsError }}</p>
        <p v-else-if="submissionsLoading" class="text-muted">Loading…</p>
        <p v-else-if="submissions.length === 0" class="text-muted">No submissions yet.</p>
        <ul v-else class="submission-list">
          <li v-for="submission in submissions" :key="submission.id" class="submission-row">
            <span class="text-mono">Student #{{ submission.student_id }}</span>
            <span class="text-muted">attempt {{ submission.attempt_number }}</span>
            <span class="text-muted">{{ formatDate(submission.submitted_at) }}</span>
            <span class="badge" :class="submission.processed_status === 'done' ? 'badge-success' : 'badge-neutral'">
              {{ submission.processed_status }}
            </span>
            <span class="badge badge-neutral">{{ submission.review_status }}</span>
            <span v-if="submission.is_empty" class="badge badge-danger">empty file</span>
            <span class="text-muted">{{ submission.line_count ?? 0 }} lines</span>
          </li>
        </ul>
      </section>

      <section v-else-if="auth.isAuthenticated" class="card card-pad">
        <p class="card-label">Submit your work</p>
        <p v-if="lastSubmission" class="form-banner form-banner-success">
          Submitted as attempt {{ lastSubmission.attempt_number }} of {{ assignment.max_attempts }},
          {{ formatDate(lastSubmission.submitted_at) }}.
        </p>
        <p v-if="submitError" class="form-banner form-banner-error">{{ submitError }}</p>
        <form @submit.prevent="submitFile">
          <div class="field">
            <label for="submission-file">File</label>
            <input id="submission-file" type="file" class="input" required @change="onFileChange" />
          </div>
          <button type="submit" class="btn btn-primary" :disabled="submitting || !selectedFile">
            {{ submitting ? 'Submitting…' : 'Submit' }}
          </button>
        </form>
      </section>

      <section v-else class="card card-pad">
        <p class="card-label">Submit your work</p>
        <p class="text-muted">
          <RouterLink to="/login">Log in</RouterLink> to submit a file for this assignment.
        </p>
      </section>
    </template>
  </section>
</template>

<style scoped>
.detail-page {
  padding: var(--space-8) var(--space-6) var(--space-12);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.detail-back {
  font-size: var(--text-sm);
  align-self: flex-start;
}

.detail-header__title {
  font-size: var(--text-2xl);
  font-weight: 700;
  margin-bottom: var(--space-3);
}

.detail-header__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-6);
  margin: 0;
  font-size: var(--text-sm);
}

.detail-header__meta dt {
  font-size: var(--text-xs);
}

.detail-header__meta dd {
  margin: 0;
  font-weight: 600;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--space-4);
  align-items: start;
}

.detail-condition {
  white-space: pre-wrap;
  font-size: var(--text-sm);
  max-height: 420px;
  overflow-y: auto;
}

.criteria-list {
  list-style: none;
  margin: 0 0 var(--space-2);
  padding: 0;
}

.criteria-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-top: 1px solid var(--color-border);
}

.criteria-row:first-child {
  border-top: none;
}

.criteria-row__title {
  font-size: var(--text-sm);
  font-weight: 600;
}

.criteria-row__points {
  font-size: var(--text-xs);
}

.criteria-row__actions {
  display: flex;
  gap: var(--space-2);
  flex: none;
}

.criteria-row__edit {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  flex-wrap: wrap;
}

.criteria-row__edit .input {
  width: auto;
  flex: 1;
  min-width: 90px;
}

.criteria-add__label {
  margin: var(--space-4) 0 var(--space-2);
}

.criteria-add__row {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.criteria-add__row .input {
  flex: 1;
  min-width: 100px;
}

.submission-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.submission-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-top: 1px solid var(--color-border);
  font-size: var(--text-sm);
}

.submission-row:first-child {
  border-top: none;
}
</style>
