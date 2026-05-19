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
      <div className="card-header-copy">
        <h3>Deployment Summary</h3>
        <p className="muted">
          Review the gateway assignment, attached objects, and processing posture before saving or activating a
          deployment.
        </p>
      </div>
      <div className="summary-grid">
        <div className="summary-item">
          <span className="summary-label">Deployment</span>
          <strong>{deploymentId || 'New deployment'}</strong>
        </div>
        <div className="summary-item">
          <span className="summary-label">Gateway</span>
          <strong>{gatewayId || 'Not selected'}</strong>
        </div>
        <div className="summary-item">
          <span className="summary-label">Status</span>
          <strong>{status}</strong>
        </div>
      </div>

      <div className="review-section">
        <h4>Saved Adapters</h4>
        {selectedAdapters.length === 0 ? (
          <p className="error">Select at least one adapter.</p>
        ) : (
          <ul className="review-list">
            {selectedAdapters.map((adapter) => (
              <li key={adapter.adapter_id}>
                <strong>{adapter.name}</strong>
                <span className="muted">{summarizeAdapterConfig(adapter.adapter_type, adapter.config)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="review-section">
        <h4>Saved Sinks</h4>
        {selectedSinks.length === 0 ? (
          <p className="error">Select at least one sink.</p>
        ) : (
          <ul className="review-list">
            {selectedSinks.map((sink) => (
              <li key={sink.sink_id}>
                <strong>{sink.name}</strong>
                <span className="muted">{summarizeSinkConfig(sink.sink_type, sink.config)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="review-section">
        <h4>Processing</h4>
        <ul className="review-list">
          <li>{validationEnabled ? 'Validation enabled' : 'Validation disabled'}</li>
          <li>{eventsEnabled ? 'Events enabled' : 'Events disabled'}</li>
          <li>{aggregatesEnabled ? 'Aggregates enabled' : 'Aggregates disabled'}</li>
        </ul>
      </div>

      <div className="review-section">
        <h4>Readiness</h4>
        <ul className="review-list">
          <li>{gatewayId ? 'Gateway selected' : 'Select a gateway before saving.'}</li>
          <li>{selectedAdapters.length > 0 ? 'Adapters attached' : 'Attach at least one saved adapter.'}</li>
          <li>{selectedSinks.length > 0 ? 'Sinks attached' : 'Attach at least one saved sink.'}</li>
        </ul>
      </div>
    </aside>
  )
}
