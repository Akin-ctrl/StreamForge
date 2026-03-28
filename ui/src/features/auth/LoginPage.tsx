import { FormEvent, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import {
  bootstrapFirstUser,
  getBootstrapStatus,
  login,
} from '../../shared/api/client'
import { setAccessToken } from '../../shared/auth/session'

type LocationState = {
  from?: string
}

type AuthMode = 'loading' | 'login' | 'bootstrap'

/**
 * Login screen for control-plane authentication.
 * Redirects users back to their original protected route when available.
 */
export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const state = location.state as LocationState | null

  const [mode, setMode] = useState<AuthMode>('loading')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    let active = true

    getBootstrapStatus()
      .then((status) => {
        if (!active) {
          return
        }
        setMode(status.bootstrap_required ? 'bootstrap' : 'login')
      })
      .catch(() => {
        if (!active) {
          return
        }
        setMode('login')
      })

    return () => {
      active = false
    }
  }, [])

  // Handles token exchange and route transition after successful auth.
  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setIsLoading(true)
    try {
      if (mode === 'bootstrap' && password !== confirmPassword) {
        throw new Error('Passwords do not match')
      }

      const token =
        mode === 'bootstrap'
          ? await bootstrapFirstUser(username, password)
          : await login(username, password)
      setAccessToken(token.access_token)
      navigate(state?.from || '/gateways', { replace: true })
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Login failed')
    } finally {
      setIsLoading(false)
    }
  }

  const title = mode === 'bootstrap' ? 'Create First Admin' : 'Control Plane Login'
  const description =
    mode === 'bootstrap'
      ? 'This deployment has no users yet. Create the first admin account to bootstrap the control plane.'
      : 'Sign in with a built-in control-plane account.'
  const submitLabel = isLoading
    ? mode === 'bootstrap'
      ? 'Creating account...'
      : 'Signing in...'
    : mode === 'bootstrap'
      ? 'Create Admin Account'
      : 'Sign in'

  if (mode === 'loading') {
    return (
      <div className="login-page">
        <div className="card">
          <h2>Loading authentication...</h2>
          <p className="muted">Checking whether this control plane needs first-user bootstrap.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="login-page">
      <form className="card" onSubmit={onSubmit}>
        <h2>{title}</h2>
        <p className="muted">{description}</p>
        <label>
          Username
          <input value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {mode === 'bootstrap' && (
          <label>
            Confirm Password
            <input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </label>
        )}
        {error && <p className="error">{error}</p>}
        <button className="btn" disabled={isLoading} type="submit">
          {submitLabel}
        </button>
      </form>
    </div>
  )
}
