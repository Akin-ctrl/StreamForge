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
              value={form.slackWebhookUrl}
              onChange={(event) => setForm((current) => ({ ...current, slackWebhookUrl: event.target.value }))}
            />
          </label>
        ) : (
          <label>
            Webhook URL
            <input value={form.webhookUrl} onChange={(event) => setForm((current) => ({ ...current, webhookUrl: event.target.value }))} />
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
