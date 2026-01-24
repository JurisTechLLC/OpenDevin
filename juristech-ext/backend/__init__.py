"""
JurisTech OpenHands Extension - Backend Package
"""

from .vision_middleware import (
    VisionMiddleware,
    VisionConfig,
    get_vision_middleware,
    process_images_in_request
)

from .api_proxy import (
    OpenHandsAPIProxy,
    ProxyConfig,
    create_proxy_app
)

__all__ = [
    'VisionMiddleware',
    'VisionConfig',
    'get_vision_middleware',
    'process_images_in_request',
    'OpenHandsAPIProxy',
    'ProxyConfig',
    'create_proxy_app'
]
