# ADR-007: Authentication Model

**Status**: Accepted  
**Date**: 2026-01-29  
**Decision**: JWT for gateways (1-year, auto-renew), built-in + OAuth for users

---

## Context

Two types of identities need authentication:
1. **Gateways** - machines connecting to Control Plane
2. **Users** - humans accessing UI and API

Each has different requirements for credential lifecycle and management.

## Options Considered

### Gateway Authentication

#### Option A: API Keys
- Static keys per gateway
- Simple to implement

**Pros**: Simple  
**Cons**: No expiry, revocation requires key rotation, no identity claims

#### Option B: mTLS (Mutual TLS)
- Certificate-based authentication
- Gateway presents client certificate

**Pros**: Strong security, no shared secrets  
**Cons**: Certificate management complexity, rotation overhead

#### Option C: JWT Tokens
- Gateway receives JWT on registration
- Token includes gateway identity and permissions

**Pros**: Standard, contains claims, expirable, revocable  
**Cons**: Token must be stored securely

### User Authentication

#### Option A: Built-in Only
- Username/password stored in Control Plane DB
- Session tokens

**Pros**: No external dependencies  
**Cons**: Another password to manage, no SSO

#### Option B: OAuth/OIDC Only
- Delegate to external identity provider
- No local user management

**Pros**: SSO, enterprise-ready  
**Cons**: Requires external IdP, complex for small deployments

#### Option C: Built-in + Optional OAuth
- Default: built-in username/password
- Optional: integrate with OAuth2/OIDC providers

**Pros**: Works out of box, scales to enterprise  
**Cons**: Two auth paths to maintain

## Decision

- **Gateways**: JWT tokens (1-year validity, auto-renew)
- **Users**: Built-in authentication + optional OAuth2/OIDC

## Rationale

### Gateway JWT

1. **Long validity**: 1-year tokens reduce renewal frequency for remote gateways
2. **Auto-renew**: Gateway renews before expiry when connected
3. **Revocable**: Control Plane can invalidate tokens immediately
4. **Claims**: Token contains gateway ID, permissions, tenant (future)

### User Auth

1. **Built-in for demo**: Works immediately, no setup required
2. **OAuth for enterprise**: Integrate with existing identity providers
3. **Progressive complexity**: Start simple, add SSO when needed

## Gateway Registration Flow

```
1. Gateway boots (first time)
2. Gateway generates unique ID (or uses hardware ID)
3. Gateway calls POST /api/v1/gateways/register
   {
     "gateway_id": "gw-factory-north",
     "hostname": "gateway-01.local",
     "hardware_info": {...}
   }
4. Control Plane creates pending registration
5. Operator approves in UI
6. Gateway calls POST /api/v1/gateways/token
7. Control Plane returns JWT:
   {
     "token": "eyJhbGc...",
     "expires_at": "2027-01-29T00:00:00Z",
     "gateway_id": "gw-factory-north"
   }
8. Gateway stores token securely
9. All subsequent API calls include: Authorization: Bearer <token>
```

## Token Renewal

```
30 days before expiry:
1. Gateway calls POST /api/v1/gateways/token/renew
2. Control Plane issues new token
3. Gateway replaces old token

If renewal fails:
- Gateway continues operating (offline mode)
- Alert in Control Plane UI
- Manual intervention required if token expires
```

## Consequences

### Positive
- Gateways work reliably with long-lived tokens
- Auto-renewal prevents expiry issues
- Built-in auth enables quick demos
- OAuth enables enterprise integration

### Negative
- Token storage on gateway must be secure
- Two auth systems to maintain

### Mitigations
- Store tokens with restricted file permissions
- Document secure token storage
- Clear separation between auth paths in code

## Related Decisions
- [ADR-006: Gateway Autonomy](ADR-006-gateway-autonomy.md)
