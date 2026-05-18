import type { Dispatch, SetStateAction } from 'react'

import type { SinkFormState } from '../sinkForm'

type AlertRouterSinkSectionProps = {
  form: SinkFormState
  setForm: Dispatch<SetStateAction<SinkFormState>>
}

export function AlertRouterSinkSection({ form, setForm }: AlertRouterSinkSectionProps) {
  return (
    <article className="card">
      <div className="page-header">
        <h3>Alert Router</h3>
      </div>
      <div className="inline-grid">
        <label>
          Route Type
          <select value={form.routeType} onChange={(event) => setForm((current) => ({ ...current, routeType: event.target.value }))}>
            <option value="webhook">Webhook</option>
            <option value="slack">Slack</option>
          </select>
        </label>
        {form.routeType === 'slack' ? (
          <label>
            Slack Webhook URL
            <input
              placeholder={form.slackWebhookUrlConfigured ? 'Leave blank to keep current webhook' : ''}
              value={form.slackWebhookUrl}
              onChange={(event) => setForm((current) => ({ ...current, slackWebhookUrl: event.target.value }))}
            />
            {form.slackWebhookUrlConfigured && <span className="muted">A Slack webhook is already configured.</span>}
          </label>
        ) : (
          <label>
            Webhook URL
            <input
              placeholder={form.webhookUrlConfigured ? 'Leave blank to keep current webhook' : ''}
              value={form.webhookUrl}
              onChange={(event) => setForm((current) => ({ ...current, webhookUrl: event.target.value }))}
            />
            {form.webhookUrlConfigured && <span className="muted">A webhook destination is already configured.</span>}
          </label>
        )}
      </div>
      <details className="card nested-card advanced-block">
        <summary>Advanced</summary>
        <label>
          Source Topic
          <input value={form.sourceTopic} onChange={(event) => setForm((current) => ({ ...current, sourceTopic: event.target.value }))} />
        </label>
      </details>
    </article>
  )
}
