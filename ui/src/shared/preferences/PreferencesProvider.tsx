import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'

export type TimezonePreference = 'browser' | string

type PreferencesContextValue = {
  timezone: TimezonePreference
  setTimezone: (timezone: TimezonePreference) => void
  timezoneOptions: string[]
}

const TIMEZONE_KEY = 'sf-timezone'
const FALLBACK_TIMEZONES = [
  'UTC',
  'Africa/Lagos',
  'Europe/London',
  'Europe/Berlin',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Sao_Paulo',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Sydney',
]

const PreferencesContext = createContext<PreferencesContextValue | null>(null)

function resolveTimezoneOptions(): string[] {
  const intlWithSupportedValues = Intl as typeof Intl & {
    supportedValuesOf?: (kind: string) => string[]
  }

  if (typeof intlWithSupportedValues.supportedValuesOf === 'function') {
    try {
      const supported = intlWithSupportedValues.supportedValuesOf('timeZone')
      const merged = new Set<string>(['UTC', ...FALLBACK_TIMEZONES, ...supported])
      return ['UTC', ...Array.from(merged).filter((option) => option !== 'UTC')]
    } catch {
      return FALLBACK_TIMEZONES
    }
  }

  return FALLBACK_TIMEZONES
}

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [timezone, setTimezone] = useState<TimezonePreference>(() => {
    const stored = window.localStorage.getItem(TIMEZONE_KEY)
    return stored && stored.trim() ? stored : 'browser'
  })

  useEffect(() => {
    window.localStorage.setItem(TIMEZONE_KEY, timezone)
  }, [timezone])

  const value = useMemo<PreferencesContextValue>(
    () => ({
      timezone,
      setTimezone,
      timezoneOptions: resolveTimezoneOptions(),
    }),
    [timezone],
  )

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>
}

export function useOperatorPreferences() {
  const context = useContext(PreferencesContext)
  if (!context) {
    throw new Error('useOperatorPreferences must be used within a PreferencesProvider')
  }
  return context
}
