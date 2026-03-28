import { useEffect, useState } from 'react'

import { GatewayItem, approveGateway, createGateway, listGateways } from '../../shared/api/client'

/**
 * Gateway operations page.
 * Supports operator-managed gateway creation and approve actions.
 */
export function GatewaysPage() {
  const [items, setItems] = useState<GatewayItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [gatewayId, setGatewayId] = useState('gateway-demo-01')
  const [hostname, setHostname] = useState('gateway-demo-01.local')

  // Refresh list from backend and keep loading/error states consistent.
  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const gateways = await listGateways()
      setItems(gateways)
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

  return (
    <section>
      <div className="page-header">
        <h2>Gateways</h2>
        <button className="btn" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

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
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.gateway_id}>
                <td>{item.gateway_id}</td>
                <td>{item.hostname}</td>
                <td>{item.status}</td>
                <td>{item.approved ? 'Yes' : 'No'}</td>
                <td>
                  {!item.approved && (
                    <button className="btn btn-secondary" onClick={() => void onApprove(item.gateway_id)}>
                      Approve
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
