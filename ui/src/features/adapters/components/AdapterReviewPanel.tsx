import type { AdapterFormState } from '../adapterForm'

type AdapterReviewPanelProps = {
  form: AdapterFormState
}

export function AdapterReviewPanel({ form }: AdapterReviewPanelProps) {
  const pointCount = form.points.length
  const subscriptionCount = form.subscriptions.length
  const monitoredItemCount = form.monitoredItems.length

  return (
    <aside className="card composer-sidebar">
      <div className="card-header-copy">
        <h3>Adapter Summary</h3>
        <p className="muted">Review the saved reusable adapter object before validating, testing, or saving it.</p>
      </div>
      <div className="summary-grid">
        <div className="summary-item">
          <span className="summary-label">Adapter ID</span>
          <strong>{form.adapterId || 'New adapter'}</strong>
        </div>
        <div className="summary-item">
          <span className="summary-label">Type</span>
          <strong>{form.adapterType}</strong>
        </div>
        <div className="summary-item">
          <span className="summary-label">Status</span>
          <strong>{form.status}</strong>
        </div>
      </div>

      <div className="review-section">
        <h4>Connection</h4>
        {form.adapterType === 'modbus_tcp' && <p className="muted">{form.host}:{form.port}</p>}
        {form.adapterType === 'modbus_rtu' && <p className="muted">{form.serialPort} @ {form.baudrate} baud</p>}
        {form.adapterType === 'mqtt' && <p className="muted">{form.brokerHost}:{form.brokerPort}</p>}
        {form.adapterType === 'opcua' && <p className="muted">{form.endpoint}</p>}
      </div>

      <div className="review-section">
        <h4>Mapped Signals</h4>
        <ul className="review-list">
          {form.adapterType.startsWith('modbus') && <li>{pointCount} point{pointCount === 1 ? '' : 's'}</li>}
          {form.adapterType === 'mqtt' && <li>{subscriptionCount} subscription{subscriptionCount === 1 ? '' : 's'}</li>}
          {form.adapterType === 'opcua' && <li>{monitoredItemCount} monitored item{monitoredItemCount === 1 ? '' : 's'}</li>}
        </ul>
      </div>

      <div className="review-section">
        <h4>Readiness</h4>
        <ul className="review-list">
          <li>{form.name.trim() ? 'Display name provided' : 'Add a display name before saving.'}</li>
          <li>{form.description.trim() ? 'Description added' : 'Description is optional but helps reuse.'}</li>
        </ul>
      </div>
    </aside>
  )
}
