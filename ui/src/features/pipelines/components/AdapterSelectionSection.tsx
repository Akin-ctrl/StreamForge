import { Link } from 'react-router-dom'

import type { AdapterItem } from '../../../shared/api/client'
import { summarizeAdapterConfig } from '../../../shared/config/deployments'

type AdapterSelectionSectionProps = {
  adapters: AdapterItem[]
  selectedIds: string[]
  onToggle: (adapterId: string) => void
}

export function AdapterSelectionSection({ adapters, selectedIds, onToggle }: AdapterSelectionSectionProps) {
  return (
    <article className="card">
      <div className="page-header">
        <h3>Adapters</h3>
        <span className="muted">{selectedIds.length} selected</span>
      </div>
      <p className="muted">
        Choose the saved ingress connections that should run on this gateway. Each adapter can already contain many
        mapped points, subscriptions, or monitored items.
      </p>
      {adapters.length === 0 ? (
        <div className="empty-state">
          <p className="muted">No adapters are configured yet.</p>
          <Link className="btn btn-secondary" to="/adapters">
            Configure Adapters
          </Link>
        </div>
      ) : (
        <div className="selection-grid">
          {adapters.map((adapter) => {
            const selected = selectedIds.includes(adapter.adapter_id)
            return (
              <label key={adapter.adapter_id} className={`selection-card${selected ? ' selected' : ''}`}>
                <span className="selection-card-header">
                  <input type="checkbox" checked={selected} onChange={() => onToggle(adapter.adapter_id)} />
                  <span>
                    <strong>{adapter.name}</strong>
                    <span className="muted selection-card-id">{adapter.adapter_id}</span>
                  </span>
                </span>
                <span className="selection-card-meta">
                  <span>{adapter.adapter_type}</span>
                  <span>{adapter.status}</span>
                </span>
                <span className="muted">{summarizeAdapterConfig(adapter.adapter_type, adapter.config)}</span>
              </label>
            )
          })}
        </div>
      )}
    </article>
  )
}
