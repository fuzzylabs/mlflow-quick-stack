# MLflow Quick Stack

A single `docker compose up` to get a production-shaped MLflow platform with:

| Service | Purpose | URL |
|---------|---------|-----|
| **MLflow** | Tracking server (GenAI + AI Gateway, built-in auth) | `https://mlflow.local.dev` |
| **PostgreSQL 18** | Backend metadata store + auth DB | internal only |
| **MinIO** | S3-compatible artifact storage | Console: `https://minio.local.dev` / API: `https://s3.local.dev` |
| **LocalAI** | OpenAI-compatible local model server | `https://localai.local.dev` |
| **Open WebUI** | Chat UI for LocalAI + Ollama models | `https://chat.local.dev` |
| **Traefik v3** | HTTPS reverse proxy | Dashboard: `https://traefik.local.dev` |

All traffic goes through Traefik on ports **80** (→ redirect) and **443** (TLS).  
Backend services are not exposed to the host (except optional localhost direct-access ports).

---

## Quick Start

### 1. Clone & configure

```bash
cp .env.example .env        # edit credentials as needed
```

### 2. Generate self-signed TLS certificates

```bash
chmod +x scripts/*.sh
./scripts/generate-certs.sh  # creates volumes/traefik/certs/local-{cert,key}.pem
```

Trust the certificate system-wide to avoid browser warnings (works on macOS and RHEL/CentOS/Fedora):

```bash
sudo ./scripts/trust-cert.sh         # add to OS trust store
# sudo ./scripts/trust-cert.sh remove  # revoke later if needed
```

### 3. Add local DNS entries

```bash
sudo ./scripts/hosts.sh add
# or manually:
sudo tee -a /etc/hosts <<EOF
127.0.0.1  mlflow.local.dev
127.0.0.1  minio.local.dev
127.0.0.1  s3.local.dev
127.0.0.1  traefik.local.dev
EOF
```

### 4. Start the stack

```bash
docker compose up -d
```

First run builds the custom MLflow image (~60 s).  
Watch progress with `docker compose logs -f mlflow`.

### 5. Verify

```bash
docker compose ps          # all services should be healthy
open https://mlflow.local.dev   # MLflow UI — login with admin / admin-s3cr3t!
```

---

## Default Credentials

| Service | Username | Password | Where to change |
|---------|----------|----------|-----------------|
| MLflow | `admin` | `admin-s3cr3t!` | `.env` → `MLFLOW_AUTH_ADMIN_PASSWORD` and `volumes/mlflow/basic_auth.ini` |
| MinIO Console | `minioadmin` | `minio-s3cr3t!` | `.env` → `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` |
| PostgreSQL | `mlflow` | `mlflow-s3cr3t!` | `.env` → `POSTGRES_USER` / `POSTGRES_PASSWORD` |
| LocalAI | API key | `change-me-to-a-localai-key` | `.env` → `LOCALAI_API_KEY` |
| Open WebUI | `admin@local.dev` | `change-me` | `.env` → `OPENWEBUI_ADMIN_EMAIL` / `OPENWEBUI_ADMIN_PASSWORD` |
| Traefik Dashboard | `admin` | `admin` | `volumes/traefik/dynamic/config.yml` → `basic-auth` middleware |

> **MLflow note:** MLflow v3.10+ requires passwords of at least 13 characters.

> **Traefik note:** The dashboard password is a bcrypt hash inside `volumes/traefik/dynamic/config.yml`.  
> Generate a new one with:  
> ```bash
> htpasswd -nbB admin 'your-new-password'
> ```
> Then paste the full `admin:$2y$...` line into the `users` array.

---

## AI Gateway (Ollama / LLM Endpoints)

MLflow's built-in AI Gateway lets you create managed endpoints for LLM providers.
This stack is pre-configured to connect to **Ollama** running on your host machine,
but you can also point it at an external Ollama server on your network.

### Prerequisites

