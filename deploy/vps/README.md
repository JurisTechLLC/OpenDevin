# OpenHands VPS Deployment

This directory contains everything needed to deploy OpenHands on a VPS (Virtual Private Server) with full Docker support.

## Prerequisites

- A VPS with at least 4GB RAM and 2 CPU cores (8GB RAM recommended)
- Ubuntu 20.04+, Debian 11+, or CentOS 8+ (Ubuntu recommended)
- A domain name pointing to your VPS IP (for SSL)
- GitHub OAuth App credentials

## Quick Start

### 1. Provision a VPS

Recommended providers:
- DigitalOcean ($12-24/month for 4-8GB RAM)
- Linode ($12-24/month for 4-8GB RAM)
- Vultr ($12-24/month for 4-8GB RAM)
- AWS EC2 (t3.medium or larger)

### 2. Initial Server Setup

SSH into your VPS and run:

```bash
# Clone the repository
git clone https://github.com/JurisTechLLC/OpenDevin.git
cd OpenDevin/deploy/vps

# Run the setup script (installs Docker, creates directories)
sudo ./setup.sh
```

### 3. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your configuration
nano .env
```

Required configuration:
- `JWT_SECRET`: Generate with `openssl rand -base64 32`
- `GITHUB_APP_CLIENT_ID`: From your GitHub OAuth App
- `GITHUB_APP_CLIENT_SECRET`: From your GitHub OAuth App

### 4. Create GitHub OAuth App

1. Go to https://github.com/settings/developers
2. Click "New OAuth App"
3. Fill in:
   - Application name: `OpenHands`
   - Homepage URL: `https://your-domain.com`
   - Authorization callback URL: `https://your-domain.com/api/github/callback`
4. Copy the Client ID and Client Secret to your `.env` file

### 5. Deploy

```bash
# Deploy OpenHands
./deploy.sh
```

### 6. Set Up SSL (Recommended)

```bash
# Set up Let's Encrypt SSL certificate
sudo ./setup-ssl.sh your-domain.com your-email@example.com
```

## File Structure

```
deploy/vps/
├── docker-compose.prod.yml  # Production Docker Compose configuration
├── .env.example             # Environment variable template
├── setup.sh                 # Initial VPS setup script
├── deploy.sh                # Deployment script
├── setup-ssl.sh             # SSL certificate setup script
├── nginx/
│   └── nginx.conf           # Nginx reverse proxy configuration
└── README.md                # This file
```

## Configuration Options

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET` | Yes | Secret key for JWT tokens |
| `GITHUB_APP_CLIENT_ID` | Yes | GitHub OAuth App Client ID |
| `GITHUB_APP_CLIENT_SECRET` | Yes | GitHub OAuth App Client Secret |
| `SANDBOX_RUNTIME_CONTAINER_IMAGE` | No | Docker image for code sandboxes |
| `SANDBOX_USER_ID` | No | User ID for sandbox (default: 0) |
| `WORKSPACE_BASE` | No | Host path for workspace files |
| `APP_MODE` | No | `saas` (with auth) or `oss` (no auth) |
| `LLM_API_KEY` | No | Default LLM API key |
| `LLM_MODEL` | No | Default LLM model (default: gpt-4o) |
| `DOMAIN` | No | Your domain name (for SSL) |

## Management Commands

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f

# Restart services
docker compose -f docker-compose.prod.yml restart

# Stop services
docker compose -f docker-compose.prod.yml down

# Update to latest version
./deploy.sh --update

# Check container status
docker compose -f docker-compose.prod.yml ps
```

## Updating

To update to the latest version:

```bash
cd /path/to/OpenDevin/deploy/vps
./deploy.sh --update
```

This will:
1. Pull the latest code from the repository
2. Rebuild the Docker images
3. Restart the containers

## Troubleshooting

### Container won't start

Check the logs:
```bash
docker compose -f docker-compose.prod.yml logs openhands
```

### SSL certificate issues

Ensure your domain is pointing to the VPS IP:
```bash
dig +short your-domain.com
```

Renew certificate manually:
```bash
sudo certbot renew
```

### Docker socket permission issues

Ensure the Docker socket is accessible:
```bash
ls -la /var/run/docker.sock
```

### Memory issues

OpenHands requires at least 4GB RAM. Check memory usage:
```bash
free -h
docker stats
```

## Security Considerations

1. Always use HTTPS in production
2. Keep your `.env` file secure and never commit it to version control
3. Regularly update the system and Docker images
4. Consider setting up a firewall (ufw) to restrict access
5. Use strong, unique values for `JWT_SECRET`

## Support

For issues and questions:
- GitHub Issues: https://github.com/JurisTechLLC/OpenDevin/issues
- OpenHands Documentation: https://docs.all-hands.dev
