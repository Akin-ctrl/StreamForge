import type { SinkFormState } from '../sinkForm'

type SinkReviewPanelProps = {
  form: SinkFormState
}

export function SinkReviewPanel({ form }: SinkReviewPanelProps) {
  return (
    <aside className="card composer-sidebar">
      <h3>Review</h3>
      <div className="review-grid">
        <strong>Sink ID</strong>
        <span>{form.sinkId || 'New sink'}</span>
        <strong>Type</strong>
        <span>{form.sinkType}</span>
        <strong>Status</strong>
        <span>{form.status}</span>
      </div>

      <div className="builder-section">
        <h4>Destination</h4>
        {form.sinkType === 'timescaledb' && <p className="muted">{form.table} via TimescaleDB</p>}
        {form.sinkType === 'kafka' && <p className="muted">{form.targetBootstrap} → {form.targetTopic}</p>}
        {form.sinkType === 'http' && <p className="muted">{form.method} {form.url}</p>}
        {form.sinkType === 'alert_router' && (
          <p className="muted">{form.routeType === 'slack' ? form.slackWebhookUrl : form.webhookUrl}</p>
        )}
      </div>
    </aside>
  )
}
