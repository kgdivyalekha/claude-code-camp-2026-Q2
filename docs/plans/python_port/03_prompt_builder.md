# Python Port: Boukensha Prompt Builder (03_prompt_builder)

**Status**: Planning — This document defines the port plan for `week1_baseline/ruby/03_prompt_builder/` to Python.

Extend the tool registry (02_the_registry) with a Prompt Builder that serializes `Context` into the exact
API payload format each LLM provider expects. The Prompt Builder delegates to a backend strategy, providing
a unified interface for generating API-ready payloads, headers, and URLs without making any network calls.

This step introduces backend strategies for Anthropic, OpenAI, Gemini, Ollama, and Ollama Cloud, each
implementing a shared contract for message/tool serialization, model metadata, and cost estimation.
Support for `UnsupportedModelError` is added alongside the existing `UnknownToolError`.

## Decisions

These decisions build on 00_config, 01_struct_skeleton, and 02_the_registry:

- **Strategy pattern for backends**: The `PromptBuilder` holds a reference to a `Context` and a `Backend`
  instance. It delegates `to_messages()`, `to_tools()`, `to_api_payload()`, `headers()`, and `url()` to the
  backend. This keeps backends swappable without changing the builder interface.

- **Backend base class**: `BackendBase` defines shared model validation, model metadata lookup, and cost
  estimation. Each concrete backend registers its `MODELS` dict. The base validates the model at init time.

- **Tasks move to this step**: The `Base` and `Player` task classes are formally part of this step, providing
  provider/model resolution and prompt override logic. They were implicitly present in prior steps but now
  own the full contract (`.provider()`, `.model()`, `.system_prompt()`, `.prompt()`).

- **UnsupportedModelError**: A new custom exception for when a backend is initialized with an unsupported
  model. Rejected models raise a descriptive error listing supported models.

- **No HTTP calls**: PromptBuilder prepares payloads only. Making API calls is a separate concern for a
  later step (the agent loop).

- **System prompt resolution**: The `system_prompt()` method checks for user overrides before falling back
  to the default prompt. Anthropic and Gemini pass it as a top-level field; Ollama and OpenAI embed it in
  the messages array.

- **Cost estimation is informational**: Backends provide `estimate_cost()` returning floats for token-based
  models or `None` for usage-based models (Ollama Cloud). These are static tutorial prices.

- **Ruby blocks → Python lambdas/functions**: The block pattern from the registry carries through unchanged.

## Target Python Structure (as planned)

```
week1_baseline/python/03_prompt_builder/
├── src/
│   └── boukensha/
│       ├── __init__.py              # Package exports (all public classes)
│       ├── tool.py                  # Tool dataclass (copy from 02_the_registry)
│       ├── message.py               # Message dataclass (copy from 02_the_registry)
│       ├── context.py               # Context class (copy from 02_the_registry)
│       ├── errors.py                # UnknownToolError, UnsupportedModelError
│       ├── registry.py              # Registry class (copy from 02_the_registry)
│       ├── prompt_builder.py        # PromptBuilder class (NEW)
│       ├── tasks/
│       │   ├── __init__.py          # Re-exports Base and Player
│       │   ├── base.py              # Base task class with provider/model/prompt logic (NEW)
│       │   └── player.py            # Player task class (NEW)
│       └── backends/
│           ├── __init__.py          # Backend exports
│           ├── base.py              # BackendBase - shared model validation/estimation (NEW)
│           ├── anthropic.py         # Anthropic backend (NEW)
│           ├── gemini.py            # Gemini backend (NEW)
│           ├── ollama.py            # Ollama backend (NEW)
│           ├── ollama_cloud.py      # Ollama Cloud backend (NEW)
│           └── openai.py            # OpenAI backend (NEW)
├── examples/
│   └── example.py                   # Usage example / smoke test
├── prompts/
│   └── system.md                    # Default system prompt (copy from Ruby)
├── pyproject.toml                   # Package config
└── README.md                        # Usage documentation
```

### Already Ported (available from 02_the_registry)
- **tool.py**: Tool dataclass
- **message.py**: Message dataclass
- **context.py**: Context class
- **errors.py**: UnknownToolError (will add UnsupportedModelError)
- **registry.py**: Registry class

### New in This Step
- **errors.py**: Add UnsupportedModelError exception
- **tasks/base.py**: Base task class with provider/model resolution and prompt reading
- **tasks/player.py**: Concrete player task
- **prompt_builder.py**: PromptBuilder class
- **backends/__init__.py**: Backend package exports
- **backends/base.py**: BackendBase with model validation and cost estimation
- **backends/anthropic.py**: Anthropic API serialization
- **backends/gemini.py**: Gemini API serialization
- **backends/ollama.py**: Ollama API serialization
- **backends/ollama_cloud.py**: Ollama Cloud API serialization
- **backends/openai.py**: OpenAI API serialization
- **prompts/system.md**: Default system prompt

## Quick Setup

### 1. Ensure prior steps are ported and installed
```bash
source venv/bin/activate
pip install -e week1_baseline/python/00_config
pip install -e week1_baseline/python/01_struct_skeleton
pip install -e week1_baseline/python/02_the_registry
```

