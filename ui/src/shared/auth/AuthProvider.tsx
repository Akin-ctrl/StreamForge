import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { getCurrentUser, logout as logoutRequest } from '../api/client'

type AuthSessionContextValue = {
  isAuthenticated: boolean
  isLoading: boolean
  refreshSession: () => Promise<void>
  logout: () => Promise<void>
}

const AuthSessionContext = createContext<AuthSessionContextValue | null>(null)

type AuthProviderProps = {
  children: React.ReactNode
}

/**
 * Resolves browser auth state from the control-plane session cookie.
 * The UI no longer persists bearer tokens in localStorage.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  const refreshSession = useCallback(async () => {
    setIsLoading(true)
    try {
      await getCurrentUser()
      setIsAuthenticated(true)
    } catch {
      setIsAuthenticated(false)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      await logoutRequest()
    } catch {
      // Treat logout as best-effort for the browser session.
    } finally {
      setIsAuthenticated(false)
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshSession()
  }, [refreshSession])

  const value = useMemo<AuthSessionContextValue>(
    () => ({
      isAuthenticated,
      isLoading,
      refreshSession,
      logout,
    }),
    [isAuthenticated, isLoading, logout, refreshSession],
  )

  return <AuthSessionContext.Provider value={value}>{children}</AuthSessionContext.Provider>
}

export function useAuthSession(): AuthSessionContextValue {
  const context = useContext(AuthSessionContext)
  if (!context) {
    throw new Error('useAuthSession must be used within an AuthProvider')
  }
  return context
}
