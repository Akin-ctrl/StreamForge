import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { type LogEntry, listLogs } from '../../shared/api/client'
import { DataTableCard } from '../../shared/data-display/DataTableCard'
import { DetailPanel } from '../../shared/data-display/DetailPanel'
import { FilterPanel } from '../../shared/data-display/FilterPanel'
import { StatusChip } from '../../shared/data-display/StatusChip'
import { formatDateTime } from '../../shared/format/datetime'
import { PageCallout } from '../../shared/layout/PageCallout'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'
import { normalizeFilterValue } from '../../shared/telemetry/filters'

const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] as const

function uniqueValues(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim())))).sort()
}

function logEntryKey(entry: LogEntry): string {
  return `${entry.gateway_id}:${entry.timestamp}:${entry.logger}:${entry.message}`
}

function logLevelTone(level: string): 'good' | 'warn' | 'bad' | 'neutral' {
  if (level === 'ERROR' || level === 'CRITICAL') {
    return 'bad'
  }
  if (level === 'WARNING') {
    return 'warn'
  }
  if (level === 'INFO') {
    return 'good'
  }
  return 'neutral'
}

export function LogsPage() {
  const { timezone } = useOperatorPreferences()
  const [searchParams, setSearchParams] = useSearchParams()
  const [items, setItems] = useState<LogEntry[]>([])
  const [selectedLogKey, setSelectedLogKey] = useState<string | null>(null)
  const [gatewayFilter, setGatewayFilter] = useState(searchParams.get('gateway') ?? '')
  const [componentFilter, setComponentFilter] = useState(searchParams.get('component') ?? '')
  const [levelFilter, setLevelFilter] = useState(searchParams.get('level') ?? '')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await listLogs({
        gateway_id: normalizeFilterValue(gatewayFilter),
        component: normalizeFilterValue(componentFilter),
        level: normalizeFilterValue(levelFilter),
        limit: 200,
      })
      setItems(rows)
      const nextSelected = rows[0] ? logEntryKey(rows[0]) : null
      if (!selectedLogKey && nextSelected) {
        setSelectedLogKey(nextSelected)
      }
      if (selectedLogKey && !rows.some((row) => logEntryKey(row) === selectedLogKey)) {
        setSelectedLogKey(nextSelected)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load runtime logs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setGatewayFilter(searchParams.get('gateway') ?? '')
    setComponentFilter(searchParams.get('component') ?? '')
    setLevelFilter(searchParams.get('level') ?? '')
  }, [searchParams])

  useEffect(() => {
    const nextParams = new URLSearchParams()
    const normalizedGateway = normalizeFilterValue(gatewayFilter)
    const normalizedComponent = normalizeFilterValue(componentFilter)
    const normalizedLevel = normalizeFilterValue(levelFilter)
    if (normalizedGateway) {
      nextParams.set('gateway', normalizedGateway)
    }
    if (normalizedComponent) {
      nextParams.set('component', normalizedComponent)
    }
    if (normalizedLevel) {
      nextParams.set('level', normalizedLevel)
    }
    if (nextParams.toString() !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: true })
    }
  }, [gatewayFilter, componentFilter, levelFilter, searchParams, setSearchParams])

  useEffect(() => {
    void refresh()
  }, [gatewayFilter, componentFilter, levelFilter])

  const selectedLog = items.find((item) => logEntryKey(item) === selectedLogKey) ?? null
  const components = useMemo(() => uniqueValues(items.map((item) => item.component)), [items])
  const gateways = useMemo(() => uniqueValues(items.map((item) => item.gateway_id)), [items])
  const clearFilters = () => {
    setGatewayFilter('')
    setComponentFilter('')
    setLevelFilter('')
  }

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>Logs</h2>
          <p className="muted">
            Inspect recent gateway-runtime logs captured through gateway heartbeat state. This view follows heartbeat
            cadence rather than live streaming container output.
          </p>
        </div>
        <button className="btn" onClick={() => void refresh()} type="button">
          Refresh
        </button>
      </div>

      <PageCallout title="How to use this view">
        <p className="muted">
          Filter the recent runtime log tail by gateway, component, or level, then inspect one entry at a time for
          exception context and operator-facing troubleshooting.
        </p>
      </PageCallout>

      <FilterPanel
        description="Narrow the recent runtime log tail by gateway, component, or severity."
        onClear={clearFilters}
        title="Filters"
      >
        <label>
          Gateway ID
          <input
            list="log-gateway-options"
            value={gatewayFilter}
            onChange={(event) => setGatewayFilter(event.target.value)}
            placeholder="Any gateway"
          />
          <datalist id="log-gateway-options">
            {gateways.map((value) => (
              <option key={value} value={value} />
            ))}
          </datalist>
        </label>
        <label>
          Component
          <input
            list="log-component-options"
            value={componentFilter}
            onChange={(event) => setComponentFilter(event.target.value)}
            placeholder="Any component"
          />
          <datalist id="log-component-options">
            {components.map((value) => (
              <option key={value} value={value} />
            ))}
          </datalist>
        </label>
        <label>
          Level
          <select value={levelFilter} onChange={(event) => setLevelFilter(event.target.value)}>
            <option value="">Any level</option>
            {LOG_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>
      </FilterPanel>

      {loading && (
        <article className="card empty-state">
          <p>Loading recent runtime logs...</p>
          <p className="muted">Fetching the current gateway-runtime log tail carried through heartbeat state.</p>
        </article>
      )}
      {error && <p className="error">{error}</p>}

      {!loading && (
        <div className="alarm-layout">
          <DataTableCard
            description={`${items.length} log line(s) currently match the selected filters.`}
            title="Recent Runtime Logs"
          >
            <table className="table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Gateway</th>
                  <th>Component</th>
                  <th>Level</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const itemKey = logEntryKey(item)
                  return (
                    <tr
                      key={itemKey}
                      className={selectedLogKey === itemKey ? 'alarm-row-selected' : undefined}
                      onClick={() => setSelectedLogKey(itemKey)}
                    >
                      <td>{formatDateTime(item.timestamp, timezone, { includeTimezone: true })}</td>
                      <td>{item.gateway_id}</td>
                      <td>{item.component}</td>
                      <td>
                        <StatusChip label={String(item.level)} tone={logLevelTone(String(item.level))} />
                      </td>
                      <td>{item.message}</td>
                    </tr>
                  )
                })}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={5}>No recent runtime logs match the current filters.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </DataTableCard>

          <DetailPanel
            description="Select a log line to inspect the gateway, logger, and exception details."
            title="Log Detail"
          >
            {selectedLog ? (
              <div className="review-grid">
                <div className="detail-list">
                  <div className="detail-item">
                    <span className="summary-label">Gateway</span>
                    <div>
                      <Link to={`/fleet?gateway=${encodeURIComponent(selectedLog.gateway_id)}`}>{selectedLog.gateway_id}</Link>
                    </div>
                  </div>
                  <div className="detail-item">
                    <span className="summary-label">Component</span>
                    <strong>{selectedLog.component}</strong>
                  </div>
                  <div className="detail-item">
                    <span className="summary-label">Level</span>
                    <StatusChip label={String(selectedLog.level)} tone={logLevelTone(String(selectedLog.level))} />
                  </div>
                  <div className="detail-item">
                    <span className="summary-label">Logger</span>
                    <strong>{selectedLog.logger}</strong>
                  </div>
                  <div className="detail-item">
                    <span className="summary-label">Captured</span>
                    <strong>{formatDateTime(selectedLog.timestamp, timezone, { includeTimezone: true })}</strong>
                  </div>
                </div>
                <div>
                  <strong>Message</strong>
                  <pre className="json-preview">{selectedLog.message}</pre>
                </div>
                {selectedLog.exception ? (
                  <div>
                    <strong>Exception</strong>
                    <pre className="json-preview">{selectedLog.exception}</pre>
                  </div>
                ) : null}
              </div>
            ) : null}
          </DetailPanel>
        </div>
      )}
    </section>
  )
}
