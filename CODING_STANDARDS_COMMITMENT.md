# Coding Standards Commitment for This Repository

## Why This File Exists

This file records the non-negotiable engineering standards for this repository.

These standards apply to all application code, infrastructure code, runtime code, industrial protocol integrations, tests, examples, reference solutions, and supporting scripts.

This is not a style preference document. It is the baseline quality bar for code that is allowed to remain in the repository.

## Understanding Confirmed

We fully understand the requirement:
- Best practices must be followed in everything we build.
- Code quality is not optional.
- Security quality is not optional.
- Industrial and operational reliability are not optional.
- The code must be easy to read, trace, validate, and maintain.
- If a piece of code is functionally correct but poorly engineered, it is still incomplete.

## Core Engineering Standards

All code in this repository must consistently meet the following requirements.

### 1. Language and Style Discipline
- Follow PEP 8 for Python and the equivalent community-standard formatting and naming rules for every language used in the repository.
- Maintain naming, spacing, line length discipline, import order, and readability.
- Prefer explicit code over clever code.
- Keep files, classes, and functions small enough to be understood without guesswork.

### 2. Logging Discipline
- Use structured, meaningful logs.
- Use the appropriate log level: DEBUG, INFO, WARNING, ERROR.
- Do not use `print(...)` for runtime, service, or operational logging.
- Do not log secrets, credentials, raw tokens, or sensitive payloads.
- Logs must help an operator understand what happened, why it happened, and what the current state is.

### 3. Architecture and Object Design
- Use OOP where appropriate and keep responsibilities clear.
- Maintain single-purpose methods and predictable interfaces.
- Keep transformation, validation, transport, persistence, and presentation concerns separated.
- Do not let one module silently own too many responsibilities.
- Shared contracts must have one authoritative source of truth.

### 4. Documentation and Readability
- Add module-level docstrings to non-trivial modules.
- Add class and function docstrings for public or important internal behavior.
- Use type hints across public APIs.
- Add useful comments that explain intent, assumptions, edge cases, or tricky logic.
- Do not add comments that merely repeat obvious code.
- Optimize for beginner-first readability: simple control flow, descriptive names, and explicit error handling.

### 5. Reliability and Maintainability
- Validate inputs and handle edge cases deliberately.
- Prefer reusable components and shared helpers over copy-paste patterns.
- Avoid hardcoded duplicated business rules across backend, UI, and runtime layers.
- Keep domain contracts strict once a canonical model has been chosen.
- Failures must be diagnosable and recovery paths must be intentional.

## Software Engineering Standards

### 6. Single Source of Truth
- Validation rules, domain contracts, defaults, and allowed states must not be duplicated across multiple layers without a deliberate reason.
- UI, backend, and runtime code must not drift into separately maintained interpretations of the same object model.
- If a shared contract exists, it must be consumed rather than redefined.

### 7. Explicit Interfaces and Strong Typing
- Use strong typing and explicit interfaces across service boundaries and public modules.
- Avoid `any`, weakly typed blobs, and ambiguous data shapes unless there is a clear, temporary, documented reason.
- Transitional compatibility logic must be explicit, limited, and documented.

### 8. Testability and Verification
- Code must be written so it can be validated through tests or structured verification.
- Production-critical paths must have meaningful coverage or an equivalent live verification method.
- Tests must reflect the real architecture and backing systems where practical.
- Convenience test paths must not quietly redefine the architecture.

### 9. Operational Quality
- Health, readiness, startup, shutdown, retry, and recovery behavior must be explicit.
- Service lifecycle code must be observable and deterministic.
- Runtime control logic must behave consistently across equivalent code paths.

## Security Engineering Standards

### 10. Secure by Default
- Default settings must be safe, not merely convenient.
- Development-only shortcuts must be clearly gated and must not silently leak into production paths.
- Authentication, authorization, and session handling must use secure defaults.

### 11. Secrets and Credential Handling
- Secrets must not be stored, echoed, logged, or returned carelessly.
- Plaintext secrets must not be persisted in ordinary domain records unless there is a deliberate, documented exception with compensating controls.
- Credentials shown in the UI must be masked or abstracted wherever possible.
- Secret handling must support future migration to stronger secret-management patterns without redesigning the system.

### 12. Least Privilege and Access Control
- Access control must follow least-privilege principles.
- Roles and permissions must be explicit, meaningful, and enforceable.
- Administrative power must not be the default fallback for ordinary users or services.
- Operational actions that change system behavior must be protected deliberately.

### 13. Secure Data and Session Handling
- Session and token handling must minimize exposure to browser, script, transport, and storage risks.
- Sensitive information must be redacted from logs, API errors, review panels, debug output, and test fixtures where practical.
- Transport and persistence choices must be made with security consequences in mind, not only convenience.

### 14. Auditability and Accountability
- Security-sensitive and operationally significant actions must be attributable to an actor.
- Configuration changes, approvals, destructive actions, and deployment activations must be traceable.
- The system must make it possible to answer who changed what, when, and why.

## Industrial and Operational Technology Standards

### 15. Industrial Reliability
- Industrial protocol handling must prefer deterministic, understandable behavior over hidden complexity.
- One field device, broker session, or server session may expose many signals, and that model must be represented clearly.
- Failure handling must avoid silent data loss where possible and must surface degraded states clearly.

### 16. Safe Operational Behavior
- Startup, restart, and recovery behavior must be safe and predictable.
- Backpressure, throttling, and degraded operation must be explicit rather than implied.
- Runtime orchestration must not depend on fragile incidental behavior.

### 17. Control-Plane and Change Safety
- Changes to active deployments, adapters, sinks, and gateway approvals must be treated as operationally significant actions.
- The system must preserve clarity between draft configuration, active configuration, and historical actions.
- Industrial operators must be protected from hidden side effects and ambiguous state transitions.

## External Baselines

These repository standards are aligned with the expectations of established engineering and security guidance, including:
- NIST Secure Software Development Framework (SSDF)
- OWASP ASVS
- CISA Secure by Design principles
- NIST guidance for operational technology and industrial control systems
- ISA/IEC 62443 industrial cybersecurity expectations

These are not copied verbatim here, but they define the level of seriousness expected from implementation and review.

## Enforcement Principle

If a piece of code does not meet these standards, it must be revised before being considered final.

Functionally correct code is not automatically acceptable code.

Code review, testing, architecture review, and security review should all enforce this document.