### 2. Install 03_prompt_builder
```bash
pip install -e week1_baseline/python/03_prompt_builder
```

### 3. Run it
```bash
./week1_baseline/bin/python/03_prompt_builder
```

---

## Porting Plan: File by File

### 1. Tasks: Base (`lib/boukensha/tasks/base.rb` → `src/boukensha/tasks/base.py`)

**Ruby**:
```ruby
module Boukensha
  module Tasks
    class Base
      def self.task_name
        raise NotImplementedError, "#{self} must define .task_name"
      end

      def self.provider(settings)
        fetch(settings, :provider) || raise(ArgumentError, "tasks.#{task_name}.provider is required in settings.yml")
      end

      def self.model(settings)
        fetch(settings, :model) || raise(ArgumentError, "tasks.#{task_name}.model is required in settings.yml")
      end

      def self.prompt_override?(settings, prompt = :system)
        node = fetch(settings, :prompt_override)
        return false unless node.is_a?(Hash)
        (node[prompt.to_s] || node[prompt.to_sym]) == true
      end

      def self.prompt(settings, name=:system, user_prompts_dir: nil, default_prompts_dir: nil)
        if prompt_override?(settings, name) && (text = read_user_prompt(name, user_prompts_dir: user_prompts_dir))
          return text
        end
        read_default_prompt(name, default_prompts_dir: default_prompts_dir)
      end

      def self.system_prompt(settings, user_prompts_dir: nil, default_prompts_dir: nil)
        prompt(settings, :system, user_prompts_dir: user_prompts_dir, default_prompts_dir: default_prompts_dir)
      end

      class << self
        private
        def fetch(settings, key)
          settings[key.to_s] || settings[key.to_sym]
        end
        def read_user_prompt(prompt_name, user_prompts_dir: nil)
          return nil unless user_prompts_dir
          read_file(File.join(user_prompts_dir, task_name, "#{prompt_name}.md"))
        end
        def read_default_prompt(prompt_name, default_prompts_dir: nil)
          return nil unless default_prompts_dir
          read_file(File.join(default_prompts_dir, "#{prompt_name}.md"))
        end
        def read_file(path)
          File.exist?(path) ? File.read(path).strip : nil
        end
      end
    end
  end
end
```

**Python**:
```python
import os
from typing import Any, Dict, Optional


class Base:
    """Base class for task configuration.
    
    Provides provider/model resolution and prompt file reading.
    Subclasses must set task_name.
    """
    task_name: str = ""

    @classmethod
    def provider(cls, settings: Dict[str, Any]) -> str:
        value = cls._fetch(settings, "provider")
        if not value:
            raise ValueError(
                f"tasks.{cls.task_name}.provider is required in settings.yml"
            )
        return value

    @classmethod
    def model(cls, settings: Dict[str, Any]) -> str:
        value = cls._fetch(settings, "model")
        if not value:
            raise ValueError(
                f"tasks.{cls.task_name}.model is required in settings.yml"
            )
        return value

    @classmethod
    def prompt_override(cls, settings: Dict[str, Any], prompt: str = "system") -> bool:
        node = cls._fetch(settings, "prompt_override")
        if not isinstance(node, dict):
            return False
        return node.get(prompt, False) is True

    @classmethod
    def prompt(
        cls,
        settings: Dict[str, Any],
        name: str = "system",
        user_prompts_dir: Optional[str] = None,
        default_prompts_dir: Optional[str] = None,
    ) -> Optional[str]:
        if cls.prompt_override(settings, name):
            text = cls._read_user_prompt(name, user_prompts_dir=user_prompts_dir)
            if text is not None:
                return text
        return cls._read_default_prompt(name, default_prompts_dir=default_prompts_dir)

    @classmethod
    def system_prompt(
        cls,
        settings: Dict[str, Any],
        user_prompts_dir: Optional[str] = None,
        default_prompts_dir: Optional[str] = None,
    ) -> Optional[str]:
        return cls.prompt(
            settings, "system",
            user_prompts_dir=user_prompts_dir,
            default_prompts_dir=default_prompts_dir,
        )

    @classmethod
    def _fetch(cls, settings: Dict[str, Any], key: str) -> Any:
        """Fetch a key from settings, checking both string and underscore forms."""
        return settings.get(key) or settings.get(key)

    @classmethod
    def _read_user_prompt(
        cls, prompt_name: str, user_prompts_dir: Optional[str] = None
    ) -> Optional[str]:
        if not user_prompts_dir:
            return None
        path = os.path.join(user_prompts_dir, cls.task_name, f"{prompt_name}.md")
        return cls._read_file(path)

    @classmethod
    def _read_default_prompt(
        cls, prompt_name: str, default_prompts_dir: Optional[str] = None
    ) -> Optional[str]:
        if not default_prompts_dir:
            return None
        path = os.path.join(default_prompts_dir, f"{prompt_name}.md")
        return cls._read_file(path)

    @classmethod
    def _read_file(cls, path: str) -> Optional[str]:
        if os.path.isfile(path):
            with open(path, "r") as f:
                return f.read().strip()
        return None
```

