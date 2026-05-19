/**
 * Shared helpers for event and aggregate query filters.
 * Keep date and text normalization consistent across operator pages.
 */

export function normalizeFilterValue(value: string): string | undefined {
  const normalized = value.trim()
  return normalized ? normalized : undefined
}

export function localDateTimeToIso(value: string): string | undefined {
  if (!value.trim()) {
    return undefined
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return undefined
  }

  return parsed.toISOString()
}

export function recordKey(sourceTable: string, recordId: number): string {
  return `${sourceTable}:${recordId}`
}
