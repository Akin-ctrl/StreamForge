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
      <h3>Review</h3>
      <div className="review-grid">
        <strong>Adapter ID</strong>
        <span>{form.adapterId || 'New adapter'}</span>
        <strong>Type</strong>
        <span>{form.adapterType}</span>
        <strong>Status</strong>
        <span>{form.status}</span>
      </div>

      <div className="builder-section">
        <h4>Connection</h4>
        {form.adapterType === 'modbus_tcp' && <p className="muted">{form.host}:{form.port}</p>}
        {form.adapterType === 'modbus_rtu' && <p className="muted">{form.serialPort} @ {form.baudrate} baud</p>}
        {form.adapterType === 'mqtt' && <p className="muted">{form.brokerHost}:{form.brokerPort}</p>}
        {form.adapterType === 'opcua' && <p className="muted">{form.endpoint}</p>}
      </div>

      <div className="builder-section">
        <h4>Mapped Signals</h4>
        <ul className="plain-list">
          {form.adapterType.startsWith('modbus') && <li>{pointCount} point{pointCount === 1 ? '' : 's'}</li>}
          {form.adapterType === 'mqtt' && <li>{subscriptionCount} subscription{subscriptionCount === 1 ? '' : 's'}</li>}
          {form.adapterType === 'opcua' && <li>{monitoredItemCount} monitored item{monitoredItemCount === 1 ? '' : 's'}</li>}
        </ul>
      </div>
    </aside>
  )
}
