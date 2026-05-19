type AdapterBasicsSectionProps = {
  adapterId: string
  name: string
  adapterType: string
  status: string
  description: string
  editing: boolean
  adapterOptions: Array<{ value: string; label: string }>
  onAdapterIdChange: (value: string) => void
  onNameChange: (value: string) => void
  onAdapterTypeChange: (value: string) => void
  onStatusChange: (value: string) => void
  onDescriptionChange: (value: string) => void
}

export function AdapterBasicsSection(props: AdapterBasicsSectionProps) {
  const {
    adapterId,
    name,
    adapterType,
    status,
    description,
    editing,
    adapterOptions,
    onAdapterIdChange,
    onNameChange,
    onAdapterTypeChange,
    onStatusChange,
    onDescriptionChange,
  } = props

  return (
    <article className="card">
      <div className="page-header">
        <div className="card-header-copy">
          <h3>Adapter Basics</h3>
          <p className="muted">Give the adapter a stable identity, choose the protocol, and describe what source connection this object represents.</p>
        </div>
      </div>
      <div className="inline-grid">
        <label>
          Adapter ID
          <input disabled={editing} value={adapterId} onChange={(event) => onAdapterIdChange(event.target.value)} />
        </label>
        <label>
          Name
          <input value={name} onChange={(event) => onNameChange(event.target.value)} />
        </label>
      </div>
      <div className="inline-grid">
        <label>
          Type
          <select disabled={editing} value={adapterType} onChange={(event) => onAdapterTypeChange(event.target.value)}>
            {adapterOptions.map((option) => (
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
        <textarea rows={3} value={description} onChange={(event) => onDescriptionChange(event.target.value)} />
      </label>
    </article>
  )
}
