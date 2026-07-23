# Python Port: Boukensha Agent Loop (05_agent_loop)

**Status**: Planning — This document defines the port plan for `week1_baseline/ruby/05_agent_loop/` to Python.

The Agent Loop is the heart of BOUKENSHA. Everything built before this — the structs, the registry, the prompt builder, the client — was setup. The loop is where the agent actually does work: it sends requests, dispatches tools, and knows when to stop.

This step introduces the `Agent` class, the `LoopError` exception, and adds `parse_response` and `assistant_message`/`assistant_parts` methods to every backend. The `Client.call()` method gains a `tools` parameter to support the wind-down call (tools disabled).

## Decisions

These decisions build on 00_config through 04_api_client:

- **Agent class mirrors Ruby's `Boukensha::Agent`**: Same iteration loop, tool call handling, wind-down logic, and fallback message generation. The Python `Agent` class lives in `src/boukensha/agent.py`.

- **`parse_response` delegates to backend via PromptBuilder**: The Ruby `PromptBuilder.parse_response(response)` delegates to `@backend.parse_response(response)`. The Python `PromptBuilder` gains the same method.

- **Every backend implements `parse_response`**: Returns the normalized shape `{"stop_reason": "tool_use" | "end_turn", "content": [...]}`. This is the key abstraction that keeps the Agent loop provider-agnostic.

- **Every backend implements `assistant_message` or `assistant_parts`**: The inverse of `parse_response` — rebuilds a provider-specific assistant message from normalized content blocks. Needed when replaying conversation history on the next request.

- **Tool call IDs**: Anthropic and OpenAI assign unique `id` per tool call. Ollama, Ollama Cloud, and Gemini reuse the function name as the `id`. The normalized shape always includes `"id"`, `"name"`, and `"input"`.

- **`Client.call()` gains `tools` parameter**: The wind-down call passes `tools=[]` to disable tools. The Ruby client already has this; the Python client needs it added.

- **`LoopError` exception**: Raised for runaway agents (though the current implementation uses wind-down instead of raising). Added to `errors.py` for future use.

- **No HTTP call in Agent**: The Agent loop only calls `@client.call()` and `@builder.parse_response()`. All network I/O stays in `Client`.

## Target Python Structure (as planned)

```
week1_baseline/python/05_agent_loop/
├── src/
│   └── boukensha/
│       ├── __init__.py              # Package exports (add Agent, LoopError)
│       ├── agent.py                 # Agent class (NEW)
│       ├── client.py                # Client class (modify: add tools param)
│       ├── config.py                # Config class (copy from 04_api_client)
│       ├── tool.py                  # Tool dataclass (copy from 04_api_client)
│       ├── message.py               # Message dataclass (copy from 04_api_client)
│       ├── context.py               # Context class (copy from 04_api_client)
│       ├── errors.py                # Add LoopError (modify 04_api_client version)
│       ├── registry.py              # Registry class (copy from 04_api_client)
│       ├── prompt_builder.py        # PromptBuilder class (modify: add parse_response)
│       ├── tasks/
│       │   ├── __init__.py          # Task exports (copy)
│       │   ├── base.py              # Base task class (copy)
│       │   └── player.py            # Player task class (copy)
│       └── backends/
│           ├── __init__.py          # Backend exports (copy)
│           ├── base.py              # BackendBase (copy)
│           ├── anthropic.py         # Anthropic backend (modify: add parse_response)
│           ├── gemini.py            # Gemini backend (modify: add parse_response, assistant_parts)
│           ├── ollama.py            # Ollama backend (modify: add parse_response, assistant_message)
│           ├── ollama_cloud.py      # Ollama Cloud backend (modify: add parse_response, assistant_message)
│           └── openai.py            # OpenAI backend (modify: add parse_response, assistant_message)
├── examples/
│   └── example.py                   # Agent loop example (NEW)
├── prompts/
│   └── system.md                    # Default system prompt (copy from 04_api_client)
├── pyproject.toml                   # Package config (copy from 04_api_client, bump version)
└── README.md                        # Usage documentation (NEW)
```

### Already Ported (from 04_api_client)
All files from step 4 are carried forward unchanged:
- **config.py**, **tool.py**, **message.py**, **context.py**, **registry.py**
- **client.py** (will modify to add `tools` parameter)
- **prompt_builder.py** (will modify to add `parse_response`)
- **errors.py** (will add `LoopError` to existing `UnknownToolError`, `UnsupportedModelError`, `ApiError`)
- **tasks/base.py**, **tasks/player.py**
- **backends/base.py**, **backends/anthropic.py**, **backends/gemini.py**, **backends/ollama.py**, **backends/ollama_cloud.py**, **backends/openai.py**
- **prompts/system.md**

### New in This Step
- **agent.py**: Agent class with iteration loop, tool dispatch, wind-down logic
- **errors.py**: Add `LoopError` exception

