import type { ConnectionProbeResult, ConnectionTestResult, DeploymentPreflightResult, ValidationIssue, ValidationResult } from '../api/client'

export type ActionResultViewModel = {
  tone: 'success' | 'warning' | 'error'
  title: string
  summary: string
  errors: string[]
  warnings: string[]
  fieldIssues: ValidationIssue[]
  probes: ConnectionProbeResult[]
}

function humanizeFieldPath(fieldPath: string | null | undefined): string | null {
  if (!fieldPath) {
    return null
  }

  return fieldPath
    .split('[].')
    .join('[] ')
    .split('.')
    .join(' > ')
}

export function formatValidationIssue(issue: ValidationIssue): string {
  const fieldLabel = humanizeFieldPath(issue.field_path)
  if (!fieldLabel) {
    return issue.message
  }
  return `${fieldLabel}: ${issue.message}`
}

export function validationResultToViewModel(title: string, result: ValidationResult): ActionResultViewModel {
  return {
    tone: result.valid ? 'success' : 'error',
    title,
    summary: result.valid ? 'Validation passed for the current draft.' : 'Validation found issues in the current draft.',
    errors: result.errors,
    warnings: result.warnings,
    fieldIssues: result.field_issues,
    probes: [],
  }
}

export function connectionTestToViewModel(title: string, result: ConnectionTestResult): ActionResultViewModel {
  const tone =
    result.status === 'passed'
      ? 'success'
      : result.status === 'unsupported_here' ||
          result.status === 'cannot_test_from_control_plane' ||
          result.status === 'cannot_test_from_gateway'
        ? 'warning'
        : 'error'

  return {
    tone,
    title,
    summary: result.message,
    errors: result.ok ? [] : result.status === 'failed' ? [result.message] : [],
    warnings: result.warnings,
    fieldIssues: [],
    probes: result.probes,
  }
}

export function preflightToViewModel(result: DeploymentPreflightResult): ActionResultViewModel {
  return {
    tone: result.ready ? 'success' : 'error',
    title: 'Deployment Preflight',
    summary: result.ready
      ? 'Deployment is structurally ready to save and apply.'
      : 'Deployment preflight found issues that should be fixed before apply.',
    errors: result.errors,
    warnings: result.warnings,
    fieldIssues: result.field_issues,
    probes: [],
  }
}
