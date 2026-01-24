#!/usr/bin/env python3
"""
JurisTech OpenHands Extension - Integration Script
This script integrates the extension with an existing OpenHands installation.
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path


def find_openhands_installation():
    """Find the OpenHands installation directory."""
    # Common locations to check
    possible_paths = [
        Path.home() / "OpenDevin",
        Path.home() / "OpenHands",
        Path("/opt/OpenDevin"),
        Path("/opt/OpenHands"),
        Path.cwd() / "OpenDevin",
        Path.cwd() / "OpenHands",
    ]
    
    for path in possible_paths:
        if path.exists() and (path / "openhands").exists():
            return path
    
    return None


def create_extension_config(openhands_path: Path, config_path: Path):
    """Create the extension configuration file."""
    config = {
        "version": "1.0.0",
        "extension_name": "JurisTech OpenHands Extension",
        "vision": {
            "enabled": True,
            "ollama_base_url": "http://localhost:11434",
            "vision_model": "llava:7b",
            "max_image_size_mb": 10.0,
            "description_max_tokens": 500,
            "auto_process_images": True
        },
        "models": {
            "models": [
                {
                    "name": "ollama/glm4",
                    "display_name": "GLM-4 (Local)",
                    "provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "api_key_env": None,
                    "is_vision_capable": False,
                    "is_coding_model": True,
                    "max_tokens": 4096,
                    "temperature": 0.0
                },
                {
                    "name": "ollama/llava:7b",
                    "display_name": "Llava 7B (Vision)",
                    "provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "api_key_env": None,
                    "is_vision_capable": True,
                    "is_coding_model": False,
                    "max_tokens": 4096,
                    "temperature": 0.0
                },
                {
                    "name": "anthropic/claude-opus-4-5-20251101",
                    "display_name": "Claude Opus 4.5",
                    "provider": "anthropic",
                    "base_url": None,
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "is_vision_capable": False,
                    "is_coding_model": True,
                    "max_tokens": 8192,
                    "temperature": 0.0
                }
            ],
            "default_model": "ollama/glm4"
        },
        "devin_container": {
            "enabled": False,
            "container_name": "juristech-devin-sandbox",
            "image": "ubuntu:22.04",
            "ssh_port": 2222,
            "workspace_path": "/workspace",
            "expose_ports": [3000, 3001, 8000, 8080]
        }
    }
    
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"Created configuration at: {config_path}")
    return config


def patch_openhands_llm(openhands_path: Path, ext_path: Path):
    """
    Create a minimal patch to OpenHands LLM module to support vision processing.
    This creates a wrapper that can be imported instead of modifying core files.
    """
    wrapper_path = ext_path / "backend" / "llm_wrapper.py"
    
    wrapper_code = '''"""