### Modified in This Step
- **client.py**: Add `tools` parameter to `call()` method
- **prompt_builder.py**: Add `parse_response()` method
- **backends/anthropic.py**: Add `parse_response()` method
- **backends/openai.py**: Add `parse_response()` and `assistant_message()` methods
- **backends/gemini.py**: Add `parse_response()` and `assistant_parts()` methods
- **backends/ollama.py**: Add `parse_response()` and `assistant_message()` methods
- **backends/ollama_cloud.py**: Add `parse_response()` and `assistant_message()` methods
- **__init__.py**: Export `Agent` and `LoopError`

## Quick Setup

### 1. Ensure prior steps are ported and installed
```bash
source venv/bin/activate
pip install -e week1_baseline/python/00_config
pip install -e week1_baseline/python/01_struct_skeleton
pip install -e week1_baseline/python/02_the_registry
pip install -e week1_baseline/python/03_prompt_builder
pip install -e week1_baseline/python/04_api_client
```

### 2. Install 05_agent_loop
```bash
pip install -e week1_baseline/python/05_agent_loop
```

### 3. Run it
```bash
./week1_baseline/bin/python/05_agent_loop
```

---

## Porting Plan: File by File

### 1. Copy Prior Step as Template

Copy the entire `04_api_client` directory to `05_agent_loop`. All source files, `pyproject.toml`, `README.md`, and `prompts/` are reused. Only add new files and modify existing ones.

```bash
cp -r week1_baseline/python/04_api_client week1_baseline/python/05_agent_loop
```

---

### 2. LoopError Exception (`lib/boukensha/errors.rb` → `src/boukensha/errors.py`)

**Ruby** (from step 5):
```ruby
module Boukensha
  class LoopError < StandardError; end
end
```

**Python** (add to existing errors.py):
```python
class LoopError(Exception):
    """Raised when the agent exceeds its iteration limit."""
    pass
```

---

### 3. Agent (`lib/boukensha/agent.rb` → `src/boukensha/agent.py`)

**Ruby** (full file, 111 lines):
```ruby
module Boukensha
  class Agent
    MAX_ITERATIONS = 25
    WRAP_UP_OUTPUT_TOKENS = 400
    WRAP_UP_DIRECTIVE = <<~MSG.strip
      You have reached your action limit for this turn. Do not call any more tools.
      Briefly summarize what you accomplished, what is still unfinished, and the
      single next action you would take.
    MSG

    def initialize(context:, registry:, builder:, client:,
                   task_settings: nil, max_iterations: nil, max_output_tokens: nil)
      @context           = context
      @registry          = registry
      @builder           = builder
      @client            = client
      @max_iterations    = resolve_max_iterations(task_settings, max_iterations)
      @max_output_tokens = resolve_max_output_tokens(task_settings, max_output_tokens)
      @iteration         = 0
    end

    def run
      loop do
        return wrap_up("max_iterations") if iteration_limit_reached?
        @iteration += 1
        puts "[iteration #{@iteration}/#{@max_iterations}]"
        response = @client.call(**call_opts)
        parsed   = @builder.parse_response(response)
        if parsed[:stop_reason] == "tool_use"
          handle_tool_calls(parsed[:content])
        else
          return extract_text(parsed[:content])
        end
      end
    end

    private

    def resolve_max_iterations(task_settings, explicit)
      return explicit.to_i unless explicit.nil?
      return @context.task.max_iterations(task_settings) if task_settings && @context.task.respond_to?(:max_iterations)
      MAX_ITERATIONS
    end

    def resolve_max_output_tokens(task_settings, explicit)
      return explicit unless explicit.nil?
      return @context.task.max_output_tokens(task_settings) if task_settings && @context.task.respond_to?(:max_output_tokens)
      nil
    end

    def iteration_limit_reached?
      @max_iterations.positive? && @iteration >= @max_iterations
    end

    def call_opts
      @max_output_tokens ? { max_output_tokens: @max_output_tokens } : {}
    end

    def wrap_up(reason)
      @context.add_message(:user, WRAP_UP_DIRECTIVE)
      response = @client.call(tools: [], max_output_tokens: WRAP_UP_OUTPUT_TOKENS)
      text     = extract_text(@builder.parse_response(response)[:content])
      text.strip.empty? ? fallback_message(reason) : text
    rescue ApiError
      fallback_message(reason)
    end

    def fallback_message(reason)
      "I reached my #{@max_iterations}-action limit for this turn before finishing " \
      "(#{reason}). Ask me to continue and I'll pick up from here."
    end

    def extract_text(content)
      content.select { |b| b["type"] == "text" }.map { |b| b["text"] }.join
    end

    def handle_tool_calls(content)
      @context.add_message(:assistant, content)
      content.select { |b| b["type"] == "tool_use" }.each do |block|
        name   = block["name"]
        args   = block["input"]
        use_id = block["id"]
        puts "  tool call → #{name}(#{args})"
        result = @registry.dispatch(name, args)
        puts "  tool result → #{result.to_s[0..60]}"
        @context.add_message(:tool_result, result.to_s, tool_use_id: use_id)
      end
    end
  end
end
```

