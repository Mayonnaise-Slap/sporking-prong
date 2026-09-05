<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

import { apiClient } from '@/api/client'
import { extractErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import type {
  AssignmentWithCriteria,
  CommentCreatePayload,
  CommentUpdatePayload,
  CriterionGradeView,
  FinalGradeUpsertPayload,
  HeuristicsCheckItem,
  JobPublic,
  PlagiarismMatchPublic,
  SubmissionPublic,
  SubmissionUpdatePayload,
  UserListItem,
} from '@/types/api'
// Aliased to dodge the DOM lib's own global `Comment` (a node type) — this
// one is app/models.py's Comment row.
import type { Comment as CommentModel, FinalGrade } from '@/types/models'
import { parseApiDate } from '@/utils/date'

const props = defineProps<{ id: number }>()

const auth = useAuthStore()

// Per features/backend_is.md Appendix 3: comments/criterion-grades/
// plagiarism-matches/final-grade are all require_staff-gated reads, so a
// plain student only ever sees the submission + its jobs — every section
// gated on `isStaff` below would 403 for them, hence gating the fetches
// themselves rather than just the write controls. `canGrade` is narrower
// still (TA only, not supervisor) — supervisors get the same full
// read-only picture as a TA, just no editing.
const isStaff = computed(() => (auth.user?.is_ta || auth.user?.is_supervisor) ?? false)
const canGrade = computed(() => auth.user?.is_ta ?? false)

const dateFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
function formatDate(value: string) {
  return dateFormatter.format(parseApiDate(value))
}

const submission = ref<SubmissionPublic | null>(null)
const assignment = ref<AssignmentWithCriteria | null>(null)
const jobs = ref<JobPublic[]>([])
const comments = ref<CommentModel[]>([])
const criterionGrades = ref<CriterionGradeView[]>([])
const plagiarismMatches = ref<PlagiarismMatchPublic[]>([])
const finalGrade = ref<FinalGrade | null>(null)
const users = ref<UserListItem[]>([])
const userNameById = ref<Record<number, string>>({})

const loading = ref(true)
const loadError = ref('')

const textLines = computed(() => submission.value?.processed_text.split('\n') ?? [])

function userLabel(userId: number | null, fallbackPrefix = 'User') {
  if (userId === null) return null
  return userNameById.value[userId] ?? `${fallbackPrefix} #${userId}`
}

// For the reviewer picker — every registered user, sorted for a stable,
// scannable dropdown. GET /users carries no role flags, so this can't be
// filtered down to TAs/supervisors only (matches the backend's own lack of
// a role check on assigned_reviewer_id).
const reviewerOptions = computed(() =>
  [...users.value].sort((a, b) => (a.full_name || a.email).localeCompare(b.full_name || b.email)),
)

const heuristicsChecks = computed<HeuristicsCheckItem[]>(() => {
  const job = jobs.value.find((j) => j.job_type === 'heuristics')
  return (job?.result as HeuristicsCheckItem[] | undefined) ?? []
})

function criterionBadgeClass(status: string) {
  switch (status) {
    case 'full':
      return 'badge-success'
    case 'partial':
      return 'badge-warning'
    case 'none':
      return 'badge-danger'
    default:
      return 'badge-neutral' // unmarked
  }
}

const commentsByEndLine = computed(() => {
  const map: Record<number, CommentModel[]> = {}
  for (const c of comments.value) {
    ;(map[c.end_line] ??= []).push(c)
  }
  return map
})

const draftComments = computed(() => comments.value.filter((c) => c.status === 'draft'))
const postingAllDrafts = ref(false)
const postAllError = ref('')

async function postAllDrafts() {
  if (draftComments.value.length === 0) return

  postAllError.value = ''
  postingAllDrafts.value = true
  try {
    const updated = await Promise.all(
      draftComments.value.map((c) => apiClient.patch<CommentModel>(`/comments/${c.id}`, { status: 'sent' })),
    )
    for (const { data } of updated) {
      const index = comments.value.findIndex((c) => c.id === data.id)
      if (index !== -1) comments.value[index] = data
    }
  } catch (err) {
    postAllError.value = extractErrorMessage(err, 'Could not post all comments.')
  } finally {
    postingAllDrafts.value = false
  }
}

// ---- GitHub-style drag-to-select-lines commenting (TA only) ----
const dragStartLine = ref<number | null>(null)
const dragEndLine = ref<number | null>(null)
const isDragging = ref(false)

const dragRange = computed(() => {
  if (dragStartLine.value === null || dragEndLine.value === null) return null
  return { start: Math.min(dragStartLine.value, dragEndLine.value), end: Math.max(dragStartLine.value, dragEndLine.value) }
})

const composerRange = ref<{ start: number; end: number } | null>(null)
const composerBody = ref('')
const addingComment = ref(false)
const commentsError = ref('')

function onGutterMouseDown(lineNumber: number) {
  if (!canGrade.value) return
  isDragging.value = true
  dragStartLine.value = lineNumber
  dragEndLine.value = lineNumber
  composerRange.value = null
}

function onGutterMouseEnter(lineNumber: number) {
  if (!isDragging.value) return
  dragEndLine.value = lineNumber
}

function onWindowMouseUp() {
  if (!isDragging.value) return
  isDragging.value = false
  if (dragRange.value) {
    composerRange.value = { ...dragRange.value }
    composerBody.value = ''
  }
  dragStartLine.value = null
  dragEndLine.value = null
}

interface LineRangeInfo {
  status: string
  isStart: boolean
  isEnd: boolean
}

// Every line within a comment's (or the in-progress selection's) range gets
// an entry here, driving the continuous colored box drawn around it — the
// box's color is the comment's status; an active drag/pending composer uses
// a neutral "selecting" pseudo-status.
const lineRangeInfo = computed<Record<number, LineRangeInfo>>(() => {
  const map: Record<number, LineRangeInfo> = {}
  for (const c of comments.value) {
    for (let ln = c.start_line; ln <= c.end_line; ln++) {
      map[ln] = { status: c.status, isStart: ln === c.start_line, isEnd: ln === c.end_line }
    }
  }
  const pending = dragRange.value ?? composerRange.value
  if (pending) {
    for (let ln = pending.start; ln <= pending.end; ln++) {
      map[ln] = { status: 'selecting', isStart: ln === pending.start, isEnd: ln === pending.end }
    }
  }
  return map
})

async function submitComposer(status: 'draft' | 'sent') {
  if (!composerRange.value || !composerBody.value.trim()) return

  const payload: CommentCreatePayload = {
    start_line: composerRange.value.start,
    end_line: composerRange.value.end,
    body: composerBody.value.trim(),
    status,
  }

  commentsError.value = ''
  addingComment.value = true
  try {
    const { data } = await apiClient.post<CommentModel>(`/submissions/${props.id}/comments`, payload)
    comments.value.push(data)
    composerRange.value = null
    composerBody.value = ''
  } catch (err) {
    commentsError.value = extractErrorMessage(err, 'Could not add this comment.')
  } finally {
    addingComment.value = false
  }
}

function cancelComposer() {
  composerRange.value = null
  composerBody.value = ''
}

const editingCommentId = ref<number | null>(null)
const commentDraft = reactive({ body: '', status: '' })

function startEditComment(comment: CommentModel) {
  editingCommentId.value = comment.id
  commentDraft.body = comment.body
  commentDraft.status = comment.status
}

function cancelEditComment() {
  editingCommentId.value = null
}

async function saveCommentEdit(comment: CommentModel) {
  const payload: CommentUpdatePayload = {}
  if (commentDraft.body !== comment.body) payload.body = commentDraft.body
  if (commentDraft.status !== comment.status) payload.status = commentDraft.status

  if (Object.keys(payload).length === 0) {
    editingCommentId.value = null
    return
  }

  commentsError.value = ''
  try {
    const { data } = await apiClient.patch<CommentModel>(`/comments/${comment.id}`, payload)
    const index = comments.value.findIndex((c) => c.id === comment.id)
    if (index !== -1) comments.value[index] = data
    editingCommentId.value = null
  } catch (err) {
    commentsError.value = extractErrorMessage(err, 'Could not save this comment.')
  }
}

async function removeComment(comment: CommentModel) {
  commentsError.value = ''
  try {
    await apiClient.delete(`/comments/${comment.id}`)
    comments.value = comments.value.filter((c) => c.id !== comment.id)
  } catch (err) {
    commentsError.value = extractErrorMessage(err, 'Could not delete this comment.')
  }
}

// ---- Review status / reviewer assignment (TA only) ----
const reviewStatusDraft = ref('pending')
const reviewerIdDraft = ref<number | null>(null)
const savingReview = ref(false)
const reviewError = ref('')

function initReviewDraft() {
  if (!submission.value) return
  reviewStatusDraft.value = submission.value.review_status
  reviewerIdDraft.value = submission.value.assigned_reviewer_id
}

async function saveReview() {
  if (!submission.value) return

  const payload: SubmissionUpdatePayload = {}
  if (reviewStatusDraft.value !== submission.value.review_status) {
    payload.review_status = reviewStatusDraft.value
  }
  if (reviewerIdDraft.value !== submission.value.assigned_reviewer_id) {
    payload.assigned_reviewer_id = reviewerIdDraft.value
  }
  if (Object.keys(payload).length === 0) return

  reviewError.value = ''
  savingReview.value = true
  try {
    const { data } = await apiClient.patch<SubmissionPublic>(`/submissions/${submission.value.id}`, payload)
    submission.value = data
  } catch (err) {
    reviewError.value = extractErrorMessage(err, 'Could not update review status.')
  } finally {
    savingReview.value = false
  }
}

// ---- Final grade (TA only writes; staff-only reads) ----
const finalGradeDraft = reactive({ points: 0, next_step: 'grade' })
const savingFinalGrade = ref(false)
const finalGradeError = ref('')

function initFinalGradeDraft() {
  finalGradeDraft.points = finalGrade.value?.points ?? 0
  finalGradeDraft.next_step = finalGrade.value?.next_step ?? 'grade'
}

async function saveFinalGrade() {
  const payload: FinalGradeUpsertPayload = {
    points: finalGradeDraft.points,
    next_step: finalGradeDraft.next_step,
  }

  finalGradeError.value = ''
  savingFinalGrade.value = true
  try {
    const { data } = await apiClient.put<FinalGrade>(`/submissions/${props.id}/final-grade`, payload)
    finalGrade.value = data
  } catch (err) {
    finalGradeError.value = extractErrorMessage(err, 'Could not save the final grade.')
  } finally {
    savingFinalGrade.value = false
  }
}

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    const { data: sub } = await apiClient.get<SubmissionPublic>(`/submissions/${props.id}`)
    submission.value = sub
    initReviewDraft()

    const [{ data: assignmentData }, { data: jobsData }, { data: userList }] = await Promise.all([
      apiClient.get<AssignmentWithCriteria>(`/assignments/${sub.assignment_id}`),
      apiClient.get<JobPublic[]>(`/submissions/${props.id}/jobs`),
      apiClient.get<UserListItem[]>('/users'),
    ])
    assignment.value = assignmentData
    jobs.value = jobsData
    users.value = userList
    userNameById.value = Object.fromEntries(
      userList.filter((u) => u.full_name).map((u) => [u.id, u.full_name as string]),
    )

    if (isStaff.value) {
      const [commentsRes, gradesRes, plagiarismRes, finalGradeRes] = await Promise.all([
        apiClient.get<CommentModel[]>(`/submissions/${props.id}/comments`),
        apiClient.get<CriterionGradeView[]>(`/submissions/${props.id}/criterion_grades`),
        apiClient.get<PlagiarismMatchPublic[]>(`/submissions/${props.id}/plagiarism-matches`),
        apiClient.get<FinalGrade | null>(`/submissions/${props.id}/final-grade`),
      ])
      comments.value = commentsRes.data
      criterionGrades.value = gradesRes.data
      plagiarismMatches.value = plagiarismRes.data
      finalGrade.value = finalGradeRes.data
      initFinalGradeDraft()
    }
  } catch (err) {
    loadError.value = extractErrorMessage(err, 'Could not load this submission.')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAll()
  window.addEventListener('mouseup', onWindowMouseUp)
})
onUnmounted(() => window.removeEventListener('mouseup', onWindowMouseUp))
</script>

