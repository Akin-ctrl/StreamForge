import { useEffect, useMemo, useState } from 'react'

import { GatewayItem, PipelineItem, SinkItem, listGateways, listPipelines, listSinks } from '../../shared/api/client'

/**
 * Main operations landing page.
 * Shows current gateways, pipelines, and sinks in one place.
 */
export function OverviewPage() {
  const [gateways, setGateways] = useState<GatewayItem[]>([])
  const [pipelines, setPipelines] = useState<PipelineItem[]>([])
  const [sinks, setSinks] = useState<SinkItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const [gatewayRows, pipelineRows, sinkRows] = await Promise.all([listGateways(), listPipelines(), listSinks()])
      setGateways(gatewayRows)
      setPipelines(pipelineRows)
      setSinks(sinkRows)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load overview')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const approvedGateways = useMemo(() => gateways.filter((item) => item.approved).length, [gateways])

  return (
    <section>
      <div className="page-header">
        <h2>Overview</h2>
        <button className="btn" onClick={() => void refresh()} type="button">
          Refresh
        </button>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p>Loading overview...</p>}

      <div className="overview-kpis">
        <article className="card">
          <h3>Gateways</h3>
          <p className="overview-kpi-value">{gateways.length}</p>
          <p className="muted">Approved: {approvedGateways}</p>
        </article>
        <article className="card">
          <h3>Pipelines</h3>
          <p className="overview-kpi-value">{pipelines.length}</p>
          <p className="muted">Configured in control plane</p>
        </article>
        <article className="card">
          <h3>Sinks</h3>
          <p className="overview-kpi-value">{sinks.length}</p>
          <p className="muted">Pipeline output targets</p>
        </article>
      </div>

      <div className="overview-grid">
        <article className="card">
          <h3>Recent Pipelines</h3>
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Gateway</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {pipelines.slice(0, 8).map((item) => (
                <tr key={item.id}>
                  <td>{item.id}</td>
                  <td>{item.name}</td>
                  <td>{item.gateway_id}</td>
                  <td>{new Date(item.created_at).toLocaleString()}</td>
                </tr>
              ))}
              {pipelines.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    No pipelines yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </article>

        <article className="card">
          <h3>Gateways</h3>
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Approved</th>
              </tr>
            </thead>
            <tbody>
              {gateways.slice(0, 8).map((item) => (
                <tr key={item.gateway_id}>
                  <td>{item.gateway_id}</td>
                  <td>{item.status}</td>
                  <td>{item.approved ? 'Yes' : 'No'}</td>
                </tr>
              ))}
              {gateways.length === 0 && (
                <tr>
                  <td colSpan={3} className="muted">
                    No gateways yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </article>

        <article className="card">
          <h3>Sinks</h3>
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Pipeline</th>
                <th>Type</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {sinks.slice(0, 8).map((item) => (
                <tr key={item.id}>
                  <td>{item.id}</td>
                  <td>{item.pipeline_id}</td>
                  <td>{item.sink_type}</td>
                  <td>{item.status}</td>
                </tr>
              ))}
              {sinks.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    No sinks yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </article>
      </div>
    </section>
  )
}