JurisTech OpenHands Extension - LLM Wrapper
Wraps the OpenHands LLM to add vision processing capabilities.
"""

import sys
import os
from pathlib import Path

# Add the extension to the path
ext_path = Path(__file__).parent.parent
sys.path.insert(0, str(ext_path))

from config.extension_config import get_config
from backend.vision_middleware import VisionMiddleware, VisionConfig

# Store the original LLM class
_original_llm = None
_vision_middleware = None


def get_vision_middleware():
    """Get or create the vision middleware instance."""
    global _vision_middleware
    if _vision_middleware is None:
        config = get_config()
        _vision_middleware = VisionMiddleware(
            VisionConfig(
                enabled=config.vision.enabled,
                ollama_base_url=config.vision.ollama_base_url,
                vision_model=config.vision.vision_model,
                max_image_size_mb=config.vision.max_image_size_mb,
                description_max_tokens=config.vision.description_max_tokens
            )
        )
    return _vision_middleware


async def process_images_before_completion(messages):
    """Process any images in messages before sending to the LLM."""
    config = get_config()
    if not config.vision.enabled or not config.vision.auto_process_images:
        return messages
    
    middleware = get_vision_middleware()
    return await middleware.enhance_conversation(messages)


def patch_llm_completion(original_completion):
    """Patch the LLM completion function to add vision processing."""
    import asyncio
    
    async def patched_completion(*args, **kwargs):
        # Process images if present
        if 'messages' in kwargs:
            kwargs['messages'] = await process_images_before_completion(kwargs['messages'])
        
        # Call original completion
        return await original_completion(*args, **kwargs)
    
    return patched_completion
'''
    
    with open(wrapper_path, "w") as f:
        f.write(wrapper_code)
    
    print(f"Created LLM wrapper at: {wrapper_path}")


def create_startup_script(openhands_path: Path, ext_path: Path):
    """Create a startup script that launches OpenHands with the extension."""
    script_path = ext_path / "start_openhands_extended.sh"
    
    script_content = f'''#!/bin/bash
# JurisTech OpenHands Extension - Startup Script
# This script starts OpenHands with the extension enabled.

# Set extension environment variables
export JURISTECH_EXT_CONFIG="{ext_path / 'config' / 'extension_config.json'}"
export JURISTECH_EXT_PATH="{ext_path}"

# Add extension to Python path
export PYTHONPATH="${{PYTHONPATH}}:{ext_path}"

# Change to OpenHands directory
cd "{openhands_path}"

# Start OpenHands
echo "Starting OpenHands with JurisTech Extension..."
echo "Extension config: $JURISTECH_EXT_CONFIG"

# Run OpenHands
make run
'''
    
    with open(script_path, "w") as f:
        f.write(script_content)
    
    os.chmod(script_path, 0o755)
    print(f"Created startup script at: {script_path}")


def create_windows_startup_script(openhands_path: Path, ext_path: Path):
    """Create a Windows startup script."""
    script_path = ext_path / "start_openhands_extended.bat"
    
    script_content = f'''@echo off
REM JurisTech OpenHands Extension - Startup Script (Windows)
REM This script starts OpenHands with the extension enabled.

REM Set extension environment variables
set JURISTECH_EXT_CONFIG={ext_path / 'config' / 'extension_config.json'}
set JURISTECH_EXT_PATH={ext_path}

REM Add extension to Python path
set PYTHONPATH=%PYTHONPATH%;{ext_path}

REM Change to OpenHands directory
cd /d "{openhands_path}"

REM Start OpenHands
echo Starting OpenHands with JurisTech Extension...
echo Extension config: %JURISTECH_EXT_CONFIG%

REM Run OpenHands
make run
'''
    
    with open(script_path, "w") as f:
        f.write(script_content)
    
    print(f"Created Windows startup script at: {script_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Integrate JurisTech Extension with OpenHands"
    )
    parser.add_argument(
        "--openhands-path",
        type=Path,
        help="Path to OpenHands installation"
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        default=Path.home() / ".juristech-openhands" / "config.json",
        help="Path to save extension configuration"
    )
    
    args = parser.parse_args()
    
    # Find OpenHands installation
    openhands_path = args.openhands_path
    if openhands_path is None:
        openhands_path = find_openhands_installation()
    
    if openhands_path is None or not openhands_path.exists():
        print("Error: Could not find OpenHands installation.")
        print("Please specify the path with --openhands-path")
        sys.exit(1)
    
    print(f"Found OpenHands at: {openhands_path}")
    
    # Get extension path
    ext_path = Path(__file__).parent.resolve()
    print(f"Extension path: {ext_path}")
    
    # Create configuration
    create_extension_config(openhands_path, args.config_path)
    
    # Create LLM wrapper
    patch_openhands_llm(openhands_path, ext_path)
    
    # Create startup scripts
    create_startup_script(openhands_path, ext_path)
    create_windows_startup_script(openhands_path, ext_path)
    
    print("\n" + "="*60)
    print("JurisTech OpenHands Extension installed successfully!")
    print("="*60)
    print(f"\nConfiguration file: {args.config_path}")
    print(f"\nTo start OpenHands with the extension:")
    print(f"  Linux/Mac: {ext_path}/start_openhands_extended.sh")
    print(f"  Windows:   {ext_path}\\start_openhands_extended.bat")
    print("\nFeatures enabled:")
    print("  - Image processing with Llava 7B")
    print("  - Multiple coding model support")
    print("  - Devin.ai development container (optional)")
    print("\nEdit the configuration file to customize settings.")


if __name__ == "__main__":
    main()
