// Every datetime the API returns is naive-UTC (app/models.py's _utcnow()) —
// the JSON has no timezone marker at all, e.g. "2026-10-05T20:59:00". Per
// the ECMA-262 grammar, `new Date(...)` treats a date-ONLY string as UTC but
// a date-TIME string with no offset as LOCAL time — so parsing an API
// timestamp directly silently shifts it by the viewer's UTC offset. Append
// "Z" (unless a zone is already present) before parsing anything from the
// backend.
export function parseApiDate(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`)
}

// Inverse direction: format a Date as a `datetime-local` input value
// ("YYYY-MM-DDTHH:mm") in the viewer's own local time, so editing a deadline
// shows the same local time the read-only views already display via
// parseApiDate + Intl.DateTimeFormat.
export function toDatetimeLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
