import { Link } from 'react-router-dom'

import type { AdapterItem, DeploymentItem, GatewayItem, SinkItem } from '../../../shared/api/client'
import { summarizeAdapterConfig, summarizeSinkConfig } from '../../../shared/config/deployments'

type TopologyViewProps = {
  gateway: GatewayItem
  activeDeployment: DeploymentItem | null
  adapters: AdapterItem[]
  sinks: SinkItem[]
}

function processingNodes(activeDeployment: DeploymentItem | null): string[] {
  if (!activeDeployment) {
    return []
  }

  const nodes: string[] = []
  if (activeDeployment.validation_config?.enabled) {
    nodes.push('Validation')
  }
  if (activeDeployment.events_config?.enabled) {
    nodes.push('Events')
  }
  if (activeDeployment.aggregates_config?.enabled) {
    nodes.push('Aggregates')
  }
  return nodes
}

export function TopologyView({ gateway, activeDeployment, adapters, sinks }: TopologyViewProps) {
  const processing = processingNodes(activeDeployment)

  return (
    <div className="fleet-topology">
      <div className="topology-column">
        <h4>Gateway</h4>
        <div className="topology-node">
          <strong>{gateway.gateway_id}</strong>
          <span className="muted">{gateway.hostname}</span>
        </div>
      </div>

      <div className="topology-column">
        <h4>Deployment</h4>
        {activeDeployment ? (
          <div className="topology-node">
            <strong>{activeDeployment.name}</strong>
            <span className="muted">{activeDeployment.deployment_id}</span>
            <Link className="topology-link" to={`/pipelines/${encodeURIComponent(activeDeployment.deployment_id)}/edit`}>
              Open deployment
            </Link>
          </div>
        ) : (
          <div className="topology-node topology-node-empty">
            <span className="muted">No active deployment</span>
          </div>
        )}
      </div>

      <div className="topology-column">
        <h4>Adapters</h4>
        {adapters.length > 0 ? (
          adapters.map((adapter) => (
            <div className="topology-node" key={adapter.adapter_id}>
              <strong>{adapter.name}</strong>
              <span className="muted">{adapter.adapter_id}</span>
              <span className="muted">{summarizeAdapterConfig(adapter.adapter_type, adapter.config)}</span>
            </div>
          ))
        ) : (
          <div className="topology-node topology-node-empty">
            <span className="muted">No attached adapters</span>
          </div>
        )}
      </div>

      <div className="topology-column">
        <h4>Processing</h4>
        {processing.length > 0 ? (
          processing.map((node) => (
            <div className="topology-node" key={node}>
              <strong>{node}</strong>
            </div>
          ))
        ) : (
          <div className="topology-node topology-node-empty">
            <span className="muted">No processing stages enabled</span>
          </div>
        )}
      </div>

      <div className="topology-column">
        <h4>Sinks</h4>
        {sinks.length > 0 ? (
          sinks.map((sink) => (
            <div className="topology-node" key={sink.sink_id}>
              <strong>{sink.name}</strong>
              <span className="muted">{sink.sink_id}</span>
              <span className="muted">{summarizeSinkConfig(sink.sink_type, sink.config)}</span>
            </div>
          ))
        ) : (
          <div className="topology-node topology-node-empty">
            <span className="muted">No attached sinks</span>
          </div>
        )}
      </div>
    </div>
  )
}
