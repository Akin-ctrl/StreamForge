import type { Dispatch, SetStateAction } from 'react'

import {
  createDefaultMqttMappingForm,
  createDefaultMqttSubscriptionForm,
  type AdapterFormState,
  type MqttMappingForm,
  type MqttSubscriptionForm,
} from '../adapterForm'

type MqttConfigSectionProps = {
  form: AdapterFormState
  setForm: Dispatch<SetStateAction<AdapterFormState>>
}

function updateSubscription(
  subscriptions: MqttSubscriptionForm[],
  index: number,
  nextSubscription: MqttSubscriptionForm,
) {
  return subscriptions.map((subscription, subscriptionIndex) => (subscriptionIndex === index ? nextSubscription : subscription))
}

function updateMapping(mappings: MqttMappingForm[], index: number, nextMapping: MqttMappingForm) {
  return mappings.map((mapping, mappingIndex) => (mappingIndex === index ? nextMapping : mapping))
}

export function MqttConfigSection({ form, setForm }: MqttConfigSectionProps) {
  return (
    <article className="card">
      <div className="page-header">
        <h3>MQTT</h3>
      </div>
      <div className="inline-grid">
        <label>
          Broker Host
          <input value={form.brokerHost} onChange={(event) => setForm((current) => ({ ...current, brokerHost: event.target.value }))} />
        </label>
        <label>
          Broker Port
          <input value={form.brokerPort} onChange={(event) => setForm((current) => ({ ...current, brokerPort: event.target.value }))} />
        </label>
        <label>
          Client ID
          <input value={form.clientId} onChange={(event) => setForm((current) => ({ ...current, clientId: event.target.value }))} />
        </label>
        <label>
          Default Asset ID
          <input value={form.defaultAssetId} onChange={(event) => setForm((current) => ({ ...current, defaultAssetId: event.target.value }))} />
        </label>
      </div>
      <div className="inline-grid">
        <label>
          Username
          <input value={form.username} onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))} />
        </label>
        <label>
          Password
          <input
            type="password"
            value={form.password}
            onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
          />
        </label>
        <label>
          QoS
          <input value={form.qos} onChange={(event) => setForm((current) => ({ ...current, qos: event.target.value }))} />
        </label>
      </div>

      <div className="nested-card card builder-section">
        <div className="page-header">
          <h4>Subscriptions</h4>
          <button
            className="btn btn-secondary"
            onClick={() => setForm((current) => ({ ...current, subscriptions: [...current.subscriptions, createDefaultMqttSubscriptionForm()] }))}
            type="button"
          >
            Add Subscription
          </button>
        </div>
        {form.subscriptions.length === 0 ? (
          <p className="muted">Add the MQTT topic subscriptions this adapter should consume.</p>
        ) : (
          form.subscriptions.map((subscription, subscriptionIndex) => (
            <div className="rule-stack" key={`${subscription.topic_filter}-${subscriptionIndex}`}>
              <div className="inline-grid">
                <input
                  placeholder="Topic filter"
                  value={subscription.topic_filter}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      subscriptions: updateSubscription(current.subscriptions, subscriptionIndex, {
                        ...subscription,
                        topic_filter: event.target.value,
                      }),
                    }))
                  }
                />
                <select
                  value={subscription.message_type}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      subscriptions: updateSubscription(current.subscriptions, subscriptionIndex, {
                        ...subscription,
                        message_type: event.target.value,
                      }),
                    }))
                  }
                >
                  <option value="telemetry">Telemetry</option>
                  <option value="event">Event</option>
                </select>
                <select
                  value={subscription.payload_format}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      subscriptions: updateSubscription(current.subscriptions, subscriptionIndex, {
                        ...subscription,
                        payload_format: event.target.value,
                      }),
                    }))
                  }
                >
                  <option value="json">JSON</option>
                </select>
                <input
                  placeholder="Asset override"
                  value={subscription.asset_id_override}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      subscriptions: updateSubscription(current.subscriptions, subscriptionIndex, {
                        ...subscription,
                        asset_id_override: event.target.value,
                      }),
                    }))
                  }
                />
                <input
                  placeholder="QoS"
                  value={subscription.qos}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      subscriptions: updateSubscription(current.subscriptions, subscriptionIndex, {
                        ...subscription,
                        qos: event.target.value,
                      }),
                    }))
                  }
                />
                <button
                  className="btn btn-secondary"
                  onClick={() => setForm((current) => ({ ...current, subscriptions: current.subscriptions.filter((_, index) => index !== subscriptionIndex) }))}
                  type="button"
                >
                  Remove
                </button>
              </div>

              <div className="nested-card card builder-section">
                <div className="page-header">
                  <h5>Mappings</h5>
                  <button
                    className="btn btn-secondary"
                    onClick={() =>
                      setForm((current) => ({
                        ...current,
                        subscriptions: updateSubscription(current.subscriptions, subscriptionIndex, {
                          ...subscription,
                          mappings: [...subscription.mappings, createDefaultMqttMappingForm()],
                        }),
                      }))
                    }
                    type="button"
                  >
                    Add Mapping
                  </button>
                </div>
                {subscription.mappings.length === 0 ? (
                  <p className="muted">Add mappings from JSON fields to normalized parameters.</p>
                ) : (
                  subscription.mappings.map((mapping, mappingIndex) => (
                    <div className="inline-grid" key={`${mapping.json_field}-${mappingIndex}`}>
                      <input
                        placeholder="JSON field"
                        value={mapping.json_field}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            subscriptions: updateSubscription(current.subscriptions, subscriptionIndex, {
                              ...subscription,
                              mappings: updateMapping(subscription.mappings, mappingIndex, {
                                ...mapping,
                                json_field: event.target.value,
                              }),
                            }),
                          }))
                        }
                      />
                      <input
                        placeholder="Parameter"
                        value={mapping.parameter}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            subscriptions: updateSubscription(current.subscriptions, subscriptionIndex, {
                              ...subscription,
                              mappings: updateMapping(subscription.mappings, mappingIndex, {
                                ...mapping,
                                parameter: event.target.value,
                              }),
                            }),
                          }))
                        }
                      />
                      <input
                        placeholder="Unit"
                        value={mapping.unit}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            subscriptions: updateSubscription(current.subscriptions, subscriptionIndex, {
                              ...subscription,
                              mappings: updateMapping(subscription.mappings, mappingIndex, {
                                ...mapping,
                                unit: event.target.value,
                              }),
                            }),
                          }))
                        }
                      />
                      <select
                        value={mapping.data_type}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            subscriptions: updateSubscription(current.subscriptions, subscriptionIndex, {
                              ...subscription,
                              mappings: updateMapping(subscription.mappings, mappingIndex, {
                                ...mapping,
                                data_type: event.target.value,
                              }),
                            }),
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
                      <button
                        className="btn btn-secondary"
                        onClick={() =>
                          setForm((current) => ({
                            ...current,
                            subscriptions: updateSubscription(current.subscriptions, subscriptionIndex, {
                              ...subscription,
                              mappings: subscription.mappings.filter((_, index) => index !== mappingIndex),
                            }),
                          }))
                        }
                        type="button"
                      >
                        Remove
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <details className="card nested-card advanced-block">
        <summary>Advanced</summary>
        <div className="inline-grid">
          <label>
            Keepalive (s)
            <input
              value={form.keepaliveSeconds}
              onChange={(event) => setForm((current) => ({ ...current, keepaliveSeconds: event.target.value }))}
            />
          </label>
          <label>
            Connect Timeout (s)
            <input
              value={form.connectTimeoutSeconds}
              onChange={(event) => setForm((current) => ({ ...current, connectTimeoutSeconds: event.target.value }))}
            />
          </label>
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={form.cleanStart}
              onChange={(event) => setForm((current) => ({ ...current, cleanStart: event.target.checked }))}
            />
            Clean Start
          </label>
          <label>
            Telemetry Topic
            <input value={form.outputTopic} onChange={(event) => setForm((current) => ({ ...current, outputTopic: event.target.value }))} />
          </label>
          <label>
            Events Topic
            <input value={form.eventsTopic} onChange={(event) => setForm((current) => ({ ...current, eventsTopic: event.target.value }))} />
          </label>
        </div>
      </details>
    </article>
  )
}
