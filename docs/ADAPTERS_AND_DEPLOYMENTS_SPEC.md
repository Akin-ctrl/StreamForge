# Adapters And Deployments Spec

This document locks the intended operator model for protocol configuration and deployment composition.

It exists because the platform now supports multiple adapter types and multi-component gateway configs, while the older pipeline-centric UI language is too narrow for a product-grade operator experience.

## Product Model

The operator model should be:

- `Gateways`: deployment targets
- `Adapters`: first-class configured source connectors
- `Sinks`: first-class configured destination connectors
- `Deployments`: composed gateway configurations that attach adapters and sinks to a gateway, alongside validation, event, and aggregate rules

### Why this model

The runtime already supports one active gateway configuration containing multiple adapters and multiple sinks. The UI should reflect that directly instead of implying a one-adapter-to-one-sink workflow.

## Workflow

1. Create or edit adapter instances on `Adapters`
2. Create or edit sink instances on `Sinks`
3. Create or edit deployments on `Deployments`
4. Apply a deployment to a gateway

The deployment composer should select from already configured adapters and sinks. It should not be the main place where protocol configuration is authored.

## Adapter UX Principles

The UI should abstract protocol difficulty rather than exposing raw protocol plumbing by default.

Every adapter form should present:

1. `Identity`
   - adapter name
   - adapter id
   - adapter type
   - enabled/disabled

2. `Connection`
   - protocol transport settings

3. `Data Mapping`
   - points, subscriptions, or monitored items
   - classification into telemetry and events

4. `Asset Context`
   - default asset id
   - optional per-point or per-subscription override

5. `Advanced`
   - retry/reconnect/security/runtime tuning

6. `Validation`
   - config validation
   - test connection
   - normalized output preview

Strong defaults, help text, and protocol-aware forms are required. Raw internal Kafka topic wiring should stay hidden unless an operator explicitly opens advanced settings.

## Common Adapter Object

Each adapter instance should carry:

- `adapter_id`
- `name`
- `adapter_type`
- `enabled`
- `description`
- `config`
- `created_at`
- `updated_at`

## Core Modeling Rule

An adapter instance represents one source connection or session context and may contain many mapped signals inside it.

That means:

- one Modbus adapter instance may read temperature, pressure, humidity, and state points from the same PLC
- one MQTT adapter instance may subscribe to one or more topics and map many payload fields
- one OPC UA adapter instance may monitor many nodes from the same server session

The product model must not assume one adapter per parameter.

The correct operator mental model is:

- one adapter instance per source connection/session context
- many points, subscriptions, or monitored items inside that adapter

This is the standard industrial case and should be treated as the default design assumption.

## Protocol Specs

### Modbus TCP

Operator-facing fields:

- `host`
- `port`
- `unit_id`
- `default_asset_id`
- `poll_interval_ms`

Point mapping should be a repeatable table with:

- `point_name`
- `memory_area`
  - `holding_register`
  - `input_register`
  - `coil`
  - `discrete_input`
- `address`
- `data_type`
  - `bool`
  - `int16`
  - `uint16`
  - `int32`
  - `uint32`
  - `float32`
  - `float64`
- `byte_order`
- `word_order`
- `scale`
- `offset`
- `unit`
- `classification`
  - `telemetry`
  - `event`
- optional `event_type`

One Modbus adapter instance is expected to carry many mapped PLC points. A PLC with temperature, pressure, humidity, tank level, and motor state should normally be modeled as one adapter instance with multiple point rows, not one adapter per parameter.

Notes:

- Protocol default TCP port is `502`
- Dev-simulator defaults such as `5020` must be treated as environment-specific presets, not protocol defaults
- The UI should support human-friendly Modbus addressing and show the translated wire address clearly

### Modbus RTU

Operator-facing fields:

- `serial_port`
- `baudrate`
- `bytesize`
- `parity`
- `stopbits`
- `timeout`
- `unit_id`
- `default_asset_id`
- `poll_interval_ms`