<template>
  <section class="review-page">
    <p v-if="loading" class="text-muted review-page__status">Loading…</p>
    <p v-else-if="loadError" class="form-banner form-banner-error review-page__status">{{ loadError }}</p>

    <template v-else-if="submission && assignment">
      <div class="review-topbar">
        <RouterLink :to="`/assignments/${assignment.id}`" class="text-muted review-back">
          &larr; {{ assignment.title }}
        </RouterLink>
        <h1 class="review-topbar__title">
          {{ submission.student_full_name || `Student #${submission.student_id}` }}
          <span class="text-muted review-topbar__attempt">attempt {{ submission.attempt_number }} of {{ assignment.max_attempts }}</span>
        </h1>
        <div class="review-topbar__actions">
          <button
            v-if="canGrade && draftComments.length > 0"
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="postingAllDrafts"
            @click="postAllDrafts"
          >
            {{ postingAllDrafts ? 'Posting…' : `Post all comments (${draftComments.length})` }}
          </button>
          <RouterLink
            v-if="isStaff"
            :to="{
              path: `/students/${submission.student_id}/submissions`,
              query: submission.student_full_name ? { name: submission.student_full_name } : {},
            }"
            class="review-topbar__history-link"
          >
            View all submissions by this student
          </RouterLink>
        </div>
      </div>
      <p v-if="postAllError" class="form-banner form-banner-error">{{ postAllError }}</p>

      <!-- High-level signals, ahead of the text (features/img.png's debrief header row) -->
      <div class="review-debrief">
        <section class="card card-pad">
          <p class="card-label">Submission</p>
          <div class="review-debrief__badges">
            <span
              class="badge"
              :class="submission.processed_status === 'done' ? 'badge-success' : 'badge-neutral'"
              title="Whether the background job pipeline (heuristics, etc.) has finished running on this submission yet."
            >
              Preprocessing: {{ submission.processed_status }}
            </span>
            <span
              class="badge badge-neutral"
              title="Where this submission stands in the review queue: pending, in review, or reviewed."
            >
              Review: {{ submission.review_status }}
            </span>
            <span
              v-if="isStaff"
              class="badge"
              :class="finalGrade ? 'badge-success' : 'badge-neutral'"
              title="Whether a final grade has been recorded for this submission yet."
            >
              Grade: {{ finalGrade ? 'done' : 'pending' }}
            </span>
            <span v-if="submission.is_empty" class="badge badge-danger" title="The submitted file had no non-whitespace content.">
              empty file
            </span>
          </div>
          <dl class="review-debrief__meta">
            <div>
              <dt class="text-muted">Submitted</dt>
              <dd>{{ formatDate(submission.submitted_at) }}</dd>
            </div>
            <div>
              <dt class="text-muted">Deadline</dt>
              <dd>{{ formatDate(assignment.deadline_at) }}</dd>
            </div>
            <div>
              <dt class="text-muted">Lines</dt>
              <dd>{{ submission.line_count ?? 0 }}</dd>
            </div>
            <div v-if="isStaff">
              <dt class="text-muted">Reviewer</dt>
              <dd>{{ userLabel(submission.assigned_reviewer_id) ?? 'Unassigned' }}</dd>
            </div>
          </dl>

          <form v-if="canGrade" class="review-status-edit" @submit.prevent="saveReview">
            <p v-if="reviewError" class="form-banner form-banner-error">{{ reviewError }}</p>
            <div class="field">
              <label for="review-status">Review status</label>
              <select id="review-status" v-model="reviewStatusDraft" class="input">
                <option value="pending">pending</option>
                <option value="in_review">in_review</option>
                <option value="reviewed">reviewed</option>
              </select>
            </div>
            <div class="field">
              <label for="reviewer-id">Reviewer</label>
              <select id="reviewer-id" v-model="reviewerIdDraft" class="input">
                <option :value="null">Unassigned</option>
                <option v-for="user in reviewerOptions" :key="user.id" :value="user.id">
                  {{ user.full_name || user.email }}
                </option>
              </select>
            </div>
            <button type="submit" class="btn btn-primary btn-sm" :disabled="savingReview">
              {{ savingReview ? 'Saving…' : 'Save' }}
            </button>
          </form>
        </section>

        <section v-if="isStaff" class="card card-pad">
          <p class="card-label">Plagiarism (cross-check)</p>
          <ul v-if="plagiarismMatches.length > 0" class="review-debrief__list">
            <li v-for="match in plagiarismMatches" :key="match.id">
              <span class="badge" :class="match.similarity_pct >= 25 ? 'badge-danger' : 'badge-neutral'">{{ match.similarity_pct }}%</span>
              <span class="text-muted">vs. submission #{{ match.matched_submission_id }}</span>
              <span v-if="match.note" class="text-muted">{{ match.note }}</span>
            </li>
          </ul>
          <p v-else class="text-muted">N/A &mdash; not yet evaluated.</p>
        </section>

        <section class="card card-pad">
          <p class="card-label">Pre-checks</p>
          <ul class="review-debrief__list">
            <li v-for="(check, index) in heuristicsChecks" :key="index" class="review-debrief__check">
              <span class="review-debrief__dot" :style="{ background: check.color }"></span>
              <span class="review-debrief__check-rubric">{{ check.rubric }}</span>
              <span class="text-muted">{{ check.comment }}</span>
            </li>
            <li v-if="heuristicsChecks.length === 0" class="text-muted">Still processing…</li>
          </ul>
        </section>
      </div>

      <div class="review-columns" :class="{ 'review-columns--no-rubric': !isStaff }">
        <aside class="review-aside card card-pad">
          <p class="card-label">Assignment condition</p>
          <pre class="review-condition text-mono">{{ assignment.condition_markdown }}</pre>
        </aside>

        <section class="card review-main">
          <div class="review-main__head">
            <p class="card-label">{{ submission.line_count ?? 0 }} lines</p>
            <p v-if="canGrade" class="text-muted review-main__hint">Drag on the line numbers to comment on a range</p>
          </div>

          <p v-if="commentsError" class="form-banner form-banner-error review-main__error">{{ commentsError }}</p>

          <div class="review-text">
            <template v-for="(line, idx) in textLines" :key="idx">
              <div
                class="review-line"
                :class="[
                  lineRangeInfo[idx + 1] ? `review-line--${lineRangeInfo[idx + 1].status}` : '',
                  { 'review-line--range-start': lineRangeInfo[idx + 1]?.isStart },
                  { 'review-line--range-end': lineRangeInfo[idx + 1]?.isEnd },
                ]"
              >
                <span
                  class="review-line__gutter text-mono text-muted"
                  :class="{ 'review-line__gutter--draggable': canGrade }"
                  @mousedown="onGutterMouseDown(idx + 1)"
                  @mouseenter="onGutterMouseEnter(idx + 1)"
                  >{{ idx + 1 }}</span
                >
                <span class="review-line__content text-mono">{{ line || ' ' }}</span>
              </div>

              <article
                v-for="comment in commentsByEndLine[idx + 1] || []"
                :key="comment.id"
                class="review-comment"
                :class="[`review-comment--${comment.status}`, { 'review-comment--auto': comment.source_job_id }]"
              >
                <div class="review-comment__head">
                  <span class="badge" :class="`badge-${comment.status === 'sent' ? 'success' : comment.status === 'suggested' ? 'warning' : comment.status === 'dismissed' ? 'danger' : 'neutral'}`">
                    {{ comment.status }}
                  </span>
                  <span v-if="comment.source_job_id" class="badge badge-primary">auto-suggested</span>
                  <span class="text-muted">{{ userLabel(comment.author_id) ?? 'unassigned' }}</span>
                </div>

                <div v-if="editingCommentId === comment.id" class="review-comment__edit">
                  <textarea v-model="commentDraft.body" class="textarea"></textarea>
                  <select v-model="commentDraft.status" class="input">
                    <option value="draft">draft</option>
                    <option value="suggested">suggested</option>
                    <option value="sent">sent</option>
                    <option value="dismissed">dismissed</option>
                  </select>
                  <div class="form-actions">
                    <button type="button" class="btn btn-primary btn-sm" @click="saveCommentEdit(comment)">Save</button>
                    <button type="button" class="btn btn-outline btn-sm" @click="cancelEditComment">Cancel</button>
                  </div>
                </div>
                <p v-else class="review-comment__body">{{ comment.body }}</p>

                <div v-if="canGrade && editingCommentId !== comment.id" class="review-comment__actions">
                  <button type="button" class="btn btn-outline btn-sm" @click="startEditComment(comment)">Edit</button>
                  <button type="button" class="btn btn-outline btn-sm" @click="removeComment(comment)">Delete</button>
                </div>
              </article>

              <article v-if="composerRange && composerRange.end === idx + 1" class="review-comment review-comment--composer">
                <p class="text-muted review-comment__range">
                  Commenting on lines {{ composerRange.start }}&ndash;{{ composerRange.end }}
                </p>
                <textarea v-model="composerBody" class="textarea" placeholder="Leave a comment…" autofocus></textarea>
                <div class="form-actions">
                  <button type="button" class="btn btn-outline btn-sm" :disabled="addingComment" @click="submitComposer('draft')">
                    Save draft
                  </button>
                  <button type="button" class="btn btn-primary btn-sm" :disabled="addingComment" @click="submitComposer('sent')">
                    Send
                  </button>
                  <button type="button" class="btn btn-outline btn-sm" @click="cancelComposer">Cancel</button>
                </div>
              </article>
            </template>
          </div>
        </section>

        <aside v-if="isStaff" class="review-aside card card-pad">
          <p class="card-label">Rubric</p>
          <ul class="grade-list">
            <li v-for="grade in criterionGrades" :key="grade.criterion_id" class="grade-row">
              <div>
                <p class="grade-row__title">{{ grade.title }}</p>
                <p class="text-muted grade-row__points">{{ grade.min_points ?? 0 }}&ndash;{{ grade.max_points }} pts</p>
                <p v-if="grade.comment" class="text-muted grade-row__comment">{{ grade.comment }}</p>
              </div>
              <span class="badge" :class="criterionBadgeClass(grade.status)">{{ grade.status }}</span>
            </li>
            <li v-if="criterionGrades.length === 0" class="text-muted">No rubric criteria yet.</li>
          </ul>
        </aside>
      </div>

      <section v-if="isStaff" class="card card-pad final-grade-card">
        <p class="card-label">Final grade</p>

        <template v-if="canGrade">
          <p v-if="finalGradeError" class="form-banner form-banner-error">{{ finalGradeError }}</p>
          <form class="final-grade-form" @submit.prevent="saveFinalGrade">
            <div class="final-grade-form__fields">
              <div class="field">
                <label for="final-grade-points">Points</label>
                <input id="final-grade-points" v-model.number="finalGradeDraft.points" type="number" min="0" step="0.5" class="input" required />
              </div>
              <div class="field">
                <label for="final-grade-next-step">Next step</label>
                <select id="final-grade-next-step" v-model="finalGradeDraft.next_step" class="input">
                  <option value="grade">grade</option>
                  <option value="remediate">remediate</option>
                </select>
              </div>
            </div>
            <button type="submit" class="btn btn-primary btn-sm" :disabled="savingFinalGrade">
              {{ savingFinalGrade ? 'Saving…' : 'Save final grade' }}
            </button>
          </form>
        </template>
        <p v-else-if="finalGrade" class="text-muted">{{ finalGrade.points }} pts &middot; next step: {{ finalGrade.next_step }}</p>
        <p v-else class="text-muted">Not graded yet.</p>
      </section>
    </template>
  </section>
