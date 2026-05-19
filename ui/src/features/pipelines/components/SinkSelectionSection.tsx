import { Link } from 'react-router-dom'

import type { SinkItem } from '../../../shared/api/client'
import { summarizeSinkConfig } from '../../../shared/config/deployments'

type SinkSelectionSectionProps = {
  sinks: SinkItem[]
  selectedIds: string[]
  onToggle: (sinkId: string) => void
}

export function SinkSelectionSection({ sinks, selectedIds, onToggle }: SinkSelectionSectionProps) {
  return (
    <article className="card">
      <div className="page-header">
        <h3>Saved Sinks</h3>
        <Link className="btn btn-secondary" to="/sinks">
          Manage Saved Sinks
        </Link>
      </div>
      <p className="muted">{selectedIds.length} selected</p>
      <p className="muted">
        Choose the saved delivery targets that should receive this gateway&apos;s validated, event, and aggregate
        output.
      </p>
      {sinks.length === 0 ? (
        <div className="empty-state">
          <p className="muted">No sinks are configured yet.</p>
          <Link className="btn btn-secondary" to="/sinks">
            Configure Sinks
          </Link>
        </div>
      ) : (
        <div className="selection-grid">
          {sinks.map((sink) => {
            const selected = selectedIds.includes(sink.sink_id)
            return (
              <label key={sink.sink_id} className={`selection-card${selected ? ' selected' : ''}`}>
                <span className="selection-card-header">
                  <input type="checkbox" checked={selected} onChange={() => onToggle(sink.sink_id)} />
                  <span>
                    <strong>{sink.name}</strong>
                    <span className="muted selection-card-id">{sink.sink_id}</span>
                  </span>
                </span>
                <span className="selection-card-meta">
                  <span>{sink.sink_type}</span>
                  <span>{sink.status}</span>
                </span>
                <span className="muted">{summarizeSinkConfig(sink.sink_type, sink.config)}</span>
              </label>
            )
          })}
        </div>
      )}
    </article>
  )
}
