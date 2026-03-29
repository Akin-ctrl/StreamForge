import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { clearAccessToken } from '../../shared/auth/session'

// Primary navigation for MVP operator screens.
const links = [
  { to: '/overview', label: 'Overview' },
  { to: '/gateways', label: 'Gateways' },
  { to: '/alarms', label: 'Alarms' },
  { to: '/dlq', label: 'DLQ' },
  { to: '/create-pipeline', label: 'Create Pipeline' },
  { to: '/health', label: 'Health' },
]

/**
 * Shared application shell for all protected routes.
 * Renders sidebar navigation and page outlet content.
 */
export function AppShell() {
  const navigate = useNavigate()
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const stored = window.localStorage.getItem('sf-theme')
    return stored === 'dark' ? 'dark' : 'light'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    window.localStorage.setItem('sf-theme', theme)
  }, [theme])

  // Clear token first to guarantee subsequent guarded routes redirect to login.
  const onLogout = () => {
    clearAccessToken()
    navigate('/login', { replace: true })
  }

  const onToggleTheme = () => {
    setTheme((current) => (current === 'light' ? 'dark' : 'light'))
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <h1>StreamForge</h1>
        <nav>
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                isActive ? 'nav-link nav-link-active' : 'nav-link'
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
        <button className="btn btn-secondary" onClick={onToggleTheme} type="button">
          {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
        </button>
        <button className="btn btn-secondary" onClick={onLogout}>
          Logout
        </button>
      </aside>

      <main className="app-content">
        <Outlet />
      </main>
    </div>
  )
}