</template>

<style scoped>
/* Deliberately not `.container` — this page is meant to fill the screen
   (features/img.png), not sit in the app's usual 1120px column. */
.review-page {
  width: 100%;
  max-width: 2200px;
  margin: 0 auto;
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.review-page__status {
  padding: var(--space-6);
}

.review-topbar {
  display: flex;
  align-items: baseline;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.review-back {
  font-size: var(--text-sm);
}

.review-topbar__title {
  font-size: var(--text-2xl);
  font-weight: 700;
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.review-topbar__attempt {
  font-size: var(--text-sm);
  font-weight: 400;
}

.review-topbar__actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-left: auto;
}

.review-topbar__history-link {
  font-size: var(--text-sm);
}

/* ---- Debrief row ---- */
.review-debrief {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-4);
  align-items: start;
}

.review-debrief__badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.review-debrief__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  margin: 0;
  font-size: var(--text-sm);
}

.review-debrief__meta dt {
  font-size: var(--text-xs);
}

.review-debrief__meta dd {
  margin: 0;
  font-weight: 600;
}

.review-debrief__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  font-size: var(--text-sm);
}

.review-debrief__check {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.review-debrief__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
}

.review-debrief__check-rubric {
  font-weight: 600;
}

.review-status-edit {
  display: flex;
  align-items: flex-end;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.review-status-edit .field {
  margin-bottom: 0;
}

/* ---- Three-column review layout ---- */
.review-columns {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 320px;
  gap: var(--space-4);
  align-items: start;
}

.review-columns--no-rubric {
  grid-template-columns: 300px minmax(0, 1fr);
}

.review-aside {
  position: sticky;
  top: calc(var(--header-height) + var(--space-4));
  max-height: calc(100vh - var(--header-height) - var(--space-8));
  overflow-y: auto;
}

.review-condition {
  margin: 0;
  white-space: pre-wrap;
  font-size: var(--text-sm);
}

.review-main {
  padding: var(--space-4);
  min-width: 0;
}

.review-main__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.review-main__hint {
  font-size: var(--text-xs);
}

.review-main__error {
  margin-bottom: var(--space-3);
}

.review-text {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.review-line {
  display: flex;
  gap: var(--space-3);
  padding: 1px var(--space-3);
  border-style: solid;
  border-color: transparent;
  border-width: 0 3px;
}

.review-line--range-start {
  border-top-width: 3px;
  border-top-left-radius: var(--radius-sm);
  border-top-right-radius: var(--radius-sm);
  margin-top: var(--space-1);
}

.review-line--range-end {
  border-bottom-width: 3px;
  border-bottom-left-radius: var(--radius-sm);
  border-bottom-right-radius: var(--radius-sm);
  margin-bottom: var(--space-1);
}

.review-line--draft {
  background: var(--color-neutral-bg);
  border-color: var(--color-neutral);
}

.review-line--suggested {
  background: var(--color-warning-bg);
  border-color: var(--color-warning);
}

.review-line--sent {
  background: var(--color-success-bg);
  border-color: var(--color-success);
}

.review-line--dismissed {
  background: var(--color-danger-bg);
  border-color: var(--color-danger);
}

.review-line--selecting {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
}

.review-line__gutter {
  flex: none;
  width: 3ch;
  text-align: right;
  user-select: none;
  font-size: var(--text-sm);
}

.review-line__gutter--draggable {
  cursor: crosshair;
}

.review-line__gutter--draggable:hover {
  color: var(--color-primary);
  font-weight: 600;
}

.review-line__content {
  font-size: var(--text-sm);
  white-space: pre-wrap;
  word-break: break-word;
}

.review-comment {
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  border-left: 4px solid var(--color-neutral);
  padding: var(--space-3) var(--space-4);
}

.review-comment--suggested {
  border-left-color: var(--color-warning);
}

.review-comment--sent {
  border-left-color: var(--color-success);
}

.review-comment--dismissed {
  border-left-color: var(--color-danger);
}

.review-comment--auto {
  background: var(--color-primary-bg);
}

.review-comment--composer {
  border-left-color: var(--color-primary);
  background: var(--color-primary-bg);
}

.review-comment__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  font-size: var(--text-sm);
}

.review-comment__body {
  font-size: var(--text-sm);
  line-height: 1.6;
  margin: 0;
}

.review-comment__edit {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.review-comment__actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.review-comment__range {
  font-size: var(--text-xs);
  margin-bottom: var(--space-2);
}

/* ---- Rubric (right column) ---- */
.grade-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.grade-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-top: 1px solid var(--color-border);
}

.grade-row:first-child {
  border-top: none;
}

.grade-row__title {
  font-size: var(--text-sm);
  font-weight: 600;
}

.grade-row__points,
.grade-row__comment {
  font-size: var(--text-xs);
}

/* ---- Final grade ---- */
.final-grade-card {
  align-self: stretch;
}

.final-grade-form {
  display: flex;
  align-items: flex-end;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.final-grade-form__fields {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.final-grade-form__fields .field {
  min-width: 140px;
  margin-bottom: 0;
}

@media (max-width: 1000px) {
  .review-columns,
  .review-columns--no-rubric {
    grid-template-columns: 1fr;
  }

  .review-aside {
    position: static;
    max-height: none;
  }
}
</style>