**Python**:
```python
import json
from typing import Any, Dict, List, Optional

from .client import Client
from .context import Context
from .errors import ApiError
from .prompt_builder import PromptBuilder
from .registry import Registry


class Agent:
    """The agent loop — sends requests, dispatches tools, and knows when to stop."""

    MAX_ITERATIONS = 25
    WRAP_UP_OUTPUT_TOKENS = 400
    WRAP_UP_DIRECTIVE = (
        "You have reached your action limit for this turn. Do not call any more tools. "
        "Briefly summarize what you accomplished, what is still unfinished, and the "
        "single next action you would take."
    )

    def __init__(
        self,
        context: Context,
        registry: Registry,
        builder: PromptBuilder,
        client: Client,
        task_settings: Optional[Dict[str, Any]] = None,
        max_iterations: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
    ) -> None:
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.max_iterations = self._resolve_max_iterations(task_settings, max_iterations)
        self.max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self.iteration = 0

    def run(self) -> str:
        """Start the loop and return the final text response when the agent is done."""
        while True:
            if self._iteration_limit_reached():
                return self._wrap_up("max_iterations")

            self.iteration += 1
            print(f"[iteration {self.iteration}/{self.max_iterations}]")

            response = self.client.call(**self._call_opts())
            parsed = self.builder.parse_response(response)

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"])
            else:
                return self._extract_text(parsed["content"])

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_max_iterations(
        self,
        task_settings: Optional[Dict[str, Any]],
        explicit: Optional[int],
    ) -> int:
        if explicit is not None:
            return int(explicit)
        if task_settings and self.context.task is not None:
            try:
                return self.context.task.max_iterations(task_settings)
            except (AttributeError, TypeError):
                pass
        return self.MAX_ITERATIONS

    def _resolve_max_output_tokens(
        self,
        task_settings: Optional[Dict[str, Any]],
        explicit: Optional[int],
    ) -> Optional[int]:
        if explicit is not None:
            return explicit
        if task_settings and self.context.task is not None:
            try:
                return self.context.task.max_output_tokens(task_settings)
            except (AttributeError, TypeError):
                pass
        return None

    def _iteration_limit_reached(self) -> bool:
        return self.max_iterations > 0 and self.iteration >= self.max_iterations

    def _call_opts(self) -> Dict[str, Any]:
        opts: Dict[str, Any] = {}
        if self.max_output_tokens is not None:
            opts["max_output_tokens"] = self.max_output_tokens
        return opts

    def _wrap_up(self, reason: str) -> str:
        """One final, tools-disabled model call so the agent ends gracefully."""
        self.context.add_message("user", self.WRAP_UP_DIRECTIVE)
        try:
            response = self.client.call(
                tools=[],
                max_output_tokens=self.WRAP_UP_OUTPUT_TOKENS,
            )
            text = self._extract_text(
                self.builder.parse_response(response)["content"]
            )
            if text.strip():
                return text
        except ApiError:
            pass
        return self._fallback_message(reason)

    def _fallback_message(self, reason: str) -> str:
        return (
            f"I reached my {self.max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    @staticmethod
    def _extract_text(content: List[Dict[str, Any]]) -> str:
        return "".join(
            block["text"] for block in content if block.get("type") == "text"
        )

    def _handle_tool_calls(self, content: List[Dict[str, Any]]) -> None:
        """Store the assistant message, then dispatch each tool call."""
        self.context.add_message("assistant", content)

        for block in content:
            if block.get("type") != "tool_use":
                continue

            name = block["name"]
            args = block["input"]
            use_id = block["id"]

            print(f"  tool call → {name}({args})")
            result = self.registry.dispatch(name, args)
            result_str = str(result)
            print(f"  tool result → {result_str[:60]}")

            self.context.add_message("tool_result", result_str, tool_use_id=use_id)
```

**Key translation notes**:
- `@context.task.respond_to?(:max_iterations)` → `hasattr(self.context.task, 'max_iterations')` via try/except
- `parsed[:stop_reason]` → `parsed["stop_reason"]` (Python dicts use string keys)
- `puts` → `print()`
- `result.to_s[0..60]` → `str(result)[:60]`
- `rescue ApiError` → `except ApiError`
- `<<~MSG.strip` → triple-quoted string with `.strip()`
- `@max_iterations.positive?` → `self.max_iterations > 0`
- `@context.add_message(:user, ...)` → `self.context.add_message("user", ...)` (Python uses string roles)
- `@context.add_message(:assistant, content)` → `self.context.add_message("assistant", content)` — note: content is a list of dicts, not a string. The `Context.add_message` method must handle this (see Context note below).

**Important**: The Ruby `Context.add_message` accepts content as either a string or a list of content blocks. The Python `Context.add_message` currently only handles string content. It needs to be updated to accept `content` as `Union[str, List[Dict[str, Any]]]` and store it appropriately in the `Message` object.

---

### 4. Client — Add `tools` parameter (`lib/boukensha/client.rb` → `src/boukensha/client.py`)

