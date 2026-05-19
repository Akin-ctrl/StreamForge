import type { CatalogAdapterType, CatalogField, CatalogSinkType, CatalogSection } from '../api/client'

export type CatalogContract = CatalogAdapterType | CatalogSinkType

function findField(fields: CatalogField[], fieldKey: string): CatalogField | undefined {
  for (const field of fields) {
    if (field.key === fieldKey) {
      return field
    }
    if (field.children?.length) {
      const child = findField(field.children, fieldKey)
      if (child) {
        return child
      }
    }
  }
  return undefined
}

function collectFlaggedFieldKeys(fields: CatalogField[], predicate: (field: CatalogField) => boolean): string[] {
  const keys: string[] = []
  for (const field of fields) {
    if (predicate(field)) {
      keys.push(field.key)
    }
    if (field.children?.length) {
      keys.push(...collectFlaggedFieldKeys(field.children, predicate))
    }
  }
  return keys
}

export function getCatalogSection(contract: CatalogContract | undefined, sectionKey: string): CatalogSection | undefined {
  return contract?.sections?.find((section) => section.key === sectionKey)
}

export function getCatalogField(
  contract: CatalogContract | undefined,
  sectionKey: string,
  fieldKey: string,
): CatalogField | undefined {
  const section = getCatalogSection(contract, sectionKey)
  return section ? findField(section.fields, fieldKey) : undefined
}

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

export function getCatalogOptions(
  contract: CatalogContract | undefined,
  sectionKey: string,
  fieldKey: string,
): Array<{ value: string; label: string }> {
  return getCatalogField(contract, sectionKey, fieldKey)?.options || []
}

export function isCatalogFieldInternal(
  contract: CatalogContract | undefined,
  sectionKey: string,
  fieldKey: string,
): boolean {
  return Boolean(getCatalogField(contract, sectionKey, fieldKey)?.internal)
}

export function getInternalFieldKeys(contract: CatalogContract | undefined, sectionKey: string): string[] {
  const section = getCatalogSection(contract, sectionKey)
  return section ? collectFlaggedFieldKeys(section.fields, (field) => Boolean(field.internal)) : []
}
