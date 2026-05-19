import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from './app/layout/AppShell'
import { AdaptersPage } from './features/adapters/AdaptersPage'
import { AggregatesPage } from './features/aggregates/AggregatesPage'
import { AlarmsPage } from './features/alarms/AlarmsPage'
import { DlqPage } from './features/dlq/DlqPage'
import { EventsPage } from './features/events/EventsPage'
import { LoginPage } from './features/auth/LoginPage'
import { GatewaysPage } from './features/gateways/GatewaysPage'
import { HealthPage } from './features/health/HealthPage'
import { OverviewPage } from './features/overview/OverviewPage'
import { PipelineBuilderPage } from './features/pipelines/PipelineBuilderPage'
import { PipelinesPage } from './features/pipelines/PipelinesPage'
import { SinksPage } from './features/sinks/SinksPage'
import { AuthProvider } from './shared/auth/AuthProvider'
import { UsersPage } from './features/users/UsersPage'
import { ProtectedRoute } from './shared/auth/ProtectedRoute'

/**
 * Top-level route map.
 * - /login is public
 * - all other routes are protected behind auth
 */
function App() {
  return (
    <AuthProvider>
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
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<OverviewPage />} />
          <Route path="gateways" element={<GatewaysPage />} />
          <Route path="adapters" element={<AdaptersPage />} />
          <Route path="pipelines" element={<PipelinesPage />} />
          <Route path="pipelines/:deploymentId/edit" element={<PipelineBuilderPage />} />
          <Route path="sinks" element={<SinksPage />} />
          <Route path="events" element={<EventsPage />} />
          <Route path="aggregates" element={<AggregatesPage />} />
          <Route path="alarms" element={<AlarmsPage />} />
          <Route path="dlq" element={<DlqPage />} />
          <Route path="create-pipeline" element={<PipelineBuilderPage />} />
          <Route path="health" element={<HealthPage />} />
          <Route path="users" element={<UsersPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}

export default App
