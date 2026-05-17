import type { Dispatch, SetStateAction } from 'react'

import { createDefaultPointForm, type AdapterFormState, type ModbusPointForm } from '../adapterForm'

type ModbusPointsEditorProps = {
  form: AdapterFormState
  setForm: Dispatch<SetStateAction<AdapterFormState>>
}

function updatePoint(points: ModbusPointForm[], index: number, nextPoint: ModbusPointForm) {
  return points.map((point, pointIndex) => (pointIndex === index ? nextPoint : point))
}

export function ModbusPointsEditor({ form, setForm }: ModbusPointsEditorProps) {
  return (
    <div className="nested-card card builder-section">
      <div className="page-header">
        <h4>Points</h4>
        <button
          className="btn btn-secondary"
          onClick={() => setForm((current) => ({ ...current, points: [...current.points, createDefaultPointForm()] }))}
          type="button"
        >
          Add Point
        </button>
      </div>
      {form.points.length === 0 ? (
        <p className="muted">Add the parameters or state points this connection should read.</p>
      ) : (
        form.points.map((point, index) => (
          <div className="rule-stack" key={`${point.point_name}-${index}`}>
            <div className="inline-grid">
              <input
                placeholder="Point name"
                value={point.point_name}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    points: updatePoint(current.points, index, { ...point, point_name: event.target.value }),
                  }))
                }
              />
              <select
                value={point.memory_area}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    points: updatePoint(current.points, index, { ...point, memory_area: event.target.value }),
                  }))
                }
              >
                <option value="holding_register">Holding Register</option>
                <option value="input_register">Input Register</option>
                <option value="coil">Coil</option>
                <option value="discrete_input">Discrete Input</option>
              </select>
              <input
                placeholder="Address"
                value={point.address}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    points: updatePoint(current.points, index, { ...point, address: event.target.value }),
                  }))
                }
              />
              <select
                value={point.data_type}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    points: updatePoint(current.points, index, { ...point, data_type: event.target.value }),
                  }))
                }
              >
                <option value="bool">Boolean</option>
                <option value="int16">int16</option>
                <option value="uint16">uint16</option>
                <option value="int32">int32</option>
                <option value="uint32">uint32</option>
                <option value="float32">float32</option>
                <option value="float64">float64</option>
              </select>
            </div>
            <div className="inline-grid">
              <select
                value={point.byte_order}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    points: updatePoint(current.points, index, { ...point, byte_order: event.target.value }),
                  }))
                }
              >
                <option value="big">Byte Order: Big</option>
                <option value="little">Byte Order: Little</option>
              </select>
              <select
                value={point.word_order}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    points: updatePoint(current.points, index, { ...point, word_order: event.target.value }),
                  }))
                }
              >
                <option value="big">Word Order: Big</option>
                <option value="little">Word Order: Little</option>
              </select>
              <input
                placeholder="Scale"
                value={point.scale}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    points: updatePoint(current.points, index, { ...point, scale: event.target.value }),
                  }))
                }
              />
              <input
                placeholder="Offset"
                value={point.offset}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    points: updatePoint(current.points, index, { ...point, offset: event.target.value }),
                  }))
                }
              />
            </div>
            <div className="inline-grid">
              <input
                placeholder="Unit"
                value={point.unit}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    points: updatePoint(current.points, index, { ...point, unit: event.target.value }),
                  }))
                }
              />
              <select
                value={point.classification}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    points: updatePoint(current.points, index, { ...point, classification: event.target.value }),
                  }))
                }
              >
                <option value="telemetry">Telemetry</option>
                <option value="event">Event</option>
              </select>
              <input
                placeholder="Event type (optional)"
                value={point.event_type}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    points: updatePoint(current.points, index, { ...point, event_type: event.target.value }),
                  }))
                }
              />
              <button
                className="btn btn-secondary"
                onClick={() => setForm((current) => ({ ...current, points: current.points.filter((_, itemIndex) => itemIndex !== index) }))}
                type="button"
              >
                Remove
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
