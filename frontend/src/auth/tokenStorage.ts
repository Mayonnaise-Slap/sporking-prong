// Plain (non-reactive) bearer-token persistence, kept separate from the
// Pinia auth store so the axios client (src/api/client.ts) can read/clear the
// token without importing Pinia state — avoids a store <-> client import
// cycle and keeps the client usable before an app/pinia instance exists.
const STORAGE_KEY = 'taco.auth.token'

export function getToken(): string | null {
  return localStorage.getItem(STORAGE_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(STORAGE_KEY)
}
