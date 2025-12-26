# Security Model & Best Practices

**Comprehensive security architecture for industrial data gateway deployments.**

---

## Table of Contents

1. [Security Principles](#security-principles)
2. [Authentication](#authentication)
3. [Authorization (RBAC)](#authorization-rbac)
4. [Network Security](#network-security)
5. [Data Encryption](#data-encryption)
6. [Secrets Management](#secrets-management)
7. [Audit & Compliance](#audit--compliance)
8. [Threat Model](#threat-model)
9. [Security Checklist](#security-checklist)
10. [Incident Response](#incident-response)

---

## Security Principles

### Defense in Depth

Multiple layers of security controls:
```
Physical Security → Network Security → Application Security → Data Security
```

### Least Privilege

Every component has minimum required permissions:
- Adapters can only write to assigned Kafka topics
- Sinks can only read from specific topics
- Gateway Runtime cannot access Control Plane database directly
- UI users have role-based access

### Zero Trust

Never trust, always verify:
- All network traffic encrypted (even internal)
- All API calls authenticated
- All configuration changes audited
- No implicit trust between components

---

## Authentication

### User Authentication (Control Plane UI/API)

**Method**: JWT (JSON Web Tokens) with OAuth2/OIDC

**Flow**:
```
1. User logs in via UI
   ↓
2. Control API validates credentials (or delegates to IdP)
   ↓
3. API issues JWT token (expires in 24 hours)
   ↓
4. UI includes token in Authorization header
   ↓
5. API validates token on every request
```

**JWT Structure**:
```json
{
  "sub": "alice@example.com",
  "roles": ["Engineer"],
  "permissions": ["pipelines:read", "pipelines:create"],
  "gateway_access": ["gateway-factory-01", "gateway-factory-02"],
  "exp": 1704988800,
  "iat": 1704902400,
  "iss": "streamforge-api"
}
```

**Token refresh**:
```bash
# UI automatically refreshes token before expiration
POST /api/v1/auth/refresh
Authorization: Bearer <current-token>

Response:
{
  "token": "<new-token>",
  "expires_at": "2025-01-12T00:00:00Z"
}
```

### Gateway Authentication (Machine-to-Machine)

**Method**: mTLS (mutual TLS) + long-lived JWT

**Initial registration**:
```bash
# Gateway generates certificate on first boot
openssl req -new -x509 -days 3650 \
  -keyout /etc/streamforge/gateway.key \
  -out /etc/streamforge/gateway.crt \
  -subj "/CN=gateway-rig-alpha-001"

# Register with Control API (one-time, admin approval)
curl -X POST https://api.streamforge.example.com/api/v1/gateways/register \
  -H "Content-Type: application/json" \
  -d '{
    "gateway_id": "gateway-rig-alpha-001",
    "certificate": "<PEM-encoded-cert>",
    "metadata": {
      "location": "Offshore Rig Alpha",
      "hardware": "Dell Edge Gateway 3200"
    }
  }'

# Admin approves in UI
# Control API issues long-lived JWT (1 year expiration)
{
  "gateway_id": "gateway-rig-alpha-001",
  "token": "eyJhbGciOi...",
  "expires_at": "2026-01-10T00:00:00Z"
}
```

**Ongoing authentication**:
```bash
# Gateway includes token in every API call
GET /api/v1/gateways/gateway-rig-alpha-001/config/current
Authorization: Bearer <gateway-token>
```

**Token rotation**:
```bash
# Automatic renewal 30 days before expiration
POST /api/v1/gateways/{gateway_id}/renew-token
Authorization: Bearer <current-token>
```

### Adapter Authentication to Kafka

**Method**: SASL/SCRAM-SHA-512

**Configuration**:
```yaml
# Kafka server-side
listeners=SASL_SSL://0.0.0.0:9093
security.inter.broker.protocol=SASL_SSL
sasl.mechanism.inter.broker.protocol=SCRAM-SHA-512
sasl.enabled.mechanisms=SCRAM-SHA-512
```

**Adapter credentials**:
```json
{
  "output": {
    "kafka_bootstrap": "kafka.example.com:9093",
    "security_protocol": "SASL_SSL",
    "sasl_mechanism": "SCRAM-SHA-512",
    "sasl_username": "${secret:kafka_adapter_user}",
    "sasl_password": "${secret:kafka_adapter_password}"
  }
}
```

**Credential creation**:
```bash
# Create Kafka user with specific permissions
kafka-configs --bootstrap-server kafka:9093 \
  --alter --add-config 'SCRAM-SHA-512=[password=<secure-password>]' \
  --entity-type users --entity-name adapter-user
```

---

## Authorization (RBAC)

### Roles & Permissions

| Role | Permissions | Use Case |
|------|-------------|----------|
| **Viewer** | Read dashboards, view configs | Business analysts, executives |
| **Operator** | Viewer + acknowledge alarms, view logs | Operations team, 24/7 monitoring |
| **Engineer** | Operator + create/edit pipelines, test connections | Industrial engineers, integrators |
| **Admin** | Engineer + manage gateways, users, deploy configs | System administrators |
| **Copilot** | Read topology, suggest changes (requires approval) | AI assistant |

### Permission Matrix

| Resource | Viewer | Operator | Engineer | Admin |
|----------|--------|----------|----------|-------|
| View dashboards | ✓ | ✓ | ✓ | ✓ |
| View configs | ✓ | ✓ | ✓ | ✓ |
| Acknowledge alarms | ✗ | ✓ | ✓ | ✓ |
| View logs | ✗ | ✓ | ✓ | ✓ |
| Create pipelines | ✗ | ✗ | ✓ | ✓ |
| Edit pipelines | ✗ | ✗ | ✓ | ✓ |
| Delete pipelines | ✗ | ✗ | ✗ | ✓ |
| Deploy configs | ✗ | ✗ | ✗ | ✓ |
| Manage gateways | ✗ | ✗ | ✗ | ✓ |
| Manage users | ✗ | ✗ | ✗ | ✓ |

### Kafka Topic ACLs

**Per-adapter isolation**:
```bash
# Adapter can only write to its assigned topics
kafka-acls --bootstrap-server kafka:9093 \
  --add --allow-principal User:adapter-modbus-001 \
  --operation Write \
  --topic telemetry.raw \
  --topic events.raw

# Adapter cannot read (write-only)
kafka-acls --bootstrap-server kafka:9093 \
  --add --deny-principal User:adapter-modbus-001 \
  --operation Read \
  --topic '*'
```

**Sink permissions**:
```bash
# Sink can only read from clean topics
kafka-acls --bootstrap-server kafka:9093 \
  --add --allow-principal User:sink-timescaledb \
  --operation Read \
  --topic telemetry.clean \
  --topic events.clean \
  --group sink-timescaledb-group
```

### Implementation (Control API)

```python
# control_plane/api/auth.py
from functools import wraps
from jose import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer

security = HTTPBearer()

def get_current_user(token: str = Depends(security)):
    try:
        payload = jwt.decode(token.credentials, JWT_SECRET, algorithms=["HS256"])
        return User(
            email=payload["sub"],
            roles=payload["roles"],
            permissions=payload["permissions"]
        )
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_permission(permission: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: User = Depends(get_current_user), **kwargs):
            if permission not in user.permissions:
                raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator

# Usage in API endpoints
@app.post("/api/v1/pipelines")
@require_permission("pipelines:create")
async def create_pipeline(pipeline: PipelineCreate, user: User = Depends(get_current_user)):
    # Create pipeline logic
    audit_log(user.email, "pipeline.create", pipeline.id)
    return {"status": "created"}
```

---

## Network Security

### Network Segmentation

```
┌─────────────────────────────────────────────┐
│ DMZ (Public)                                │
│ - Load Balancer                             │
│ - UI (HTTPS only)                           │
└─────────────┬───────────────────────────────┘
              │ (Firewall)
┌─────────────▼───────────────────────────────┐
│ Control Plane Network                       │
│ - Control API (private IP)                  │
│ - PostgreSQL (no external access)           │
└─────────────┬───────────────────────────────┘
              │ (Firewall)
┌─────────────▼───────────────────────────────┐
│ Data Plane Network                          │
│ - Kafka cluster (VPN/private peering only)  │
│ - Schema Registry                           │
└─────────────┬───────────────────────────────┘
              │ (VPN)
┌─────────────▼───────────────────────────────┐
│ Edge Networks                               │
│ - Gateways (outbound only)                  │
│ - Protocol adapters (isolated)              │
└─────────────────────────────────────────────┘
```

### Firewall Rules

**DMZ → Control Plane**:
```
Allow: TCP 443 (HTTPS) → Control API
Block: All other inbound
```

**Control Plane → Data Plane**:
```
Allow: TCP 9093 (Kafka over TLS)
Allow: TCP 8081 (Schema Registry)
Allow: TCP 5432 (PostgreSQL, internal only)
```

**Edge → Cloud** (outbound only):
```
Allow: TCP 443 → control.streamforge.cloud (Control API)
Allow: TCP 9093 → kafka.streamforge.cloud (Kafka replication)
Allow: UDP 123 → pool.ntp.org (NTP)
Block: All inbound (no SSH, no admin ports)
```

**Edge local management** (restricted):
```
Allow: TCP 22 (SSH) from 192.168.1.0/24 (management VLAN only)
Allow: TCP 9090 (Prometheus metrics) from monitoring server
```

### VPN Configuration (for Edge → Cloud)

**IPSec tunnel**:
```bash
# Edge gateway
ipsec up streamforge-tunnel

# Traffic routed through tunnel:
# - Kafka replication (9093)
# - Control API (443)

# Public internet bypass:
# - NTP (no sensitive data)
```

**WireGuard alternative**:
```ini
# /etc/wireguard/wg0.conf
[Interface]
PrivateKey = <gateway-private-key>
Address = 10.0.1.2/24

[Peer]
PublicKey = <cloud-public-key>
Endpoint = vpn.streamforge.cloud:51820
AllowedIPs = 10.0.0.0/16
PersistentKeepalive = 25
```

---

## Data Encryption

### In Transit

**All network traffic encrypted**:

| Connection | Method | Key Strength |
|------------|--------|--------------|
| UI ↔ Control API | HTTPS/TLS 1.3 | RSA 2048 / ECDSA P-256 |
| Gateway ↔ Control API | HTTPS/TLS 1.3 | RSA 2048 |
| Edge Kafka ↔ Central Kafka | Kafka over TLS (SASL_SSL) | AES-256 |
| Adapter ↔ Local Kafka | TLS | AES-256 |

**TLS configuration** (Control API):
```nginx
# nginx.conf
ssl_protocols TLSv1.3;
ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
ssl_stapling on;
ssl_stapling_verify on;
```

**Kafka TLS** (broker config):
```properties
listeners=SSL://0.0.0.0:9093
ssl.keystore.location=/var/private/ssl/kafka.server.keystore.jks
ssl.keystore.password=${KEYSTORE_PASSWORD}
ssl.key.password=${KEY_PASSWORD}
ssl.truststore.location=/var/private/ssl/kafka.server.truststore.jks
ssl.truststore.password=${TRUSTSTORE_PASSWORD}
ssl.client.auth=required
ssl.enabled.protocols=TLSv1.3
ssl.cipher.suites=TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
```

### At Rest

**Kafka logs** (disk encryption):
```bash
# Linux LUKS encryption
cryptsetup luksFormat /dev/sdb
cryptsetup luksOpen /dev/sdb kafka_data
mkfs.ext4 /dev/mapper/kafka_data
mount /dev/mapper/kafka_data /var/lib/kafka/data
```

**Database** (PostgreSQL):
```bash
# Transparent Data Encryption (TDE)
# Or cloud-managed encryption (AWS RDS encryption, Azure SQL TDE)
```

**Edge gateway** (local buffering):
```bash
# Full disk encryption (on sensitive deployments)
cryptsetup luksFormat /dev/mmcblk0p2
# Auto-unlock on boot with TPM
```

---

## Secrets Management

### HashiCorp Vault Integration

**Architecture**:
```
Gateway Runtime → Vault Agent → HashiCorp Vault
  ↓ (inject secrets)
Adapter containers
```

**Vault setup**:
```bash
# Enable KV v2 secrets engine
vault secrets enable -path=secret kv-v2

# Store OPC UA credentials
vault kv put secret/streamforge/opcua/plc-01 \
  username=operator \
  password=<secure-password>

# Store Kafka credentials
vault kv put secret/streamforge/kafka/adapter-credentials \
  username=adapter-user \
  password=<secure-password>
```

**Policy** (least privilege):
```hcl
# adapters-policy.hcl
path "secret/data/streamforge/opcua/*" {
  capabilities = ["read"]
}

path "secret/data/streamforge/kafka/adapter-credentials" {
  capabilities = ["read"]
}

# No write, no delete, no list
```

**Adapter config** (references secrets):
```json
{
  "source": {
    "opcua_endpoint": "opc.tcp://plc.example.com:4840",
    "username": "${vault:secret/streamforge/opcua/plc-01#username}",
    "password": "${vault:secret/streamforge/opcua/plc-01#password}"
  },
  "output": {
    "kafka_username": "${vault:secret/streamforge/kafka/adapter-credentials#username}",
    "kafka_password": "${vault:secret/streamforge/kafka/adapter-credentials#password}"
  }
}
```

**Gateway Runtime** (resolves secrets):
```python
# gateway_runtime/secrets.py
import hvac

vault_client = hvac.Client(url='https://vault.example.com')
vault_client.auth.approle.login(role_id=ROLE_ID, secret_id=SECRET_ID)

def resolve_secrets(config):
    """Replace ${vault:path#key} with actual secret values"""
    for key, value in config.items():
        if isinstance(value, str) and value.startswith("${vault:"):
            path, field = value[8:-1].split('#')
            secret = vault_client.secrets.kv.v2.read_secret_version(path=path)
            config[key] = secret['data']['data'][field]
    return config
```

### Alternative: Kubernetes Secrets

```yaml
# For Kubernetes deployments
apiVersion: v1
kind: Secret
metadata:
  name: kafka-credentials
  namespace: streamforge
type: Opaque
data:
  username: YWRhcHRlci11c2Vy  # base64-encoded
  password: PHNlY3VyZS1wYXNzd29yZD4=

---
apiVersion: v1
kind: Pod
metadata:
  name: adapter-modbus-001
spec:
  containers:
  - name: adapter
    image: streamforge/adapter-modbus:1.0.0
    env:
    - name: KAFKA_USERNAME
      valueFrom:
        secretKeyRef:
          name: kafka-credentials
          key: username
    - name: KAFKA_PASSWORD
      valueFrom:
        secretKeyRef:
          name: kafka-credentials
          key: password
```

---

## Audit & Compliance

### Audit Log

**Every security-relevant event logged**:

```json
{
  "timestamp": "2025-01-10T14:30:00.123Z",
  "event_type": "authentication.success",
  "user": "alice@example.com",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "resource": "/api/v1/auth/login",
  "result": "success"
}
```

**Configuration changes**:
```json
{
  "timestamp": "2025-01-10T15:00:00Z",
  "event_type": "pipeline.update",
  "user": "bob@example.com",
  "resource_id": "offshore_well_12",
  "action": "update",
  "changes": {
    "poll_interval_ms": {"old": 1000, "new": 500}
  },
  "approved_by": null,
  "ip_address": "10.0.1.50"
}
```

**Failed authentication**:
```json
{
  "timestamp": "2025-01-10T16:00:00Z",
  "event_type": "authentication.failure",
  "user": "unknown@example.com",
  "ip_address": "203.0.113.45",
  "reason": "invalid_credentials",
  "result": "blocked"
}
```

### Storage

**Dual storage**:
1. **PostgreSQL** (queryable, indexed)
   ```sql
   CREATE TABLE audit_log (
     id SERIAL PRIMARY KEY,
     timestamp TIMESTAMPTZ NOT NULL,
     event_type VARCHAR(100) NOT NULL,
     user_email VARCHAR(255),
     resource_id VARCHAR(255),
     action VARCHAR(50),
     changes JSONB,
     ip_address INET,
     INDEX idx_timestamp (timestamp),
     INDEX idx_user (user_email),
     INDEX idx_event_type (event_type)
   );
   ```

2. **Kafka topic** `audit_trail` (immutable, long retention)
   ```properties
   retention.ms=-1  # Infinite retention
   cleanup.policy=compact  # Or just append-only
   min.insync.replicas=3  # High durability
   ```

### Compliance Reports

**GDPR**: User data access logs
```sql
SELECT timestamp, event_type, resource_id, action
FROM audit_log
WHERE user_email = 'user@example.com'
  AND timestamp > NOW() - INTERVAL '90 days'
ORDER BY timestamp DESC;
```

**SOC 2**: Config change audit trail
```sql
SELECT timestamp, user_email, event_type, changes
FROM audit_log
WHERE event_type LIKE 'pipeline.%' OR event_type LIKE 'gateway.%'
  AND timestamp BETWEEN '2025-01-01' AND '2025-12-31'
ORDER BY timestamp;
```

**ISO 27001**: Access control review
```sql
SELECT user_email, COUNT(*) as failed_logins
FROM audit_log
WHERE event_type = 'authentication.failure'
  AND timestamp > NOW() - INTERVAL '30 days'
GROUP BY user_email
HAVING COUNT(*) > 5;
```

---

## Threat Model

### Threats & Mitigations

| Threat | Impact | Mitigation |
|--------|--------|------------|
| **Unauthorized access to Control API** | Configuration tampering, data exposure | JWT auth, RBAC, rate limiting, IP whitelist |
| **MITM attack on edge → cloud** | Data interception, credential theft | TLS 1.3, certificate pinning |
| **Compromised adapter container** | Malicious data injection | Sandboxing, read-only filesystem, limited Kafka ACLs |
| **Kafka credential theft** | Unauthorized data access | SASL/SCRAM, credential rotation, Vault integration |
| **DDoS on Control API** | Service unavailability | Rate limiting, CDN, auto-scaling |
| **Insider threat (malicious admin)** | Data deletion, config destruction | Audit logs, approval workflows, immutable backups |
| **Physical access to edge gateway** | Device tampering | Disk encryption, tamper-evident seals, secure boot |

### Attack Scenarios

**Scenario 1: Compromised Edge Gateway**

**Attack**:
```
Attacker gains physical access to edge gateway
Boots into recovery mode
Attempts to read Kafka data or credentials
```

**Mitigations**:
- Full disk encryption (LUKS)
- Secure boot (TPM-based)
- Credentials stored in Vault (not on disk)
- Tamper-evident physical seals
- Remote wipe capability

**Scenario 2: Stolen JWT Token**

**Attack**:
```
Attacker intercepts JWT token (XSS, browser vulnerability)
Uses token to access Control API
```

**Mitigations**:
- Short token expiration (24 hours)
- HttpOnly cookies (for web UI)
- IP address binding (optional)
- Token revocation on logout
- Audit logging of all token usage

---

## Security Checklist

### Pre-Deployment

- [ ] TLS certificates generated and installed
- [ ] Secrets stored in Vault (not hardcoded)
- [ ] Firewall rules configured
- [ ] VPN tunnel established (for edge deployments)
- [ ] Kafka ACLs configured
- [ ] Database credentials rotated from defaults
- [ ] Admin accounts use strong passwords (or SSO)
- [ ] Audit logging enabled

### Post-Deployment

- [ ] Security scan completed (vulnerability assessment)
- [ ] Penetration testing performed
- [ ] Audit logs reviewed (no unauthorized access)
- [ ] Backups encrypted and tested
- [ ] Incident response plan documented
- [ ] Security training for operators completed

### Ongoing

- [ ] Monthly credential rotation
- [ ] Quarterly access review (remove unused accounts)
- [ ] Security patches applied within 7 days
- [ ] Audit logs reviewed weekly
- [ ] Backup restoration tested quarterly

---

## Incident Response

### Incident Response Plan

**Severity Levels**:

| Level | Definition | Example | Response Time |
|-------|------------|---------|---------------|
| **Critical** | Active breach, data exfiltration | Compromised admin account | < 1 hour |
| **High** | Potential breach, failed access attempts | 100 failed logins from unknown IP | < 4 hours |
| **Medium** | Security misconfiguration | Exposed API endpoint | < 24 hours |
| **Low** | Security best practice violation | Weak password detected | < 1 week |

### Response Procedure

**Step 1: Detection**
```
Automated alerts (failed logins, unusual access patterns)
Manual reports (user notices suspicious activity)
```

**Step 2: Containment**
```
# Revoke compromised credentials
vault token revoke <token-id>

# Block suspicious IP
iptables -A INPUT -s 203.0.113.45 -j DROP

# Disable compromised user
POST /api/v1/users/alice@example.com/disable
```

**Step 3: Investigation**
```sql
-- Review audit logs
SELECT * FROM audit_log
WHERE user_email = 'alice@example.com'
  AND timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp;

-- Check for unauthorized config changes
SELECT * FROM audit_log
WHERE event_type LIKE '%.create' OR event_type LIKE '%.delete'
  AND user_email = 'alice@example.com';
```

**Step 4: Remediation**
```
- Rotate all affected credentials
- Apply security patches
- Update firewall rules
- Restore from backup if data compromised
```

**Step 5: Post-Incident**
```
- Document incident in report
- Update security procedures
- Conduct training
- Implement additional controls
```

### Emergency Contacts

```
Security Team Lead: security@example.com
On-Call Engineer: +1-555-ONCALL
Vendor Support: support@streamforge.io
```

---

**End of Security Documentation**

For architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).
For deployment, see [DEPLOYMENT.md](DEPLOYMENT.md).
