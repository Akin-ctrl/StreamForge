import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import {
  type AdapterItem,
  type DeploymentItem,
  type GatewayItem,
  type HealthResponse,
  type SinkItem,
  getHealth,
  listAdapters,
  listDeployments,
  listGateways,
  listSinks,
} from '../../shared/api/client'
import { summarizeDeployment } from '../../shared/config/deployments'
import { buildGatewayTopologyContext } from '../../shared/fleet/topology'
import {
  componentEntries,
  gatewayIssues,
  heartbeatLabel,
  heartbeatState,
  heartbeatTone,
  metricNumber,
  runtimeStatus,
  runtimeTone,
} from '../../shared/fleet/status'
import { formatDateTime } from '../../shared/format/datetime'
import { formatBytes, formatNumber } from '../../shared/format/metrics'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'
import { TopologyView } from './components/TopologyView'

function statusChipClass(tone: 'good' | 'warn' | 'bad' | 'neutral'): string {
  return `fleet-status-chip fleet-status-chip-${tone}`
}

export function FleetPage() {
  const { timezone } = useOperatorPreferences()
  const [searchParams, setSearchParams] = useSearchParams()
  const [gateways, setGateways] = useState<GatewayItem[]>([])
  const [deployments, setDeployments] = useState<DeploymentItem[]>([])
  const [adapters, setAdapters] = useState<AdapterItem[]>([])
  const [sinks, setSinks] = useState<SinkItem[]>([])
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const selectedGatewayId = searchParams.get('gateway')

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
      setError(loadError instanceof Error ? loadError.message : 'Failed to load fleet visibility')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  useEffect(() => {
    if (gateways.length === 0) {
      return
    }

    if (selectedGatewayId && gateways.some((gateway) => gateway.gateway_id === selectedGatewayId)) {
      return
    }

    const preferredGateway = gateways.find((gateway) => gateway.approved) || gateways[0]
    if (preferredGateway) {
      setSearchParams({ gateway: preferredGateway.gateway_id }, { replace: true })
    }
  }, [gateways, selectedGatewayId, setSearchParams])

  const gatewayContexts = useMemo(
    () => gateways.map((gateway) => buildGatewayTopologyContext(gateway, deployments, adapters, sinks)),
    [gateways, deployments, adapters, sinks],
  )

  const selectedContext =
    gatewayContexts.find((context) => context.gateway.gateway_id === selectedGatewayId) ||
    gatewayContexts[0] ||
    null

  const activeDeploymentCount = useMemo(
    () => deployments.filter((deployment) => deployment.status === 'active').length,
    [deployments],
  )

  const onSelectGateway = (gatewayId: string) => {
    setSearchParams({ gateway: gatewayId }, { replace: true })
  }

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>Fleet</h2>
          <p className="muted">
            Monitor approved gateways, runtime health, active deployment wiring, and the live topology of adapters,
            processing stages, and sinks.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" onClick={() => void refresh()} type="button">
            Refresh
          </button>
          <Link className="btn btn-secondary" to="/gateways">
            Manage Gateways
          </Link>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p>Loading fleet visibility...</p>}

      {!loading && (
        <>
          <div className="overview-kpis">
            <article className="card">
              <h3>Gateways</h3>
              <p className="overview-kpi-value">{gateways.length}</p>
              <p className="muted">Approved: {health?.gateway_states?.approved ?? gateways.filter((item) => item.approved).length}</p>
            </article>
            <article className="card">
              <h3>Healthy Runtime</h3>
              <p className="overview-kpi-value">{health?.gateway_states?.healthy ?? 0}</p>
              <p className="muted">Degraded: {health?.gateway_states?.degraded ?? 0}</p>
            </article>
            <article className="card">
              <h3>Active Deployments</h3>
              <p className="overview-kpi-value">{activeDeploymentCount}</p>
              <p className="muted">Across all gateways</p>
            </article>
            <article className="card">
              <h3>Offline Heartbeats</h3>
              <p className="overview-kpi-value">
                {gateways.filter((gateway) => heartbeatState(gateway.last_seen_at) === 'offline').length}
              </p>
              <p className="muted">Never seen: {gateways.filter((gateway) => heartbeatState(gateway.last_seen_at) === 'never-seen').length}</p>
            </article>
          </div>

          <div className="fleet-layout">
            <article className="card fleet-gateway-list">
              <h3>Gateway Inventory</h3>
              <div className="fleet-gateway-stack">
                {gatewayContexts.map((context) => {
                  const activeDeployment = context.activeDeployment
                  const heartbeat = heartbeatState(context.gateway.last_seen_at)
                  const runtime = runtimeStatus(context.gateway)
                  const issues = gatewayIssues(context.gateway, activeDeployment ? 1 : 0)
                  const summary = activeDeployment ? summarizeDeployment(activeDeployment) : null

                  return (
                    <button
                      className={
                        context.gateway.gateway_id === selectedContext?.gateway.gateway_id
                          ? 'fleet-gateway-card fleet-gateway-card-selected'
                          : 'fleet-gateway-card'
                      }
                      key={context.gateway.gateway_id}
                      onClick={() => onSelectGateway(context.gateway.gateway_id)}
                      type="button"
                    >
                      <div className="fleet-gateway-card-header">
                        <div>
                          <strong>{context.gateway.gateway_id}</strong>
                          <p className="muted">{context.gateway.hostname}</p>
                        </div>
                        <div className="fleet-chip-row">
                          <span className={statusChipClass(runtimeTone(runtime))}>{runtime}</span>
                          <span className={statusChipClass(heartbeatTone(heartbeat))}>{heartbeatLabel(heartbeat)}</span>
                        </div>
                      </div>
                      <div className="fleet-card-meta">
                        <span>{context.gateway.approved ? 'Approved' : 'Pending approval'}</span>
                        <span>{activeDeployment ? activeDeployment.deployment_id : 'No active deployment'}</span>
                        <span>{context.deployments.length} deployment{context.deployments.length === 1 ? '' : 's'}</span>
                      </div>
                      {summary && (
                        <div className="fleet-card-meta">
                          <span>{summary.adapterCount} adapters</span>
                          <span>{summary.sinkCount} sinks</span>
                        </div>
                      )}
                      {issues.length > 0 && <p className="muted">{issues[0]}</p>}
                    </button>
                  )
                })}
                {gatewayContexts.length === 0 && <p className="muted">No gateways available yet.</p>}
              </div>
            </article>

            <div className="fleet-detail-stack">
              {selectedContext ? (
                <>
                  <article className="card gateway-health-card">
                    <div className="page-header">
                      <div>
                        <h3>{selectedContext.gateway.gateway_id}</h3>
                        <p className="muted">{selectedContext.gateway.hostname}</p>
                      </div>
                      <div className="page-actions">
                        <div className="fleet-chip-row">
                          <span className={statusChipClass(runtimeTone(runtimeStatus(selectedContext.gateway)))}>
                            {runtimeStatus(selectedContext.gateway)}
                          </span>
                          <span className={statusChipClass(heartbeatTone(heartbeatState(selectedContext.gateway.last_seen_at)))}>
                            {heartbeatLabel(heartbeatState(selectedContext.gateway.last_seen_at))}
                          </span>
                        </div>
                        <Link className="btn btn-secondary" to={`/logs?gateway=${encodeURIComponent(selectedContext.gateway.gateway_id)}`}>
                          View Logs
                        </Link>
                      </div>
                    </div>

                    <div className="inline-grid">
                      <div>
                        <strong>Status</strong>
                        <p className="muted">{selectedContext.gateway.status}</p>
                      </div>
                      <div>
                        <strong>Approved</strong>
                        <p className="muted">{selectedContext.gateway.approved ? 'Yes' : 'No'}</p>
                      </div>
                      <div>
                        <strong>Last Seen</strong>
                        <p className="muted">{formatDateTime(selectedContext.gateway.last_seen_at || null, timezone, { includeTimezone: true })}</p>
                      </div>
                      <div>
                        <strong>Last Config Sync</strong>
                        <p className="muted">{formatDateTime(selectedContext.gateway.last_config_sync_at || null, timezone, { includeTimezone: true })}</p>
                      </div>
                      <div>
                        <strong>Config Version</strong>
                        <p className="muted">{selectedContext.gateway.last_config_version || 'Unknown'}</p>
                      </div>
                    </div>

                    <div className="inline-grid">
                      <div className="nested-card card">
                        <strong>CPU</strong>
                        <p className="overview-kpi-value metric-value">
                          {formatNumber(metricNumber(selectedContext.gateway.system_metrics || null, 'cpu_percent'))}%
                        </p>
                      </div>
                      <div className="nested-card card">
                        <strong>Memory</strong>
                        <p className="overview-kpi-value metric-value">
                          {formatNumber(metricNumber(selectedContext.gateway.system_metrics || null, 'memory_percent'))}%
                        </p>
                        <p className="muted">
                          {formatBytes(metricNumber(selectedContext.gateway.system_metrics || null, 'memory_used_bytes'))} /{' '}
                          {formatBytes(metricNumber(selectedContext.gateway.system_metrics || null, 'memory_total_bytes'))}
                        </p>
                      </div>
                      <div className="nested-card card">
                        <strong>Network RX</strong>
                        <p className="overview-kpi-value metric-value">
                          {formatBytes(metricNumber(selectedContext.gateway.system_metrics || null, 'network_rx_bytes_per_sec'))}/s
                        </p>
                      </div>
                      <div className="nested-card card">
                        <strong>Network TX</strong>
                        <p className="overview-kpi-value metric-value">
                          {formatBytes(metricNumber(selectedContext.gateway.system_metrics || null, 'network_tx_bytes_per_sec'))}/s
                        </p>
                      </div>
                    </div>

                    <div className="section-grid">
                      <div>
                        <strong>Runtime Components</strong>
                        <div className="component-grid">
                          {componentEntries(selectedContext.gateway).length > 0 ? (
                            componentEntries(selectedContext.gateway).map((component) => (
                              <div className="component-pill" key={`${selectedContext.gateway.gateway_id}-${component.name}`}>
                                <strong>{component.name}</strong>: {component.status}
                              </div>
                            ))
                          ) : (
                            <p className="muted">No runtime component detail reported yet.</p>
                          )}
                        </div>
                      </div>

                      {gatewayIssues(selectedContext.gateway, selectedContext.activeDeployment ? 1 : 0).length > 0 && (
                        <div className="nested-card card">
                          <strong>Operator Attention</strong>
                          <ul className="plain-list">
                            {gatewayIssues(selectedContext.gateway, selectedContext.activeDeployment ? 1 : 0).map((issue) => (
                              <li key={issue}>{issue}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </article>

                  <article className="card">
                    <div className="page-header">
                      <h3>Deployments On This Gateway</h3>
                      {selectedContext.activeDeployment && (
                        <Link
                          className="btn btn-secondary"
                          to={`/pipelines/${encodeURIComponent(selectedContext.activeDeployment.deployment_id)}/edit`}
                        >
                          Open Active Deployment
                        </Link>
                      )}
                    </div>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Deployment</th>
                          <th>Status</th>
                          <th>Adapters</th>
                          <th>Sinks</th>
                          <th>Updated</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedContext.deployments.map((deployment) => {
                          const summary = summarizeDeployment(deployment)
                          return (
                            <tr key={deployment.deployment_id}>
                              <td>
                                <Link to={`/pipelines/${encodeURIComponent(deployment.deployment_id)}/edit`}>
                                  {deployment.deployment_id}
                                </Link>
                              </td>
                              <td>{deployment.status}</td>
                              <td>{summary.adapterCount}</td>
                              <td>{summary.sinkCount}</td>
                              <td>{formatDateTime(deployment.updated_at, timezone, { includeTimezone: true })}</td>
                            </tr>
                          )
                        })}
                        {selectedContext.deployments.length === 0 && (
                          <tr>
                            <td colSpan={5}>No deployments are attached to this gateway yet.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </article>

                  <article className="card">
                    <div className="page-header">
                      <h3>Active Topology</h3>
                      <p className="muted">Current active deployment path from gateway to adapters, processing stages, and sinks.</p>
                    </div>
                    <TopologyView
                      gateway={selectedContext.gateway}
                      activeDeployment={selectedContext.activeDeployment}
                      adapters={selectedContext.adapters}
                      sinks={selectedContext.sinks}
                    />
                  </article>
                </>
              ) : (
                <article className="card">
                  <p className="muted">No gateway data is available yet.</p>
                </article>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  )
}
