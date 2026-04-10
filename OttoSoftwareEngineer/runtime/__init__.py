"""Runtime module for OttoSoftwareEngineer.

Provides the sandboxed execution environment where the agent runs code,
browses the web, and edits files. Each session gets its own isolated
sandbox (Docker container, Kubernetes pod, or local process).

Mirrors the Devin.ai architecture where each session runs in its own
isolated VM with shell, browser, and code editor.
"""

from OttoSoftwareEngineer.runtime.base import Runtime, RuntimeStatus
from OttoSoftwareEngineer.runtime.impl.docker_runtime import DockerRuntime
from OttoSoftwareEngineer.runtime.impl.local_runtime import LocalRuntime

__all__ = [
    "Runtime",
    "RuntimeStatus",
    "DockerRuntime",
    "LocalRuntime",
]
