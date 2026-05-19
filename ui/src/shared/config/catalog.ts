/**
 * Catalog helpers stay grouped behind this barrel so feature code can keep one stable import path
 * while the lookup/default/visibility logic stays separated by responsibility.
 */
export * from './catalogFields'
export * from './catalogDefaults'
export * from './catalogVisibility'
