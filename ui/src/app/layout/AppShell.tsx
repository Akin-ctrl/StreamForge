import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { clearAccessToken } from '../../shared/auth/session'

// Primary navigation for MVP operator screens.
const links = [
  { to: '/gateways', label: 'Gateways' },
  { to: '/create-pipeline', label: 'Create Pipeline' },
  { to: '/health', label: 'Health' },
]

/**
 * Shared application shell for all protected routes.
 * Renders sidebar navigation and page outlet content.
 */
export function AppShell() {
  const navigate = useNavigate()

  // Clear token first to guarantee subsequent guarded routes redirect to login.
  const onLogout = () => {
    clearAccessToken()
    navigate('/login', { replace: true })
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
