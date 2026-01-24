"""
JurisTech OpenHands UI Wrapper - Backend Proxy

This FastAPI backend acts as a proxy between the JurisTech custom UI and OpenHands.
It intercepts requests, applies extension features (Supervisor AI, RAG, vision processing),
and forwards them to the OpenHands backend.
"""

import os
import json
import httpx
from typing import Optional, Any, Dict, List
from fastapi import FastAPI, Request, Response, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenHands backend URL (running in background)
OPENHANDS_URL = os.getenv("OPENHANDS_URL", "http://127.0.0.1:3001")
OPENHANDS_API_URL = f"{OPENHANDS_URL}/api"

app = FastAPI(
    title="JurisTech OpenHands Wrapper",
    description="Custom UI wrapper for OpenHands with extension features",
    version="1.0.0"
)

# CORS configuration - allow our frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTP client for proxying requests
http_client = httpx.AsyncClient(timeout=60.0)


class SupervisorConfig(BaseModel):
    """Configuration for a supervisor AI"""
    id: str
    name: str
    enabled: bool = True
    system_prompt: str = ""
    model: str = "claude-3-opus"
    auto_send: bool = False


class ExtensionSettings(BaseModel):
    """Extension settings"""
    vision_enabled: bool = True
    rag_enabled: bool = True
    supervisors: List[SupervisorConfig] = []
    auto_send_enabled: bool = False


# In-memory storage for extension settings (will be persisted to file)
extension_settings = ExtensionSettings()
SETTINGS_FILE = os.path.expanduser("~/.juristech-openhands/wrapper-settings.json")


def load_settings():
    """Load settings from file"""
    global extension_settings
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
                extension_settings = ExtensionSettings(**data)
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")


def save_settings():
    """Save settings to file"""
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(extension_settings.model_dump(), f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")


# Load settings on startup
load_settings()


# ============== Extension API Endpoints ==============

@app.get("/extension/settings")
async def get_extension_settings():
    """Get current extension settings"""
    return extension_settings


@app.post("/extension/settings")
async def update_extension_settings(settings: ExtensionSettings):
    """Update extension settings"""
    global extension_settings
    extension_settings = settings
    save_settings()
    return {"status": "ok", "settings": extension_settings}


@app.get("/extension/supervisors")
async def get_supervisors():
    """Get list of configured supervisors"""
    return {"supervisors": extension_settings.supervisors}


@app.post("/extension/supervisors")
async def add_supervisor(supervisor: SupervisorConfig):
    """Add a new supervisor"""
    extension_settings.supervisors.append(supervisor)
    save_settings()
    return {"status": "ok", "supervisor": supervisor}


@app.delete("/extension/supervisors/{supervisor_id}")
async def delete_supervisor(supervisor_id: str):
    """Delete a supervisor"""
    extension_settings.supervisors = [
        s for s in extension_settings.supervisors if s.id != supervisor_id
    ]
    save_settings()
    return {"status": "ok"}


@app.get("/extension/health")
async def extension_health():
    """Health check for extension services"""
    return {
        "status": "healthy",
        "openhands_url": OPENHANDS_URL,
        "vision_enabled": extension_settings.vision_enabled,
        "rag_enabled": extension_settings.rag_enabled,
        "supervisors_count": len(extension_settings.supervisors)
    }


# ============== Proxy Endpoints ==============

# Headers that should not be forwarded from upstream response
EXCLUDED_RESPONSE_HEADERS = {
    'transfer-encoding',
    'content-encoding',
    'content-length',
    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'te',
    'trailers',
    'upgrade',
}


async def proxy_request(request: Request, path: str) -> Response:
    """Proxy a request to OpenHands backend"""
    url = f"{OPENHANDS_URL}/{path}"

    # Get request body if present
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        body = await request.body()

    # Forward headers (excluding host and connection-related headers)
    headers = {}
    for key, value in request.headers.items():
        key_lower = key.lower()
        if key_lower not in {'host', 'connection', 'keep-alive', 'transfer-encoding', 'content-length'}:
            # Sanitize header values - remove any non-ASCII characters
            try:
                value.encode('latin-1')
                headers[key] = value
            except UnicodeEncodeError:
                logger.warning(f"Skipping header {key} with non-ASCII value")

    try:
        response = await http_client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            params=request.query_params
        )

        # Filter response headers - only forward safe headers with valid values
        response_headers = {}
        for key, value in response.headers.items():
            key_lower = key.lower()
            if key_lower not in EXCLUDED_RESPONSE_HEADERS:
                # Sanitize header values - ensure they're valid HTTP header values
                try:
                    value.encode('latin-1')
                    response_headers[key] = value
                except (UnicodeEncodeError, UnicodeDecodeError):
                    logger.warning(f"Skipping response header {key} with invalid value")

        # Get content-type, defaulting to application/octet-stream
        content_type = response.headers.get("content-type", "application/octet-stream")
        # Extract just the media type without parameters if it causes issues
        if content_type:
            try:
                content_type.encode('latin-1')
            except (UnicodeEncodeError, UnicodeDecodeError):
                content_type = "application/octet-stream"

        # Return the response
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers,
            media_type=content_type
        )
    except httpx.RequestError as e:
        logger.error(f"Proxy error: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to OpenHands: {str(e)}")


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_api(request: Request, path: str):
    """Proxy all /api/* requests to OpenHands"""
    return await proxy_request(request, f"api/{path}")


@app.api_route("/feedback/{path:path}", methods=["GET", "POST"])
async def proxy_feedback(request: Request, path: str):
    """Proxy feedback requests to OpenHands"""
    return await proxy_request(request, f"feedback/{path}")


@app.api_route("/oauth/{path:path}", methods=["GET", "POST"])
async def proxy_oauth(request: Request, path: str):
    """Proxy OAuth requests to OpenHands"""
    return await proxy_request(request, f"oauth/{path}")


# ============== WebSocket Proxy ==============

@app.websocket("/ws/{path:path}")
async def websocket_proxy(websocket: WebSocket, path: str):
    """Proxy WebSocket connections to OpenHands"""
    await websocket.accept()
    
    # Connect to OpenHands WebSocket
    openhands_ws_url = f"ws://127.0.0.1:3001/ws/{path}"
    
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", openhands_ws_url) as response:
                # This is a simplified WebSocket proxy
                # For full WebSocket support, we'd need a proper WebSocket client
                pass
    except Exception as e:
        logger.error(f"WebSocket proxy error: {e}")
    finally:
        await websocket.close()


# ============== Static File Proxy ==============

@app.get("/{path:path}")
async def proxy_static(request: Request, path: str):
    """Proxy static files and other requests to OpenHands"""
    if path.startswith("extension/"):
        raise HTTPException(status_code=404, detail="Not found")
    return await proxy_request(request, path)


@app.get("/")
async def proxy_root(request: Request):
    """Proxy root request to OpenHands"""
    return await proxy_request(request, "")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3002)
