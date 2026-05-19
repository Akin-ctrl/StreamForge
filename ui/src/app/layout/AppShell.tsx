import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuthSession } from '../../shared/auth/AuthProvider'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'

// Primary navigation for MVP operator screens.
const links = [
  { to: '/overview', label: 'Overview' },
  { to: '/fleet', label: 'Fleet' },
  { to: '/gateways', label: 'Gateways' },
  { to: '/adapters', label: 'Adapters' },
  { to: '/pipelines', label: 'Deployments' },
  { to: '/sinks', label: 'Sinks' },
  { to: '/events', label: 'Events' },
  { to: '/aggregates', label: 'Aggregates' },
  { to: '/logs', label: 'Logs' },
  { to: '/alarms', label: 'Alarms' },
  { to: '/dlq', label: 'DLQ' },
  { to: '/create-pipeline', label: 'Compose Deployment' },
  { to: '/health', label: 'Health' },
  { to: '/users', label: 'Users' },
]

/**
 * Shared application shell for all protected routes.
 * Renders sidebar navigation and page outlet content.
 */
export function AppShell() {
  const navigate = useNavigate()
  const { logout } = useAuthSession()
  const { timezone, setTimezone, timezoneOptions } = useOperatorPreferences()
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const stored = window.localStorage.getItem('sf-theme')
    return stored === 'dark' ? 'dark' : 'light'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    window.localStorage.setItem('sf-theme', theme)
  }, [theme])

  // Clear the browser session first to guarantee guarded routes redirect to login.
  const onLogout = async () => {
    await logout()
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
        <label className="sidebar-field">
          Timezone
          <select value={timezone} onChange={(event) => setTimezone(event.target.value)}>
            <option value="browser">Browser Local</option>
            {timezoneOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <button className="btn btn-secondary" onClick={onToggleTheme} type="button">
          {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
        </button>
        <button className="btn btn-secondary" onClick={() => void onLogout()}>
          Logout
        </button>
      </aside>

      <main className="app-content">
        <Outlet />
      </main>
    </div>
  )
}
