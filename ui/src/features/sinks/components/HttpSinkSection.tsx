import type { Dispatch, SetStateAction } from 'react'

import type { CatalogSinkType } from '../../../shared/api/client'
import { getCatalogOptions } from '../../../shared/config/catalog'
import type { SinkFormState } from '../sinkForm'

type HttpSinkSectionProps = {
  contract?: CatalogSinkType
  form: SinkFormState
  setForm: Dispatch<SetStateAction<SinkFormState>>
}

const fallbackMethods = [{ value: 'POST', label: 'POST' }]

export function HttpSinkSection({ contract, form, setForm }: HttpSinkSectionProps) {
  const methodOptions = getCatalogOptions(contract, 'destination', 'method')

  return (
    <article className="card">
      <div className="page-header">
        <h3>HTTP Forwarder</h3>
      </div>
      <div className="inline-grid">
        <label>
          Destination URL
          <input value={form.url} onChange={(event) => setForm((current) => ({ ...current, url: event.target.value }))} />
        </label>
        <label>
          Method
          <select value={form.method} onChange={(event) => setForm((current) => ({ ...current, method: event.target.value }))}>
            {(methodOptions.length > 0 ? methodOptions : fallbackMethods).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
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
