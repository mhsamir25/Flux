import { useCallback } from 'react'

import executionApi from '../api/executionApi'
import usePipelineStore from '../store/pipelineStore'

// fastapi-users returns error codes as a plain string `detail` (verified directly against
// the running backend, not assumed — e.g. {"detail": "REGISTER_USER_ALREADY_EXISTS"} on a
// duplicate email, {"detail": "LOGIN_BAD_CREDENTIALS"} on a bad login). Known codes get a
// friendly message; anything unrecognized still degrades to readable text instead of a raw
// SCREAMING_SNAKE_CASE code.
const ERROR_MESSAGES = {
  REGISTER_USER_ALREADY_EXISTS: 'An account with this email already exists.',
  LOGIN_BAD_CREDENTIALS: 'Incorrect email or password.',
  LOGIN_USER_NOT_VERIFIED: 'Please verify your email before signing in.',
}

function humanizeAuthError(err) {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') {
    return ERROR_MESSAGES[detail] || detail.replaceAll('_', ' ').toLowerCase()
  }
  if (detail?.reason) return detail.reason
  return 'Something went wrong. Please try again.'
}

export default function useAuth() {
  const accessToken = usePipelineStore((s) => s.accessToken)
  const username = usePipelineStore((s) => s.username)
  const setAuth = usePipelineStore((s) => s.setAuth)
  const clearAuth = usePipelineStore((s) => s.clearAuth)

  // Bypasses the axios interceptor's "attach token from the store" behavior on purpose —
  // this runs *before* the token is in the store yet (bootstrapping right after login, or
  // restoring a session from localStorage).
  const fetchCurrentUser = useCallback(async (token) => {
    const res = await executionApi.get('/api/users/me', { headers: { Authorization: `Bearer ${token}` } })
    return res.data
  }, [])

  const login = useCallback(
    async (email, password) => {
      // fastapi-users' login route is OAuth2PasswordRequestForm — form-encoded, field named
      // `username` even though it holds the email — not JSON (verified against the real
      // endpoint; a JSON body gets silently ignored/422'd).
      const params = new URLSearchParams()
      params.append('username', email)
      params.append('password', password)
      try {
        const res = await executionApi.post('/api/auth/jwt/login', params)
        const token = res.data.access_token
        const user = await fetchCurrentUser(token)
        setAuth(token, user.email)
        return user
      } catch (err) {
        throw new Error(humanizeAuthError(err))
      }
    },
    [fetchCurrentUser, setAuth]
  )

  const register = useCallback(
    async (email, password) => {
      try {
        await executionApi.post('/api/auth/register', { email, password })
      } catch (err) {
        throw new Error(humanizeAuthError(err))
      }
      return login(email, password) // register doesn't itself return a token
    },
    [login]
  )

  const logout = useCallback(() => clearAuth(), [clearAuth])

  // Called once on app mount to restore a session from a previously-stored token. Re-fetches
  // the real user (rather than trusting a possibly-stale/expired stored token blindly) —
  // this also doubles as the "is this token still valid" check.
  const restore = useCallback(async () => {
    const token = localStorage.getItem('flux_access_token')
    if (!token) return
    try {
      const user = await fetchCurrentUser(token)
      setAuth(token, user.email)
    } catch {
      clearAuth()
    }
  }, [fetchCurrentUser, setAuth, clearAuth])

  return { isGuest: !accessToken, username, login, register, logout, restore }
}
