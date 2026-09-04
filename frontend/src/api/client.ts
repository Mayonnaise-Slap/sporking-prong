import axios from 'axios'

import { clearToken, getToken } from '@/auth/tokenStorage'

// Base URL points at the FastAPI app (app/main.py, port 8000 per
// features/backend_is.md). Override per-environment via VITE_API_BASE_URL.
const baseURL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export const apiClient = axios.create({ baseURL })

apiClient.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken()
    }
    return Promise.reject(error)
  },
)
