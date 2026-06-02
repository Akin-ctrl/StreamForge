# Deployment Templates

This directory is reserved for future StreamForge package and image-pull
templates.

The current supported local development stack lives in
`deploy/dev/docker-compose.yml`.

Do not treat this directory as production-ready yet. Redpanda is the chosen
Kafka-compatible edge broker direction, but production packaging, image-pull
templates, remote-site installation, storage layout, TLS, and backup/recovery
guidance are still pending.

The local development stack in `deploy/dev/` is intentionally more conservative
than an ad hoc demo: Redpanda is version-pinned, supporting helper images avoid
floating `latest` references, and the broker data volume is visible to the
gateway runtime for local overflow checks. Those choices are development
baseline hardening, not a production installation template.
