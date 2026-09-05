// Mirrors the SQLModel tables in app/models.py, as designed in
// features/corebackmodels.md. Field shapes here are informal (matching the
// backend's own "not enforced by the schema" JSON blobs), not generated from
// an OpenAPI spec — keep in sync by hand as the backend evolves.

export interface User {
  id: number
  email: string
  full_name: string | null
  group_label?: string | null
  is_supervisor: boolean
  is_ta: boolean
  is_active: boolean
}

export interface Assignment {
  id: number
  title: string
  condition_markdown: string
  deadline_at: string
  max_attempts: number
  pass_threshold_points: number
  created_by_id: number
  created_at: string
}

export interface RubricCriterion {
  id: number
  assignment_id: number
  order_index: number
  title: string
  max_points: number
  min_points: number | null
}

export type ProcessedStatus = 'pending' | 'done'
export type ReviewStatus = 'pending' | 'in_review' | 'reviewed'

export interface Submission {
  id: number
  assignment_id: number
  student_id: number
  attempt_number: number
  submitted_at: string
  original_file_id: number
  processed_text: string
  processed_status: ProcessedStatus
  line_count: number | null
  is_empty: boolean
  assigned_reviewer_id: number | null
  review_status: ReviewStatus
  reviewed_at: string | null
  created_at: string
}

export interface SubmissionFile {
  id: number
  original_filename: string
  content_type?: string | null
  size_bytes: number
  created_at: string
}

export type JobType =
  | 'heuristics'
  | 'cross_check'
  | 'ai_detection'
  | 'common_mistake_scan'
  | 'rubric_grading'

export type JobStatus = 'pending' | 'running' | 'succeeded' | 'failed'

export interface Job<TResult = unknown> {
  id: number
  submission_id: number
  job_type: JobType
  status: JobStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  result: TResult
}

export interface PlagiarismMatch {
  id: number
  job_id: number
  submission_id: number
  matched_submission_id: number
  similarity_pct: number
  matched_spans?: Array<{ start_line: number; end_line: number }> | null
  note?: string | null
  created_at: string
}

export type CriterionGradeStatus = 'unmarked' | 'none' | 'partial' | 'full'

export interface CriterionGrade {
  id: number
  submission_id: number
  criterion_id: number
  status: CriterionGradeStatus
  comment?: string | null
  updated_at: string
}

export type CommentStatus = 'draft' | 'suggested' | 'sent' | 'dismissed'

export interface Comment {
  id: number
  submission_id: number
  start_line: number
  end_line: number
  body: string
  author_id: number | null
  source_comment_id: number | null
  source_job_id: number | null
  status: CommentStatus
  created_at: string
  updated_at: string
  sent_at: string | null
}

export interface FinalGrade {
  id: number
  submission_id: number
  points: number
  assigned_by_id: number
  assigned_at: string
  next_step: 'grade' | 'remediate'
}
