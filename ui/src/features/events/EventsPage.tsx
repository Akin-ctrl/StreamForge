import { useEffect, useMemo, useState } from 'react'

import { type EventItem, listEvents } from '../../shared/api/client'
import { formatDateTime } from '../../shared/format/datetime'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'
import { localDateTimeToIso, normalizeFilterValue, recordKey } from '../../shared/telemetry/filters'

function uniqueValues(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim())))).sort()
}

export function EventsPage() {
  const { timezone } = useOperatorPreferences()
  const [items, setItems] = useState<EventItem[]>([])
  const [selectedEventKey, setSelectedEventKey] = useState<string | null>(null)
  const [gatewayFilter, setGatewayFilter] = useState('')
  const [assetFilter, setAssetFilter] = useState('')
  const [eventTypeFilter, setEventTypeFilter] = useState('')
  const [classificationFilter, setClassificationFilter] = useState('')
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await listEvents({
        gateway_id: normalizeFilterValue(gatewayFilter),
        asset_id: normalizeFilterValue(assetFilter),
        event_type: normalizeFilterValue(eventTypeFilter),
        classification: normalizeFilterValue(classificationFilter),
        start_time: localDateTimeToIso(startTime),
        end_time: localDateTimeToIso(endTime),
        limit: 200,
      })
      setItems(rows)
      const nextSelected = rows[0] ? recordKey(rows[0].source_table, rows[0].record_id) : null
      if (!selectedEventKey && nextSelected) {
        setSelectedEventKey(nextSelected)
      }
      if (
        selectedEventKey &&
        !rows.some((row) => recordKey(row.source_table, row.record_id) === selectedEventKey)
      ) {
        setSelectedEventKey(nextSelected)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load event records')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [gatewayFilter, assetFilter, eventTypeFilter, classificationFilter, startTime, endTime])

  const selectedEvent = items.find((item) => recordKey(item.source_table, item.record_id) === selectedEventKey) ?? null
  const eventTypes = useMemo(() => uniqueValues(items.map((item) => item.event_type)), [items])
  const classifications = useMemo(() => uniqueValues(items.map((item) => item.classification)), [items])

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>Events</h2>
          <p className="muted">
            Review cleaned event records emitted by saved deployments. This view is backed by the configured
            TimescaleDB event sinks.
          </p>
        </div>
        <button className="btn" onClick={() => void refresh()} type="button">
          Refresh
        </button>
      </div>

      <div className="card alarm-filters">
        <label>
          Gateway ID
          <input value={gatewayFilter} onChange={(event) => setGatewayFilter(event.target.value)} placeholder="Any gateway" />
        </label>
        <label>
          Asset ID
          <input value={assetFilter} onChange={(event) => setAssetFilter(event.target.value)} placeholder="Any asset" />
        </label>
        <label>
          Event Type
          <input
            list="event-type-options"
            value={eventTypeFilter}
            onChange={(event) => setEventTypeFilter(event.target.value)}
            placeholder="Any event type"
          />
          <datalist id="event-type-options">
            {eventTypes.map((value) => (
              <option key={value} value={value} />
            ))}
          </datalist>
        </label>
        <label>
          Classification
          <input
            list="event-classification-options"
            value={classificationFilter}
            onChange={(event) => setClassificationFilter(event.target.value)}
            placeholder="Any classification"
          />
          <datalist id="event-classification-options">
            {classifications.map((value) => (
              <option key={value} value={value} />
            ))}
          </datalist>
        </label>
        <label>
          From
          <input type="datetime-local" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
        </label>
        <label>
          To
          <input type="datetime-local" value={endTime} onChange={(event) => setEndTime(event.target.value)} />
        </label>
      </div>

      {loading && <p>Loading event records...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && (
        <div className="alarm-layout">
          <div className="card">
            <table className="table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Asset</th>
                  <th>Type</th>
                  <th>Classification</th>
                  <th>Gateway</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const itemKey = recordKey(item.source_table, item.record_id)
                  return (
                    <tr
                      key={itemKey}
                      className={selectedEventKey === itemKey ? 'alarm-row-selected' : undefined}
                      onClick={() => setSelectedEventKey(itemKey)}
                    >
                      <td>{formatDateTime(item.gateway_time, timezone, { includeTimezone: true })}</td>
                      <td>{item.asset_id}</td>
                      <td>{item.event_type}</td>
                      <td>{item.classification}</td>
                      <td>{item.gateway_id ?? 'Unknown'}</td>
                      <td>{item.source_table}</td>
                    </tr>
                  )
                })}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={6}>No event records match the current filters.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="card alarm-detail">
            <h3>Event Detail</h3>
            {!selectedEvent && (
              <p className="muted">Select an event to inspect state transitions and the persisted payload.</p>
            )}
            {selectedEvent && (
              <div className="review-grid">
                <p>
                  <strong>Gateway:</strong> {selectedEvent.gateway_id ?? 'Unknown'}
                </p>
                <p>
                  <strong>Asset:</strong> {selectedEvent.asset_id}
                </p>
                <p>
                  <strong>Occurred:</strong> {formatDateTime(selectedEvent.gateway_time, timezone, { includeTimezone: true })}
                </p>
                <p>
                  <strong>Device Time:</strong> {formatDateTime(selectedEvent.device_time, timezone, { includeTimezone: true })}
                </p>
                <p>
                  <strong>Source Table:</strong> {selectedEvent.source_table}
                </p>
                <div>
                  <strong>Previous State</strong>
                  <pre className="json-preview">{JSON.stringify(selectedEvent.previous_state, null, 2)}</pre>
                </div>
                <div>
                  <strong>New State</strong>
                  <pre className="json-preview">{JSON.stringify(selectedEvent.new_state, null, 2)}</pre>
                </div>
                <div>
                  <strong>Metadata</strong>
                  <pre className="json-preview">{JSON.stringify(selectedEvent.metadata, null, 2)}</pre>
                </div>
                <div>
                  <strong>Payload</strong>
                  <pre className="json-preview">{JSON.stringify(selectedEvent.payload, null, 2)}</pre>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
