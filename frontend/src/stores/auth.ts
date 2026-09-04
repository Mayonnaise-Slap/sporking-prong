import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiClient } from '@/api/client'
import { clearToken, getToken, setToken } from '@/auth/tokenStorage'
import type {
  RestoreConfirmPayload,
  RestoreRequestPayload,
  TokenResponse,
  UserLoginPayload,
  UserPublic,
  UserRegisterPayload,
} from '@/types/api'
import type { User } from '@/types/models'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const user = ref<User | null>(null)

  const isAuthenticated = computed(() => token.value !== null)

  function applyToken(value: string) {
    token.value = value
    setToken(value)
  }

  async function login(payload: UserLoginPayload) {
    const { data } = await apiClient.post<TokenResponse>('/auth/login', payload)
    applyToken(data.access_token)
    await fetchMe()
  }

  // POST /auth/register only creates the account (returns UserPublic, no
  // token) — there's no auto-login on the backend, so log in with the same
  // credentials right after to get a usable session.
  async function register(payload: UserRegisterPayload) {
    await apiClient.post<UserPublic>('/auth/register', payload)
    await login({ email: payload.email, password: payload.password })
  }

  async function fetchMe() {
    const { data } = await apiClient.get<User>('/auth/me')
    user.value = data
    return data
  }

  // Called once at startup: if a token survived a reload, confirm it's
  // still valid and load the user. The client's response interceptor
  // already clears an invalid token on a 401, so a failure here just
  // leaves the store logged out.
  async function initialize() {
    if (token.value) {
      try {
        await fetchMe()
      } catch {
        logout()
      }
    }
  }

  async function restoreRequest(payload: RestoreRequestPayload) {
    await apiClient.post('/auth/restore', payload)
  }

  async function restoreConfirm(payload: RestoreConfirmPayload) {
    await apiClient.post('/auth/restore/confirm', payload)
  }

  function logout() {
    token.value = null
    user.value = null
    clearToken()
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    register,
    fetchMe,
    initialize,
    restoreRequest,
    restoreConfirm,
    logout,
  }
})
