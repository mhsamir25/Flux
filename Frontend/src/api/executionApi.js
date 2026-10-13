import axios from 'axios'

import usePipelineStore from '../store/pipelineStore'

// Base URL configurable via .env (VITE_API_BASE_URL); defaults to the backend's Uvicorn
// dev port. The previous version of this client (before it existed) was hardcoded to 8001
// in a stray console warning — the real backend runs on 8000.
const executionApi = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
})

// Attach the JWT only if one exists — every route this client talks to works fine with no
// token at all (guest mode, PLAN.md §12); this interceptor never blocks a request for lack
// of one.
executionApi.interceptors.request.use((config) => {
  const token = usePipelineStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On a 401 from a protected route, surface the login modal rather than a silent failure
// (PLAN.md §13). The modal itself isn't built until a later checkpoint; this just flips the
// store flag it will read once it exists.
executionApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      usePipelineStore.getState().setShowAuthModal(true)
    }
    return Promise.reject(error)
  }
)

export default executionApi
