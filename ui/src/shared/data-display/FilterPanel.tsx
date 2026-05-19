import type { ReactNode } from 'react'

type FilterPanelProps = {
  title: string
  description: string
  onClear?: () => void
  children: ReactNode
}

export function FilterPanel({ title, description, onClear, children }: FilterPanelProps) {
  return (
    <article className="card filter-panel-card">
      <div className="filter-header">
        <div className="card-header-copy">
          <h3>{title}</h3>
          <p className="muted">{description}</p>
        </div>
        {onClear ? (
          <div className="page-actions">
            <button className="btn btn-secondary" onClick={onClear} type="button">
              Clear Filters
            </button>
          </div>
        ) : null}
      </div>
      <div className="alarm-filters filter-panel">{children}</div>
    </article>
  )
}
