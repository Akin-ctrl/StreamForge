import type { GatewayItem } from '../../../shared/api/client'

type DeploymentBasicsSectionProps = {
  deploymentId: string
  name: string
  gatewayId: string
  status: string
  editing: boolean
  gateways: GatewayItem[]
  onDeploymentIdChange: (value: string) => void
  onNameChange: (value: string) => void
  onGatewayIdChange: (value: string) => void
  onStatusChange: (value: string) => void
}

export function DeploymentBasicsSection(props: DeploymentBasicsSectionProps) {
  const {
    deploymentId,
    name,
    gatewayId,
    status,
    editing,
    gateways,
    onDeploymentIdChange,
    onNameChange,
    onGatewayIdChange,
    onStatusChange,
  } = props

  return (
    <article className="card">
      <div className="page-header">
        <div className="card-header-copy">
          <h3>Gateway Assignment</h3>
          <p className="muted">
            Bind one gateway to this deployment and keep the deployment identity readable before attaching reusable
            adapters and sinks.
          </p>
        </div>
      </div>
      <div className="inline-grid">
        <label>
          Deployment ID
          <input disabled={editing} value={deploymentId} onChange={(event) => onDeploymentIdChange(event.target.value)} />
        </label>
        <label>
          Name
          <input value={name} onChange={(event) => onNameChange(event.target.value)} />
        </label>
      </div>
      <div className="inline-grid">
        <label>
          Gateway
          <select value={gatewayId} onChange={(event) => onGatewayIdChange(event.target.value)}>
            {gateways.map((gateway) => (
              <option key={gateway.gateway_id} value={gateway.gateway_id}>
                {gateway.gateway_id}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select value={status} onChange={(event) => onStatusChange(event.target.value)}>
            <option value="draft">draft</option>
            <option value="active">active</option>
            <option value="disabled">disabled</option>
          </select>
        </label>
      </div>
    </article>
  )
}