**Ruby** (step 5 client — note the `tools: nil` parameter):
```ruby
def call(max_output_tokens: 1024, tools: nil)
  # ...
  request.body = @builder.to_api_payload(max_output_tokens: max_output_tokens, tools: tools).to_json
  # ...
end
```

**Python** (modify existing `call` method signature and payload construction):
```python
def call(self, max_output_tokens: int = 1024, tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    # ...
    payload = self.builder.to_api_payload(max_output_tokens=max_output_tokens, tools=tools)
    # ...
```

**Change**: Add `tools: Optional[List[Dict[str, Any]]] = None` parameter to `call()`. Pass it through to `builder.to_api_payload()`.

---

### 5. PromptBuilder — Add `parse_response` (`lib/boukensha/prompt_builder.rb` → `src/boukensha/prompt_builder.py`)

**Ruby** (step 5):
```ruby
def parse_response(response)
  @backend.parse_response(response)
end
```

**Python** (add to existing PromptBuilder class):
```python
def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
    return self.backend.parse_response(response)
```

---

### 6. Backend: Anthropic — Add `parse_response` (`lib/boukensha/backends/anthropic.rb` → `src/boukensha/backends/anthropic.py`)

**Ruby**:
```ruby
def parse_response(response)
  stop_reason = response["stop_reason"] == "tool_use" ? "tool_use" : "end_turn"
  { stop_reason: stop_reason, content: response["content"] || [] }
end
```

**Python** (add to existing Anthropic class):
```python
def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
    stop_reason = "tool_use" if response.get("stop_reason") == "tool_use" else "end_turn"
    return {"stop_reason": stop_reason, "content": response.get("content") or []}
```

**Note**: Anthropic's content array is already in the normalized shape — no conversion needed. No `assistant_message` needed because Anthropic's content array doubles as the wire format.

---

### 7. Backend: OpenAI — Add `parse_response` and `assistant_message` (`lib/boukensha/backends/openai.rb` → `src/boukensha/backends/openai.py`)

**Ruby**:
```ruby
def parse_response(response)
  message    = response.dig("choices", 0, "message") || {}
  tool_calls = message["tool_calls"] || []
  content = []
  content << { "type" => "text", "text" => message["content"] } if message["content"]
  tool_calls.each do |tc|
    content << {
      "type"  => "tool_use",
      "id"    => tc["id"],
      "name"  => tc.dig("function", "name"),
      "input" => JSON.parse(tc.dig("function", "arguments") || "{}")
    }
  end
  { stop_reason: tool_calls.empty? ? "end_turn" : "tool_use", content: content }
end

def assistant_message(content)
  blocks = content.is_a?(String) ? [{ "type" => "text", "text" => content }] : content
  text_blocks = blocks.select { |b| b["type"] == "text" }
  tool_blocks = blocks.select { |b| b["type"] == "tool_use" }
  message = { role: "assistant", content: text_blocks.map { |b| b["text"] }.join }
  unless tool_blocks.empty?
    message[:tool_calls] = tool_blocks.map do |b|
      { id: b["id"], type: "function", function: { name: b["name"], arguments: b["input"].to_json } }
    end
  end
  message
end
```

**Python** (add to existing OpenAI class):
```python
import json

def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
    message = (response.get("choices") or [{}])[0].get("message") or {}
    tool_calls = message.get("tool_calls") or []

    content = []
    if message.get("content"):
        content.append({"type": "text", "text": message["content"]})

    for tc in tool_calls:
        fn = tc.get("function") or {}
        try:
            arguments = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            arguments = {}
        content.append({
            "type": "tool_use",
            "id": tc["id"],
            "name": fn.get("name"),
            "input": arguments,
        })

    stop_reason = "tool_use" if tool_calls else "end_turn"
    return {"stop_reason": stop_reason, "content": content}

def assistant_message(self, content: Any) -> Dict[str, Any]:
    blocks = content if isinstance(content, list) else [{"type": "text", "text": str(content)}]
    text_blocks = [b for b in blocks if b.get("type") == "text"]
    tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]

    message = {"role": "assistant", "content": "".join(b["text"] for b in text_blocks)}
    if tool_blocks:
        message["tool_calls"] = [
            {
                "id": b["id"],
                "type": "function",
                "function": {
                    "name": b["name"],
                    "arguments": json.dumps(b["input"]),
                },
            }
            for b in tool_blocks
        ]
    return message
```

**Key translation**:
- `response.dig("choices", 0, "message")` → `(response.get("choices") or [{}])[0].get("message") or {}`
- `tc.dig("function", "name")` → `tc.get("function", {}).get("name")`
- `JSON.parse(tc.dig("function", "arguments") || "{}")` → `json.loads(fn.get("arguments") or "{}")`
- `content.is_a?(String)` → `isinstance(content, str)`
- `b["input"].to_json` → `json.dumps(b["input"])`

---

### 8. Backend: Gemini — Add `parse_response` and `assistant_parts` (`lib/boukensha/backends/gemini.rb` → `src/boukensha/backends/gemini.py`)

