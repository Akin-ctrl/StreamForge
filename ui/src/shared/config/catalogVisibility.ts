import type { CatalogField } from '../api/client'
import type { CatalogContract } from './catalogFields'
import { getCatalogField, getCatalogSection } from './catalogFields'

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
