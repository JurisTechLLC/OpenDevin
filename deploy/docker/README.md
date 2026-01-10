# OpenHands Self-Hosted Deployment

This directory contains everything needed to deploy OpenHands on your own infrastructure using Docker.

## Prerequisites

- Docker Engine 24.0+
- Docker Compose v2.0+
- At least 4GB RAM
- 20GB+ disk space
- An LLM API key (OpenAI, Anthropic, etc.)

## Quick Start

1. **Initial Setup**
   ```bash
   cd deploy/docker
   ./deploy.sh setup
   ```

2. **Configure Environment**
   Edit `.env` and set your LLM API key:
   ```bash
   nano .env
   # Set LLM_API_KEY=your-actual-api-key
   ```

3. **Build and Start**
   ```bash
   ./deploy.sh build
   ./deploy.sh start
   ```

4. **Access OpenHands**
   Open http://localhost:3000 in your browser

## Configuration

### Required Settings

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | Your LLM provider API key |
| `LLM_MODEL` | Model to use (default: gpt-4o) |
| `JWT_SECRET` | Secret for JWT tokens (auto-generated) |
| `POSTGRES_PASSWORD` | Database password (auto-generated) |

### Optional Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENHANDS_PORT` | 3000 | Port for OpenHands UI |
| `NGINX_HTTP_PORT` | 80 | HTTP port for nginx |
| `NGINX_HTTPS_PORT` | 443 | HTTPS port for nginx |
| `WORKSPACE_BASE` | ./workspace | Path for workspace files |
| `LLM_BASE_URL` | - | Custom LLM endpoint URL |

## Commands

```bash
./deploy.sh setup    # Initial setup
./deploy.sh build    # Build Docker images
./deploy.sh start    # Start all services
./deploy.sh stop     # Stop all services
./deploy.sh restart  # Restart all services
./deploy.sh logs     # View logs
./deploy.sh status   # Show service status
./deploy.sh pull     # Pull latest images
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Nginx (Reverse Proxy)               │
│                    Port 80/443                           │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                    OpenHands App                         │
│                    Port 3000                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Frontend   │  │   Backend   │  │   Sandbox   │     │
│  │   (React)   │  │  (FastAPI)  │  │  (Docker)   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
┌─────────▼─────┐ ┌───────▼───────┐ ┌─────▼─────┐
│    Redis      │ │   PostgreSQL  │ │  Volumes  │
│   (Cache)     │ │   (Database)  │ │  (Data)   │
└───────────────┘ └───────────────┘ └───────────┘
```

## Production Deployment

### SSL/TLS Setup

1. Obtain SSL certificates (Let's Encrypt recommended)
2. Place certificates in `nginx/ssl/`:
   - `fullchain.pem` - Certificate chain
   - `privkey.pem` - Private key
3. Uncomment HTTPS server block in `nginx/nginx.conf`
4. Update `DOMAIN_NAME` in `.env`

### Cloud Deployment Options

#### DigitalOcean Droplet
```bash
# Create a droplet with Docker pre-installed
# SSH into the droplet
git clone https://github.com/JurisTechLLC/OpenDevin.git
cd OpenDevin/deploy/docker
./deploy.sh setup
# Configure .env
./deploy.sh build
./deploy.sh start
```

#### AWS EC2
```bash
# Launch an EC2 instance with Docker
# Security group: Allow ports 80, 443, 3000
# Follow same steps as DigitalOcean
```

#### Fly.io
```bash
# Install flyctl
fly launch
fly secrets set LLM_API_KEY=your-key
fly deploy
```

## Customization

### Custom Agents

Create custom agents by adding Python files to `openhands/agenthub/`:

```python
# openhands/agenthub/custom_agent/custom_agent.py
from openhands.controller.agent import Agent

class CustomAgent(Agent):
    def step(self, state):
        # Your custom logic
        pass
```

### Configuration File

For advanced configuration, create `config.toml`:

```toml
[core]
workspace_base = "/opt/workspace"
max_iterations = 500

[llm]
model = "gpt-4o"
temperature = 0.0

[agent]
enable_browsing = true
enable_jupyter = true
```

## Troubleshooting

### Container won't start
```bash
./deploy.sh logs openhands
# Check for error messages
```

### Permission issues
```bash
# Ensure Docker socket is accessible
sudo chmod 666 /var/run/docker.sock
```

### Out of memory
```bash
# Increase Docker memory limit
# Or use a larger instance
```

## Multi-Tenant Setup (JurisTech)

For multi-tenant deployments, additional configuration is required:

1. Set `MULTI_TENANT_ENABLED=true` in `.env`
2. Configure GitHub App credentials
3. Set up error ingestion endpoint

See Phase 2 documentation for multi-tenant architecture details.

## Support

- [OpenHands Documentation](https://docs.openhands.dev)
- [GitHub Issues](https://github.com/All-Hands-AI/OpenHands/issues)
- [Slack Community](https://dub.sh/openhands)
