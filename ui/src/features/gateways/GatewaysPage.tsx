import { useEffect, useMemo, useState } from 'react'

import {
  type DeploymentItem,
  type GatewayEnrollmentCreateResponse,
  type GatewayEnrollmentItem,
  type GatewayItem,
  approveGateway,
  createGateway,
  createGatewayEnrollment,
  disableGatewayEnrollment,
  listDeployments,
  listGatewayEnrollments,
  listGateways,
} from '../../shared/api/client'
import { summarizeDeployment } from '../../shared/config/deployments'
import { formatDateTime } from '../../shared/format/datetime'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'

export function GatewaysPage() {
  const { timezone } = useOperatorPreferences()
  const [items, setItems] = useState<GatewayItem[]>([])
  const [enrollments, setEnrollments] = useState<GatewayEnrollmentItem[]>([])
  const [deployments, setDeployments] = useState<DeploymentItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [gatewayId, setGatewayId] = useState('gateway-demo-01')
  const [hostname, setHostname] = useState('gateway-demo-01.local')
  const [enrollmentName, setEnrollmentName] = useState('Site install token')
  const [siteName, setSiteName] = useState('')
  const [siteCode, setSiteCode] = useState('')
  const [maxUses, setMaxUses] = useState('1')
  const [expiresInHours, setExpiresInHours] = useState('24')
  const [createdEnrollment, setCreatedEnrollment] = useState<GatewayEnrollmentCreateResponse | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const [gateways, deploymentRows, enrollmentRows] = await Promise.all([
        listGateways(),
        listDeployments(),
        listGatewayEnrollments(),
      ])
      setItems(gateways)
      setDeployments(deploymentRows)
      setEnrollments(enrollmentRows)
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
      setMessage(`Gateway ${targetGatewayId} approved.`)
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
      setMessage(`Gateway ${gatewayId} created and approved.`)
      await refresh()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Failed to create gateway')
    }
  }

  const onCreateEnrollment = async () => {
    setError(null)
    setMessage(null)
    setCreatedEnrollment(null)

    const resolvedMaxUses = maxUses.trim() ? Number(maxUses) : null
    const resolvedExpiryHours = expiresInHours.trim() ? Number(expiresInHours) : null
    if (resolvedMaxUses !== null && (!Number.isInteger(resolvedMaxUses) || resolvedMaxUses < 1)) {
      setError('Max uses must be a positive whole number, or blank for unlimited use.')
      return
    }
    if (resolvedExpiryHours !== null && (!Number.isFinite(resolvedExpiryHours) || resolvedExpiryHours <= 0)) {
      setError('Expiry must be a positive number of hours, or blank for no expiry.')
      return
    }

    try {
      const created = await createGatewayEnrollment({
        name: enrollmentName,
        site_name: siteName.trim() || null,
        site_code: siteCode.trim() || null,
        max_uses: resolvedMaxUses,
        expires_at: resolvedExpiryHours === null ? null : new Date(Date.now() + resolvedExpiryHours * 60 * 60 * 1000).toISOString(),
      })
      setCreatedEnrollment(created)
      setMessage('Enrollment token created. Copy it now; it will not be shown again.')
      await refresh()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Failed to create enrollment token')
    }
  }

  const onDisableEnrollment = async (enrollmentId: string) => {
    setError(null)
    setMessage(null)
    try {
      await disableGatewayEnrollment(enrollmentId)
      setMessage(`Enrollment token ${enrollmentId} disabled.`)
      await refresh()
    } catch (disableError) {
      setError(disableError instanceof Error ? disableError.message : 'Failed to disable enrollment token')
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

  const pendingGateways = useMemo(() => items.filter((item) => !item.approved), [items])
  const activeEnrollmentCount = useMemo(
    () => enrollments.filter((item) => !item.disabled && (item.max_uses == null || item.used_count < item.max_uses)).length,
    [enrollments],
  )

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>Gateways</h2>
          <p className="muted">
            Enroll field gateways, approve pending devices, and keep the gateway inventory aligned with real site
            deployments.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn" onClick={() => void refresh()} type="button">
            Refresh
          </button>
        </div>
      </div>
      <p className="muted">
        Each gateway runs one active deployment at a time. That deployment can attach multiple adapters, multiple sinks,
        and the validation, event, and aggregate rules for the runtime.
      </p>

      <div className="card">
        <div className="page-header">
          <div>
            <h3>Enrollment Tokens</h3>
            <p className="muted">
              Create a site/install token, place it on the gateway as <code>CONTROL_PLANE_ENROLLMENT_TOKEN</code>,
              then approve the pending gateway when it appears.
            </p>
          </div>
          <strong>{activeEnrollmentCount} active</strong>
        </div>
        <div className="inline-grid">
          <label>
            Token Name
            <input value={enrollmentName} onChange={(event) => setEnrollmentName(event.target.value)} />
          </label>
          <label>
            Site Name
            <input value={siteName} onChange={(event) => setSiteName(event.target.value)} placeholder="Plant A" />
          </label>
          <label>
            Site Code
            <input value={siteCode} onChange={(event) => setSiteCode(event.target.value)} placeholder="plant-a" />
          </label>
          <label>
            Max Uses
            <input value={maxUses} onChange={(event) => setMaxUses(event.target.value)} inputMode="numeric" />
          </label>
          <label>
            Expires In Hours
            <input value={expiresInHours} onChange={(event) => setExpiresInHours(event.target.value)} inputMode="decimal" />
          </label>
          <button className="btn" onClick={() => void onCreateEnrollment()} type="button">
            Create Enrollment Token
          </button>
        </div>

        {createdEnrollment && (
          <div className="nested-card enrollment-token-card">
            <strong>Copy this token now</strong>
            <p className="muted">For safety, the full token is only returned once.</p>
            <code>{createdEnrollment.token}</code>
          </div>
        )}

        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Preview</th>
                <th>Site</th>
                <th>Uses</th>
                <th>Expires</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {enrollments.map((item) => (
                <tr key={item.enrollment_id}>
                  <td>{item.name}</td>
                  <td>{item.token_preview}</td>
                  <td>{item.site_name || item.site_code || 'Unassigned'}</td>
                  <td>
                    {item.used_count}
                    {item.max_uses === null ? ' / unlimited' : ` / ${item.max_uses}`}
                  </td>
                  <td>{formatDateTime(item.expires_at || null, timezone, { includeTimezone: true })}</td>
                  <td>{item.disabled ? 'Disabled' : 'Active'}</td>
                  <td>
                    {!item.disabled && (
                      <button
                        className="btn btn-secondary"
                        onClick={() => void onDisableEnrollment(item.enrollment_id)}
                        type="button"
                      >
                        Disable
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {enrollments.length === 0 && (
                <tr>
                  <td colSpan={7}>No enrollment tokens have been created yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {pendingGateways.length > 0 && (
        <div className="card">
          <div className="page-header">
            <div>
              <h3>Pending Gateway Approvals</h3>
              <p className="muted">Review enrolled gateways before they can receive runtime tokens or deployment config.</p>
            </div>
          </div>
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Hostname</th>
                  <th>Last Seen</th>
                  <th>Hardware</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pendingGateways.map((item) => (
                  <tr key={item.gateway_id}>
                    <td>{item.gateway_id}</td>
                    <td>{item.hostname}</td>
                    <td>{formatDateTime(item.last_seen_at || null, timezone, { includeTimezone: true })}</td>
                    <td>
                      <code>{JSON.stringify(item.hardware_info || {})}</code>
                    </td>
                    <td>
                      <button className="btn btn-secondary" onClick={() => void onApprove(item.gateway_id)} type="button">
                        Approve
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="card">
        <h3>Manual Gateway Creation</h3>
        <p className="muted">
          Keep this for controlled environments and local development. Production-like installs should prefer enrollment
          tokens and operator approval.
        </p>
        <div className="inline-grid">
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
      </div>

      {loading && <p>Loading gateways...</p>}
      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}

      {!loading && (
        <div className="table-scroll">
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
        </div>
      )}
    </section>
  )
}
