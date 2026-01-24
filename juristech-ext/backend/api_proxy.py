"""
JurisTech OpenHands Extension - API Proxy
Intercepts OpenHands API requests and adds extension functionality.
"""

import asyncio
import json
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass
import httpx

from .vision_middleware import VisionMiddleware, VisionConfig, process_images_in_request
from ..config.extension_config import get_config, ExtensionConfig


@dataclass
class ProxyConfig:
    """Configuration for the API proxy."""
    openhands_backend_url: str = "http://127.0.0.1:3000"
    listen_port: int = 3002
    enable_vision_processing: bool = True
    enable_model_routing: bool = True


class OpenHandsAPIProxy:
    """
    Proxy that sits between the OpenHands frontend and backend.
    Adds extension functionality like vision processing.
    """
    
    def __init__(self, config: Optional[ProxyConfig] = None):
        self.config = config or ProxyConfig()
        self.ext_config = get_config()
        self._client = httpx.AsyncClient(timeout=300.0)
        self._vision_middleware = VisionMiddleware(
            VisionConfig(
                enabled=self.ext_config.vision.enabled,
                ollama_base_url=self.ext_config.vision.ollama_base_url,
                vision_model=self.ext_config.vision.vision_model,
                max_image_size_mb=self.ext_config.vision.max_image_size_mb,
                description_max_tokens=self.ext_config.vision.description_max_tokens
            )
        )
    
    async def process_chat_request(
        self,
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a chat/completion request, adding vision processing if needed.
        
        Args:
            request_data: The original request data
            
        Returns:
            Modified request data with vision enhancements
        """
        # Check if vision processing is enabled
        if not self.ext_config.vision.enabled:
            return request_data
        
        # Check if there are any images in the messages
        messages = request_data.get("messages", [])
        has_images = any(
            isinstance(msg.get("content"), list) and
            any(block.get("type") == "image" for block in msg.get("content", []))
            for msg in messages
        )
        
        if has_images and self.ext_config.vision.auto_process_images:
            # Process images with Llava
            enhanced_messages = await self._vision_middleware.enhance_conversation(messages)
            request_data = {**request_data, "messages": enhanced_messages}
        
        return request_data
    
    async def route_to_model(
        self,
        request_data: Dict[str, Any],
        model_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Route the request to the appropriate model based on configuration.
        
        Args:
            request_data: The request data
            model_override: Optional model to use instead of default
            
        Returns:
            Modified request data with correct model routing
        """
        if not self.config.enable_model_routing:
            return request_data
        
        # Get the target model
        target_model = model_override or request_data.get("model")
        
        if not target_model:
            return request_data
        
        # Find the model configuration
        model_config = None
        for m in self.ext_config.models.models:
            if m.name == target_model:
                model_config = m
                break
        
        if model_config:
            # Update request with model-specific settings
            if model_config.base_url:
                request_data["base_url"] = model_config.base_url
            if model_config.max_tokens:
                request_data["max_tokens"] = model_config.max_tokens
        
        return request_data
    
    async def forward_request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        """
        Forward a request to the OpenHands backend.
        
        Args:
            method: HTTP method
            path: Request path
            data: Request body data
            headers: Request headers
            
        Returns:
            Response from the backend
        """
        url = f"{self.config.openhands_backend_url}{path}"
        
        # Process the request if it's a chat/completion endpoint
        if data and path in ["/api/chat", "/api/completions", "/v0/chat"]:
            data = await self.process_chat_request(data)
            data = await self.route_to_model(data)
        
        response = await self._client.request(
            method=method,
            url=url,
            json=data,
            headers=headers
        )
        
        return response
    
    async def close(self):
        """Close the proxy and cleanup resources."""
        await self._client.aclose()
        await self._vision_middleware.close()


# FastAPI app for the proxy server
def create_proxy_app():
    """Create a FastAPI app for the proxy server."""
    try:
        from fastapi import FastAPI, Request, Response
        from fastapi.responses import StreamingResponse
    except ImportError:
        print("FastAPI not installed. Install with: pip install fastapi uvicorn")
        return None
    
    app = FastAPI(
        title="JurisTech OpenHands Extension Proxy",
        description="Proxy server that adds vision processing and model routing to OpenHands",
        version="1.0.0"
    )
    
    proxy = OpenHandsAPIProxy()
    
    @app.on_event("shutdown")
    async def shutdown():
        await proxy.close()
    
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_request(request: Request, path: str):
        """Proxy all requests to the OpenHands backend."""
        method = request.method
        
        # Get request body if present
        data = None
        if method in ["POST", "PUT", "PATCH"]:
            try:
                data = await request.json()
            except:
                pass
        
        # Get headers (excluding host)
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ["host", "content-length"]
        }
        
        # Forward the request
        response = await proxy.forward_request(
            method=method,
            path=f"/{path}",
            data=data,
            headers=headers
        )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
    
    return app


if __name__ == "__main__":
    import uvicorn
    
    app = create_proxy_app()
    if app:
        uvicorn.run(app, host="127.0.0.1", port=3002)
