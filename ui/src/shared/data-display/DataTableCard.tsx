import type { ReactNode } from 'react'

type DataTableCardProps = {
  title: string
  description: ReactNode
  actions?: ReactNode
  children: ReactNode
}

export function DataTableCard({ title, description, actions, children }: DataTableCardProps) {
  return (
    <article className="card table-card">
      <div className="page-header">
        <div className="card-header-copy">
          <h3>{title}</h3>
          <p className="muted table-caption">{description}</p>
        </div>
        {actions ? <div className="page-actions">{actions}</div> : null}
      </div>
      <div className="table-scroll">{children}</div>
    </article>
  )
}
