import type { SinkFormState } from '../sinkForm'

type SinkReviewPanelProps = {
  form: SinkFormState
}

export function SinkReviewPanel({ form }: SinkReviewPanelProps) {
  return (
    <aside className="card composer-sidebar">
      <div className="card-header-copy">
        <h3>Sink Summary</h3>
        <p className="muted">Review the saved reusable sink target before validating, testing, or saving it.</p>
      </div>
      <div className="summary-grid">
        <div className="summary-item">
          <span className="summary-label">Sink ID</span>
          <strong>{form.sinkId || 'New sink'}</strong>
        </div>
        <div className="summary-item">
          <span className="summary-label">Type</span>
          <strong>{form.sinkType}</strong>
        </div>
        <div className="summary-item">
          <span className="summary-label">Status</span>
          <strong>{form.status}</strong>
        </div>
      </div>

      <div className="review-section">
        <h4>Ingress</h4>
        <p className="muted">
          {form.sourceTopic || 'No source topic'} · {form.kafkaGroupId || 'No consumer group'}
        </p>
      </div>

      <div className="review-section">
        <h4>Destination</h4>
        {form.sinkType === 'timescaledb' && (
          <p className="muted">
            {form.table} via TimescaleDB
            {form.dbDsnConfigured ? ' · credentials configured' : form.dbDsn.trim() ? ' · credentials pending save' : ''}
          </p>
        )}
        {form.sinkType === 'kafka' && <p className="muted">{form.targetBootstrap} → {form.targetTopic}</p>}
        {form.sinkType === 'http' && <p className="muted">{form.method} {form.url}</p>}
        {form.sinkType === 'alert_router' && (
          <p className="muted">
            {form.routeType === 'slack'
              ? form.slackWebhookUrlConfigured
                ? 'Slack webhook configured'
                : form.slackWebhookUrl.trim()
                  ? 'Slack webhook pending save'
                  : 'Slack webhook not configured'
              : form.webhookUrlConfigured
                ? 'Webhook configured'
                : form.webhookUrl.trim()
                  ? 'Webhook pending save'
                  : 'Webhook not configured'}
          </p>
        )}
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
