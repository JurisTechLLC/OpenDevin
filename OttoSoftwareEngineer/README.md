# OttoSoftwareEngineer

An autonomous AI software engineer platform that mirrors the [Devin.ai](https://devin.ai) architecture. Otto provides a complete agent-driven development environment with planning, code execution, testing, debugging, and PR creation capabilities.

## Architecture Overview

```
OttoSoftwareEngineer/
├── core/                    # Core infrastructure
│   ├── events/              # Event-driven communication system
│   │   ├── event.py         # Base Event class and EventSource enum
│   │   ├── actions.py       # Action types (shell, editor, browser, etc.)
│   │   ├── observations.py  # Observation types (command output, errors, etc.)
│   │   └── stream.py        # EventStream pub/sub bus
│   ├── schema/              # Type definitions and enumerations
│   │   ├── agent.py         # AgentState lifecycle enum
│   │   ├── action.py        # ActionType enum
│   │   └── observation.py   # ObservationType enum
│   ├── exceptions.py        # Custom exception hierarchy
│   └── logger.py            # Structured logging
│
├── config/                  # Configuration system
│   ├── otto_config.py       # Master config (TOML, env vars, runtime)
│   ├── llm_config.py        # LLM provider settings
│   ├── sandbox_config.py    # Sandbox environment settings
│   └── agent_config.py      # Agent behavior settings
│
├── controller/              # Agent orchestration engine
│   ├── agent_controller.py  # Core execution loop and state machine
│   ├── state.py             # Session state, metrics, plan tracking
│   ├── stuck_detector.py    # Loop detection and recovery
│   └── planner.py           # Interactive planning (Devin 2.0)
│
├── runtime/                 # Sandboxed execution environment
│   ├── base.py              # Abstract Runtime interface
│   ├── impl/
│   │   ├── docker_runtime.py   # Docker container sandbox
│   │   └── local_runtime.py    # Local development runtime
│   └── tools/               # Sandbox tool interfaces
│       ├── shell.py         # Bash shell execution
│       ├── browser.py       # Chrome CDP web browsing
│       ├── editor.py        # File read/write/edit
│       └── search.py        # Codebase search (ripgrep, glob)
│
├── server/                  # Communication layer
│   ├── agent_session.py     # Single session lifecycle
│   └── session_manager.py   # Multi-session management
│
├── llm/                     # LLM integration layer
│   ├── llm.py               # Unified provider interface with retry
│   ├── metrics.py           # Cost and token tracking
│   └── model_features.py    # Model capability detection
│
├── knowledge/               # Knowledge management system
│   ├── playbook.py          # Reusable task procedures
│   ├── knowledge_store.py   # Persistent information store
│   ├── skill.py             # Repository-loaded skills (SKILL.md)
│   └── microagent.py        # Repo-specific agent instructions
│
└── agenthub/                # Agent implementations
    ├── base_agent.py        # Abstract agent interface
    └── codeact_agent.py     # Primary ReAct agent
```

## Core Components

### 1. Event System (`core/events/`)

The backbone of Otto's architecture. All communication between components flows through the **EventStream** — a thread-safe pub/sub bus that:

- Assigns monotonically increasing IDs to events
- Redacts secrets from event content
- Persists events for session replay and audit
- Notifies subscribers (controller, runtime, server) in real-time

**Events** are either **Actions** (commands from user/agent) or **Observations** (feedback from environment).

### 2. Agent Controller (`controller/`)

The central orchestration engine driving the agent execution loop:

```
INIT → PLANNING → RUNNING → FINISHED/ERROR/STOPPED
         ↑            ↓
         └── AWAITING_USER_INPUT
```

**Key features:**
- **State machine** with well-defined transitions
- **Interactive planning** (Devin 2.0): agent scans codebase and proposes a plan before executing
- **Stuck detection**: identifies repeated actions and loops, attempts recovery
- **Delegation**: spawn child agent controllers for parallel sub-tasks (managed Devins)
- **Budget enforcement**: tracks LLM costs and iteration counts

### 3. Sandboxed Runtime (`runtime/`)

Each session runs in an isolated execution environment providing:

| Tool | Description |
|------|-------------|
| **Shell** | Bash command execution (builds, tests, git, packages) |
| **Browser** | Chrome DevTools Protocol for web research and testing |
| **Editor** | File read, write, and targeted find-and-replace editing |
| **Search** | Codebase search via ripgrep (content) and glob (files) |
| **IPython** | Python code execution in a Jupyter kernel |

**Implementations:**
- `DockerRuntime`: Production container-based isolation (mirrors Devin.ai VMs)
- `LocalRuntime`: Development/testing without containers

### 4. Communication Layer (`server/`)

- **AgentSession**: Owns the event stream, controller, and runtime for one conversation
- **SessionManager**: Manages multiple concurrent sessions with limits and quotas
- Real-time event streaming to frontend via EventStream subscriptions

### 5. LLM Integration (`llm/`)

Unified interface to multiple providers:
- OpenAI (GPT-4o, GPT-4 Turbo)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Opus)
- Google (Gemini Pro, Gemini 2.0 Flash)
- AWS Bedrock, local models via Ollama

**Features:** automatic retry with exponential backoff, cost tracking, token counting, model capability detection, prompt caching support.

### 6. Knowledge System (`knowledge/`)

Persistent knowledge management mirroring Devin.ai's features:

- **Playbooks**: Reusable step-by-step task procedures with trigger patterns
- **Knowledge Notes**: Persistent information store (CRUD)
- **Skills**: Step-by-step instructions loaded from `SKILL.md` files in repos
- **Microagents**: Repository-specific agent instructions (`AGENTS.md`, `.agents/`)

### 7. Agent Hub (`agenthub/`)

- **BaseAgent**: Abstract interface — agents receive state and return actions
- **CodeActAgent**: Primary implementation using ReAct (Reasoning + Acting) pattern
  - Formats history as LLM messages
  - Uses function calling for tool interaction
  - Parses LLM responses into typed actions

## Design Patterns

- **Event-Driven Architecture**: All components communicate via the EventStream
- **Abstract Base Classes**: Runtime, Agent, and Tool interfaces allow multiple implementations
- **State Machine**: AgentController manages well-defined lifecycle transitions
- **Pub/Sub**: EventStream subscribers enable loose coupling
- **Strategy Pattern**: Pluggable agents, runtimes, and LLM providers
- **Dataclass Models**: Type-safe data structures throughout

## Configuration

Otto supports three configuration sources (in priority order):

1. **Environment variables**: `OTTO_LLM_MODEL`, `OTTO_SANDBOX_TIMEOUT`, etc.
2. **TOML config file**: `OttoConfig.from_toml("config.toml")`
3. **Runtime defaults**: Sensible defaults for all settings

Example:
```python
from OttoSoftwareEngineer.config import OttoConfig

config = OttoConfig.from_env()
config.llm.model = "claude-3-5-sonnet"
config.sandbox.runtime_type = "docker"
config.agent.max_iterations = 200
```

## Quick Start

```python
from OttoSoftwareEngineer.agenthub import CodeActAgent
from OttoSoftwareEngineer.config import OttoConfig, LLMConfig
from OttoSoftwareEngineer.core.events.stream import EventStream
from OttoSoftwareEngineer.controller import AgentController
from OttoSoftwareEngineer.llm import LLM

# Configure
config = OttoConfig.from_env()
llm = LLM(config.llm)

# Create components
event_stream = EventStream(sid="session-1")
agent = CodeActAgent(llm=llm, config=config.agent)
controller = AgentController(
    agent=agent,
    event_stream=event_stream,
    max_iterations=config.agent.max_iterations,
)
```
