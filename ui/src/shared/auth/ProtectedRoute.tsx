import { Navigate, useLocation } from 'react-router-dom'

import { useAuthSession } from './AuthProvider'

type ProtectedRouteProps = {
  children: React.ReactNode
}

/**
 * Blocks access to private pages until the browser session is confirmed.
 * The requested path is preserved in router state for post-login redirect.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const location = useLocation()
  const { isAuthenticated, isLoading } = useAuthSession()

  if (isLoading) {
    return (
      <div className="login-page">
        <div className="card">
          <h2>Loading session...</h2>
          <p className="muted">Checking the current control-plane session.</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}