**Ruby**:
```ruby
def parse_response(response)
  parts = response.dig("candidates", 0, "content", "parts") || []
  content   = []
  tool_used = false
  parts.each do |part|
    if part["functionCall"]
      fc = part["functionCall"]
      content << { "type" => "tool_use", "id" => fc["name"], "name" => fc["name"], "input" => fc["args"] || {} }
      tool_used = true
    elsif part["text"]
      content << { "type" => "text", "text" => part["text"] }
    end
  end
  { stop_reason: tool_used ? "tool_use" : "end_turn", content: content }
end

def assistant_parts(content)
  blocks = content.is_a?(String) ? [{ "type" => "text", "text" => content }] : content
  blocks.map do |b|
    if b["type"] == "tool_use"
      { functionCall: { name: b["name"], args: b["input"] } }
    else
      { text: b["text"] }
    end
  end
end
```

**Python** (add to existing Gemini class):
```python
def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
    candidates = response.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts") if candidates else []
    if parts is None:
        parts = []

    content = []
    tool_used = False

    for part in parts:
        if "functionCall" in part:
            fc = part["functionCall"]
            content.append({
                "type": "tool_use",
                "id": fc.get("name"),
                "name": fc.get("name"),
                "input": fc.get("args") or {},
            })
            tool_used = True
        elif "text" in part:
            content.append({"type": "text", "text": part["text"]})

    stop_reason = "tool_use" if tool_used else "end_turn"
    return {"stop_reason": stop_reason, "content": content}

def assistant_parts(self, content: Any) -> List[Dict[str, Any]]:
    blocks = content if isinstance(content, list) else [{"type": "text", "text": str(content)}]
    result = []
    for b in blocks:
        if b.get("type") == "tool_use":
            result.append({"functionCall": {"name": b["name"], "args": b["input"]}})
        else:
            result.append({"text": b["text"]})
    return result
```

**Key translation**:
- `response.dig("candidates", 0, "content", "parts")` → chained `.get()` calls
- `part["functionCall"]` → `"functionCall" in part` (check key existence)
- `fc["args"] || {}` → `fc.get("args") or {}`

---

### 9. Backend: Ollama — Add `parse_response` and `assistant_message` (`lib/boukensha/backends/ollama.rb` → `src/boukensha/backends/ollama.py`)

**Ruby**:
```ruby
def parse_response(response)
  message    = response["message"] || {}
  tool_calls = message["tool_calls"] || []
  content = []
  content << { "type" => "text", "text" => message["content"] } if message["content"] && !message["content"].empty?
  tool_calls.each do |tc|
    fn = tc["function"] || {}
    content << { "type" => "tool_use", "id" => fn["name"], "name" => fn["name"], "input" => fn["arguments"] || {} }
  end
  { stop_reason: tool_calls.empty? ? "end_turn" : "tool_use", content: content }
end

def assistant_message(content)
  blocks = content.is_a?(String) ? [{ "type" => "text", "text" => content }] : content
  text_blocks = blocks.select { |b| b["type"] == "text" }
  tool_blocks = blocks.select { |b| b["type"] == "tool_use" }
  message = { role: "assistant", content: text_blocks.map { |b| b["text"] }.join }
  unless tool_blocks.empty?
    message[:tool_calls] = tool_blocks.map do |b|
      { function: { name: b["name"], arguments: b["input"] } }
    end
  end
  message
end
```

**Python** (add to existing Ollama class):
```python
def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
    message = response.get("message") or {}
    tool_calls = message.get("tool_calls") or []

    content = []
    if message.get("content"):
        content.append({"type": "text", "text": message["content"]})

    for tc in tool_calls:
        fn = tc.get("function") or {}
        content.append({
            "type": "tool_use",
            "id": fn.get("name"),
            "name": fn.get("name"),
            "input": fn.get("arguments") or {},
        })

    stop_reason = "tool_use" if tool_calls else "end_turn"
    return {"stop_reason": stop_reason, "content": content}

def assistant_message(self, content: Any) -> Dict[str, Any]:
    blocks = content if isinstance(content, list) else [{"type": "text", "text": str(content)}]
    text_blocks = [b for b in blocks if b.get("type") == "text"]
    tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]

    message = {"role": "assistant", "content": "".join(b["text"] for b in text_blocks)}
    if tool_blocks:
        message["tool_calls"] = [
            {"function": {"name": b["name"], "arguments": b["input"]}}
            for b in tool_blocks
        ]
    return message
```

**Key translation**:
- `message["content"] && !message["content"].empty?` → `message.get("content")` (empty string is falsy in Python)
- `fn["arguments"] || {}` → `fn.get("arguments") or {}`
- `tool_calls.empty?` → `not tool_calls`

---

### 10. Backend: OllamaCloud — Add `parse_response` and `assistant_message` (`lib/boukensha/backends/ollama_cloud.rb` → `src/boukensha/backends/ollama_cloud.py`)

Identical to Ollama's `parse_response` and `assistant_message`. The Ruby implementation is a direct copy. Same for Python.

