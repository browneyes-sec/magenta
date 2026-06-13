# Web Architecture for Production Deployment

## Deployment Topology

```
                          ┌─────────────┐
                          │   DNS / CDN   │
                          │  Cloudflare   │
                          └──────┬───────┘
                                 │
                          ┌──────▼───────┐
                          │  Azure Front  │
                          │  Door / WAF   │
                          └──────┬───────┘
                                 │
                          ┌──────▼───────┐
                          │  Reverse Proxy │
                          │  Nginx / Caddy │
                          └──────┬───────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
     │  FastAPI W1   │  │  FastAPI W2   │  │  FastAPI W3   │
     │  (Uvicorn)    │  │  (Uvicorn)    │  │  (Uvicorn)    │
     └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    Internal Services      │
                    │                           │
                    │  ┌──────┐  ┌──────────┐  │
                    │  │ Redis │  │ PostgreSQL│  │
                    │  └──────┘  └──────────┘  │
                    │  ┌──────┐  ┌──────────┐  │
                    │  │OLLAMA│  │Elasticsearch│ │
                    │  └──────┘  └──────────┘  │
                    │  ┌──────┐  ┌──────────┐  │
                    │  │Event │  │ Data Lake │  │
                    │  │ Hubs │  │ (Blob)    │  │
                    │  └──────┘  └──────────┘  │
                    └─────────────────────────┘
```

## Component Breakdown

### 1. DNS & CDN

| Service | Purpose |
|---|---|
| Cloudflare / Azure DNS | `magenta.example.com` → Front Door |
| CDN | Static assets (Swagger UI, ReDoc, Kibana dashboards) |
| DDoS protection | Cloudflare / Azure DDoS Standard |

### 2. Web Application Firewall (WAF)

```yaml
waf_rules:
  - name: magenta-api
    priority: 1
    action: Block
    match:
      - SQL injection patterns
      - XSS patterns
      - Path traversal
    exceptions:
      - paths: ["/webhooks/sentinel", "/webhooks/splunk"]  # SIEM payloads may trigger FP
```

### 3. Reverse Proxy (Nginx)

```nginx
upstream magenta_backend {
    least_conn;
    server 10.0.1.10:8000 max_fails=3 fail_timeout=30s;
    server 10.0.1.11:8000 max_fails=3 fail_timeout=30s;
    server 10.0.1.12:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 443 ssl http2;
    server_name magenta.example.com;

    location / {
        proxy_pass http://magenta_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /ws {
        proxy_pass http://magenta_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
    }
}
```

### 4. FastAPI Server

```bash
# Run with Gunicorn + Uvicorn workers
gunicorn magenta.api.server:create_app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --max-requests 10000 \
    --max-requests-jitter 1000 \
    --graceful-timeout 30
```

### 5. Health Probe Endpoints

```yaml
kubernetes:
  livenessProbe:
    httpGet:
      path: /healthz
      port: 8000
    initialDelaySeconds: 10
    periodSeconds: 30
  readinessProbe:
    httpGet:
      path: /readyz
      port: 8000
    initialDelaySeconds: 5
    periodSeconds: 10
```

## Container Images

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY magenta/ magenta/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["gunicorn", "magenta.api.server:create_app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000"]
```

## Scaling

| Strategy | Mechanism | Trigger |
|---|---|---|
| Horizontal (API) | K8s HPA based on CPU | >70% CPU utilization |
| Horizontal (Workers) | K8s HPA based on queue depth | >50 queued missions |
| Vertical (OLLAMA) | Scale GPU node pool | >80% VRAM utilization |
| Database | Read replicas for reporting | >1000 QPS on primary |

## Network Security

| Layer | Policy |
|---|---|
| Ingress | WAF + rate limiting + HTTPS only |
| Service mesh | mTLS between all pods (Istio/Linkerd) |
| Database | Private subnet, no public access |
| Cache (Redis) | AUTH token, TLS, private subnet |
| Model (OLLAMA) | Internal service only, no public endpoint |
| Event Hubs | Managed identity + private endpoint |
