import { formatValidationIssue, type ActionResultViewModel } from './validationIssues'

type ActionResultPanelProps = {
  result: ActionResultViewModel
}

export function ActionResultPanel({ result }: ActionResultPanelProps) {
  return (
    <article className={`card action-result action-result-${result.tone}`}>
      <div className="page-header">
        <h3>{result.title}</h3>
        <span className="muted">{result.tone === 'success' ? 'Passed' : result.tone === 'warning' ? 'Attention' : 'Failed'}</span>
      </div>
      <p>{result.summary}</p>

      {result.errors.length > 0 && (
        <div className="builder-section">
          <strong>Errors</strong>
          <ul className="plain-list">
            {result.errors.map((error) => (
              <li key={error} className="error">
                {error}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="builder-section">
          <strong>Warnings</strong>
          <ul className="plain-list">
            {result.warnings.map((warning) => (
              <li key={warning} className="muted">
                {warning}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.fieldIssues.length > 0 && (
        <div className="builder-section">
          <strong>Field Issues</strong>
          <ul className="plain-list">
            {result.fieldIssues.map((issue, index) => (
              <li key={`${issue.field_path || 'general'}-${index}`} className={issue.severity === 'error' ? 'error' : 'muted'}>
                {formatValidationIssue(issue)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.probes.length > 0 && (
        <div className="builder-section">
          <strong>Checks</strong>
          <ul className="plain-list">
            {result.probes.map((probe) => (
              <li key={`${probe.name}-${probe.message}`}>
                <strong>{probe.name}</strong>
                <span className="muted">{probe.status}: {probe.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  )
}