---

### 11. Context — Handle list content in `add_message`

**Ruby** `Context.add_message` accepts content as either a string or a list of content blocks. The Python `Context.add_message` currently only handles string content. It needs to be updated.

**Python** (modify existing `add_message`):
```python
def add_message(self, role: str, content: Any, tool_use_id: Optional[str] = None) -> None:
    # Import Message here to avoid circular dependency at module load time
    from .message import Message
    self.messages.append(Message(role, content, tool_use_id))
```

**Change**: The `content` parameter type changes from `str` to `Any` (accepts both strings and lists of dicts). The `Message` class must also handle both types.

---

### 12. Message — Handle list content

**Ruby** `Message` stores content as-is (string or array). The Python `Message` dataclass currently expects `content: str`. It needs to accept `Union[str, List[Dict[str, Any]]]`.

**Python** (modify existing `message.py`):
```python
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union


@dataclass
class Message:
    role: str
    content: Union[str, List[Dict[str, Any]]]
    tool_use_id: Optional[str] = None
```

---

### 13. Package Exports (`lib/boukensha.rb` → `src/boukensha/__init__.py`)

**Python** (modify existing file from 04_api_client):
```python
# Boukensha agent loop — backends, tasks, registry, builder, client, and agent
# Re-uses config, struct, registry, prompt builder, and client classes from prior steps

# Local struct, config, and registry classes
from .config import Config  # noqa: F401
from .tool import Tool  # noqa: F401
from .message import Message  # noqa: F401
from .context import Context  # noqa: F401
from .errors import UnknownToolError, UnsupportedModelError, ApiError, LoopError  # noqa: F401
from .registry import Registry  # noqa: F401

# From prior step (03_prompt_builder)
from .prompt_builder import PromptBuilder  # noqa: F401
from . import tasks  # noqa: F401
from . import backends  # noqa: F401

# From prior step (04_api_client)
from .client import Client  # noqa: F401

# New in this step (05_agent_loop)
from .agent import Agent  # noqa: F401

__all__ = [
    "Config",
    "Tool",
    "Message",
    "Context",
    "Registry",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "LoopError",
    "PromptBuilder",
    "Client",
    "Agent",
    "tasks",
    "backends",
]
```

**Change**: Add `LoopError` to imports and `__all__`; add `Agent` to imports and `__all__`.

---

### 14. Example (`examples/example.rb` → `examples/example.py`)

**Ruby** (88 lines):
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
require_relative "../lib/boukensha"

config          = Boukensha::Config.new
player_settings = config.tasks(:player)
system_prompt   = Boukensha::Tasks::Player.system_prompt(
  player_settings,
  user_prompts_dir: config.user_prompts_dir,
  default_prompts_dir: Boukensha::Config::PROMPTS_DIR
)
base_dir        = File.expand_path("..", __dir__)

ctx      = Boukensha::Context.new(task: Boukensha::Tasks::Player, system: system_prompt)
registry = Boukensha::Registry.new(ctx)

provider = Boukensha::Tasks::Player.provider(player_settings)
model    = Boukensha::Tasks::Player.model(player_settings)

backend =
case provider
when "anthropic"
  Boukensha::Backends::Anthropic.new(api_key: ENV.fetch("ANTHROPIC_API_KEY"), model: model)
when "openai"
  Boukensha::Backends::OpenAI.new(api_key: ENV.fetch("OPENAI_API_KEY"), model: model)
when "gemini"
  Boukensha::Backends::Gemini.new(api_key: ENV.fetch("GEMINI_API_KEY"), model: model)
when "ollama"
  Boukensha::Backends::Ollama.new(model: model)
when "ollama_cloud"
  Boukensha::Backends::OllamaCloud.new(api_key: ENV.fetch("OLLAMA_API_KEY"), model: model)
else
  raise ArgumentError, "Unsupported provider for player task: #{provider}"
end

builder  = Boukensha::PromptBuilder.new(ctx, backend)
client   = Boukensha::Client.new(builder)
agent    = Boukensha::Agent.new(
  context: ctx, registry: registry, builder: builder, client: client,
  task_settings: player_settings
)

registry.tool("read_file",
  description: "Read the contents of a file from disk",
  parameters: { path: { type: "string", description: "The file path to read" } }
) do |path:|
  File.read(File.expand_path(path, base_dir))
end

registry.tool("list_directory",
  description: "List the files in a directory",
  parameters: { path: { type: "string", description: "The directory path to list" } }
) do |path:|
  Dir.entries(File.expand_path(path, base_dir)).reject { |f| f.start_with?(".") }.join(", ")
end

ctx.add_message(:user, "Read the README.md file and summarise what this MUD player assistant framework can do.")

puts "=== BOUKENSHA Step 5: Agent Loop ==="
puts
puts "Config: #{config}"
puts "Provider: #{provider}"
puts "Model: #{model}"
puts "Max iterations: #{Boukensha::Tasks::Player.max_iterations(player_settings)}"
puts "Max output tokens: #{Boukensha::Tasks::Player.max_output_tokens(player_settings)}"
puts

