import type { ReactNode } from 'react'

type DetailPanelProps = {
  title: string
  description: string
  children?: ReactNode
}

export function DetailPanel({ title, description, children }: DetailPanelProps) {
  return (
    <aside className="card alarm-detail">
      <div className="card-header-copy">
        <h3>{title}</h3>
        {!children ? <p className="muted">{description}</p> : null}
      </div>
      {children}
    </aside>
  )
}
