import { useEffect, useMemo, useState } from 'react'

import { DeploymentItem, GatewayItem, approveGateway, createGateway, listDeployments, listGateways } from '../../shared/api/client'
import { summarizeDeployment } from '../../shared/config/deployments'
import { formatDateTime } from '../../shared/format/datetime'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'

export function GatewaysPage() {
  const { timezone } = useOperatorPreferences()
  const [items, setItems] = useState<GatewayItem[]>([])
  const [deployments, setDeployments] = useState<DeploymentItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [gatewayId, setGatewayId] = useState('gateway-demo-01')
  const [hostname, setHostname] = useState('gateway-demo-01.local')

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const [gateways, deploymentRows] = await Promise.all([listGateways(), listDeployments()])
      setItems(gateways)
      setDeployments(deploymentRows)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load gateways')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const onApprove = async (targetGatewayId: string) => {
    try {
      await approveGateway(targetGatewayId)
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

  const activeDeploymentByGateway = useMemo(() => {
    const next: Record<string, DeploymentItem> = {}
    for (const deployment of deployments) {
      if (deployment.status !== 'active') {
        continue
      }
      const current = next[deployment.gateway_id]
      if (!current || new Date(deployment.updated_at).getTime() > new Date(current.updated_at).getTime()) {
        next[deployment.gateway_id] = deployment
      }
    }
    return next
  }, [deployments])

  return (
    <section>
      <div className="page-header">
        <h2>Gateways</h2>
        <button className="btn" onClick={() => void refresh()} type="button">
          Refresh
        </button>
      </div>
      <p className="muted">
        Each gateway runs one active deployment at a time. That deployment can attach multiple adapters, multiple sinks,
        and the validation, event, and aggregate rules for the runtime.
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
        <button className="btn" onClick={() => void onCreate()} type="button">
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
              const activeDeployment = activeDeploymentByGateway[item.gateway_id]
              const summary = activeDeployment ? summarizeDeployment(activeDeployment) : null

              return (
                <tr key={item.gateway_id}>
                  <td>{item.gateway_id}</td>
                  <td>{item.hostname}</td>
                  <td>{item.status}</td>
                  <td>{item.approved ? 'Yes' : 'No'}</td>
                  <td>{activeDeployment ? `${activeDeployment.deployment_id} - ${activeDeployment.name}` : 'None'}</td>
                  <td>{summary ? summary.adapterCount : 0}</td>
                  <td>{summary ? summary.sinkCount : 0}</td>
                  <td>{formatDateTime(item.last_seen_at || null, timezone, { includeTimezone: true })}</td>
                  <td>{formatDateTime(item.last_config_sync_at || null, timezone, { includeTimezone: true })}</td>
                  <td>
                    {!item.approved && (
                      <button className="btn btn-secondary" onClick={() => void onApprove(item.gateway_id)} type="button">
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
