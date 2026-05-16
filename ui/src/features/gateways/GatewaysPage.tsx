import { useEffect, useState } from 'react'

import { GatewayItem, PipelineItem, SinkItem, approveGateway, createGateway, listGateways, listPipelines, listSinks } from '../../shared/api/client'
import { summarizeDeployment } from '../../shared/config/deployments'
import { formatDateTime } from '../../shared/format/datetime'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'

/**
 * Gateway operations page.
 * Supports operator-managed gateway creation and approve actions.
 */
export function GatewaysPage() {
  const { timezone } = useOperatorPreferences()
  const [items, setItems] = useState<GatewayItem[]>([])
  const [pipelines, setPipelines] = useState<PipelineItem[]>([])
  const [sinks, setSinks] = useState<SinkItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [gatewayId, setGatewayId] = useState('gateway-demo-01')
  const [hostname, setHostname] = useState('gateway-demo-01.local')

  // Refresh list from backend and keep loading/error states consistent.
  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const [gateways, pipelineRows, sinkRows] = await Promise.all([listGateways(), listPipelines(), listSinks()])
      setItems(gateways)
      setPipelines(pipelineRows)
      setSinks(sinkRows)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load gateways')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  // Approve gateway then reload table to reflect backend state.
  const onApprove = async (gatewayId: string) => {
    try {
      await approveGateway(gatewayId)
      await refresh()
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : 'Failed to approve gateway')
    }
  }

  const onCreate = async () => {
    setError(null)
    try {
      await createGateway({
        gateway_id: gatewayId,
        hostname,
        approved: true,
      })
      await refresh()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Failed to create gateway')
    }
  }

  const sinkCountByPipeline = sinks.reduce<Record<number, number>>((counts, sink) => {
    counts[sink.pipeline_id] = (counts[sink.pipeline_id] || 0) + 1
    return counts
  }, {})

  const latestPipelineByGateway = pipelines.reduce<Record<string, PipelineItem>>((latest, pipeline) => {
    const current = latest[pipeline.gateway_id]
    if (!current || new Date(pipeline.created_at).getTime() > new Date(current.created_at).getTime()) {
      latest[pipeline.gateway_id] = pipeline
    }
    return latest
  }, {})

  return (
    <section>
      <div className="page-header">
        <h2>Gateways</h2>
        <button className="btn" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>
      <p className="muted">
        Each gateway runs one active deployment/config at a time. That active deployment can include multiple adapters,
        validation rules, event flow, aggregate rules, and multiple sinks.
      </p>

      <div className="card">
        <h3>Create Gateway</h3>
        <label>
          Gateway ID
          <input value={gatewayId} onChange={(event) => setGatewayId(event.target.value)} />
        </label>
        <label>
          Hostname
          <input value={hostname} onChange={(event) => setHostname(event.target.value)} />
        </label>
        <button className="btn" onClick={() => void onCreate()}>
          Create Gateway
        </button>
      </div>

      {loading && <p>Loading gateways...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && (
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Hostname</th>
              <th>Status</th>
              <th>Approved</th>
              <th>Active Deployment</th>
              <th>Adapters</th>
              <th>Sinks</th>
              <th>Last Seen</th>
              <th>Last Config Sync</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const activePipeline = latestPipelineByGateway[item.gateway_id]
              const summary = activePipeline ? summarizeDeployment(activePipeline.config, sinkCountByPipeline[activePipeline.id] || 0) : null

              return (
                <tr key={item.gateway_id}>
                  <td>{item.gateway_id}</td>
                  <td>{item.hostname}</td>
                  <td>{item.status}</td>
                  <td>{item.approved ? 'Yes' : 'No'}</td>
                  <td>{activePipeline ? `${activePipeline.id} - ${activePipeline.name}` : 'None'}</td>
                  <td>{summary ? summary.adapterCount : 0}</td>
                  <td>{summary ? summary.sinkCount : 0}</td>
                  <td>{formatDateTime(item.last_seen_at || null, timezone, { includeTimezone: true })}</td>
                  <td>{formatDateTime(item.last_config_sync_at || null, timezone, { includeTimezone: true })}</td>
                  <td>
                    {!item.approved && (
                      <button className="btn btn-secondary" onClick={() => void onApprove(item.gateway_id)}>
                        Approve
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </section>
  )
}