1. Install and run [Ollama](https://ollama.com) on the host or a remote machine
2. Pull a model: `ollama pull <model-name>` (e.g. `llama3`, `mistral`, `deepseek-r1:32b`)

### Ollama Connection Options

| Ollama Location | API Base URL to use in AI Gateway | Notes |
|----------------|-----------------------------------|-------|
| **Same machine** (macOS/Windows) | `http://host.docker.internal:11434` | Default — uses Docker's magic hostname |
| **Same machine** (Linux) | `http://172.17.0.1:11434` | Docker bridge gateway IP (or use `--add-host`) |
| **Remote server** on LAN/VPN | `http://192.168.1.50:11434` | Use the server's IP; Ollama must bind to `0.0.0.0` |
| **Remote server** with DNS | `http://ollama.internal.lan:11434` | Must be resolvable from inside the Docker network |
| **Ollama in Docker** (same compose) | `http://ollama:11434` | Add an `ollama` service to `docker-compose.yml` |

#### Pointing to an External Ollama Server

By default Ollama only listens on `127.0.0.1`. To make it accessible over the network,
set `OLLAMA_HOST` on the **Ollama server machine**:

```bash
# On the Ollama server — bind to all interfaces
OLLAMA_HOST=0.0.0.0 ollama serve

# Or via systemd override (Linux):
sudo systemctl edit ollama
# Add:
#   [Service]
#   Environment="OLLAMA_HOST=0.0.0.0"
# Then: sudo systemctl restart ollama

# Or via launchctl (macOS, if installed via brew):
launchctl setenv OLLAMA_HOST "0.0.0.0"
# Restart Ollama after setting
```

Then update `.env` on the Docker host to point to the remote Ollama IP:

```bash
# .env
OLLAMA_BASE_URL=http://192.168.1.50:11434
```

> **Security:** Ollama has no built-in authentication. Only expose it on trusted
> networks or behind a VPN/firewall. Never bind `0.0.0.0` on a public interface
> without additional access controls.

#### Verifying Connectivity from the MLflow Container

```bash
# Check that the MLflow container can reach Ollama:
docker compose exec mlflow curl -s http://192.168.1.50:11434/api/tags | head -c 200

# For host.docker.internal (default):
docker compose exec mlflow curl -s http://host.docker.internal:11434/api/tags | head -c 200
```

If the connection fails, check:
- Ollama is running and bound to `0.0.0.0` (not `127.0.0.1`)
- No firewall blocking port `11434` between the machines
- The IP is reachable from the Docker network (try `ping` from the container)

#### Adding Ollama as a Docker Compose Service

If you prefer running Ollama inside Docker (e.g. with GPU passthrough), add it
to `docker-compose.yml`:

```yaml
services:
  # ... existing services ...

  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    volumes:
      - ./volumes/ollama:/root/.ollama
    ports:
      - "11434:11434"
    networks:
      - mlflow-network
    # Uncomment for NVIDIA GPU:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: all
    #           capabilities: [gpu]
```

Then update `.env`:

```bash
OLLAMA_BASE_URL=http://ollama:11434
```

And remove `extra_hosts: host.docker.internal:host-gateway` from the `mlflow` service
(no longer needed when Ollama is on the same Docker network).

Pull models after the container starts:

```bash
docker compose exec ollama ollama pull <model-name>
```

### Creating an Endpoint via the UI

1. Open `https://mlflow.local.dev` and log in
2. Navigate to **AI Gateway** in the sidebar
3. Create a **Secret** — Ollama doesn't need a real key, enter any non-empty value (e.g. `ollama`)
4. Create an **Endpoint**:
   - **Provider**: Ollama
   - **API Base URL**: the URL from the connection table above (e.g. `http://host.docker.internal:11434` for local, or `http://192.168.1.50:11434` for remote)
   - **API Key Name / API Key**: use the secret you created (value is ignored by Ollama)
   - **Model**: the Ollama model name (e.g. `llama3`, `mistral`, `deepseek-r1:32b`)

### Testing via curl

```bash
curl -sk -u admin:admin-s3cr3t! \
  -X POST https://mlflow.local.dev/gateway/mlflow/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-endpoint-name",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Testing via Python SDK

```python
import mlflow
import os

os.environ["MLFLOW_TRACKING_USERNAME"] = "admin"
os.environ["MLFLOW_TRACKING_PASSWORD"] = "admin-s3cr3t!"
os.environ["MLFLOW_TRACKING_INSECURE_TLS"] = "true"

mlflow.set_tracking_uri("https://mlflow.local.dev")

from mlflow.deployments import get_deploy_client
client = get_deploy_client("mlflow")
response = client.predict(
    endpoint="your-endpoint-name",
    inputs={"messages": [{"role": "user", "content": "Hello!"}]}
)
print(response)
```

### Using Ollama Tracing

```python
import mlflow
import ollama

mlflow.set_tracking_uri("https://mlflow.local.dev")
mlflow.ollama.autolog()

with mlflow.start_run():
    response = ollama.chat(
        model="<model-name>",
        messages=[{"role": "user", "content": "Hello!"}]
    )
```

---

## LocalAI (OpenAI-compatible Model Server)

[LocalAI](https://localai.io/) provides an OpenAI-compatible API for running LLMs locally.
It supports model auto-unloading and memory-safe single-model mode.

### Key Features

- **API key authentication** — all requests require `Authorization: Bearer <key>`
- **Idle watchdog** — automatically unloads models after `LOCALAI_WATCHDOG_IDLE_TIMEOUT` (default: 15 min)
- **Single-model mode** — `LOCALAI_MAX_ACTIVE_BACKENDS=1` ensures only one model is loaded at a time (LRU eviction)
- **Busy watchdog** — kills stuck backends after `LOCALAI_WATCHDOG_BUSY_TIMEOUT` (default: 5 min)
- **Built-in web UI** — browse and manage models at `https://localai.local.dev`

### GPU Support

The default image is CPU-only (`localai/localai:latest-cpu`). For NVIDIA GPU acceleration:

1. Change `.env`:
   ```bash
   LOCALAI_IMAGE_TAG=latest-gpu-nvidia-cuda-12
   ```
2. Uncomment the `deploy.resources.reservations` block in `docker-compose.yml` under the `localai` service.

> **Apple Silicon note:** The `latest-cpu` image is `linux/amd64` and runs under Rosetta emulation.
> Some backends (llama-cpp AVX2/AVX512) may not work. Use the `llama-cpp-fallback` binary or
> consider using Ollama natively on the host for ARM Macs.

### Adding Models

There are three ways to add models:

#### Option 1: LocalAI Web Gallery (easiest)

1. Open `https://localai.local.dev` in your browser
2. Browse the model gallery and click **Install** on any model
3. The model is downloaded and configured automatically
4. Models persist in `volumes/localai/models/` across restarts

#### Option 2: Download a GGUF file + write a YAML config (offline-friendly)

This is the recommended approach for air-gapped / offline deployments.

**Step 1 — Download a GGUF model file:**

```bash
# Example: download Gemma 3 1B from HuggingFace
curl -L -o volumes/localai/models/gemma-3-1b-it-Q4_K_M.gguf \
  "https://huggingface.co/bartowski/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_K_M.gguf"
```

> Use `-Q4_K_M` or `-Q5_K_M` quantisations for a good balance of quality and size.

**Step 2 — Create a model config YAML:**

Create a file in `volumes/localai/models/` with the model name as the filename
(e.g. `gemma-3-1b-it.yaml`):

```yaml
name: gemma-3-1b-it
backend: llama-cpp
parameters:
  model: gemma-3-1b-it-Q4_K_M.gguf
context_size: 8192
template:
  chat_message: |
    <start_of_turn>{{.RoleName}}
    {{.Content}}<end_of_turn>
  chat: |
    {{.Input}}
    <start_of_turn>model
stopwords:
  - <end_of_turn>
  - <start_of_turn>
```

**Model config reference:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Model name used in API calls (`"model": "gemma-3-1b-it"`) |
| `backend` | Yes | Inference backend — usually `llama-cpp` for GGUF models |
| `parameters.model` | Yes | Filename of the GGUF file (must be in the same `models/` directory) |
| `context_size` | No | Max context window in tokens (default: value from `.env` `LOCALAI_CONTEXT_SIZE`) |
| `template.chat_message` | No | Go template for each message. Use `{{.RoleName}}` and `{{.Content}}` |
| `template.chat` | No | Go template wrapping the full conversation. `{{.Input}}` = all messages |
| `stopwords` | No | Tokens that signal the model to stop generating |
| `threads` | No | Override CPU threads for this model (default: `LOCALAI_THREADS`) |
| `gpu_layers` | No | Number of layers to offload to GPU (requires GPU image) |

> **Chat templates vary per model family.** Check the model's HuggingFace page or
> `tokenizer_config.json` for the correct format. Common templates:
> - **Gemma/Gemma 3:** `<start_of_turn>role\n...<end_of_turn>`
> - **Llama 3/3.1:** `<|begin_of_text|><|start_header_id|>role<|end_header_id|>...<|eot_id|>`
> - **Mistral/Mixtral:** `[INST] ... [/INST]`
> - **Phi-3/4:** `<|user|>\n...<|end|>\n<|assistant|>`

**Step 3 — Restart LocalAI to pick up the new model:**

```bash
docker compose restart localai
```

#### Option 3: Install via the API

```bash
# Install from HuggingFace via the gallery API
curl -sk -H "Authorization: Bearer $LOCALAI_API_KEY" \
  https://localai.local.dev/models/apply \
  -d '{"id": "huggingface://bartowski/gemma-3-1b-it-GGUF/gemma-3-1b-it-Q4_K_M.gguf"}'
```

### Verifying Models

```bash
# List installed models
curl -sk -H "Authorization: Bearer $LOCALAI_API_KEY" \
  https://localai.local.dev/v1/models | python3 -m json.tool

# Test chat completion
curl -sk -H "Authorization: Bearer $LOCALAI_API_KEY" \
  -H "Content-Type: application/json" \
  https://localai.local.dev/v1/chat/completions \
  -d '{
    "model": "gemma-3-1b-it",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Memory Management

| Setting | Env Var | Default | Effect |
|---------|---------|---------|--------|
| Max loaded models | `LOCALAI_MAX_ACTIVE_BACKENDS` | `1` | LRU eviction when limit reached |
| Idle timeout | `LOCALAI_WATCHDOG_IDLE_TIMEOUT` | `15m` | Unload idle models automatically |
| Busy timeout | `LOCALAI_WATCHDOG_BUSY_TIMEOUT` | `5m` | Kill stuck inference backends |

---

## Open WebUI (Chat Interface)

[Open WebUI](https://docs.openwebui.com/) provides a ChatGPT-like interface
that connects to both **LocalAI** and **Ollama** running on the host.

### Login

An admin account is **auto-created on first launch** from the `.env` file:

| Setting | Env Var | Default |
|---------|---------|---------|
| Email (login) | `OPENWEBUI_ADMIN_EMAIL` | `admin@local.dev` |
| Password | `OPENWEBUI_ADMIN_PASSWORD` | `change-me` |
| Display name | `OPENWEBUI_ADMIN_NAME` | `Admin` |

1. Open `https://chat.local.dev`
2. Log in with the email and password above
3. Models from LocalAI (and Ollama if running) appear in the model dropdown

> Public signup is disabled (`ENABLE_INITIAL_ADMIN_SIGNUP=False`).
> Additional users can be created by the admin from **Admin Panel → Users**.

### API Key Access

API key generation is enabled. To create an API key:

1. Log in to Open WebUI at `https://chat.local.dev`
2. Go to **Settings → Account → API Keys**
3. Click **Create new API key**

Use the key with the OpenAI-compatible API:

```bash
curl -sk -H "Authorization: Bearer <your-openwebui-api-key>" \
  -H "Content-Type: application/json" \
  https://chat.local.dev/api/chat/completions \
  -d '{
    "model": "gemma-3-1b-it",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Backend Connections

| Backend | How it connects | Config |
|---------|----------------|--------|
| **LocalAI** | `http://localai:8080/v1` (Docker network) | `OPENAI_API_BASE_URL` + `OPENAI_API_KEY` in compose |
| **Ollama** (host) | `http://host.docker.internal:11434` | `OLLAMA_BASE_URL` in `.env` |

Both backends are enabled by default. Models from both appear in the Open WebUI dropdown.

### Offline Mode

Open WebUI runs with `OFFLINE_MODE=true` — no HuggingFace Hub downloads or version
checks are made at startup. This makes it suitable for air-gapped deployments.

> If you need RAG/embedding features, pre-cache the `sentence-transformers/all-MiniLM-L6-v2`
> model in `volumes/open-webui/cache/` before going offline, or disable `OFFLINE_MODE`.

### Disabling a Backend

To use only LocalAI (no Ollama), set in `.env`:
```bash
OLLAMA_BASE_URL=
```

To use only Ollama (no LocalAI), remove or comment out the `open-webui` and `localai` services.

---

## Security Considerations

### Secrets Encryption

MLflow encrypts AI Gateway secrets (API keys) at rest using a Key Encryption Key (KEK).
The passphrase is set via `MLFLOW_CRYPTO_KEK_PASSPHRASE` in `.env`.

**Important:**
- The `.env.example` ships with a placeholder — generate a real one before first use:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- If you change the passphrase after secrets have been stored, rotate with:
  ```bash
  docker compose exec mlflow mlflow crypto rotate-kek
  ```

### Flask Secret Key

`MLFLOW_FLASK_SERVER_SECRET_KEY` is used to sign session cookies. Change it from the default
before any real use:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Auth Model

| Frontend | Auth Method |
|----------|-------------|
| MLflow | Built-in basic-auth (`--app-name basic-auth`) — session cookies + HTTP Basic |
| MinIO Console | MinIO's own login (no Traefik proxy auth) |
| MinIO S3 API | AWS Signature v4 (no Traefik proxy auth) |
| Traefik Dashboard | Traefik basicAuth middleware (bcrypt hash in `config.yml`) |

MLflow's auth DB is stored in the same PostgreSQL instance as the tracking metadata
(configured in `volumes/mlflow/basic_auth.ini`).

### Production Hardening Checklist

- [ ] Change all default passwords in `.env` and `volumes/mlflow/basic_auth.ini`
- [ ] Generate unique `MLFLOW_FLASK_SERVER_SECRET_KEY` and `MLFLOW_CRYPTO_KEK_PASSPHRASE`
- [ ] Generate unique `LOCALAI_API_KEY` and `OPENWEBUI_SECRET_KEY`
- [ ] Generate a new Traefik basicAuth hash and update `volumes/traefik/dynamic/config.yml`
- [ ] Switch to real TLS certificates (see below)
- [ ] Restrict network access — don't expose MinIO or PostgreSQL ports externally
- [ ] Remove localhost direct-access ports (comment out `LOCALHOST_*_PORT` vars in `.env`)

---

## TLS Certificates

### Self-Signed (Development)

The default setup uses self-signed certificates generated by `scripts/generate-certs.sh`.
These are stored in `volumes/traefik/certs/` and referenced from `volumes/traefik/dynamic/config.yml`.

### Using Your Own Certificates

To use certificates from your own CA or a purchased cert:

1. Place your cert and key files in `volumes/traefik/certs/`:
   ```bash
   cp /path/to/your-cert.pem volumes/traefik/certs/local-cert.pem
   cp /path/to/your-key.pem  volumes/traefik/certs/local-key.pem
   chmod 600 volumes/traefik/certs/local-key.pem
   ```

2. If your filenames differ, update `volumes/traefik/dynamic/config.yml`:
   ```yaml
   tls:
     certificates:
       - certFile: /etc/traefik/certs/your-cert.pem
         keyFile: /etc/traefik/certs/your-key.pem
     stores:
       default:
         defaultCertificate:
           certFile: /etc/traefik/certs/your-cert.pem
           keyFile: /etc/traefik/certs/your-key.pem
   ```

3. If your cert includes intermediate CAs, concatenate them into the cert file:
   ```bash
   cat your-domain.pem intermediate-ca.pem > volumes/traefik/certs/local-cert.pem
   ```

4. Restart Traefik (or wait for auto-reload):
   ```bash
   docker compose restart traefik
   ```

### Let's Encrypt (Production)

For automatic free certificates from Let's Encrypt:

1. In `volumes/traefik/traefik.yml`, uncomment the `certificatesResolvers` block and set your email:
   ```yaml
   certificatesResolvers:
     letsencrypt:
       acme:
         email: you@example.com
         storage: /letsencrypt/acme.json
         httpChallenge:
           entryPoint: web
   ```

2. In `volumes/traefik/dynamic/config.yml`, change every `tls: {}` to:
   ```yaml
   tls:
     certResolver: letsencrypt
   ```

3. Remove (or keep as fallback) the self-signed cert entries under `tls.certificates` and `tls.stores`

4. Ensure port 80 is reachable from the internet for the HTTP-01 challenge

5. Restart:
   ```bash
   docker compose restart traefik
   ```

> Let's Encrypt certificates are cached in `volumes/traefik/acme/` and auto-renewed.

---

## External Caddy Reverse Proxy

If you want to use [Caddy](https://caddyserver.com/) as the public-facing reverse proxy
(e.g. on a VPS, or to get automatic HTTPS with real domain names), you can point Caddy
at the localhost ports exposed by the Docker Compose stack.

### Option A — Caddy replaces Traefik (same machine)

Disable Traefik's host port bindings by commenting out its `ports:` in `docker-compose.yml`,
then use Caddy to terminate TLS and proxy directly to the service ports:

```caddyfile
# /etc/caddy/Caddyfile  (or wherever you keep your Caddy config)

mlflow.example.com {
    reverse_proxy localhost:5000
}

minio.example.com {
    reverse_proxy localhost:9001
}

s3.example.com {
    reverse_proxy localhost:9000
}
```

Caddy automatically obtains and renews Let's Encrypt certificates for each domain.

> **Tip:** Update `.env` domain variables and the MLflow `--allowed-hosts` flag
> in `docker-compose.yml` to include your new domain(s).

### Option B — Caddy in front of Traefik (same machine)

Keep Traefik running on its default ports but bind them to `127.0.0.1` only
(so they aren't publicly reachable). Caddy handles public TLS and forwards to Traefik:

```yaml
# docker-compose.yml — change Traefik ports:
ports:
  - "127.0.0.1:8080:80"
  - "127.0.0.1:8443:443"
```

```caddyfile
mlflow.example.com {
    reverse_proxy https://127.0.0.1:8443 {
        transport http {
            tls_insecure_skip_verify   # Traefik has self-signed certs
        }
        header_up Host {upstream_hostport}
    }
}

minio.example.com {
    reverse_proxy https://127.0.0.1:8443 {
        transport http {
            tls_insecure_skip_verify
        }
        header_up Host {upstream_hostport}
    }
}

s3.example.com {
    reverse_proxy https://127.0.0.1:8443 {
        transport http {
            tls_insecure_skip_verify
        }
        header_up Host {upstream_hostport}
    }
}
```

### Option C — Caddy on a remote machine

If Caddy runs on a separate server (e.g. an edge proxy / VPS), point it at the
Docker host's IP or private network address:

```caddyfile
mlflow.example.com {
    reverse_proxy http://<DOCKER_HOST_IP>:5000
}

minio.example.com {
    reverse_proxy http://<DOCKER_HOST_IP>:9001
}

s3.example.com {
    reverse_proxy http://<DOCKER_HOST_IP>:9000
}
```

Replace `<DOCKER_HOST_IP>` with the target machine's IP (e.g. `10.0.0.5`).
Ensure the `LOCALHOST_*_PORT` variables are set in `.env` so the services bind
their ports on the Docker host.

### Caddy Headers & WebSocket Support

MLflow uses WebSockets for live UI updates. Add WebSocket support if needed:

```caddyfile
mlflow.example.com {
    reverse_proxy localhost:5000 {
        header_up X-Forwarded-Proto {scheme}
        header_up X-Real-IP {remote_host}
    }
}
```

### Updating MLflow `--allowed-hosts`

When changing domains, update the `--allowed-hosts` flag in `docker-compose.yml`
to include the new domain. For example:

```yaml
command: >
  mlflow server
    ...
    --allowed-hosts "mlflow.example.com,localhost:*,127.0.0.1:*"
    --cors-allowed-origins "https://mlflow.example.com,http://localhost:*"
    ...
```

### Quick Checklist for Caddy Setup

- [ ] Domains point to the Caddy server's IP (DNS A records)
- [ ] `LOCALHOST_*_PORT` vars are set in `.env` (services must be reachable)
- [ ] `.env` domain variables updated to match your real domains
- [ ] `--allowed-hosts` in `docker-compose.yml` includes the new domain
- [ ] `--cors-allowed-origins` in `docker-compose.yml` allows the new origin
- [ ] `volumes/mlflow/basic_auth.ini` credentials match `.env` if passwords changed
- [ ] If Traefik is disabled, comment out its `ports:` in `docker-compose.yml`

### Option D — Single Domain, Port-Based Routing

When you only have **one domain** (e.g. `myserver.example.com`) and can't create subdomains,
use different ports on the same domain to route to each service.
Caddy will automatically obtain a single certificate that covers all port blocks.

> **Using Traefik instead of Caddy?** See
> [Single Domain with Traefik](#single-domain-with-traefik-port-based-routing)
> for the equivalent entrypoint-based setup.

```caddyfile
# MLflow UI + API + AI Gateway  →  https://myserver.example.com
myserver.example.com {
    reverse_proxy localhost:5000 {
        header_up X-Forwarded-Proto {scheme}
        header_up X-Real-IP {remote_host}
    }
}

# MinIO Console  →  https://myserver.example.com:9443
myserver.example.com:9443 {
    reverse_proxy localhost:9001
}

# MinIO S3 API  →  https://myserver.example.com:9444
myserver.example.com:9444 {
    reverse_proxy localhost:9000
}
```

This gives you:

| Service | URL |
|---------|-----|
| MLflow | `https://myserver.example.com` |
| MinIO Console | `https://myserver.example.com:9443` |
| MinIO S3 API | `https://myserver.example.com:9444` |

> **Note:** Caddy listens on extra ports (9443, 9444) so make sure your firewall
> allows inbound traffic on those ports.

Update `docker-compose.yml` accordingly:

```yaml
command: >
  mlflow server
    ...
    --allowed-hosts "myserver.example.com,localhost:*,127.0.0.1:*"
    --cors-allowed-origins "https://myserver.example.com,http://localhost:*"
    ...
```

And for S3 clients, point the endpoint URL at the S3 port:

```bash
export AWS_ENDPOINT_URL=https://myserver.example.com:9444
aws s3 ls
```

#### Path-Based Alternative (single port, single domain)

If you can't open extra ports either, use path prefixes to route everything
through `:443` on one domain. This requires `handle_path` to strip the prefix
before forwarding:

```caddyfile
myserver.example.com {
    # MLflow  →  /  (default)
    handle /* {
        reverse_proxy localhost:5000 {
            header_up X-Forwarded-Proto {scheme}
        }
    }

    # MinIO Console  →  /minio/
    handle_path /minio/* {
        reverse_proxy localhost:9001
    }

    # MinIO S3 API  →  /s3/
    handle_path /s3/* {
        reverse_proxy localhost:9000
    }
}
```

> **Caveat:** Path-based routing works for API calls (`aws --endpoint-url`), but the
> MinIO Console UI may not work correctly behind a path prefix because it uses
> absolute URLs internally. The **port-based approach above is recommended**
> when you need everything on one domain.

---

## S3 Buckets

Four MinIO buckets are created automatically on first start:

| Bucket | Env Var | Purpose |
|--------|---------|---------|
| `mlflow` | `S3_BUCKET_MLFLOW` | MLflow artifact store (experiments, models, runs) |
| `quantized-models` | `S3_BUCKET_QUANTIZED_MODELS` | Quantized model storage |
| `full-precision-models` | `S3_BUCKET_FULL_PRECISION_MODELS` | Full precision model storage |
| `datasets` | `S3_BUCKET_DATASETS` | Dataset storage |

Bucket names are configurable via `.env`. Access them using the MinIO S3 API at `https://s3.local.dev` with the `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` credentials from `.env`.

```bash
# Example: list buckets with the AWS CLI
aws --endpoint-url https://s3.local.dev --no-verify-ssl s3 ls
```

---

## Connecting an MLflow Client

```python
import mlflow
import os

os.environ["MLFLOW_TRACKING_USERNAME"] = "admin"
os.environ["MLFLOW_TRACKING_PASSWORD"] = "admin-s3cr3t!"
os.environ["MLFLOW_TRACKING_INSECURE_TLS"] = "true"  # only for self-signed certs

mlflow.set_tracking_uri("https://mlflow.local.dev")
mlflow.set_experiment("my-experiment")

with mlflow.start_run():
    mlflow.log_param("model", "gpt-4")
    mlflow.log_metric("latency", 0.42)
```

Or via environment variables:

```bash
export MLFLOW_TRACKING_URI=https://mlflow.local.dev
export MLFLOW_TRACKING_USERNAME=admin
export MLFLOW_TRACKING_PASSWORD=admin-s3cr3t!
export MLFLOW_TRACKING_INSECURE_TLS=true
```

---

## Localhost Direct Access

Services can also be accessed directly on localhost (bypassing Traefik) via ports configured in `.env`:

| Service | URL | Env Var |
|---------|-----|---------|
| MLflow | `http://localhost:5000` | `LOCALHOST_MLFLOW_PORT` |
| MinIO Console | `http://localhost:9001` | `LOCALHOST_MINIO_CONSOLE_PORT` |
| MinIO S3 API | `http://localhost:9000` | `LOCALHOST_MINIO_API_PORT` |

Comment out or leave empty to disable direct access.

---

## Changing the Domain

The Traefik **file provider does not support environment variable interpolation**, so you need to update domains in three places:

1. `.env` — update `DOMAIN`, `MLFLOW_DOMAIN`, `MINIO_DOMAIN`, `S3_DOMAIN`, `TRAEFIK_DOMAIN`
2. `volumes/traefik/dynamic/config.yml` — update every `Host(...)` rule to match your new domain
3. `volumes/mlflow/basic_auth.ini` — update `database_uri` if the PostgreSQL password changed
4. Re-generate certificates: `./scripts/generate-certs.sh yourdomain.com`
5. Update `/etc/hosts` (or DNS) accordingly

### Single Domain with Traefik (Port-Based Routing)

If you only have **one domain** and can't create subdomains, you can reconfigure Traefik
to use multiple entrypoints on different ports instead of subdomain-based `Host()` rules.

#### 1. Add extra entrypoints in `volumes/traefik/traefik.yml`

```yaml
entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
          permanent: true

  websecure:
    address: ":443"

  # Additional TLS entrypoints for MinIO (single-domain setup)
  minio-console:
    address: ":9443"

  minio-api:
    address: ":9444"
```

#### 2. Update routers in `volumes/traefik/dynamic/config.yml`

Change the `Host()` rules to use your single domain and bind each router
to the correct entrypoint:

```yaml
http:
  routers:
    # MLflow — main domain on :443
    mlflow:
      entryPoints:
        - websecure
      rule: "Host(`myserver.example.com`)"
      service: mlflow-svc
      tls: {}

    # MinIO Console — same domain on :9443
    minio-console:
      entryPoints:
        - minio-console
      rule: "Host(`myserver.example.com`)"
      service: minio-console-svc
      tls: {}

    # MinIO S3 API — same domain on :9444
    minio-api:
      entryPoints:
        - minio-api
      rule: "Host(`myserver.example.com`)"
      service: minio-api-svc
      tls: {}

    # Traefik Dashboard — same domain, path prefix on :443
    traefik-dashboard:
      entryPoints:
        - websecure
      rule: "Host(`myserver.example.com`) && PathPrefix(`/traefik`)"
      service: api@internal
      middlewares:
        - basic-auth
        - strip-traefik-prefix
      tls: {}

  # ... services stay the same ...

  middlewares:
    # Strip /traefik prefix before forwarding to dashboard API
    strip-traefik-prefix:
      stripPrefix:
        prefixes:
          - "/traefik"
    # ... existing basic-auth middleware ...
```

#### 3. Expose the extra ports in `docker-compose.yml`

```yaml
# Traefik service ports:
ports:
  - "80:80"
  - "443:443"
  - "9443:9443"    # MinIO Console (TLS)
  - "9444:9444"    # MinIO S3 API (TLS)
```

#### 4. Update MLflow `--allowed-hosts` in `docker-compose.yml`

```yaml
command: >
  mlflow server
    ...
    --allowed-hosts "myserver.example.com,localhost:*,127.0.0.1:*"
    --cors-allowed-origins "https://myserver.example.com,http://localhost:*"
    ...
```

#### 5. Update `.env` domain variables

```bash
DOMAIN=example.com
MLFLOW_DOMAIN=myserver.example.com
MINIO_DOMAIN=myserver.example.com
S3_DOMAIN=myserver.example.com
TRAEFIK_DOMAIN=myserver.example.com
```

#### 6. Regenerate certificates (if self-signed)

```bash
./scripts/generate-certs.sh myserver.example.com
```

The resulting URLs:

| Service | URL |
|---------|-----|
| MLflow | `https://myserver.example.com` |
| MinIO Console | `https://myserver.example.com:9443` |
| MinIO S3 API | `https://myserver.example.com:9444` |
| Traefik Dashboard | `https://myserver.example.com/traefik` |

> **Tip:** If using Let's Encrypt, the certificate obtained for `myserver.example.com`
> on port 443 is automatically shared by all TLS entrypoints via the `default` TLS store.

---

## Offline Usage

Save all images for offline deployment:

```bash
./scripts/save-images.sh     # saves to images/*.tar
./scripts/load-images.sh     # loads from images/*.tar
```

---

## Volume Layout

All persistent data is kept under `./volumes/` (git-ignored):

```
volumes/
├── postgres/              # PostgreSQL data directory
├── minio/                 # MinIO object storage
├── mlflow/
│   └── basic_auth.ini     # MLflow auth config
├── localai/
│   └── models/            # LocalAI model files & YAML configs
├── open-webui/            # Open WebUI data (SQLite DB, uploads, cache)
└── traefik/
    ├── traefik.yml        # Traefik static config
    ├── dynamic/
    │   └── config.yml     # Routers, services, middlewares, TLS
    ├── certs/             # TLS certificates (self-signed or your own)
    └── acme/              # Let's Encrypt cert cache (if enabled)
```

To start fresh: `docker compose down -v && rm -rf volumes/postgres volumes/minio`

---

## Architecture

```
                    ┌──────────────┐
         :80/:443  │   Traefik    │
  User ──────────► │  (reverse    │
                    │   proxy)     │
                    └──┬──┬──┬──┬──┬┘
                       │  │  │  │  │
       ┌───────────┘  │  │  │  └────────────┐
       │     ┌────────┘  │  └────────┐     │
       ▼     ▼           ▼        ▼     ▼
 ┌────────┐┌────────┐┌────────┐┌───────┐┌────────┐
 │ MLflow ││ MinIO  ││ MinIO  ││LocalAI││  Open  │
 │ :5000  ││Console ││ S3 API ││ :8080 ││ WebUI  │
 │(auth + ││ :9001  ││ :9000  ││(models││ :8080  │
 │ AI GW) │└───┬────┘└───┬────┘│ +API) │└───┬────┘
 └───┬────┘    │        │   └───┬───┘    │
      │        └────┬───┘       │        │
      ▼             ▼          ▼        ▼
 ┌────────┐   ┌────────┐   ┌────────────┐
 │Postgres│   │  MinIO │   │   Ollama    │
 │ :5432  │   │  /data │   │   (host)    │
 └────────┘   └────────┘   │  :11434    │
                            └────────────┘
```
