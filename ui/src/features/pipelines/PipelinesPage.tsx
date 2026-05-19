import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  DeploymentItem,
  deleteDeployment,
  listDeployments,
} from '../../shared/api/client'
import { summarizeDeployment } from '../../shared/config/deployments'
import { DataTableCard } from '../../shared/data-display/DataTableCard'
import { MetricCard } from '../../shared/data-display/MetricCard'
import { formatDateTime } from '../../shared/format/datetime'
import { PageCallout } from '../../shared/layout/PageCallout'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'

export function PipelinesPage() {
  const { timezone } = useOperatorPreferences()
  const [deployments, setDeployments] = useState<DeploymentItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const deploymentRows = await listDeployments()
      setDeployments(deploymentRows)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load deployments')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const onDelete = async (targetDeploymentId: string) => {
    setError(null)
    try {
      await deleteDeployment(targetDeploymentId)
      await refresh()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Failed to delete deployment')
    }
  }

  const activeCount = useMemo(() => deployments.filter((deployment) => deployment.status === 'active').length, [deployments])
  const totalAttachedAdapters = useMemo(
    () => deployments.reduce((count, deployment) => count + deployment.adapter_ids.length, 0),
    [deployments],
  )
  const totalAttachedSinks = useMemo(
    () => deployments.reduce((count, deployment) => count + deployment.sink_ids.length, 0),
    [deployments],
  )

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>Deployments</h2>
          <p className="muted">
            Review saved deployment compositions here. Each deployment attaches reusable saved adapters and sinks to one
            gateway with deployment-level validation, event, and aggregate behavior.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" onClick={() => void refresh()} type="button">
            Refresh
          </button>
          <Link className="btn" to="/create-pipeline">
            Compose Deployment
          </Link>
        </div>
      </div>

      <PageCallout title="How to use this view">
        <p className="muted">
          Review saved gateway compositions here, then open one deployment when you need to adjust attached objects or
          deployment-level processing policy.
        </p>
      </PageCallout>

      {error && <p className="error">{error}</p>}
      {loading && (
        <article className="card empty-state">
          <p>Loading deployments...</p>
          <p className="muted">Fetching saved deployment compositions and their attached object counts.</p>
        </article>
      )}

      <div className="overview-kpis">
        <MetricCard detail="Saved deployment compositions" title="Total Deployments" value={deployments.length} />
        <MetricCard
          detail="Gateways currently pointed at an active deployment"
          title="Active"
          value={activeCount}
        />
        <MetricCard detail="Adapter attachments across all deployments" title="Attached Adapters" value={totalAttachedAdapters} />
        <MetricCard detail="Sink attachments across all deployments" title="Attached Sinks" value={totalAttachedSinks} />
      </div>

      <div className="overview-grid">
        <DataTableCard
          description="Review saved deployment compositions, where they run, and how many reusable objects each one attaches."
          title="Deployment Inventory"
        >
          <table className="table">
            <thead>
              <tr>
                <th>Deployment ID</th>
                <th>Gateway</th>
                <th>Status</th>
                <th>Saved Adapters</th>
                <th>Saved Sinks</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {deployments.map((deployment) => {
                const summary = summarizeDeployment(deployment)
                return (
                  <tr key={deployment.deployment_id}>
                    <td>{deployment.deployment_id}</td>
                    <td>
                      <Link to={`/fleet?gateway=${encodeURIComponent(deployment.gateway_id)}`}>{deployment.gateway_id}</Link>
                    </td>
                    <td>{deployment.status}</td>
                    <td>{summary.adapterCount} attached</td>
                    <td>{summary.sinkCount} attached</td>
                    <td>{formatDateTime(deployment.created_at, timezone, { includeTimezone: true })}</td>
                    <td>
                      <div className="table-actions">
                        <Link className="btn btn-secondary" to={`/pipelines/${encodeURIComponent(deployment.deployment_id)}/edit`}>
                          Edit
                        </Link>
                        <button className="btn btn-secondary" onClick={() => void onDelete(deployment.deployment_id)} type="button">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
              {deployments.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted">
                    No deployments configured yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </DataTableCard>
      </div>
    </section>
  )
}
