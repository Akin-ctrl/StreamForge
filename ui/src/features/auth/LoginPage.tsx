import { FormEvent, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { login } from '../../shared/api/client'
import { setAccessToken } from '../../shared/auth/session'

type LocationState = {
  from?: string
}

/**
 * Login screen for control-plane authentication.
 * Redirects users back to their original protected route when available.
 */
export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const state = location.state as LocationState | null

  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin123')
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  // Handles token exchange and route transition after successful auth.
  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setIsLoading(true)
    try {
      const token = await login(username, password)
      setAccessToken(token.access_token)
      navigate(state?.from || '/gateways', { replace: true })
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Login failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="login-page">
      <form className="card" onSubmit={onSubmit}>
        <h2>Control Plane Login</h2>
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
        {error && <p className="error">{error}</p>}
        <button className="btn" disabled={isLoading} type="submit">
          {isLoading ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
