const TOKEN_KEY = 'sf_access_token'

/** Returns the current access token from local storage. */
export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

/** Persists the access token after a successful login. */
export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

/** Clears session state during logout. */
export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

/** Convenience auth check for route guards. */
export function isAuthenticated(): boolean {
  return Boolean(getAccessToken())
}