**Key translation**:
- `class << self; private` → `@classmethod` with leading underscore convention
- Ruby symbols → Python strings for settings keys
- `raise(ArgumentError)` → `raise ValueError`
- `File.join` → `os.path.join`
- `File.exist?` → `os.path.isfile`
- `File.read(path).strip` → `open(path).read().strip`

---

### 2. Tasks: Player (`lib/boukensha/tasks/player.rb` → `src/boukensha/tasks/player.py`)

**Ruby**:
```ruby
module Boukensha
  module Tasks
    class Player < Base
      def self.task_name = "player"
    end
  end
end
```

**Python**:
```python
from .base import Base


class Player(Base):
    task_name = "player"
```

---

### 3. UnsupportedModelError (`lib/boukensha/errors.rb` → `src/boukensha/errors.py`)

**Ruby**:
```ruby
module Boukensha
  class UnknownToolError < StandardError; end
  class UnsupportedModelError < StandardError; end
end
```

**Python** (add to existing errors.py):
```python
class UnknownToolError(Exception):
    """Raised when dispatch() is called with an unknown tool name."""
    pass


class UnsupportedModelError(Exception):
    """Raised when a backend is initialized with an unsupported model."""
    pass
```

---

### 4. Backend Base (`lib/boukensha/backends/base.rb` → `src/boukensha/backends/base.py`)

**Ruby**:
```ruby
module Boukensha
  module Backends
    class Base
      attr_reader :model

      def self.models
        const_get(:MODELS)
      rescue NameError
        raise NotImplementedError, "#{self} must define MODELS"
      end

      def self.model_info(model)
        models[model.to_s]
      end

      def self.validate_model!(model)
        model = model.to_s
        return model if model_info(model)
        supported = models.keys.sort.join(", ")
        raise UnsupportedModelError, "#{name} does not support model #{model.inspect}. Supported models: #{supported}"
      end

      def model_info
        @model_info
      end

      def context_window
        model_info.fetch(:context_window)
      end

      def input_token_cost_per_million
        model_info.fetch(:cost_per_million).fetch(:input)
      end

      def output_token_cost_per_million
        model_info.fetch(:cost_per_million).fetch(:output)
      end

      def usage_unit
        model_info.fetch(:usage_unit)
      end

      def usage_level
        model_info[:usage_level]
      end

      def estimate_cost(input_tokens:, output_tokens:)
        return nil unless input_token_cost_per_million && output_token_cost_per_million
        ((input_tokens * input_token_cost_per_million) +
          (output_tokens * output_token_cost_per_million)) / 1_000_000.0
      end

      private

      def configure_model(model)
        @model = self.class.validate_model!(model)
        @model_info = self.class.model_info(@model)
      end
    end
  end
end
```

**Python**:
```python
from typing import Any, ClassVar, Dict, Optional

from ..errors import UnsupportedModelError


class BackendBase:
    """Base class for LLM API backends.
    
    Provides model validation, metadata lookup, and cost estimation.
    Subclasses must define MODELS as a ClassVar.
    """
    MODELS: ClassVar[Dict[str, Dict[str, Any]]] = {}

    def __init__(self, model: str) -> None:
        self.model: str = self.__class__.validate_model(model)
        self._model_info: Dict[str, Any] = self.__class__.model_info(self.model)

    @classmethod
    def models(cls) -> Dict[str, Dict[str, Any]]:
        return cls.MODELS

    @classmethod
    def model_info(cls, model: str) -> Optional[Dict[str, Any]]:
        return cls.MODELS.get(model)

    @classmethod
    def validate_model(cls, model: str) -> str:
        if cls.model_info(model):
            return model
        supported = ", ".join(sorted(cls.MODELS.keys()))
        raise UnsupportedModelError(
            f"{cls.__name__} does not support model '{model}'. "
            f"Supported models: {supported}"
        )

    @property
    def model_info(self) -> Dict[str, Any]:
        return self._model_info

    @property
    def context_window(self) -> int:
        return self._model_info["context_window"]

    @property
    def input_token_cost_per_million(self) -> Optional[float]:
        return self._model_info.get("cost_per_million", {}).get("input")

    @property
    def output_token_cost_per_million(self) -> Optional[float]:
        return self._model_info.get("cost_per_million", {}).get("output")

    @property
    def usage_unit(self) -> str:
        return self._model_info.get("usage_unit", "")

    @property
    def usage_level(self) -> Optional[str]:
        return self._model_info.get("usage_level")

    def estimate_cost(
        self, input_tokens: int, output_tokens: int
    ) -> Optional[float]:
        input_cost = self.input_token_cost_per_million
        output_cost = self.output_token_cost_per_million
        if input_cost is None or output_cost is None:
            return None
        return (
            (input_tokens * input_cost) + (output_tokens * output_cost)
        ) / 1_000_000.0
```

