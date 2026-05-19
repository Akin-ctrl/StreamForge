/**
 * Shared JSON-shaped types for control-plane contracts and UI form payloads.
 * These keep untyped API/config boundaries explicit without falling back to loose shortcuts.
 */
export type JsonPrimitive = string | number | boolean | null

export type JsonValue = JsonPrimitive | JsonObject | JsonArray

export type JsonObject = {
  [key: string]: JsonValue
}

export type JsonArray = JsonValue[]
