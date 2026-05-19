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
            Define the downstream endpoint and method while the platform keeps source-topic routing out of the normal
            operator flow.
          </p>
        </div>
      </div>
      <div className="inline-grid">
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
      <p className="muted">Source-topic routing is managed by the platform for HTTP sinks.</p>
    </article>
  )
}
