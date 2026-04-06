import { useEffect, useMemo, useState } from 'react'

import { GatewayItem, HealthResponse, getHealth } from '../../shared/api/client'
import { formatBytes, formatNumber } from '../../shared/format/metrics'
import { formatDateTime } from '../../shared/format/datetime'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'

function metricNumber(metrics: Record<string, unknown> | null | undefined, key: string): number | null {
  const value = metrics?.[key]
  return typeof value === 'number' ? value : null
}

function runtimeStatus(gateway: GatewayItem): string {
  const status = gateway.runtime_health?.status
  return typeof status === 'string' ? status : 'unknown'
}

function heartbeatState(lastSeenAt: string | null | undefined): string {
  if (!lastSeenAt) {
    return 'never-seen'
  }

  const seen = new Date(lastSeenAt).getTime()
  if (Number.isNaN(seen)) {
    return 'unknown'
  }

  const ageMinutes = (Date.now() - seen) / 60000
  if (ageMinutes <= 5) {
    return 'fresh'
  }
  if (ageMinutes <= 30) {
    return 'stale'
  }
  return 'offline'
}

function componentEntries(gateway: GatewayItem): Array<[string, string]> {
  const runtimeHealth = gateway.runtime_health as { components?: Record<string, { status?: string }> } | null
  const components = runtimeHealth?.components || {}
  return Object.entries(components).map(([name, details]) => [name, details.status || 'unknown'])
}

export function HealthPage() {
  const { timezone } = useOperatorPreferences()
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setError(null)
    try {
      setHealth(await getHealth())
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load health')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const gateways = useMemo(() => health?.gateways || [], [health])

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>Health</h2>
          <p className="muted">Control-plane, gateway autonomy, runtime component state, and live system metrics.</p>
        </div>
        <button className="btn" onClick={() => void refresh()} type="button">
          Refresh
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {health && (
        <>
          <div className="overview-kpis">
            <article className="card">
              <h3>Service</h3>
              <p className="overview-kpi-value">{health.status}</p>
              <p className="muted">{health.service}</p>
            </article>
            <article className="card">
              <h3>Healthy Gateways</h3>
              <p className="overview-kpi-value">{health.gateway_states?.healthy ?? 0}</p>
              <p className="muted">Degraded: {health.gateway_states?.degraded ?? 0}</p>
            </article>
            <article className="card">
              <h3>Unhealthy Gateways</h3>
              <p className="overview-kpi-value">{health.gateway_states?.unhealthy ?? 0}</p>
              <p className="muted">Pending approval: {health.gateway_states?.pending ?? 0}</p>
            </article>
            <article className="card">
              <h3>Control Plane</h3>
              <p className="overview-kpi-value">{health.dependencies?.database ?? 'unknown'}</p>
              <p className="muted">Users: {health.counts?.users ?? 0}</p>
            </article>
          </div>

          <div className="overview-grid">
            <article className="card">
              <h3>Inventory</h3>
              <p>Gateways: {health.counts?.gateways ?? 0}</p>
              <p>Pipelines: {health.counts?.pipelines ?? 0}</p>
              <p>Sinks: {health.counts?.sinks ?? 0}</p>
              <p>Alarms: {health.counts?.alarms ?? 0}</p>
              <p>DLQ Messages: {health.counts?.dlq_messages ?? 0}</p>
            </article>

            <article className="card">
              <h3>Gateway Sync</h3>
              <p>Approved: {health.gateway_states?.approved ?? 0}</p>
              <p>Pending: {health.gateway_states?.pending ?? 0}</p>
              <p>Fresh heartbeats: {gateways.filter((gateway) => heartbeatState(gateway.last_seen_at) === 'fresh').length}</p>
              <p>Offline heartbeats: {gateways.filter((gateway) => heartbeatState(gateway.last_seen_at) === 'offline').length}</p>
            </article>
          </div>

          <div className="section-grid">
            {gateways.map((gateway) => {
              const metrics = gateway.system_metrics || {}
              const components = componentEntries(gateway)
              return (
                <article className="card gateway-health-card" key={gateway.gateway_id}>
                  <div className="page-header">
                    <div>
                      <h3>{gateway.gateway_id}</h3>
                      <p className="muted">{gateway.hostname}</p>
                    </div>
                    <div className="review-grid">
                      <p>
                        <strong>Runtime:</strong> {runtimeStatus(gateway)}
                      </p>
                      <p>
                        <strong>Heartbeat:</strong> {heartbeatState(gateway.last_seen_at)}
                      </p>
                    </div>
                  </div>

                  <div className="inline-grid">
                    <div>
                      <strong>Status</strong>
                      <p className="muted">{gateway.status}</p>
                    </div>
                    <div>
                      <strong>Approved</strong>
                      <p className="muted">{gateway.approved ? 'Yes' : 'No'}</p>
                    </div>
                    <div>
                      <strong>Last Seen</strong>
                      <p className="muted">{formatDateTime(gateway.last_seen_at, timezone, { includeTimezone: true })}</p>
                    </div>
                    <div>
                      <strong>Last Config Sync</strong>
                      <p className="muted">{formatDateTime(gateway.last_config_sync_at, timezone, { includeTimezone: true })}</p>
                    </div>
                    <div>
                      <strong>Config Version</strong>
                      <p className="muted">{gateway.last_config_version || 'Unknown'}</p>
                    </div>
                  </div>

                  <div className="inline-grid">
                    <div className="nested-card card">
                      <strong>CPU</strong>
                      <p className="overview-kpi-value metric-value">{formatNumber(metricNumber(metrics, 'cpu_percent'))}%</p>
                    </div>
                    <div className="nested-card card">
                      <strong>Memory</strong>
                      <p className="overview-kpi-value metric-value">{formatNumber(metricNumber(metrics, 'memory_percent'))}%</p>
                      <p className="muted">
                        {formatBytes(metricNumber(metrics, 'memory_used_bytes'))} / {formatBytes(metricNumber(metrics, 'memory_total_bytes'))}
                      </p>
                    </div>
                    <div className="nested-card card">
                      <strong>Network RX</strong>
                      <p className="overview-kpi-value metric-value">{formatBytes(metricNumber(metrics, 'network_rx_bytes_per_sec'))}/s</p>
                    </div>
                    <div className="nested-card card">
                      <strong>Network TX</strong>
                      <p className="overview-kpi-value metric-value">{formatBytes(metricNumber(metrics, 'network_tx_bytes_per_sec'))}/s</p>
                    </div>
                  </div>

                  <div className="section-grid">
                    <div>
                      <strong>Runtime Components</strong>
                      <div className="component-grid">
                        {components.length > 0 ? (
                          components.map(([name, status]) => (
                            <div className="component-pill" key={`${gateway.gateway_id}-${name}`}>
                              <strong>{name}</strong>: {status}
                            </div>
                          ))
                        ) : (
                          <p className="muted">No component detail reported yet.</p>
                        )}
                      </div>
                    </div>
                  </div>
                </article>
              )
            })}

            {gateways.length === 0 && (
              <div className="card">
                <p className="muted">No gateways have reported health yet.</p>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  )
}
