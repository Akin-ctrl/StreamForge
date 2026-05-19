import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { type AggregateItem, type AggregateResolution, listAggregates } from '../../shared/api/client'
import { DataTableCard } from '../../shared/data-display/DataTableCard'
import { DetailPanel } from '../../shared/data-display/DetailPanel'
import { FilterPanel } from '../../shared/data-display/FilterPanel'
import { formatDateTime } from '../../shared/format/datetime'
import { PageCallout } from '../../shared/layout/PageCallout'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'
import { localDateTimeToIso, normalizeFilterValue, recordKey } from '../../shared/telemetry/filters'

function uniqueValues(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim())))).sort()
}

function formatMetric(value: number): string {
  return Number.isFinite(value) ? value.toFixed(2) : 'N/A'
}

export function AggregatesPage() {
  const { timezone } = useOperatorPreferences()
  const [resolution, setResolution] = useState<AggregateResolution>('1s')
  const [items, setItems] = useState<AggregateItem[]>([])
  const [selectedAggregateKey, setSelectedAggregateKey] = useState<string | null>(null)
  const [gatewayFilter, setGatewayFilter] = useState('')
  const [assetFilter, setAssetFilter] = useState('')
  const [parameterFilter, setParameterFilter] = useState('')
  const [classificationFilter, setClassificationFilter] = useState('')
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await listAggregates({
        resolution,
        gateway_id: normalizeFilterValue(gatewayFilter),
        asset_id: normalizeFilterValue(assetFilter),
        parameter: normalizeFilterValue(parameterFilter),
        classification: normalizeFilterValue(classificationFilter),
        start_time: localDateTimeToIso(startTime),
        end_time: localDateTimeToIso(endTime),
        limit: 200,
      })
      setItems(rows)
      const nextSelected = rows[0] ? recordKey(rows[0].source_table, rows[0].record_id) : null
      if (!selectedAggregateKey && nextSelected) {
        setSelectedAggregateKey(nextSelected)
      }
      if (
        selectedAggregateKey &&
        !rows.some((row) => recordKey(row.source_table, row.record_id) === selectedAggregateKey)
      ) {
        setSelectedAggregateKey(nextSelected)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load aggregate records')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [resolution, gatewayFilter, assetFilter, parameterFilter, classificationFilter, startTime, endTime])

  const selectedAggregate =
    items.find((item) => recordKey(item.source_table, item.record_id) === selectedAggregateKey) ?? null
  const parameters = useMemo(() => uniqueValues(items.map((item) => item.parameter)), [items])
  const classifications = useMemo(() => uniqueValues(items.map((item) => item.classification)), [items])
  const clearFilters = () => {
    setGatewayFilter('')
    setAssetFilter('')
    setParameterFilter('')
    setClassificationFilter('')
    setStartTime('')
    setEndTime('')
  }

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>Aggregates</h2>
          <p className="muted">
            Inspect persisted aggregate windows from the configured TimescaleDB aggregate sinks.
          </p>
        </div>
        <button className="btn" onClick={() => void refresh()} type="button">
          Refresh
        </button>
      </div>

      <PageCallout title="How to use this view">
        <p className="muted">
          Use the resolution toggle first, then filter down to the asset and parameter you care about before opening
          the detail panel for percentiles and sample quality.
        </p>
      </PageCallout>

      <div className="card tab-strip">
        <button
          className={resolution === '1s' ? 'btn' : 'btn btn-secondary'}
          onClick={() => setResolution('1s')}
          type="button"
        >
          1s Windows
        </button>
        <button
          className={resolution === '1min' ? 'btn' : 'btn btn-secondary'}
          onClick={() => setResolution('1min')}
          type="button"
        >
          1min Windows
        </button>
      </div>

      <FilterPanel
        description="Narrow the aggregate inventory by gateway, asset, parameter, classification, or time."
        onClear={clearFilters}
        title="Filters"
      >
        <label>
          Gateway ID
          <input value={gatewayFilter} onChange={(event) => setGatewayFilter(event.target.value)} placeholder="Any gateway" />
        </label>
        <label>
          Asset ID
          <input value={assetFilter} onChange={(event) => setAssetFilter(event.target.value)} placeholder="Any asset" />
        </label>
        <label>
          Parameter
          <input
            list="aggregate-parameter-options"
            value={parameterFilter}
            onChange={(event) => setParameterFilter(event.target.value)}
            placeholder="Any parameter"
          />
          <datalist id="aggregate-parameter-options">
            {parameters.map((value) => (
              <option key={value} value={value} />
            ))}
          </datalist>
        </label>
        <label>
          Classification
          <input
            list="aggregate-classification-options"
            value={classificationFilter}
            onChange={(event) => setClassificationFilter(event.target.value)}
            placeholder="Any classification"
          />
          <datalist id="aggregate-classification-options">
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
      </FilterPanel>

      {loading && (
        <article className="card empty-state">
          <p>Loading aggregate records...</p>
          <p className="muted">Fetching the latest aggregate windows from the configured aggregate sink.</p>
        </article>
      )}
      {error && <p className="error">{error}</p>}

      {!loading && (
        <div className="alarm-layout">
          <DataTableCard
            description={`${items.length} ${resolution} aggregate record(s) currently match the selected filters.`}
            title="Aggregate Inventory"
          >
            <table className="table">
              <thead>
                <tr>
                  <th>Window End</th>
                  <th>Asset</th>
                  <th>Parameter</th>
                  <th>Avg</th>
                  <th>Min</th>
                  <th>Max</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const itemKey = recordKey(item.source_table, item.record_id)
                  return (
                    <tr
                      key={itemKey}
                      className={selectedAggregateKey === itemKey ? 'alarm-row-selected' : undefined}
                      onClick={() => setSelectedAggregateKey(itemKey)}
                    >
                      <td>{formatDateTime(item.window_end, timezone, { includeTimezone: true })}</td>
                      <td>{item.asset_id}</td>
                      <td>{item.parameter}</td>
                      <td>{formatMetric(item.avg)}</td>
                      <td>{formatMetric(item.min)}</td>
                      <td>{formatMetric(item.max)}</td>
                      <td>{item.count}</td>
                    </tr>
                  )
                })}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={7}>No aggregate records match the current filters.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </DataTableCard>

          <DetailPanel
            description="Select an aggregate window to inspect percentile and quality details."
            title="Aggregate Detail"
          >
            {selectedAggregate ? (
              <div className="review-grid">
                <div className="detail-list">
                  <div className="detail-item">
                    <span className="summary-label">Gateway</span>
                    <div>
                      {selectedAggregate.gateway_id ? (
                        <Link to={`/fleet?gateway=${encodeURIComponent(selectedAggregate.gateway_id)}`}>{selectedAggregate.gateway_id}</Link>
                      ) : (
                        'Unknown'
                      )}
                    </div>
                  </div>
                  <div className="detail-item">
                    <span className="summary-label">Source Table</span>
                    <strong>{selectedAggregate.source_table}</strong>
                  </div>
                  <div className="detail-item">
                    <span className="summary-label">Window Start</span>
                    <strong>{formatDateTime(selectedAggregate.window_start, timezone, { includeTimezone: true })}</strong>
                  </div>
                  <div className="detail-item">
                    <span className="summary-label">Window End</span>
                    <strong>{formatDateTime(selectedAggregate.window_end, timezone, { includeTimezone: true })}</strong>
                  </div>
                  <div className="detail-item">
                    <span className="summary-label">Stddev</span>
                    <strong>{formatMetric(selectedAggregate.stddev)}</strong>
                  </div>
                  <div className="detail-item">
                    <span className="summary-label">P50 / P95 / P99</span>
                    <strong>
                      {formatMetric(selectedAggregate.p50)} / {formatMetric(selectedAggregate.p95)} /{' '}
                      {formatMetric(selectedAggregate.p99)}
                    </strong>
                  </div>
                  <div className="detail-item">
                    <span className="summary-label">Good / Suspect / Uncertain / Bad</span>
                    <strong>
                      {selectedAggregate.good_samples} / {selectedAggregate.suspect_samples} /{' '}
                      {selectedAggregate.uncertain_samples} / {selectedAggregate.bad_samples}
                    </strong>
                  </div>
                  <div className="detail-item">
                    <span className="summary-label">Percent Good</span>
                    <strong>{formatMetric(selectedAggregate.pct_good)}</strong>
                  </div>
                </div>
                <div>
                  <strong>Payload</strong>
                  <pre className="json-preview">{JSON.stringify(selectedAggregate.payload, null, 2)}</pre>
                </div>
              </div>
            ) : null}
          </DetailPanel>
        </div>
      )}
    </section>
  )
}
