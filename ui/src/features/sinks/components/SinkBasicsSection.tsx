type SinkBasicsSectionProps = {
  sinkId: string
  name: string
  sinkType: string
  status: string
  description: string
  editing: boolean
  sinkOptions: Array<{ value: string; label: string }>
  onSinkIdChange: (value: string) => void
  onNameChange: (value: string) => void
  onSinkTypeChange: (value: string) => void
  onStatusChange: (value: string) => void
  onDescriptionChange: (value: string) => void
}

export function SinkBasicsSection(props: SinkBasicsSectionProps) {
  const {
    sinkId,
    name,
    sinkType,
    status,
    description,
    editing,
    sinkOptions,
    onSinkIdChange,
    onNameChange,
    onSinkTypeChange,
    onStatusChange,
    onDescriptionChange,
  } = props

  return (
    <article className="card">
      <div className="page-header">
        <h3>Sink Basics</h3>
      </div>
      <div className="inline-grid">
        <label>
          Sink ID
          <input disabled={editing} value={sinkId} onChange={(event) => onSinkIdChange(event.target.value)} />
        </label>
        <label>
          Name
          <input value={name} onChange={(event) => onNameChange(event.target.value)} />
        </label>
      </div>
      <div className="inline-grid">
        <label>
          Type
          <select disabled={editing} value={sinkType} onChange={(event) => onSinkTypeChange(event.target.value)}>
            {sinkOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select value={status} onChange={(event) => onStatusChange(event.target.value)}>
            <option value="active">active</option>
            <option value="paused">paused</option>
            <option value="disabled">disabled</option>
          </select>
        </label>
      </div>
      <label>
        Description
        <input value={description} onChange={(event) => onDescriptionChange(event.target.value)} />
      </label>
    </article>
  )
}
