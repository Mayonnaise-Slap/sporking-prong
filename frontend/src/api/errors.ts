import axios from 'axios'

// FastAPI's default error shape is { detail: string } for a raised
// HTTPException, or { detail: [{ msg, loc, ... }] } for a 422 validation
// error. Both show up across every form (login/register/restore/assignment
// creation), so this is genuine shared logic, not speculative reuse.
export function extractErrorMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const messages = detail.map((item) => item?.msg).filter(Boolean)
      if (messages.length) return messages.join('; ')
    }
  }
  return fallback
}
