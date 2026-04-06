import { TimezonePreference } from '../preferences/PreferencesProvider'

type DateTimeFormatOptions = {
  includeTimezone?: boolean
  fallback?: string
}

export function formatDateTime(
  value: string | null | undefined,
  timezone: TimezonePreference,
  options: DateTimeFormatOptions = {},
): string {
  if (!value) {
    return options.fallback || 'Not set'
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return options.fallback || 'Invalid date'
  }

  const resolvedTimeZone = timezone === 'browser' ? undefined : timezone
  const formatterOptions: Intl.DateTimeFormatOptions = options.includeTimezone
    ? {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        timeZone: resolvedTimeZone,
        timeZoneName: 'short',
      }
    : {
        dateStyle: 'medium',
        timeStyle: 'medium',
        timeZone: resolvedTimeZone,
      }

  const formatter = new Intl.DateTimeFormat(undefined, formatterOptions)

  return formatter.format(parsed)
}
