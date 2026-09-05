// Request/response DTOs, matching app/schemas.py field-for-field. Distinct
// from types/models.ts (the ORM row shape) because a few DTOs diverge from
// their table — UserPublic still drops group_label (nobody's asked for it
// yet), AssignmentPublic doesn't nest criteria, etc. Comment and FinalGrade
// happen to be identical to their ORM rows, so those two are reused directly
// from types/models.ts rather than redeclared here.
import type { Assignment, RubricCriterion } from '@/types/models'

export interface UserRegisterPayload {
  email: string
  password: string
  full_name?: string
  is_ta: boolean
  is_supervisor: boolean
}

export interface UserLoginPayload {
  email: string
  password: string
}

export interface UserPublic {
  id: number
  email: string
  full_name: string | null
  is_active: boolean
  is_ta: boolean
  is_supervisor: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

// GET /users — unauthenticated, lists every user (app/routers/auth.py's
// users_router). Used to resolve author/reviewer/student ids to display
// names anywhere the resource's own DTO only carries an id.
export interface UserListItem {
  id: number
  full_name: string | null
  email: string
}

export interface RestoreRequestPayload {
  email: string
}

export interface RestoreConfirmPayload {
  email: string
  code: string
  new_password: string
}

export interface RubricCriterionCreatePayload {
  title: string
  max_points: number
  min_points: number | null
}

// PATCH /assignments/{id}/criteria/{criterion_id} applies only the keys
// present in the JSON body (backend uses model_dump(exclude_unset=True)) —
// build this with only the fields the user actually changed, not all three.
export interface RubricCriterionUpdatePayload {
  title?: string
  max_points?: number
  min_points?: number | null
}

export interface AssignmentCreatePayload {
  title: string
  condition_markdown: string
  deadline_at: string
  max_attempts: number
  pass_threshold_points: number
  criteria: RubricCriterionCreatePayload[]
}

// PATCH /assignments/{id} — same exclude_unset semantics as
// RubricCriterionUpdatePayload: only send the keys that actually changed.
export interface AssignmentUpdatePayload {
  title?: string
  condition_markdown?: string
  deadline_at?: string
  max_attempts?: number
  pass_threshold_points?: number
}

export type AssignmentWithCriteria = Assignment & { criteria: RubricCriterion[] }

// GET/POST .../submissions response shape (SubmissionPublic) — narrower than
// the Submission ORM row in types/models.ts: no reviewed_at (the API still
// doesn't expose it), but does carry a joined student_full_name and
// assigned_reviewer_id (Appendix 2 additions).
export interface SubmissionPublic {
  id: number
  assignment_id: number
  student_id: number
  student_full_name: string | null
  attempt_number: number
  submitted_at: string
  original_file_id: number
  processed_text: string
  processed_status: string
  line_count: number | null
  is_empty: boolean
  assigned_reviewer_id: number | null
  review_status: string
  created_at: string
}

// PATCH /submissions/{id} — exclude_unset, same as the other *UpdatePayload
// types: only send the keys that actually changed.
export interface SubmissionUpdatePayload {
  review_status?: string
  assigned_reviewer_id?: number | null
}

// Only "heuristics" (app/jobs.py) is implemented; this is its actual result
// shape — a checklist of items, not documented anywhere in
// features/backend_is.md, found by reading the handler directly (Appendix
// 3). `color` is a raw hex string chosen by the backend (e.g. "#22c55e"),
// meant to be used directly as a status-dot color rather than mapped
// through the frontend's own token names.
export interface HeuristicsCheckItem {
  rubric: string
  color: string
  comment: string
}

// "cross_check" job's result (app/crosscheck.py CrossCheckReport.as_dict()).
// `matches` here duplicates what GET /submissions/{id}/plagiarism-matches
// returns (same data, persisted as PlagiarismMatch rows) — this is the
// report-level summary (overall_similarity_pct/threshold/flagged/
// provisional) that isn't stored anywhere else.
export interface CrossCheckMatch {
  matched_submission_id: number
  similarity_pct: number
  note: string
  spans: Array<{ start_line: number; end_line: number; matched_start_line: number; matched_end_line: number }>
}

export interface CrossCheckReport {
  overall_similarity_pct: number
  threshold_pct: number
  flagged: boolean
  provisional: boolean
  cohort_complete: boolean
  cohort_size: number
  boilerplate_filtered: boolean
  boilerplate_tokens: number
  cohort_overlap_pct: number
  reference_tokens: number
  reference_overlap_pct: number
  matches: CrossCheckMatch[]
}

// GET /submissions/{id}/jobs — deliberately narrower than the Job ORM row:
// no submission_id/created_at/started_at/finished_at/error_message. Result
// shape is job_type-specific: a list of debrief items for "heuristics", a
// CrossCheckReport object for "cross_check".
export interface JobPublic {
  id: number
  job_type: string
  status: string
  result: HeuristicsCheckItem[] | CrossCheckReport | null
}

export interface CommentCreatePayload {
  start_line: number
  end_line: number
  body: string
  status?: string
  author_id?: number | null
  source_comment_id?: number | null
}

export interface CommentUpdatePayload {
  body?: string
  status?: string
}

// GET /submissions/{id}/criterion_grades — every RubricCriterion for the
// submission's assignment, joined with its CriterionGrade if one exists
// (defaulting to status "unmarked"/comment null otherwise). Read-only: there
// is no write endpoint yet (see Appendix 2 / Known gaps).
export interface CriterionGradeView {
  criterion_id: number
  order_index: number
  title: string
  max_points: number
  min_points: number | null
  status: string
  comment: string | null
  updated_at: string | null
}

// GET /submissions/{id}/plagiarism-matches — narrower than the PlagiarismMatch
// ORM row: no job_id or submission_id (both implied by the URL already).
export interface PlagiarismMatchPublic {
  id: number
  matched_submission_id: number
  similarity_pct: number
  matched_spans: Array<{ start_line: number; end_line: number }> | null
  note: string | null
  created_at: string
}

// PUT /submissions/{id}/final-grade — upserts. The matching GET can return a
// bare `null` body (200 OK) when no grade has been set yet, not a 404.
export interface FinalGradeUpsertPayload {
  points: number
  next_step?: string
}
