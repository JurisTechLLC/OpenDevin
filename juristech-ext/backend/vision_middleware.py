"""
JurisTech OpenHands Extension - Vision Middleware
Intercepts image attachments and processes them with Llava for image understanding.
"""

import base64
import httpx
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class VisionConfig:
    """Configuration for vision processing."""
    enabled: bool = True
    ollama_base_url: str = "http://localhost:11434"
    vision_model: str = "llava:7b"
    max_image_size_mb: float = 10.0
    description_max_tokens: int = 500


class VisionMiddleware:
    """
    Middleware that processes images attached to messages using Llava.
    Injects image descriptions into the conversation context.
    """
    
    def __init__(self, config: Optional[VisionConfig] = None):
        self.config = config or VisionConfig()
        self._client = httpx.AsyncClient(timeout=120.0)
    
    async def process_image(self, image_data: bytes, mime_type: str = "image/jpeg") -> str:
        """
        Process an image using Llava and return a description.
        
        Args:
            image_data: Raw image bytes
            mime_type: MIME type of the image
            
        Returns:
            A text description of the image
        """
        if not self.config.enabled:
            return ""
        
        # Encode image to base64
        image_b64 = base64.b64encode(image_data).decode("utf-8")
        
        # Prepare the request for Ollama
        payload = {
            "model": self.config.vision_model,
            "prompt": "Describe this image in detail. Focus on any text, code, diagrams, UI elements, or technical content visible. Be specific and thorough.",
            "images": [image_b64],
            "stream": False,
            "options": {
                "num_predict": self.config.description_max_tokens
            }
        }
        
        try:
            response = await self._client.post(
                f"{self.config.ollama_base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except Exception as e:
            print(f"Vision processing error: {e}")
            return f"[Image processing failed: {str(e)}]"
    
    async def process_message_images(
        self, 
        message_content: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process all images in a message and inject descriptions.
        
        Args:
            message_content: List of content blocks (text, image, etc.)
            
        Returns:
            Modified content list with image descriptions injected
        """
        if not self.config.enabled:
            return message_content
        
        processed_content = []
        
        for block in message_content:
            if block.get("type") == "image":
                # Extract image data
                image_source = block.get("source", {})
                if image_source.get("type") == "base64":
                    image_data = base64.b64decode(image_source.get("data", ""))
                    mime_type = image_source.get("media_type", "image/jpeg")
                    
                    # Get description from Llava
                    description = await self.process_image(image_data, mime_type)
                    
                    # Add description as a text block before the image
                    if description:
                        processed_content.append({
                            "type": "text",
                            "text": f"[Image Analysis by Llava]\n{description}\n[End Image Analysis]"
                        })
                
                # Keep the original image block
                processed_content.append(block)
            else:
                processed_content.append(block)
        
        return processed_content
    
    async def enhance_conversation(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process all messages in a conversation and enhance with image descriptions.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Enhanced messages with image descriptions
        """
        if not self.config.enabled:
            return messages
        
        enhanced_messages = []
        
        for message in messages:
            content = message.get("content", [])
            
            # Handle string content (no images)
            if isinstance(content, str):
                enhanced_messages.append(message)
                continue
            
            # Handle list content (may contain images)
            if isinstance(content, list):
                enhanced_content = await self.process_message_images(content)
                enhanced_messages.append({
                    **message,
                    "content": enhanced_content
                })
            else:
                enhanced_messages.append(message)
        
        return enhanced_messages
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()


# Singleton instance for easy access
_vision_middleware: Optional[VisionMiddleware] = None


def get_vision_middleware(config: Optional[VisionConfig] = None) -> VisionMiddleware:
    """Get or create the vision middleware singleton."""
    global _vision_middleware
    if _vision_middleware is None:
        _vision_middleware = VisionMiddleware(config)
    return _vision_middleware


async def process_images_in_request(
    request_data: Dict[str, Any],
    config: Optional[VisionConfig] = None
) -> Dict[str, Any]:
    """
    Convenience function to process images in an API request.
    
    Args:
        request_data: The original API request data
        config: Optional vision configuration
        
    Returns:
        Modified request data with image descriptions
    """
    middleware = get_vision_middleware(config)
    
    messages = request_data.get("messages", [])
    enhanced_messages = await middleware.enhance_conversation(messages)
    
    return {
        **request_data,
        "messages": enhanced_messages
    }
