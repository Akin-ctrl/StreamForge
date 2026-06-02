import { useEffect, useMemo, useState } from 'react'

import {
  DlqItem,
  DlqStatus,
  approveDlqMessage,
  bulkAnnotateDlqMessages,
  bulkApproveDlqMessages,
  bulkDiscardDlqMessages,
  discardDlqMessage,
  listDlq,
} from '../../shared/api/client'
import { formatDateTime as formatDateTimeValue } from '../../shared/format/datetime'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'

const statusOptions: Array<DlqStatus | 'ALL'> = [
  'ALL',
  'PENDING',
  'REPROCESS_REQUESTED',
  'REPROCESSED',
  'DISCARD_REQUESTED',
  'DISCARDED',
  'REPROCESS_FAILED',
]

function canApprove(item: DlqItem) {
  return item.status === 'PENDING' || item.status === 'REPROCESS_FAILED'
}

function canDiscard(item: DlqItem) {
  return item.status === 'PENDING' || item.status === 'REPROCESS_FAILED'
}

/**
 * DLQ workflow page.
 * Supports filtering, detail inspection, single-message actions, and bulk reprocess requests.
 */
export function DlqPage() {
  const { timezone } = useOperatorPreferences()
  const [items, setItems] = useState<DlqItem[]>([])
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [statusFilter, setStatusFilter] = useState<DlqStatus | 'ALL'>('ALL')
  const [gatewayFilter, setGatewayFilter] = useState('ALL')
  const [reasonFilter, setReasonFilter] = useState('ALL')
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [bulkBusy, setBulkBusy] = useState(false)
  const [bulkNote, setBulkNote] = useState('')
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await listDlq({
        status: statusFilter === 'ALL' ? undefined : statusFilter,
        gateway_id: gatewayFilter === 'ALL' ? undefined : gatewayFilter,
        reason: reasonFilter === 'ALL' ? undefined : reasonFilter,
        limit: 200,
      })
      setItems(rows)
      setSelectedIds((current) => current.filter((messageId) => rows.some((row) => row.message_id === messageId)))
      if (!selectedMessageId && rows.length > 0) {
        setSelectedMessageId(rows[0].message_id)
      }
      if (selectedMessageId && !rows.some((row) => row.message_id === selectedMessageId)) {
        setSelectedMessageId(rows[0]?.message_id ?? null)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load DLQ messages')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [statusFilter, gatewayFilter, reasonFilter])

  const selectedItem = items.find((item) => item.message_id === selectedMessageId) ?? null
  const gatewayOptions = useMemo(
    () => Array.from(new Set(items.map((item) => item.gateway_id))).sort(),
    [items],
  )
  const reasonOptions = useMemo(
    () => Array.from(new Set(items.map((item) => item.reason))).sort(),
    [items],
  )
  const visibleIds = useMemo(() => items.map((item) => item.message_id), [items])
  const selectedItems = useMemo(
    () => items.filter((item) => selectedIds.includes(item.message_id)),
    [items, selectedIds],
  )
  const selectedApproveIds = useMemo(
    () => selectedItems.filter((item) => canApprove(item)).map((item) => item.message_id),
    [selectedItems],
  )
  const selectedDiscardIds = useMemo(
    () => selectedItems.filter((item) => canDiscard(item)).map((item) => item.message_id),
    [selectedItems],
  )
  const trimmedBulkNote = bulkNote.trim()

  const onToggleSelected = (messageId: string) => {
    setSelectedIds((current) =>
      current.includes(messageId) ? current.filter((item) => item !== messageId) : [...current, messageId],
    )
  }

  const onApprove = async (messageId: string) => {
    setBusyId(messageId)
    setError(null)
    try {
      await approveDlqMessage(messageId)
      await refresh()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to approve DLQ message')
    } finally {
      setBusyId(null)
    }
  }

  const onDiscard = async (messageId: string) => {
    setBusyId(messageId)
    setError(null)
    try {
      await discardDlqMessage(messageId)
      await refresh()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to discard DLQ message')
    } finally {
      setBusyId(null)
    }
  }

  const onBulkApprove = async () => {
    if (selectedApproveIds.length === 0) {
      return
    }

    setBulkBusy(true)
    setError(null)
    try {
      await bulkApproveDlqMessages(selectedApproveIds, undefined, trimmedBulkNote || undefined)
      setSelectedIds([])
      setBulkNote('')
      await refresh()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to bulk approve DLQ messages')
    } finally {
      setBulkBusy(false)
    }
  }

  const onBulkDiscard = async () => {
    if (selectedDiscardIds.length === 0) {
      return
    }

    setBulkBusy(true)
    setError(null)
    try {
      await bulkDiscardDlqMessages(selectedDiscardIds, undefined, trimmedBulkNote || undefined)
      setSelectedIds([])
      setBulkNote('')
      await refresh()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to bulk discard DLQ messages')
    } finally {
      setBulkBusy(false)
    }
  }

  const onBulkAnnotate = async () => {
    if (selectedIds.length === 0 || !trimmedBulkNote) {
      return
    }

    setBulkBusy(true)
    setError(null)
    try {
      await bulkAnnotateDlqMessages(selectedIds, trimmedBulkNote)
      setBulkNote('')
      await refresh()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to annotate DLQ messages')
    } finally {
      setBulkBusy(false)
    }
  }

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>DLQ</h2>
          <p className="muted">Review rejected telemetry, compare preview payloads, and request gateway-side reprocess or discard.</p>
        </div>
        <div className="page-actions">
          <button className="btn" onClick={() => void refresh()}>
            Refresh
          </button>
        </div>
      </div>

      <div className="card alarm-filters">
        <label>
          Status
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as DlqStatus | 'ALL')}>
            {statusOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label>
          Gateway
          <select value={gatewayFilter} onChange={(event) => setGatewayFilter(event.target.value)}>
            <option value="ALL">ALL</option>
            {gatewayOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label>
          Error Type
          <select value={reasonFilter} onChange={(event) => setReasonFilter(event.target.value)}>
            <option value="ALL">ALL</option>
            {reasonOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="card alarm-filters">
        <label>
          Bulk Note
          <textarea
            rows={3}
            value={bulkNote}
            placeholder="Example: Old bad scale/config rows. Discard after confirming current data is clean."
            onChange={(event) => setBulkNote(event.target.value)}
          />
        </label>
        <div className="page-actions">
          <button
            className="btn btn-secondary"
            disabled={bulkBusy || selectedApproveIds.length === 0}
            onClick={() => void onBulkApprove()}
          >
            Reprocess Selected ({selectedApproveIds.length})
          </button>
          <button
            className="btn btn-secondary"
            disabled={bulkBusy || selectedDiscardIds.length === 0}
            onClick={() => void onBulkDiscard()}
          >
            Discard Selected ({selectedDiscardIds.length})
          </button>
          <button
            className="btn"
            disabled={bulkBusy || selectedIds.length === 0 || !trimmedBulkNote}
            onClick={() => void onBulkAnnotate()}
          >
            Annotate Selected ({selectedIds.length})
          </button>
        </div>
        <p className="muted">
          Select visible DLQ rows, add an optional operator note, then reprocess, discard, or annotate the selection.
          Reprocess and discard apply only to pending or failed rows.
        </p>
      </div>

      {loading && <p>Loading DLQ messages...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && (
        <div className="alarm-layout">
          <div className="card">
            <table className="table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      checked={visibleIds.length > 0 && selectedIds.length === visibleIds.length}
                      onChange={(event) => setSelectedIds(event.target.checked ? visibleIds : [])}
                    />
                  </th>
                  <th>Reason</th>
                  <th>Status</th>
                  <th>Gateway</th>
                  <th>Asset</th>
                  <th>Failed</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const isBusy = busyId === item.message_id
                  const isSelected = selectedMessageId === item.message_id
                  return (
                    <tr
                      key={item.message_id}
                      className={isSelected ? 'alarm-row-selected' : undefined}
                      onClick={() => setSelectedMessageId(item.message_id)}
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(item.message_id)}
                          onClick={(event) => event.stopPropagation()}
                          onChange={(event) => {
                            event.stopPropagation()
                            onToggleSelected(item.message_id)
                          }}
                        />
                      </td>
                      <td>
                        <strong>{item.reason}</strong>
                        <div className="muted">{item.message_id}</div>
                      </td>
                      <td>{item.status}</td>
                      <td>{item.gateway_id}</td>
                      <td>{item.asset_id ?? 'Unknown'}</td>
                      <td>{formatDateTimeValue(item.failed_at, timezone, { includeTimezone: true })}</td>
                      <td>
                        {canApprove(item) && (
                          <button
                            className="btn btn-secondary"
                            disabled={isBusy}
                            onClick={(event) => {
                              event.stopPropagation()
                              void onApprove(item.message_id)
                            }}
                          >
                            Approve
                          </button>
                        )}
                        {canDiscard(item) && (
                          <button
                            className="btn btn-secondary"
                            disabled={isBusy}
                            onClick={(event) => {
                              event.stopPropagation()
                              void onDiscard(item.message_id)
                            }}
                          >
                            Discard
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={7}>No DLQ messages match the current filters.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="card alarm-detail">
            <h3>DLQ Detail</h3>
            {!selectedItem && <p className="muted">Select a DLQ message to inspect the failed payload and reprocess preview.</p>}
            {selectedItem && (
              <div className="review-grid">
                <p>
                  <strong>Source Topic:</strong> {selectedItem.source_topic}
                </p>
                <p>
                  <strong>Clean Topic:</strong> {selectedItem.clean_topic}
                </p>
                <p>
                  <strong>Reviewed By:</strong> {selectedItem.reviewed_by ?? 'Not reviewed'}
                </p>
                <p>
                  <strong>Reviewed At:</strong> {formatDateTimeValue(selectedItem.reviewed_at, timezone, { includeTimezone: true })}
                </p>
                <p>
                  <strong>Operator Note:</strong> {selectedItem.operator_note ?? 'None'}
                </p>
                <p>
                  <strong>Action Completed:</strong> {formatDateTimeValue(selectedItem.action_completed_at, timezone, { includeTimezone: true })}
                </p>
                <p>
                  <strong>Last Error:</strong> {selectedItem.last_error ?? 'None'}
                </p>
                <div>
                  <strong>Original Payload</strong>
                  <pre className="json-preview">{JSON.stringify(selectedItem.original_payload, null, 2)}</pre>
                </div>
                <div>
                  <strong>Reprocess Preview</strong>
                  <pre className="json-preview">{JSON.stringify(selectedItem.preview_payload, null, 2)}</pre>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
