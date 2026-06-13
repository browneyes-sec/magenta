# SSL/TLS Configuration

## Overview

Magenta enforces TLS 1.3 minimum in production. The API server itself does not terminate TLS — this is delegated to a reverse proxy (Nginx, Caddy, Azure Front Door, or AWS ALB).

## Deployment Topologies

### Docker Compose (Nginx Reverse Proxy)

```
Client ──HTTPS──► Nginx (:443) ──HTTP──► FastAPI (:8000)
```

```nginx
server {
    listen 443 ssl http2;
    server_name magenta.example.com;

    ssl_certificate /etc/letsencrypt/live/magenta.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/magenta.example.com/privkey.pem;
    ssl_protocols TLSv1.3;
    ssl_ciphers TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://magenta-api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Kubernetes (Ingress Controller)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: magenta-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/backend-protocol: "HTTP"
spec:
  ingressClassName: nginx
  tls:
    - hosts: [magenta.example.com]
      secretName: magenta-tls
  rules:
    - host: magenta.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: magenta-api
                port:
                  number: 8000
```

### Azure Front Door + Application Gateway

```
Client ──HTTPS──► Azure Front Door ──HTTPS──► App Gateway ──HTTP──► FastAPI
```

## Certificate Management

| Provider | Renewal | Automation |
|---|---|---|
| Let's Encrypt | Every 90 days | cert-manager (K8s) or certbot (Docker) |
| Azure Key Vault | Per policy | AKV certificate auto-renewal |
| Enterprise CA | Per PKI policy | Venafi / manual rotation |

## mTLS for Agent-to-Agent Communication

For A2A messages over Event Hubs, each agent presents a client certificate:

```python
# Agent authenticates to Event Hubs with mTLS
event_hub_client = EventHubConsumerClient(
    fully_qualified_namespace="magenta-agent-bus.servicebus.windows.net",
    eventhub_name="raw-alerts",
    credential=credential,  # Managed Identity
    # or:
    # connection_verifies=True,
    # client_cert_path="/etc/magenta/certs/agent.pem",
    # client_key_path="/etc/magenta/certs/agent-key.pem",
)
```

## Cipher Suite Hardening

```nginx
# Production nginx cipher config
ssl_protocols TLSv1.3;
ssl_ciphers TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384;
ssl_prefer_server_ciphers off;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 1h;
ssl_session_tickets off;
```

## HTTP → HTTPS Redirect

```nginx
server {
    listen 80;
    server_name magenta.example.com;
    return 301 https://$host$request_uri;
}
```

## FastAPI Server Configuration

The FastAPI server itself runs HTTP only (TLS handled by reverse proxy):

```bash
# Run behind reverse proxy — no TLS termination here
uvicorn magenta.api.server:create_app --host 0.0.0.0 --port 8000 --workers 4
```

## Compliance

| Standard | Requirement | Magenta Compliance |
|---|---|---|
| TLS 1.3 minimum | NIST SP 800-52 Rev. 2 | Enforced in reverse proxy |
| Certificate rotation < 90 days | Various | Let's Encrypt (90d) or automated CA |
| mTLS for internal services | Zero Trust | Event Hubs mTLS for A2A |
| HSTS | OWASP Top 10 | `Strict-Transport-Security: max-age=31536000` in nginx |
