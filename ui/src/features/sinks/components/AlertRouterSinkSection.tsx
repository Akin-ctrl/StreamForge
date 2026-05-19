import type { Dispatch, SetStateAction } from 'react'

import type { CatalogSinkType } from '../../../shared/api/client'
import { getCatalogOptionsForValue } from '../../../shared/config/catalog'
import type { SinkFormState } from '../sinkForm'

type AlertRouterSinkSectionProps = {
  contract?: CatalogSinkType
  form: SinkFormState
  setForm: Dispatch<SetStateAction<SinkFormState>>
}

export function AlertRouterSinkSection({ contract, form, setForm }: AlertRouterSinkSectionProps) {
  return (
    <article className="card">
      <div className="page-header">
        <div className="card-header-copy">
          <h3>Alert Router</h3>
          <p className="muted">
            Define where alarms should go without exposing the underlying ingress routing that the platform manages for
            this sink.
          </p>
        </div>
      </div>
      <div className="inline-grid">
        <label>
          Route Type
          <select value={form.routeType} onChange={(event) => setForm((current) => ({ ...current, routeType: event.target.value }))}>
            {getCatalogOptionsForValue(contract, 'destination', 'route_type', form.routeType).map((option) => (
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
      <p className="muted">Alarm ingress routing is managed by the platform for alert-router sinks.</p>
    </article>
  )
}
