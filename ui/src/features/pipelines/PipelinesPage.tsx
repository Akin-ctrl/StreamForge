import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  DeploymentItem,
  deleteDeployment,
  listDeployments,
} from '../../shared/api/client'
import { summarizeDeployment } from '../../shared/config/deployments'
import { formatDateTime } from '../../shared/format/datetime'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'

export function PipelinesPage() {
  const { timezone } = useOperatorPreferences()
  const [deployments, setDeployments] = useState<DeploymentItem[]>([])
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setError(null)
    try {
      const deploymentRows = await listDeployments()
      setDeployments(deploymentRows)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load deployments')
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
    <section>
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

      {error && <p className="error">{error}</p>}

      <div className="overview-kpis">
        <article className="card">
          <h3>Total Deployments</h3>
          <p className="overview-kpi-value">{deployments.length}</p>
          <p className="muted">Saved deployment compositions</p>
        </article>
        <article className="card">
          <h3>Active</h3>
          <p className="overview-kpi-value">{activeCount}</p>
          <p className="muted">Gateways currently pointed at an active deployment</p>
        </article>
        <article className="card">
          <h3>Attached Adapters</h3>
          <p className="overview-kpi-value">{totalAttachedAdapters}</p>
          <p className="muted">Adapter attachments across all deployments</p>
        </article>
        <article className="card">
          <h3>Attached Sinks</h3>
          <p className="overview-kpi-value">{totalAttachedSinks}</p>
          <p className="muted">Sink attachments across all deployments</p>
        </article>
      </div>

      <div className="overview-grid">
        <article className="card">
          <h3>Deployment Inventory</h3>
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
                      <Link className="btn btn-secondary" to={`/pipelines/${encodeURIComponent(deployment.deployment_id)}/edit`}>
                        Edit
                      </Link>{' '}
                      <button className="btn btn-secondary" onClick={() => void onDelete(deployment.deployment_id)} type="button">
                        Delete
                      </button>
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
        </article>
      </div>
    </section>
  )
}
