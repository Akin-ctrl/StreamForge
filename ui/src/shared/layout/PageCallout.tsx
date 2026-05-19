import type { ReactNode } from 'react'

type PageCalloutProps = {
  title: string
  children: ReactNode
}

export function PageCallout({ title, children }: PageCalloutProps) {
  return (
    <article className="card page-callout">
      <strong>{title}</strong>
      {children}
    </article>
  )
}
