# Authentication & Authorization

## Authentication Methods

### JWT Bearer Tokens

Default authentication method. Tokens are validated in `magenta/api/middleware.py`.

```
Authorization: Bearer <jwt_token>
```

```python
# From magenta/api/middleware.py (validation stub)
async def validate_auth(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(status_code=401)
    return {"authenticated": True, "tenant": "default"}
```

**Production JWT validation** should be implemented with:

```python
import jwt
from azure.identity import DefaultAzureCredential

# Validate Entra ID token
def validate_entra_token(token: str) -> dict:
    credential = DefaultAzureCredential()
    # Use Microsoft identity platform JWKS endpoint
    jwks_client = jwt.PyJWKClient("https://login.microsoftonline.com/common/discovery/keys")
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience="api://magenta-api",
    )
```

### API Keys (Alternative)

For machine-to-machine communication.

```
Authorization: ApiKey mk_magenta_abc123def456
```

API keys are stored hashed (SHA-256) and scoped to:

| Scope | Access |
|---|---|
| `missions:read` | List and view missions |
| `missions:write` | Create and start missions |
| `agents:admin` | Register and configure agents |
| `playbooks:admin` | Create and update playbooks |
| `webhooks:receive` | Receive webhook payloads |
| `admin` | Full access |

### Azure Managed Identity

When deployed on Azure, Magenta can use Managed Identity for authentication. No secrets needed.

```python
from azure.identity import DefaultAzureCredential
credential = DefaultAzureCredential()
token = credential.get_token("api://magenta-api/.default")
```

## Authorization (RBAC)

Roles are mapped from JWT claims or API key metadata:

| Role | Access |
|---|---|
| `soc_analyst` | Read missions, approve actions (risk < 40) |
| `soc_engineer` | Read/write missions, manage playbooks |
| `soc_admin` | Full access, manage agents, view audit logs |
| `soc_manager` | Read all, approve high-risk actions |
| `automation` | API key — scripted mission creation |

```python
# Middleware enforces:
ROLE_PERMISSIONS = {
    "soc_analyst": ["missions:read", "approval:low"],
    "soc_engineer": ["missions:*", "playbooks:*"],
    "soc_admin": ["*"],
}
```
