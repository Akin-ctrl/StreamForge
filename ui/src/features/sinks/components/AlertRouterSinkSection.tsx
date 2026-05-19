import type { Dispatch, SetStateAction } from 'react'

import type { CatalogSinkType } from '../../../shared/api/client'
import { getCatalogOptions } from '../../../shared/config/catalog'
import type { SinkFormState } from '../sinkForm'

type AlertRouterSinkSectionProps = {
  contract?: CatalogSinkType
  form: SinkFormState
  setForm: Dispatch<SetStateAction<SinkFormState>>
}

const fallbackRouteTypes = [
  { value: 'webhook', label: 'Webhook' },
  { value: 'slack', label: 'Slack' },
]

export function AlertRouterSinkSection({ contract, form, setForm }: AlertRouterSinkSectionProps) {
  const routeTypes = getCatalogOptions(contract, 'destination', 'route_type')

  return (
    <article className="card">
      <div className="page-header">
        <h3>Alert Router</h3>
      </div>
      <div className="inline-grid">
        <label>
          Route Type
          <select value={form.routeType} onChange={(event) => setForm((current) => ({ ...current, routeType: event.target.value }))}>
            {(routeTypes.length > 0 ? routeTypes : fallbackRouteTypes).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
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
