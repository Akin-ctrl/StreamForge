let nextRowId = 1

/**
 * Returns a stable UI-only identifier for repeatable form rows.
 * These ids never leave the browser state; they only keep React row identity
 * stable while operators edit fields that would otherwise change the row key.
 */
export function createFormRowId(prefix: string): string {
  const rowId = `${prefix}-${nextRowId}`
  nextRowId += 1
  return rowId
}
