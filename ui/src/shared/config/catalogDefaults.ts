import type { CatalogContract } from './catalogFields'
import { getCatalogField } from './catalogFields'

export function getCatalogFieldDefault(
  contract: CatalogContract | undefined,
  sectionKey: string,
  fieldKey: string,
): string | number | boolean | null | undefined {
  return getCatalogField(contract, sectionKey, fieldKey)?.default
}

export function getCatalogStringDefault(
  contract: CatalogContract | undefined,
  sectionKey: string,
  fieldKey: string,
  fallback = '',
): string {
  const value = getCatalogFieldDefault(contract, sectionKey, fieldKey)
  if (typeof value === 'string') {
    return value
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value)
  }

  return fallback
}

export function getCatalogBooleanDefault(
  contract: CatalogContract | undefined,
  sectionKey: string,
  fieldKey: string,
  fallback = false,
): boolean {
  const value = getCatalogFieldDefault(contract, sectionKey, fieldKey)
  return typeof value === 'boolean' ? value : fallback
}
