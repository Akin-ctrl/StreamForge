import type { ReactNode } from 'react'

type MetricCardProps = {
  title: string
  value: ReactNode
  detail: ReactNode
}

export function MetricCard({ title, value, detail }: MetricCardProps) {
  return (
    <article className="card metric-card">
      <h3>{title}</h3>
      <p className="overview-kpi-value">{value}</p>
      <p className="muted metric-card-detail">{detail}</p>
    </article>
  )
}
