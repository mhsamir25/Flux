import { useState } from 'react'

import useAuth from '../../hooks/useAuth'

const inputClass = 'ui-input'


export default function AuthModal({ onClose, onSuccess }) {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const user = mode === 'login' ? await login(email, password) : await register(email, password)
      onSuccess?.(user)
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="ui-backdrop" onClick={onClose}>
      <div
        className="ui-modal w-80 p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
          {mode === 'login' ? 'Sign In' : 'Create Account'}
        </h2>

        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          <input
            type="email"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            className={inputClass}
          />
          <input
            type="password"
            required
            minLength={3}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            className={inputClass}
          />
          {error && <p className="text-xs text-[var(--error)]">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="ui-btn ui-btn-primary w-full py-1.5"
          >
            {submitting ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login')
            setError(null)
          }}
          className="ui-btn ui-btn-ghost mt-2 w-full"
        >
          {mode === 'login' ? "Don't have an account? Register" : 'Already have an account? Sign in'}
        </button>

        <button
          type="button"
          onClick={onClose}
          className="ui-btn ui-btn-default mt-3 w-full py-1.5"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