result = agent.run

puts
puts "=== FINAL RESPONSE ==="
puts result
```

**Python**:
```python
import os
from pathlib import Path

from boukensha import Config, Context, PromptBuilder, Client, Registry, Agent
from boukensha.tasks import Player
from boukensha.backends import Anthropic, Gemini, Ollama, OllamaCloud, OpenAI

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).resolve().parent.parent.parent / ".boukensha"),
)

config = Config()
player_settings = config.tasks("player") or {}

system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)

base_dir = Path(__file__).resolve().parent.parent

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

provider = Player.provider(player_settings)
model = Player.model(player_settings)

if provider == "anthropic":
    backend = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model=model)
elif provider == "openai":
    backend = OpenAI(api_key=os.environ["OPENAI_API_KEY"], model=model)
elif provider == "gemini":
    backend = Gemini(api_key=os.environ["GEMINI_API_KEY"], model=model)
elif provider == "ollama":
    backend = Ollama(model=model)
elif provider == "ollama_cloud":
    backend = OllamaCloud(api_key=os.environ["OLLAMA_API_KEY"], model=model)
else:
    raise ValueError(f"Unsupported provider for player task: {provider}")

builder = PromptBuilder(ctx, backend)
client = Client(builder)
agent = Agent(
    context=ctx,
    registry=registry,
    builder=builder,
    client=client,
    task_settings=player_settings,
)

registry.tool(
    "read_file",
    description="Read the contents of a file from disk",
    parameters={"path": {"type": "string", "description": "The file path to read"}},
    block=lambda path: (base_dir / path).read_text(),
)

registry.tool(
    "list_directory",
    description="List the files in a directory",
    parameters={"path": {"type": "string", "description": "The directory path to list"}},
    block=lambda path: ", ".join(
        f for f in os.listdir(str(base_dir / path)) if not f.startswith(".")
    ),
)

ctx.add_message("user", "Read the README.md file and summarise what this MUD player assistant framework can do.")

print("=== BOUKENSHA Step 5: Agent Loop ===")
print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Max iterations: {Player.max_iterations(player_settings)}")
print(f"Max output tokens: {Player.max_output_tokens(player_settings)}")
print()

result = agent.run()

print()
print("=== FINAL RESPONSE ===")
print(result)
```

**Key translation notes**:
- `ENV.fetch("ANTHROPIC_API_KEY")` → `os.environ["ANTHROPIC_API_KEY"]`
- `File.expand_path("..", __dir__)` → `Path(__file__).resolve().parent.parent`
- `File.read(File.expand_path(path, base_dir))` → `(base_dir / path).read_text()`
- `Dir.entries(...).reject { |f| f.start_with?(".") }.join(", ")` → list comprehension with `os.listdir()`
- `Boukensha::Agent.new(...)` → `Agent(...)`
- `Boukensha::Tasks::Player.max_iterations(player_settings)` → `Player.max_iterations(player_settings)`
- `ctx.add_message(:user, ...)` → `ctx.add_message("user", ...)`

---

### 15. Update pyproject.toml

**Change**: Bump version from `0.4.0` to `0.5.0`:
```toml
[project]
name = "boukensha"
version = "0.5.0"
description = "Boukensha agent loop — sends requests, dispatches tools, and knows when to stop"
# ... rest unchanged
```

---

### 16. Update README.md

Replace the step 4 README with step 5 content. See the Ruby `README.md` for the full content to port. Key sections:

- **The Agent Loop**: Overview of how the loop works
- **Boukensha::Agent** → **Agent**: The `run()` method
- **Every Backend Speaks the Same Normalized Shape**: `parse_response` contract
- **Task Configuration**: YAML-based task settings
- **What the Loop Looks Like**: Example output
- **Considerations**: Assistant message ordering, multiple tool calls, iteration ceiling

---

## Dependency Chain

```
05_agent_loop (Agent, LoopError)
    ↓ extends/depends on
04_api_client (Client, ApiError)
    ↓ extends/depends on
03_prompt_builder (PromptBuilder, Backends)
    ↓ extends/depends on
02_the_registry (Registry, UnknownToolError)
    ↓ extends/depends on
01_struct_skeleton (Tool, Message, Context)
    ↓ depends on
