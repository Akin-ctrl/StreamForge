import { Navigate, useLocation } from 'react-router-dom'

import { isAuthenticated } from './session'

type ProtectedRouteProps = {
  children: React.ReactNode
}

/**
 * Blocks access to private pages when no access token is present.
 * The requested path is preserved in router state for post-login redirect.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const location = useLocation()

  if (!isAuthenticated()) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}
