import type { Dispatch, SetStateAction } from 'react'

import type { CatalogSinkType } from '../../../shared/api/client'
import { getCatalogOptionsForValue } from '../../../shared/config/catalog'
import type { SinkFormState } from '../sinkForm'

type HttpSinkSectionProps = {
  contract?: CatalogSinkType
  form: SinkFormState
  setForm: Dispatch<SetStateAction<SinkFormState>>
}

export function HttpSinkSection({ contract, form, setForm }: HttpSinkSectionProps) {
  return (
    <article className="card">
      <div className="page-header">
        <div className="card-header-copy">
          <h3>HTTP Forwarder</h3>
          <p className="muted">
            Choose the internal stream to forward, then define the downstream endpoint and method.
          </p>
        </div>
      </div>
      <div className="inline-grid">
        <label>
          Source Topic
          <input
            list="sink-source-topic-options"
            value={form.sourceTopic}
            onChange={(event) => setForm((current) => ({ ...current, sourceTopic: event.target.value }))}
          />
        </label>
        <label>
          Consumer Group
          <input
            value={form.kafkaGroupId}
            onChange={(event) => setForm((current) => ({ ...current, kafkaGroupId: event.target.value }))}
          />
        </label>
        <label>
          Destination URL
          <input value={form.url} onChange={(event) => setForm((current) => ({ ...current, url: event.target.value }))} />
        </label>
        <label>
          Method
          <select value={form.method} onChange={(event) => setForm((current) => ({ ...current, method: event.target.value }))}>
            {getCatalogOptionsForValue(contract, 'destination', 'method', form.method).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <datalist id="sink-source-topic-options">
        <option value="telemetry.clean" />
        <option value="telemetry.1s" />
        <option value="telemetry.1min" />
        <option value="events.clean" />
        <option value="alarms.raw" />
      </datalist>
      <p className="muted">Use a distinct consumer group when this sink must read independently from other sinks.</p>
    </article>
  )
}
