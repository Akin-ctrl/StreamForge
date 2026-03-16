import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from './app/layout/AppShell'
import { LoginPage } from './features/auth/LoginPage'
import { GatewaysPage } from './features/gateways/GatewaysPage'
import { HealthPage } from './features/health/HealthPage'
import { PipelineBuilderPage } from './features/pipelines/PipelineBuilderPage'
import { ProtectedRoute } from './shared/auth/ProtectedRoute'

/**
 * Top-level route map.
 * - /login is public
 * - all other routes are protected behind auth
 */
function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/gateways" replace />} />
        <Route path="gateways" element={<GatewaysPage />} />
        <Route path="create-pipeline" element={<PipelineBuilderPage />} />
        <Route path="health" element={<HealthPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
