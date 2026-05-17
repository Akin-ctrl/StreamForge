import type { Dispatch, SetStateAction } from 'react'

import type { SinkFormState } from '../sinkForm'

type HttpSinkSectionProps = {
  form: SinkFormState
  setForm: Dispatch<SetStateAction<SinkFormState>>
}

export function HttpSinkSection({ form, setForm }: HttpSinkSectionProps) {
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
            <option value="POST">POST</option>
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
