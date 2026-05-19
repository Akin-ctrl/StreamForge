import { useEffect, useState } from 'react'

import {
  AdapterItem,
  DeploymentItem,
  GatewayItem,
  HealthResponse,
  SinkItem,
  getHealth,
  listAdapters,
  listDeployments,
  listGateways,
  listSinks,
} from '../../shared/api/client'
import { DataTableCard } from '../../shared/data-display/DataTableCard'
import { MetricCard } from '../../shared/data-display/MetricCard'
import { summarizeDeployment } from '../../shared/config/deployments'
import { formatDateTime } from '../../shared/format/datetime'
import { PageCallout } from '../../shared/layout/PageCallout'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'

export function OverviewPage() {
  const { timezone } = useOperatorPreferences()
  const [gateways, setGateways] = useState<GatewayItem[]>([])
  const [deployments, setDeployments] = useState<DeploymentItem[]>([])
  const [adapters, setAdapters] = useState<AdapterItem[]>([])
  const [sinks, setSinks] = useState<SinkItem[]>([])
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const [gatewayRows, deploymentRows, adapterRows, sinkRows, healthRow] = await Promise.all([
        listGateways(),
        listDeployments(),
        listAdapters(),
        listSinks(),
        getHealth(),
      ])
      setGateways(gatewayRows)
      setDeployments(deploymentRows)
      setAdapters(adapterRows)
      setSinks(sinkRows)
      setHealth(healthRow)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load overview')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const approvedGateways = gateways.filter((item) => item.approved).length

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>Overview</h2>
          <p className="muted">
            Start here for a quick operator snapshot of configured gateways, reusable objects, and recent deployment
            activity.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn" onClick={() => void refresh()} type="button">
            Refresh
          </button>
        </div>
      </div>

      <PageCallout title="How to use this view">
        <p className="muted">
          Use this page as the operator jump-off point, then move into Fleet, Deployments, Events, Aggregates, or Logs
          when a specific surface needs deeper attention.
        </p>
      </PageCallout>

      {error && <p className="error">{error}</p>}
      {loading && (
        <article className="card empty-state">
          <p>Loading overview...</p>
          <p className="muted">Fetching gateway, deployment, adapter, sink, and control-plane health summaries.</p>
        </article>
      )}

      <div className="overview-kpis">
        <MetricCard detail={`Approved: ${approvedGateways}`} title="Gateways" value={gateways.length} />
        <MetricCard detail="Active gateway compositions" title="Deployments" value={deployments.length} />
        <MetricCard detail="Configured source connections" title="Adapters" value={adapters.length} />
        <MetricCard detail="Configured delivery targets" title="Sinks" value={sinks.length} />
      </div>

      <div className="overview-grid">
        <DataTableCard
          description="A quick view of the latest saved deployment compositions."
          title="Recent Deployments"
        >
          <table className="table">
            <thead>
              <tr>
                <th>Deployment ID</th>
                <th>Gateway</th>
                <th>Status</th>
                <th>Adapters</th>
                <th>Sinks</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {deployments.slice(0, 8).map((item) => {
                const summary = summarizeDeployment(item)
                return (
                  <tr key={item.deployment_id}>
                    <td>{item.deployment_id}</td>
                    <td>{item.gateway_id}</td>
                    <td>{item.status}</td>
                    <td>{summary.adapterCount}</td>
                    <td>{summary.sinkCount}</td>
                    <td>{formatDateTime(item.created_at, timezone, { includeTimezone: true })}</td>
                  </tr>
                )
              })}
              {deployments.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">No deployments configured yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </DataTableCard>

        <DataTableCard
          description="Recent gateway records and their current configuration posture."
          title="Gateways"
        >
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Approved</th>
                <th>Last Sync</th>
              </tr>
            </thead>
            <tbody>
              {gateways.slice(0, 8).map((item) => (
                <tr key={item.gateway_id}>
                  <td>{item.gateway_id}</td>
                  <td>{item.status}</td>
                  <td>{item.approved ? 'Yes' : 'No'}</td>
                  <td>{formatDateTime(item.last_config_sync_at || null, timezone, { includeTimezone: true })}</td>
                </tr>
              ))}
              {gateways.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">No gateways configured yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </DataTableCard>

        <article className="card review-section">
          <div className="card-header-copy">
            <h3>Control Plane Health</h3>
            <p className="muted">Current service and dependency posture reported by the control plane.</p>
          </div>
          <div className="summary-grid">
            <div className="summary-item">
              <span className="summary-label">Service</span>
              <strong>{health?.status || 'unknown'}</strong>
            </div>
            <div className="summary-item">
              <span className="summary-label">Database</span>
              <strong>{health?.dependencies?.database || 'unknown'}</strong>
            </div>
            <div className="summary-item">
              <span className="summary-label">Healthy Gateways</span>
              <strong>{health?.gateway_states?.healthy ?? 0}</strong>
            </div>
            <div className="summary-item">
              <span className="summary-label">Degraded Gateways</span>
              <strong>{health?.gateway_states?.degraded ?? 0}</strong>
            </div>
          </div>
        </article>
      </div>
    </section>
  )
}