**Key translation**:
- `attr_reader :model` → `@property model` (via `self.model` from `__init__`)
- `const_get(:MODELS)` → `cls.MODELS` (dict class variable)
- Ruby `fetch(key)` → Python dict `.get(key)` or `[key]` (for required keys)
- Ruby `rescue NameError` → not needed in Python since `MODELS` is a ClassVar
- `model.to_s` → `model` (already a string)

---

### 5. Anthropic Backend (`lib/boukensha/backends/anthropic.rb` → `src/boukensha/backends/anthropic.py`)

**Ruby**:
```ruby
module Boukensha
  module Backends
    class Anthropic < Base
      BASE_URL = "https://api.anthropic.com/v1/messages"
      MODELS = {
        "claude-haiku-4-5" => {
          context_window: 200_000,
          cost_per_million: { input: 1.0, output: 5.0 },
          usage_unit: :tokens
        },
        # ... more models
      }.freeze

      def initialize(api_key:, model:)
        @api_key = api_key
        configure_model(model)
      end

      def to_messages(messages)
        messages.map do |msg|
          case msg.role
          when :tool_result
            { role: "user", content: [{ type: "tool_result", tool_use_id: msg.tool_use_id, content: msg.content }] }
          else
            { role: msg.role.to_s, content: msg.content }
          end
        end
      end

      def to_tools(tools)
        tools.values.map do |tool|
          { name: tool.name, description: tool.description, input_schema: { type: "object", properties: tool.parameters, required: tool.parameters.keys.map(&:to_s) } }
        end
      end

      def to_payload(context, max_output_tokens: 1024)
        { model: @model, system: context.system, max_tokens: max_output_tokens, tools: to_tools(context.tools), messages: to_messages(context.messages) }
      end

      def headers
        { "Content-Type" => "application/json", "x-api-key" => @api_key, "anthropic-version" => "2023-06-01" }
      end

      def url
        BASE_URL
      end
    end
  end
end
```

**Python**:
```python
from typing import Any, ClassVar, Dict, List, Optional

from ..context import Context
from ..message import Message
from ..tool import Tool
from .base import BackendBase


class Anthropic(BackendBase):
    BASE_URL: ClassVar[str] = "https://api.anthropic.com/v1/messages"
    MODELS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "claude-haiku-4-5": {
            "context_window": 200_000,
            "cost_per_million": {"input": 1.0, "output": 5.0},
            "usage_unit": "tokens",
        },
        "claude-haiku-4-5-20251001": {
            "context_window": 200_000,
            "cost_per_million": {"input": 1.0, "output": 5.0},
            "usage_unit": "tokens",
        },
        "claude-sonnet-4-6": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 3.0, "output": 15.0},
            "usage_unit": "tokens",
        },
        "claude-opus-4-8": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 25.0},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model)
        self.api_key = api_key

    def to_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        result = []
        for msg in messages:
            if msg.role == "tool_result":
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_use_id,
                        "content": msg.content,
                    }],
                })
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def to_tools(self, tools: Dict[str, Tool]) -> List[Dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": list(tool.parameters.keys()),
                },
            }
            for tool in tools.values()
        ]

    def to_payload(
        self, context: Context, max_output_tokens: int = 1024
    ) -> Dict[str, Any]:
        return {
            "model": self.model,
            "system": context.system,
            "max_tokens": max_output_tokens,
            "tools": self.to_tools(context.tools),
            "messages": self.to_messages(context.messages),
        }

    def headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

    def url(self) -> str:
        return self.BASE_URL
```

**Key translation**:
- Ruby symbols (`:tool_result`, `:tokens`) → Python strings (`"tool_result"`, `"tokens"`)
- `.map(&:to_s)` → `list(dict.keys())` or list comprehension
- `.freeze` → not needed (use ClassVar convention)
- `configure_model(model)` → `super().__init__(model)`
- `@api_key` → `self.api_key`

---

### 6. OpenAI Backend (`lib/boukensha/backends/openai.rb` → `src/boukensha/backends/openai.py`)

**Python**:
```python
from typing import Any, ClassVar, Dict, List, Optional

from ..context import Context
from ..message import Message
from ..tool import Tool
from .base import BackendBase


class OpenAI(BackendBase):
    BASE_URL: ClassVar[str] = "https://api.openai.com/v1/chat/completions"
    MODELS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "gpt-5.5": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 30.0},
            "usage_unit": "tokens",
        },
        "gpt-5.4": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 2.5, "output": 15.0},
            "usage_unit": "tokens",
        },
        "gpt-5.4-mini": {
            "context_window": 400_000,
            "cost_per_million": {"input": 0.75, "output": 4.5},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model)
        self.api_key = api_key

    def to_messages(
        self, system: Optional[str], messages: List[Message]
    ) -> List[Dict[str, Any]]:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        for msg in messages:
            if msg.role == "tool_result":
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_use_id,
                    "content": msg.content,
                })
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def to_tools(self, tools: Dict[str, Tool]) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                },
            }
            for tool in tools.values()
        ]

    def to_payload(
        self, context: Context, max_output_tokens: int = 1024
    ) -> Dict[str, Any]:
        return {
            "model": self.model,
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools),
            "max_completion_tokens": max_output_tokens,
        }

    def headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def url(self) -> str:
        return self.BASE_URL
```

