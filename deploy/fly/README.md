# OpenHands Fly.io Deployment

Deploy OpenHands to Fly.io for a managed cloud deployment.

## Prerequisites

- [Fly.io CLI](https://fly.io/docs/hands-on/install-flyctl/) installed
- Fly.io account

## Deployment Steps

1. **Login to Fly.io**
   ```bash
   fly auth login
   ```

2. **Create the app**
   ```bash
   cd deploy/fly
   fly launch --no-deploy
   ```

3. **Create a volume for persistent storage**
   ```bash
   fly volumes create openhands_data --size 10 --region iad
   ```

4. **Set secrets**
   ```bash
   fly secrets set LLM_API_KEY=your-openai-api-key
   fly secrets set JWT_SECRET=$(openssl rand -hex 32)
   ```

5. **Deploy**
   ```bash
   fly deploy
   ```

6. **Access your app**
   ```bash
   fly open
   ```

## Configuration

### Environment Variables

Set via `fly secrets set`:

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_API_KEY` | Yes | Your LLM provider API key |
| `JWT_SECRET` | Yes | Secret for JWT tokens |
| `LLM_MODEL` | No | Model to use (default: gpt-4o) |
| `LLM_BASE_URL` | No | Custom LLM endpoint |

### Scaling

```bash
# Scale to more machines
fly scale count 2

# Increase memory
fly scale memory 8192
```

### Logs

```bash
fly logs
```

### SSH Access

```bash
fly ssh console
```

## Limitations

Fly.io deployment has some limitations compared to self-hosted Docker:

1. **No Docker-in-Docker**: The sandbox runtime requires Docker socket access, which is not available on Fly.io. This means code execution in sandboxes may be limited.

2. **Persistent Storage**: Limited to Fly.io volumes (max 500GB per volume).

For full functionality including sandbox execution, use the Docker Compose deployment on a VPS with Docker socket access.

## Cost Estimate

- **Shared CPU 2x, 4GB RAM**: ~$30/month
- **Volume (10GB)**: ~$1.50/month
- **Bandwidth**: Pay as you go

Total: ~$35-50/month for basic usage