Point mapping should follow the same model as Modbus TCP.

One RTU adapter instance is likewise expected to carry many mapped points from the same serial device context.

Notes:

- The UI should keep serial-device complexity behind a straightforward form
- Event/state mapping via coils should be first-class, not hidden

### MQTT

Operator-facing fields:

- `broker_host`
- `broker_port`
- `client_id`
- `default_asset_id`

Authentication:

- `username`
- `password`
- future TLS/certificate fields when supported

Subscriptions should be repeatable and include:

- `topic_filter`
- `message_type`
  - `telemetry`
  - `event`
- `payload_format`
  - `json`
- optional `asset_id_override`
- `qos`

Mappings should be repeatable and include:

- `topic_filter`
- `json_field`
- `parameter`
- `unit`
- `data_type`
- optional `quality_field`
- optional `device_time_field`

One MQTT adapter instance may include multiple subscriptions and many field mappings. It should be normal to map several telemetry parameters from one topic payload or several related topics under one adapter session.

Event subscriptions should additionally support:

- fixed or mapped `event_type`
- `previous_state_field`
- `new_state_field`
- optional `device_time_field`

Advanced:

- `keepalive_seconds`
- `clean_start`
- `session_expiry_interval`
- `connect_timeout_seconds`
- reconnect policy

Notes:

- MQTT is subscription-driven, not poll-driven
- `poll_interval_ms` should not be presented as a normal MQTT protocol setting

### OPC UA

Operator-facing fields:

- `endpoint`
- `default_asset_id`

Authentication:

- anonymous
- username/password
- future certificate-based options when supported

Monitored items should be repeatable and include:

- `node_id`
- `browse_name` or display label
- `parameter`
- `unit`
- optional `asset_id_override`
- `sampling_interval_ms`
- `queue_size`
- `monitoring_mode`

One OPC UA adapter instance may monitor many nodes from the same OPC UA session. Operators should configure multiple monitored items inside one adapter rather than creating separate adapters for each parameter.

Subscription-level settings:

- `publishing_interval_ms`
- future keep-alive/lifetime tuning in advanced settings

Security:

- the UI must only expose what the runtime actually supports
- if runtime support is limited to `security_mode=None` and `security_policy=None`, the UI must say so explicitly rather than presenting unsupported options as normal choices

Notes:

- OPC UA is subscription/data-change driven
- `poll_interval_ms` should not be presented as a normal OPC UA field
- Node browsing/discovery should be added when feasible to avoid forcing operators to hand-type raw node ids

## Catalog Contract Requirements

The current flat `fields[]` catalog shape is not enough for the real protocol contracts.

The catalog/descriptor model must support:

- scalar fields
- grouped sections
- repeatable nested sections
- enums and constrained choices
- defaults
- help text
- advanced-only fields
- future discovery-backed selectors

Examples of repeatable nested sections:

- Modbus: `points`
- MQTT: `subscriptions`, `mappings`
- OPC UA: `monitored_items`

## Deployment Spec

Deployments should contain:

- `deployment_id`
- `name`
- `gateway_id`
- `adapter_ids[]`
- `sink_ids[]`
- `validation`
- `events`
- `aggregates`
- `status`

Deployment workflow:

1. choose gateway
2. choose configured adapters
3. choose configured sinks
4. set validation, event, and aggregate behavior
5. review topology and apply

## Non-Goals

This spec does not require:

- exposing raw internal Kafka topic wiring as a normal operator concern
- making every advanced protocol setting mandatory in the primary form
- conflating adapter authoring with deployment composition

## Current Gap Summary

The current implementation is directionally correct at the runtime level, but not yet complete at the operator-model level:

- adapter forms are still too shallow for MQTT and OPC UA
- Modbus event/state mapping is underrepresented in the UI
- the current catalog shape is too flat
- adapters are not yet true first-class persisted objects
- deployments still inherit too much protocol-authoring responsibility
