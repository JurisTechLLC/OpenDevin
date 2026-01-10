# OpenHands Deployment Guide

This directory contains deployment configurations for self-hosting OpenHands.

## Deployment Options

| Option | Best For | Complexity | Full Sandbox Support |
|--------|----------|------------|---------------------|
| [Docker Compose](./docker/) | VPS, dedicated servers | Medium | Yes |
| [Fly.io](./fly/) | Quick cloud deployment | Low | Limited |

## Quick Comparison

### Docker Compose (Recommended)
- Full control over infrastructure
- Complete sandbox support (Docker-in-Docker)
- Best for production multi-tenant deployments
- Requires: VPS with Docker installed

### Fly.io
- Managed infrastructure
- Easy deployment and scaling
- Limited sandbox support (no Docker socket)
- Best for: Testing, light usage

## Getting Started

### Option 1: Docker Compose on VPS

```bash
# On your VPS (DigitalOcean, AWS EC2, Linode, etc.)
git clone https://github.com/JurisTechLLC/OpenDevin.git
cd OpenDevin/deploy/docker
./deploy.sh setup
# Edit .env with your LLM API key
./deploy.sh build
./deploy.sh start
```

### Option 2: Fly.io

```bash
# On your local machine
git clone https://github.com/JurisTechLLC/OpenDevin.git
cd OpenDevin/deploy/fly
fly launch --no-deploy
fly volumes create openhands_data --size 10
fly secrets set LLM_API_KEY=your-key
fly deploy
```

## System Requirements

### Minimum
- 2 CPU cores
- 4GB RAM
- 20GB disk space
- Docker Engine 24.0+

### Recommended (Production)
- 4+ CPU cores
- 8GB+ RAM
- 50GB+ SSD
- Docker Engine 24.0+

## Architecture Overview

OpenHands consists of three main components:

1. **Frontend** - React-based UI for interacting with the AI agent
2. **Backend** - FastAPI server handling WebSocket connections and agent orchestration
3. **Sandbox** - Docker containers for secure code execution

```
User Browser
     │
     ▼
┌─────────────┐
│   Nginx     │  (Reverse Proxy, SSL termination)
└─────────────┘
     │
     ▼
┌─────────────┐
│  OpenHands  │  (Frontend + Backend)
│    App      │
└─────────────┘
     │
     ▼
┌─────────────┐
│   Docker    │  (Sandbox containers for code execution)
│   Engine    │
└─────────────┘
```

## Automatic Updates

This repository is configured with a GitHub Action that automatically syncs with the upstream OpenHands project daily. To receive updates:

1. Pull the latest changes: `git pull origin main`
2. Rebuild: `./deploy.sh build`
3. Restart: `./deploy.sh restart`

## Multi-Tenant Platform (JurisTech)

For the JurisTech multi-tenant error resolution platform, additional components will be added:

- **Phase 2**: Multi-tenant API layer with PostgreSQL
- **Phase 3**: GitHub App integration for PR management

See individual phase documentation as it becomes available.

## Support

- [OpenHands Documentation](https://docs.openhands.dev)
- [GitHub Issues](https://github.com/All-Hands-AI/OpenHands/issues)
