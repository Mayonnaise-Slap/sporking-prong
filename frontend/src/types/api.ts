// Request/response DTOs, matching app/schemas.py field-for-field. Distinct
// from types/models.ts (the ORM row shape) because a few DTOs diverge from
// their table — UserPublic still drops group_label (nobody's asked for it
// yet), AssignmentPublic doesn't nest criteria, etc.
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
// the Submission ORM row in types/models.ts: no assigned_reviewer_id or
// reviewed_at, neither of which the API exposes yet.
export interface SubmissionPublic {
  id: number
  assignment_id: number
  student_id: number
  attempt_number: number
  submitted_at: string
  original_file_id: number
  processed_text: string
  processed_status: string
  line_count: number | null
  is_empty: boolean
  review_status: string
  created_at: string
}