**Key changes from Ruby**:
- `to_messages` takes `system` as a parameter (OpenAI embeds system prompt in messages array)
- `to_tools` wraps in `function` envelope (matching OpenAI's API shape)
- `tool_call_id` field for tool results (OpenAI-specific)

---

### 7. Ollama Backend (`lib/boukensha/backends/ollama.rb` → `src/boukensha/backends/ollama.py`)

**Python**:
```python
from typing import Any, ClassVar, Dict, List, Optional

from ..context import Context
from ..message import Message
from ..tool import Tool
from .base import BackendBase


class Ollama(BackendBase):
    MODELS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "gemma4": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:e2b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:e4b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:12b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:26b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:31b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "qwen3:30b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "qwen3:8b": {
            "context_window": 40_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "deepseek-r1:8b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
    }

    def __init__(self, model: str, host: str = "http://localhost:11434") -> None:
        super().__init__(model)
        self.host = host

    def to_messages(
        self, system: Optional[str], messages: List[Message]
    ) -> List[Dict[str, Any]]:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        for msg in messages:
            if msg.role == "tool_result":
                result.append({
                    "role": "tool",
                    "tool_name": msg.tool_use_id,
                    "content": msg.content,
                })
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def to_tools(self, tools: Dict[str, Tool]) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                },
            }
            for tool in tools.values()
        ]

    def to_payload(
        self, context: Context, max_output_tokens: int = 1024
    ) -> Dict[str, Any]:
        return {
            "model": self.model,
            "stream": False,
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools),
        }

    def headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json"}

    def url(self) -> str:
        return f"{self.host}/api/chat"
```

**Key changes from Ruby**:
- `initialize` takes `model:` as positional, `host:` as keyword with default
- Uses `tool_name` field for tool results (Ollama-specific)
- Same `function` envelope as OpenAI for tool definitions

---

### 8. Ollama Cloud Backend (`lib/boukensha/backends/ollama_cloud.rb` → `src/boukensha/backends/ollama_cloud.py`)

**Python**:
```python
from typing import Any, ClassVar, Dict, List, Optional

from ..context import Context
from ..message import Message
from ..tool import Tool
from .base import BackendBase


class OllamaCloud(BackendBase):
    BASE_URL: ClassVar[str] = "https://ollama.com"
    MODELS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "gemma4:31b-cloud": {
            "context_window": 256_000,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "ollama_cloud_usage",
            "usage_level": "medium",
        },
        "minimax-m3:cloud": {
            "context_window": 512_000,
            "advertised_context_window": 1_000_000,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "ollama_cloud_usage",
            "usage_level": "high",
        },
        "kimi-k2.5:cloud": {
            "context_window": 256_000,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "ollama_cloud_usage",
            "usage_level": "high",
        },
    }

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model)
        self.api_key = api_key

    def to_messages(
        self, system: Optional[str], messages: List[Message]
    ) -> List[Dict[str, Any]]:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        for msg in messages:
            if msg.role == "tool_result":
                result.append({
                    "role": "tool",
                    "tool_name": msg.tool_use_id,
                    "content": msg.content,
                })
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def to_tools(self, tools: Dict[str, Tool]) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                },
            }
            for tool in tools.values()
        ]

    def to_payload(
        self, context: Context, max_output_tokens: int = 1024
    ) -> Dict[str, Any]:
        return {
            "model": self.model,
            "stream": False,
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools),
        }

    def headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def url(self) -> str:
        return f"{self.BASE_URL}/api/chat"
```

---

### 9. Gemini Backend (`lib/boukensha/backends/gemini.rb` → `src/boukensha/backends/gemini.py`)

**Python**:
```python
from typing import Any, ClassVar, Dict, List, Optional

from ..context import Context
from ..message import Message
from ..tool import Tool
from .base import BackendBase


class Gemini(BackendBase):
    BASE_URL: ClassVar[str] = "https://generativelanguage.googleapis.com/v1beta/models"
    MODELS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "gemini-3.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.5, "output": 9.0},
            "usage_unit": "tokens",
        },
        "gemini-3.1-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.25, "output": 1.5},
            "usage_unit": "tokens",
        },
        "gemini-2.5-pro": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.25, "output": 10.0},
            "usage_unit": "tokens",
        },
        "gemini-2.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.30, "output": 2.50},
            "usage_unit": "tokens",
        },
        "gemini-2.5-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.10, "output": 0.40},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model)
        self.api_key = api_key

    def to_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        result = []
        for msg in messages:
            if msg.role == "assistant":
                result.append({
                    "role": "model",
                    "parts": [{"text": msg.content}],
                })
            elif msg.role == "tool_result":
                result.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.tool_use_id,
                            "response": {"content": msg.content},
                        }
                    }],
                })
            else:
                result.append({
                    "role": msg.role,
                    "parts": [{"text": msg.content}],
                })
        return result

    def to_tools(self, tools: Dict[str, Tool]) -> List[Dict[str, Any]]:
        if not tools:
            return []
        return [{
            "functionDeclarations": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                }
                for tool in tools.values()
            ]
        }]

    def to_payload(
        self, context: Context, max_output_tokens: int = 1024
    ) -> Dict[str, Any]:
        return {
            "systemInstruction": {"parts": [{"text": context.system}]},
            "contents": self.to_messages(context.messages),
            "tools": self.to_tools(context.tools),
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }

    def headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

    def url(self) -> str:
        return f"{self.BASE_URL}/{self.model}:generateContent"
```

**Key changes from Ruby**:
- Gemini uses `"role": "model"` instead of `"role": "assistant"`
- Messages use `"parts"` wrapper instead of top-level `"content"`
- Tool results use `functionResponse` parts
- Tools wrapped in `functionDeclarations` array
- System prompt goes in `systemInstruction`

---

### 10. PromptBuilder (`lib/boukensha/prompt_builder.rb` → `src/boukensha/prompt_builder.py`)

**Ruby**:
```ruby
module Boukensha
  class PromptBuilder
    def initialize(context, backend)
      @context = context
      @backend = backend
    end

    def to_messages
      @backend.to_messages(@context.messages)
    end

    def to_tools
      @backend.to_tools(@context.tools)
    end

    def to_api_payload(max_output_tokens: 1024)
      @backend.to_payload(@context, max_output_tokens: max_output_tokens)
    end

    def headers
      @backend.headers
    end

    def url
      @backend.url
    end
  end
end
```

**Python**:
```python
from typing import Any, Dict, List, Optional

from .context import Context


class PromptBuilder:
    """Delegates context serialization to a backend strategy.
    
    PromptBuilder does not make API calls — it only prepares the payload
    format expected by the backend's API.
    """

    def __init__(self, context: Context, backend: Any) -> None:
        self.context = context
        self.backend = backend

    def to_messages(self) -> List[Dict[str, Any]]:
        return self.backend.to_messages(self.context.messages)

    def to_tools(self) -> List[Dict[str, Any]]:
        return self.backend.to_tools(self.context.tools)

    def to_api_payload(
        self, max_output_tokens: int = 1024
    ) -> Dict[str, Any]:
        return self.backend.to_payload(
            self.context, max_output_tokens=max_output_tokens
        )

    def headers(self) -> Dict[str, str]:
        return self.backend.headers()

    def url(self) -> str:
        return self.backend.url()
```

**Key translation**:
- Direct delegation pattern — mirror of Ruby's design
- Note: `to_messages` and `to_tools` signatures differ between backends:
  - Anthropic: `to_messages(messages)` — no system prompt argument
  - OpenAI/Ollama/OllamaCloud: `to_messages(system, messages)` — system embedded in messages
  - Gemini: `to_messages(messages)` — system in separate `systemInstruction` field
- `to_api_payload` always passes `context` and `max_output_tokens` to the backend

---

### 11. Package Exports (`lib/boukensha.rb` → `src/boukensha/__init__.py`)

**Python**:
```python
# Boukensha prompt builder — backends, tasks, and delegate builder
# Re-uses struct and registry classes from prior steps

# Local struct and registry classes
from .tool import Tool  # noqa: F401
from .message import Message  # noqa: F401
from .context import Context  # noqa: F401
from .errors import UnknownToolError, UnsupportedModelError  # noqa: F401
from .registry import Registry  # noqa: F401

# New in this step
from .prompt_builder import PromptBuilder  # noqa: F401
from . import tasks  # noqa: F401
from . import backends  # noqa: F401

__all__ = [
    "Tool",
    "Message",
    "Context",
    "Registry",
    "UnknownToolError",
    "UnsupportedModelError",
    "PromptBuilder",
    "tasks",
    "backends",
]
```

### Backends `__init__.py` (`src/boukensha/backends/__init__.py`):

```python
from .base import BackendBase
from .anthropic import Anthropic
from .gemini import Gemini
from .ollama import Ollama
from .ollama_cloud import OllamaCloud
from .openai import OpenAI

__all__ = [
    "BackendBase",
    "Anthropic",
    "Gemini",
    "Ollama",
    "OllamaCloud",
    "OpenAI",
]
```

### Tasks `__init__.py` (`src/boukensha/tasks/__init__.py`):

```python
from .base import Base
from .player import Player

__all__ = ["Base", "Player"]
```

---

### 12. Example (`examples/example.rb` → `examples/example.py`)

**Python**:
```python
import os
import sys
import json
from pathlib import Path

# Add local src directory to path so we can import the local boukensha package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import local structs first (these don't depend on installed boukensha)
from boukensha import (
    Context, Tool, Message, Registry, UnknownToolError,
    PromptBuilder, backends,
)
from boukensha.tasks import Player
from boukensha.backends import Anthropic, Gemini, Ollama, OllamaCloud, OpenAI

# Remove local src from path and clear boukensha from sys.modules for config import
sys.path.pop(0)
sys.modules.pop('boukensha', None)
sys.modules.pop('boukensha.tasks', None)
sys.modules.pop('boukensha.tasks.player', None)

from boukensha import Config

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).resolve().parent.parent.parent / ".boukensha")
)

config = Config()
player_settings = config.tasks("player") or {}

# Use the prompts shipped with this package
DEFAULT_PROMPTS_DIR = str(Path(__file__).parent.parent / "prompts")

system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=DEFAULT_PROMPTS_DIR,
)

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

registry.tool(
    "look",
    description="Look around the current room for details",
    parameters={},
    block=lambda: "A damp stone corridor stretches north. Torches flicker on the walls.",
)

registry.tool(
    "move",
    description="Move the player in a direction (north, south, east, west, up, down)",
    parameters={"direction": {"type": "string", "description": "The direction to move"}},
    block=lambda direction: f"You move {direction} into a torch-lit corridor.",
)

ctx.add_message("user", "I just arrived in the dungeon. What's around me, and can you move north?")
ctx.add_message("assistant", "Let me take a look around first.")
ctx.add_message("tool_result", "A damp stone corridor stretches north. Torches flicker on the walls.", tool_use_id="toolu_01X")

provider = Player.provider(player_settings)
model = Player.model(player_settings)

if provider == "anthropic":
    backend = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""), model=model)
elif provider == "ollama":
    backend = Ollama(model=model)
elif provider == "ollama_cloud":
    backend = OllamaCloud(api_key=os.environ.get("OLLAMA_API_KEY", ""), model=model)
elif provider == "openai":
    backend = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""), model=model)
elif provider == "gemini":
    backend = Gemini(api_key=os.environ.get("GEMINI_API_KEY", ""), model=model)
else:
    raise ValueError(f"Unsupported provider for player task: {provider}")

builder = PromptBuilder(ctx, backend)

print("=== BOUKENSHA Step 3: Prompt Builder ===")
print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print()
print(json.dumps(builder.to_api_payload(), indent=2, default=str))
```

---

## Dependency Chain

```
03_prompt_builder (PromptBuilder, Backends, Tasks)
    ↓ extends/depends on
02_the_registry (Registry, UnknownToolError)
    ↓ extends/depends on
01_struct_skeleton (Tool, Message, Context)
    ↓ depends on
00_config (Config, Tasks.Base, Tasks.Player)
```

**Action**: Verify prior steps are installed before porting:
```bash
pip list | grep boukensha
```

---

## Testing / Verification Strategy

### Unit-level verification (as you build):
1. **UnsupportedModelError**: Create the exception; verify it's catchable and has a descriptive message listing supported models
2. **BackendBase**: Validate that each backend class has `MODELS` defined, and that `validate_model` raises `UnsupportedModelError` for unknown models
3. **Backend serialization**:
   - Anthropic: Verify `to_messages` wraps tool results in user messages with `tool_result` content blocks
   - OpenAI/Ollama: Verify `to_messages` inserts system prompt as first message and tool results use `role: "tool"`
   - Gemini: Verify `to_messages` maps `assistant` → `model`, wraps content in `parts`, and tool results use `functionResponse`
   - Each backend: Verify `to_tools` returns correct structure (Anthropic uses `input_schema`, OpenAI/Ollama use `function` envelope, Gemini uses `functionDeclarations`)
4. **PromptBuilder**: Verify delegation — `to_messages`, `to_tools`, `to_api_payload`, `headers`, `url` each delegate to the backend
5. **Tasks.Base**: Verify `provider()` and `model()` raise `ValueError` when settings are missing
6. **Tasks.Player**: Verify `task_name == "player"`
7. **Example smoke test**: Run `python examples/example.py`; verify output is valid JSON matching the provider's API shape

### Full integration test:
```bash
source venv/bin/activate
pip install -e week1_baseline/python/03_prompt_builder
./week1_baseline/bin/python/03_prompt_builder
```

### Expected output (shape, not exact values):
The output should be valid JSON for the selected provider's API format. For example, if the config selects `anthropic`:
```json
{
  "model": "claude-haiku-4-5",
  "system": "You are a MUD player assistant.",
  "max_tokens": 1024,
  "tools": [
    {
      "name": "look",
      "description": "Look around the current room for details",
      "input_schema": {
        "type": "object",
        "properties": {},
        "required": []
      }
    },
    {
      "name": "move",
      "description": "Move the player in a direction...",
      "input_schema": {
        "type": "object",
        "properties": {
          "direction": {
            "type": "string",
            "description": "The direction to move"
          }
        },
        "required": ["direction"]
      }
    }
  ],
  "messages": [
    {"role": "user", "content": "I just arrived in the dungeon..."},
    {"role": "assistant", "content": "Let me take a look around first."},
    {
      "role": "user",
      "content": [{
        "type": "tool_result",
        "tool_use_id": "toolu_01X",
        "content": "A damp stone corridor stretches north..."
      }]
    }
  ]
}
```

---

## Common Pitfalls

### 1. `to_messages` vs `to_messages(system, messages)` signature mismatch
**Problem**: Anthropic and Gemini backends take only `messages` (system is separate), while OpenAI and Ollama take `(system, messages)` (system embedded in array).
**Fix**: Call the backend directly from `to_api_payload` with the correct signature, rather than through a shared `to_messages` interface.
**Teaching point**: Backend APIs differ in fundamental ways; the strategy pattern accommodates this.

### 2. Ruby symbols → Python strings in message roles
**Problem**: Ruby uses `:tool_result`, `:assistant`; Python should use `"tool_result"`, `"assistant"`.
**Fix**: Compare `msg.role == "tool_result"` instead of `msg.role == :tool_result`.

### 3. `msg.role` vs `msg.tool_use_id` in Gemini
**Problem**: Gemini maps `assistant` → `model` and wraps everything in `parts`.
**Fix**: Check `msg.role` explicitly for Gemini's special mapping.

### 4. Tools serialization differences
**Problem**: Anthropic uses `input_schema`, OpenAI/Ollama use `type: "function"` + `function.parameters`, Gemini uses `functionDeclarations`.
**Fix**: Each backend implements its own `to_tools()` with the correct shape.

### 5. Model validation at init time
**Problem**: BackendBase validates the model in `__init__`, which can fail with an unhelpful error if MODELS is empty.
**Fix**: Always define MODELS as a non-empty ClassVar in each subclass.

### 6. Ollama Cloud cost estimation returns None
**Problem**: Ollama Cloud models have `nil` cost values, so `estimate_cost` returns `None`.
**Fix**: Handle None in `estimate_cost` gracefully — Ruby returns `nil`, Python returns `None`.

---

## Verifying Success

```bash
source venv/bin/activate
python -c "
from boukensha import PromptBuilder, UnsupportedModelError, backends
from boukensha.tasks import Base, Player
print('Imports work')
print(f'Player.task_name = {Player.task_name}')
# Verify UnsupportedModelError
try:
    backends.Anthropic(api_key='', model='nonexistent-model')
    print('ERROR: Should have raised UnsupportedModelError')
except UnsupportedModelError:
    print('UnsupportedModelError works correctly')
"
./week1_baseline/bin/python/03_prompt_builder
```

---

## Additional Resources

- **Ruby source**: `week1_baseline/ruby/03_prompt_builder/`
- **Python 00_config reference**: `week1_baseline/python/00_config/`
- **Python 01_struct_skeleton reference**: `week1_baseline/python/01_struct_skeleton/`
- **Python 02_the_registry reference**: `week1_baseline/python/02_the_registry/`
- **00_config plan**: `docs/plans/python_port/00_config.md`
- **01_struct_skeleton plan**: `docs/plans/python_port/01_struct_skeleton.md`
- **02_the_registry plan**: `docs/plans/python_port/02_the_registry.md`
- **Anthropic Messages API**: https://docs.anthropic.com/en/api/messages
- **OpenAI Chat Completions API**: https://platform.openai.com/docs/api-reference/chat
- **Gemini API (generateContent)**: https://ai.google.dev/api/generate-content
- **Ollama API**: https://github.com/ollama/ollama/blob/main/docs/api.md
- **Python exception docs**: https://docs.python.org/3/tutorial/errors.html

---

## What NOT to Do

- Don't make HTTP calls in PromptBuilder — it prepares payloads only
- Don't use a unified `to_messages` signature across all backends — each has different parameter needs
- Don't swallow UnsupportedModelError — an invalid model is a hard error
- Don't hardcode provider selection — read from settings like the Ruby version does
- Don't forget the `prompts/system.md` file — without it, `system_prompt()` returns None
- Don't validate tool block signatures at registration — that's a later concern
- Don't redefine Tool/Message/Context — copy from 02_the_registry

---

## Files to Create/Modify

1. Create `src/boukensha/tasks/base.py` — Base task class
2. Create `src/boukensha/tasks/player.py` — Player task class
3. Create `src/boukensha/tasks/__init__.py` — task exports
4. Create `src/boukensha/backends/__init__.py` — backend exports
5. Create `src/boukensha/backends/base.py` — BackendBase
6. Create `src/boukensha/backends/anthropic.py` — Anthropic backend
7. Create `src/boukensha/backends/gemini.py` — Gemini backend
8. Create `src/boukensha/backends/ollama.py` — Ollama backend
9. Create `src/boukensha/backends/ollama_cloud.py` — Ollama Cloud backend
10. Create `src/boukensha/backends/openai.py` — OpenAI backend
11. Modify `src/boukensha/errors.py` — add UnsupportedModelError
12. Create `src/boukensha/prompt_builder.py` — PromptBuilder
13. Update `src/boukensha/__init__.py` — export PromptBuilder, tasks, backends, UnsupportedModelError
14. Copy `src/boukensha/tool.py` from 02_the_registry
15. Copy `src/boukensha/message.py` from 02_the_registry
16. Copy `src/boukensha/context.py` from 02_the_registry
17. Copy `src/boukensha/registry.py` from 02_the_registry
18. Create `examples/example.py` — smoke test
19. Copy `prompts/system.md` — default system prompt
20. Create `pyproject.toml` — package config
21. Create `README.md` — usage docs
22. Create `week1_baseline/bin/python/03_prompt_builder` — executable launcher