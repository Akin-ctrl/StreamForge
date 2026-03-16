import { useEffect, useState } from 'react'

import { GatewayItem, approveGateway, listGateways } from '../../shared/api/client'

/**
 * Gateway operations page.
 * Shows discovered gateways and allows approve actions.
 */
export function GatewaysPage() {
  const [items, setItems] = useState<GatewayItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

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

  return (
    <section>
      <div className="page-header">
        <h2>Gateways</h2>
        <button className="btn" onClick={() => void refresh()}>
          Refresh
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