00_config (Config, Tasks.Base, Tasks.Player)
```

**Action**: Verify prior steps are installed before porting.

---

## Testing / Verification Strategy

### Unit-level verification (as you build):
1. **Agent initialization**: Verify `Agent(context, registry, builder, client)` stores all dependencies
2. **Iteration limit**: Verify `_iteration_limit_reached()` returns True when `iteration >= max_iterations`
3. **Call opts**: Verify `_call_opts()` returns correct dict with/without `max_output_tokens`
4. **Extract text**: Verify `_extract_text()` joins text blocks correctly
5. **Tool call handling**: Verify `_handle_tool_calls()` adds assistant message, dispatches tools, adds tool results
6. **Wind-down**: Verify `_wrap_up()` adds user directive, calls client with `tools=[]`, returns fallback on error
7. **Fallback message**: Verify `_fallback_message()` returns expected string
8. **Backend parse_response**: Test each backend's `parse_response` with mock response data
9. **Backend assistant_message**: Test each backend's `assistant_message` with mock content blocks
10. **Client tools parameter**: Verify `client.call(tools=[])` passes empty tools to payload
11. **PromptBuilder parse_response**: Verify it delegates to backend correctly
12. **Example smoke test**: Run `python examples/example.py`; verify it makes API calls and prints final response

### Full integration test:
```bash
source venv/bin/activate
pip install -e week1_baseline/python/05_agent_loop
./week1_baseline/bin/python/05_agent_loop
```

### Expected output (shape, not exact values):
```
=== BOUKENSHA Step 5: Agent Loop ===

Config: #<Boukensha::Config dir=/home/user/.boukensha tasks=player>
Provider: anthropic
Model: claude-haiku-4-5
Max iterations: 25
Max output tokens: 1024

[iteration 1/25]
  tool call → read_file({'path': 'README.md'})
  tool result → # The Agent Loop...
[iteration 2/25]
  tool call → list_directory({'path': '.'})
  tool result → README.md, examples, lib

=== FINAL RESPONSE ===
Here are the files in the current directory: README.md, examples, lib.
The contents of README.md are...
```

---

## Common Pitfalls

### 1. Ruby symbol keys vs Python string keys
**Problem**: Ruby uses `{ stop_reason: "tool_use" }` (symbol keys), Python uses `{"stop_reason": "tool_use"}` (string keys).
**Fix**: Always use string keys in Python dicts for the normalized shape.

### 2. `response.dig()` vs chained `.get()`
**Problem**: Ruby's `Hash#dig` returns `nil` for missing keys at any depth. Python's chained `.get()` requires explicit fallbacks.
**Fix**: Use `(response.get("choices") or [{}])[0].get("message") or {}` pattern.

### 3. Content type handling in `add_message`
**Problem**: Ruby `Context.add_message` accepts both strings and arrays. Python's version only handles strings.
**Fix**: Update `Message` dataclass to accept `Union[str, List[Dict[str, Any]]]`.

### 4. `to_json` vs `json.dumps()`
**Problem**: Ruby's `.to_json` handles all types. Python's `json.dumps()` needs `default=str` for non-serializable types.
**Fix**: Use `json.dumps(obj, default=str)` in `assistant_message` methods.

### 5. `respond_to?` vs `hasattr`
**Problem**: Ruby's `@context.task.respond_to?(:max_iterations)` checks method existence. Python needs `hasattr()` or try/except.
**Fix**: Use try/except around `self.context.task.max_iterations(task_settings)`.

### 6. `content.is_a?(String)` vs `isinstance(content, str)`
**Problem**: Ruby checks class with `is_a?`, Python uses `isinstance()`.
**Fix**: Use `isinstance(content, str)` or `isinstance(content, list)`.

### 7. Empty string truthiness
**Problem**: Ruby treats empty string as truthy (`"" && true` → `true`). Python treats empty string as falsy.
**Fix**: Use `if message.get("content"):` instead of `if message["content"] && !message["content"].empty?`.

### 8. `rescue *ERRORS` vs multiple `except` clauses
**Problem**: Ruby splats an array of exception classes. Python requires separate `except` clauses or a tuple.
**Fix**: The Agent only rescues `ApiError` (single exception), so no splat needed.

---

## Files to Create/Modify

1. Copy entire `week1_baseline/python/04_api_client/` to `week1_baseline/python/05_agent_loop/`
2. Modify `src/boukensha/errors.py` — add `LoopError`
3. Create `src/boukensha/agent.py` — Agent class
4. Modify `src/boukensha/client.py` — add `tools` parameter to `call()`
5. Modify `src/boukensha/prompt_builder.py` — add `parse_response()` method
6. Modify `src/boukensha/message.py` — accept `Union[str, List[Dict]]` for content
7. Modify `src/boukensha/context.py` — update `add_message` type hint
8. Modify `src/boukensha/backends/anthropic.py` — add `parse_response()`
9. Modify `src/boukensha/backends/openai.py` — add `parse_response()` and `assistant_message()`
10. Modify `src/boukensha/backends/gemini.py` — add `parse_response()` and `assistant_parts()`
11. Modify `src/boukensha/backends/ollama.py` — add `parse_response()` and `assistant_message()`
12. Modify `src/boukensha/backends/ollama_cloud.py` — add `parse_response()` and `assistant_message()`
13. Modify `src/boukensha/__init__.py` — export `Agent` and `LoopError`
14. Create/update `examples/example.py` — agent loop smoke test
15. Update `pyproject.toml` — version bump to 0.5.0
16. Update `README.md` — add Agent Loop documentation
17. `week1_baseline/bin/python/05_agent_loop` — executable launcher (should already exist, mirrors 04_api_client)