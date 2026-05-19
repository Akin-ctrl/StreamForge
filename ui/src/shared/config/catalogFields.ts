import type { CatalogAdapterType, CatalogField, CatalogSection, CatalogSinkType } from '../api/client'

export type CatalogContract = CatalogAdapterType | CatalogSinkType
export type CatalogOption = { value: string; label: string }

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

export function getCatalogOptions(
  contract: CatalogContract | undefined,
  sectionKey: string,
  fieldKey: string,
): CatalogOption[] {
  return getCatalogField(contract, sectionKey, fieldKey)?.options || []
}

export function getCatalogOptionsForValue(
  contract: CatalogContract | undefined,
  sectionKey: string,
  fieldKey: string,
  currentValue: string,
  currentLabel?: string,
): CatalogOption[] {
  const options = getCatalogOptions(contract, sectionKey, fieldKey)
  if (options.length > 0) {
    return options
  }

  const normalized = currentValue.trim()
  if (!normalized) {
    return []
  }

  return [{ value: normalized, label: currentLabel ?? normalized }]
}
