import { useEffect, useState } from 'react'

import { HealthResponse, getHealth } from '../../shared/api/client'

/**
 * Simple health view for control-plane status.
 */
export function HealthPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Initial health fetch on page load.
    const load = async () => {
      setError(null)
      try {
        setHealth(await getHealth())
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load health')
      }
    }
    void load()
  }, [])

  return (
    <section>
      <h2>Health</h2>
      {error && <p className="error">{error}</p>}
      {health && (
        <div className="card">
          <p>
            <strong>Service:</strong> {health.service}
          </p>
          <p>
            <strong>Status:</strong> {health.status}
          </p>
        </div>
      )}
    </section>
  )
}
