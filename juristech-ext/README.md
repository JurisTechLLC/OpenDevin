# JurisTech OpenHands Extension

A compatibility layer that adds enhanced features to OpenHands while preserving the ability to receive upstream updates from the community repository.

## Features

### 1. Image Processing with Llava
Automatically processes attached images using Llava 7B vision model and injects detailed descriptions into the conversation context. This allows the main coding model to understand images, screenshots, diagrams, and UI mockups.

**How it works:**
- When you attach an image to a message, the extension intercepts it
- The image is sent to Llava (running locally via Ollama) for analysis
- Llava generates a detailed description of the image
- The description is injected into the conversation before the main model sees it
- The main coding model can now "understand" what's in the image

### 2. Multiple Coding Models
Configure and switch between multiple coding models including:
- Local models via Ollama (GLM-4, CodeLlama, etc.)
- Anthropic Claude models (Opus, Sonnet)
- OpenAI models
- Custom model endpoints

### 3. Devin.ai Development Container
A pre-configured Docker container that provides a sandboxed development environment for AI agents like Devin.ai to use for testing and development.

## Installation

### Prerequisites
- OpenHands installed and working
- Ollama installed with Llava model pulled (`ollama pull llava:7b`)
- Python 3.10+
- Node.js 18+

### Quick Start

1. Clone this extension alongside your OpenHands installation:
```bash
cd ~/
git clone https://github.com/JurisTechLLC/juristech-openhands-ext.git
```

2. Run the integration script:
```bash
cd juristech-openhands-ext
python integrate_openhands.py --openhands-path ~/OpenDevin
```

3. Start OpenHands with the extension:
```bash
# Linux/Mac
./start_openhands_extended.sh

# Windows
start_openhands_extended.bat
```

## Configuration

The extension configuration is stored at `~/.juristech-openhands/config.json`. You can edit this file to customize settings:

```json
{
  "vision": {
    "enabled": true,
    "ollama_base_url": "http://localhost:11434",
    "vision_model": "llava:7b",
    "max_image_size_mb": 10.0,
    "description_max_tokens": 500,
    "auto_process_images": true
  },
  "models": {
    "models": [
      {
        "name": "ollama/glm4",
        "display_name": "GLM-4 (Local)",
        "provider": "ollama",
        "base_url": "http://localhost:11434"
      }
    ],
    "default_model": "ollama/glm4"
  }
}
```

## Architecture

This extension is designed as a **compatibility layer** that sits alongside OpenHands rather than modifying its core code. This approach ensures:

1. **Upstream Compatibility**: You can pull updates from the OpenHands community repository without conflicts
2. **Easy Maintenance**: Extension code is separate and easy to update
3. **Safe Rollback**: If something breaks, you can disable the extension and use vanilla OpenHands

### Components

```
juristech-openhands-ext/
├── backend/
│   ├── vision_middleware.py    # Image processing with Llava
│   ├── api_proxy.py            # API proxy for request interception
│   └── llm_wrapper.py          # LLM wrapper for vision integration
├── frontend/
│   ├── VisionSettings.tsx      # Vision settings UI component
│   └── ModelsSettings.tsx      # Models settings UI component
├── config/
│   └── extension_config.py     # Configuration management
├── docker/
│   ├── Dockerfile.devin-sandbox
│   ├── docker-compose.yml
│   └── supervisord.conf
└── integrate_openhands.py      # Integration script
```

## Using the Devin.ai Container

To start the development container:

```bash
cd docker
docker-compose up -d
```

Connect via SSH:
```bash
ssh -p 2222 devin@localhost
# Password: devin
```

The container exposes:
- Port 2222: SSH
- Ports 3000-3010: Development servers
- Ports 8000-8010: API servers

## Updating OpenHands

To update OpenHands while keeping the extension:

```bash
cd ~/OpenDevin
git pull origin main
# The extension will continue to work as it doesn't modify core files
```

## Troubleshooting

### Llava not responding
1. Check if Ollama is running: `ollama list`
2. Verify Llava is installed: `ollama pull llava:7b`
3. Test Llava directly: `ollama run llava:7b "describe this image"`

### Extension not loading
1. Check the config file exists: `cat ~/.juristech-openhands/config.json`
2. Verify PYTHONPATH includes the extension directory
3. Check logs for errors

### Images not being processed
1. Verify vision is enabled in config: `"enabled": true`
2. Check Ollama is accessible at the configured URL
3. Ensure image size is under the configured limit

## Contributing

This extension is maintained by JurisTech LLC. For issues or feature requests, please contact the development team.

## License

Proprietary - JurisTech LLC
