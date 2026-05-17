import type { AdapterItem, SinkItem } from '../../../shared/api/client'
import { summarizeAdapterConfig, summarizeSinkConfig } from '../../../shared/config/deployments'

type DeploymentReviewPanelProps = {
  deploymentId: string
  gatewayId: string
  status: string
  selectedAdapters: AdapterItem[]
  selectedSinks: SinkItem[]
  validationEnabled: boolean
  eventsEnabled: boolean
  aggregatesEnabled: boolean
}

export function DeploymentReviewPanel(props: DeploymentReviewPanelProps) {
  const {
    deploymentId,
    gatewayId,
    status,
    selectedAdapters,
    selectedSinks,
    validationEnabled,
    eventsEnabled,
    aggregatesEnabled,
  } = props

  return (
    <aside className="card composer-sidebar">
      <h3>Review</h3>
      <div className="review-grid">
        <strong>Deployment</strong>
        <span>{deploymentId || 'New deployment'}</span>
        <strong>Gateway</strong>
        <span>{gatewayId || 'Not selected'}</span>
        <strong>Status</strong>
        <span>{status}</span>
      </div>

      <div className="builder-section">
        <h4>Adapters</h4>
        {selectedAdapters.length === 0 ? (
          <p className="error">Select at least one adapter.</p>
        ) : (
          <ul className="plain-list">
            {selectedAdapters.map((adapter) => (
              <li key={adapter.adapter_id}>
                <strong>{adapter.name}</strong>
                <span className="muted">{summarizeAdapterConfig(adapter.adapter_type, adapter.config)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="builder-section">
        <h4>Sinks</h4>
        {selectedSinks.length === 0 ? (
          <p className="error">Select at least one sink.</p>
        ) : (
          <ul className="plain-list">
            {selectedSinks.map((sink) => (
              <li key={sink.sink_id}>
                <strong>{sink.name}</strong>
                <span className="muted">{summarizeSinkConfig(sink.sink_type, sink.config)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="builder-section">
        <h4>Processing</h4>
        <ul className="plain-list">
          <li>{validationEnabled ? 'Validation enabled' : 'Validation disabled'}</li>
          <li>{eventsEnabled ? 'Events enabled' : 'Events disabled'}</li>
          <li>{aggregatesEnabled ? 'Aggregates enabled' : 'Aggregates disabled'}</li>
        </ul>
      </div>
    </aside>
  )
}
