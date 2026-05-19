type StatusChipTone = 'good' | 'warn' | 'bad' | 'neutral'

type StatusChipProps = {
  tone: StatusChipTone
  label: string
}

export function StatusChip({ tone, label }: StatusChipProps) {
  return <span className={`fleet-status-chip fleet-status-chip-${tone}`}>{label}</span>
}
