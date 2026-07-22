# Python Port: Boukensha API Client (04_api_client)

**Status**: Planning — This document defines the port plan for `week1_baseline/ruby/04_api_client/` to Python.

The API Client takes the payload assembled by `PromptBuilder` and sends it to the API via HTTP POST. No tool loop yet — just proving the round trip works. The client handles retries, transient errors, SSL verification, and platform-specific certificate resolution.

This step introduces the `Client` class and the `ApiError` exception. All prior step classes (`PromptBuilder`, backends, tasks, registry, etc.) are carried forward unchanged.

## Decisions

These decisions build on 00_config, 01_struct_skeleton, 02_the_registry, and 03_prompt_builder:

- **Client uses stdlib urllib**: Python's `urllib.request` (not `requests` library) mirrors Ruby's `Net::HTTP` — no external dependencies, logic stays visible.

- **Retry strategy with exponential backoff**: `Client.call()` retries on transient errors (connection resets, timeouts) and retryable HTTP codes (408, 429, 500-503). Each retry doubles the delay: 0.5s, 1s, 2s, 4s, etc., up to MAX_RETRIES (3).

- **Transient error list**: Catch `urllib.error.URLError`, `urllib.error.HTTPError`, `socket.error`, `ssl.SSLError`, `TimeoutError`, `ConnectionError`, `BrokenPipeError` — the Python equivalents of Ruby's `EOFError`, `Errno::ECONNRESET`, `Timeout::Error`, etc.

- **ApiError exception**: Raised on non-2xx response after retries exhausted, or on transient error after MAX_RETRIES. Message includes response code, response body, and attempt count for debugging.

- **SSL/TLS verification**: Use Python's default `ssl.create_default_context()` instead of hardcoding certificate paths. Avoids platform-specific issues (`/usr/lib/ssl/cert.pem` doesn't exist on Linux/WSL2).

- **No HTTP call in PromptBuilder**: PromptBuilder only prepares payloads (already done in step 3). This step isolates network I/O from formatting.

- **JSON serialization**: Use `json.dumps(payload, default=str)` (matching Ruby's `to_json`). The `default=str` fallback handles non-serializable types gracefully.

- **Backend selection logic**: Same task-based configuration as step 3 — read `tasks.player.provider` and `tasks.player.model` from settings, construct the appropriate backend, pass it to `PromptBuilder`, then to `Client`.

- **No response parsing**: `Client.call()` returns the raw API response as a Python dict (from `json.loads()`). Parsing provider-specific response formats (extracting text, handling tool calls) is deferred to step 5 (Agent Loop).

## Target Python Structure (as planned)

```
week1_baseline/python/04_api_client/
├── src/
│   └── boukensha/
│       ├── __init__.py              # Package exports (add Client, ApiError)
│       ├── client.py                # Client class (NEW)
│       ├── config.py                # Config class (copy from 03_prompt_builder)
│       ├── tool.py                  # Tool dataclass (copy from 03_prompt_builder)
│       ├── message.py               # Message dataclass (copy from 03_prompt_builder)
│       ├── context.py               # Context class (copy from 03_prompt_builder)
│       ├── errors.py                # Add ApiError (modify 03_prompt_builder version)
│       ├── registry.py              # Registry class (copy from 03_prompt_builder)
│       ├── prompt_builder.py        # PromptBuilder class (copy from 03_prompt_builder)
│       ├── tasks/
│       │   ├── __init__.py          # Task exports (copy)
│       │   ├── base.py              # Base task class (copy)
│       │   └── player.py            # Player task class (copy)
│       └── backends/
│           ├── __init__.py          # Backend exports (copy)
│           ├── base.py              # BackendBase (copy)
│           ├── anthropic.py         # Anthropic backend (copy)
│           ├── gemini.py            # Gemini backend (copy)
│           ├── ollama.py            # Ollama backend (copy)
│           ├── ollama_cloud.py      # Ollama Cloud backend (copy)
│           └── openai.py            # OpenAI backend (copy)
├── examples/
│   └── example.py                   # Usage example / smoke test (NEW)
├── prompts/
│   └── system.md                    # Default system prompt (copy from 03_prompt_builder)
├── pyproject.toml                   # Package config (copy from 03_prompt_builder)
└── README.md                        # Usage documentation (NEW)
```

### Already Ported (from 03_prompt_builder)
All files from step 3 are carried forward unchanged:
- **config.py**, **tool.py**, **message.py**, **context.py**, **registry.py**
- **prompt_builder.py**
- **errors.py** (will add `ApiError` to existing `UnknownToolError` and `UnsupportedModelError`)
- **tasks/base.py**, **tasks/player.py**
- **backends/base.py**, **backends/anthropic.py**, **backends/gemini.py**, **backends/ollama.py**, **backends/ollama_cloud.py**, **backends/openai.py**
- **prompts/system.md**

### New in This Step
- **errors.py**: Add `ApiError` exception
- **client.py**: Client class with retry logic and HTTP handling

## Quick Setup

### 1. Ensure prior steps are ported and installed
```bash
source venv/bin/activate
pip install -e week1_baseline/python/00_config
pip install -e week1_baseline/python/01_struct_skeleton
pip install -e week1_baseline/python/02_the_registry
pip install -e week1_baseline/python/03_prompt_builder
```

### 2. Install 04_api_client
```bash
pip install -e week1_baseline/python/04_api_client
```

### 3. Run it
```bash
./week1_baseline/bin/python/04_api_client
```

---

## Porting Plan: File by File

### 1. Copy Prior Step as Template

Copy the entire `03_prompt_builder` directory to `04_api_client`. All source files, `pyproject.toml`, `README.md`, and `prompts/` are reused. Only add new files and modify `errors.py` and `__init__.py`.

```bash
cp -r week1_baseline/python/03_prompt_builder week1_baseline/python/04_api_client
```

---

### 2. ApiError Exception (`lib/boukensha/errors.rb` → `src/boukensha/errors.py`)

**Ruby**:
```ruby
module Boukensha
  class ApiError < StandardError; end
end
```

**Python** (add to existing errors.py):
```python
class ApiError(Exception):
    """Raised when an API request fails after retries are exhausted."""
    pass
```

---

### 3. Client (`lib/boukensha/client.rb` → `src/boukensha/client.py`)

**Ruby**:
```ruby
require "net/http"
require "json"
require "openssl"

module Boukensha
  class Client
    RETRYABLE_STATUS_CODES = [408, 409, 429, 500, 502, 503, 504].freeze
    TRANSIENT_ERRORS = [
      EOFError,
      Errno::ECONNRESET,
      Errno::ECONNREFUSED,
      Net::OpenTimeout,
      Net::ReadTimeout,
      OpenSSL::SSL::SSLError,
      SocketError,
      Timeout::Error
    ].freeze
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 0.5

    def initialize(builder)
      @builder = builder
    end

    def call(max_output_tokens: 1024)
      uri          = URI(@builder.url)
      http         = Net::HTTP.new(uri.host, uri.port)
      http.use_ssl = uri.scheme == "https"
      http.verify_mode = OpenSSL::SSL::VERIFY_PEER

      request      = Net::HTTP::Post.new(uri, @builder.headers)
      request.body = @builder.to_api_payload(max_output_tokens: max_output_tokens).to_json

      attempts = 0
      response = nil

      loop do
        attempts += 1

        begin
          response = http.request(request)
        rescue *TRANSIENT_ERRORS => e
          raise ApiError, "API request failed after #{attempts} attempts: #{e.class}: #{e.message}" if attempts > MAX_RETRIES

          sleep retry_delay(attempts)
          next
        end

        if retryable_response?(response) && attempts <= MAX_RETRIES
          sleep retry_delay(attempts)
          next
        end

        break
      end

      unless response.is_a?(Net::HTTPSuccess)
        raise ApiError, "API request failed after #{attempts} attempt#{'s' unless attempts == 1} (#{response.code}): #{response.body}"
      end

      JSON.parse(response.body)
    end

    private

    def retryable_response?(response)
      RETRYABLE_STATUS_CODES.include?(response.code.to_i)
    end

    def retry_delay(attempt)
      BASE_RETRY_DELAY * (2**(attempt - 1))
    end
  end
end
```

**Python**:
```python
import json
import ssl
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse
from typing import Any, Dict

from .errors import ApiError


class Client:
    """Makes HTTP requests to LLM APIs and handles retries with exponential backoff."""
    
    RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 0.5

    def __init__(self, builder: Any) -> None:
        """Initialize client with a PromptBuilder instance."""
        self.builder = builder

    def call(self, max_output_tokens: int = 1024) -> Dict[str, Any]:
        """
        POST the payload to the API endpoint and return the parsed JSON response.
        
        Retries on transient errors and retryable HTTP status codes using exponential backoff.
        Raises ApiError on non-2xx response after retries exhausted, or on non-retryable errors.
        """
        url = self.builder.url()
        headers = self.builder.headers()
        payload = self.builder.to_api_payload(max_output_tokens=max_output_tokens)
        body = json.dumps(payload, default=str)

        parsed_url = urlparse(url)
        use_ssl = parsed_url.scheme == "https"
        
        ssl_context = ssl.create_default_context() if use_ssl else None

        attempts = 0
        response = None

        while True:
            attempts += 1

            try:
                req = urllib.request.Request(
                    url,
                    data=body.encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                if ssl_context:
                    response = urllib.request.urlopen(req, context=ssl_context)
                else:
                    response = urllib.request.urlopen(req)
                
                status_code = response.status
                response_body = response.read().decode("utf-8")
                response.close()
                
                # Check if response is a success
                if 200 <= status_code < 300:
                    return json.loads(response_body)
                
                # Non-2xx response — check if retryable
                if status_code in self.RETRYABLE_STATUS_CODES and attempts <= self.MAX_RETRIES:
                    time.sleep(self._retry_delay(attempts))
                    continue
                
                # Non-2xx, non-retryable — raise
                plural = "s" if attempts != 1 else ""
                raise ApiError(
                    f"API request failed after {attempts} attempt{plural} ({status_code}): {response_body}"
                )
            
            except urllib.error.HTTPError as e:
                # HTTPError has status code and body
                status_code = e.code
                response_body = e.read().decode("utf-8")
                
                if status_code in self.RETRYABLE_STATUS_CODES and attempts <= self.MAX_RETRIES:
                    time.sleep(self._retry_delay(attempts))
                    continue
                
                plural = "s" if attempts != 1 else ""
                raise ApiError(
                    f"API request failed after {attempts} attempt{plural} ({status_code}): {response_body}"
                ) from e
            
            except (
                urllib.error.URLError,
                ssl.SSLError,
                TimeoutError,
                ConnectionError,
                BrokenPipeError,
                OSError,
            ) as e:
                # Transient error — retry if attempts remain
                if attempts > self.MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempts} attempts: {type(e).__name__}: {e}"
                    ) from e
                
                time.sleep(self._retry_delay(attempts))
                continue

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        """Calculate exponential backoff delay: 0.5s, 1s, 2s, 4s, ..."""
        return Client.BASE_RETRY_DELAY * (2 ** (attempt - 1))
```

**Key translation**:
- `require` → `import`
- `URI()` → `urllib.parse.urlparse()`
- `Net::HTTP` → `urllib.request` (stdlib)
- `Net::HTTP::Post` → `urllib.request.Request(..., method="POST")`
- `uri.scheme == "https"` → `parsed_url.scheme == "https"`
- `OpenSSL::SSL::VERIFY_PEER` → `ssl.create_default_context()` (automatic)
- `http.use_ssl` → conditional `ssl_context` parameter to `urlopen()`
- `.to_json` → `json.dumps(payload, default=str)`
- `JSON.parse(response.body)` → `json.loads(response_body)`
- `loop do...break` → `while True...break`
- `rescue *ERRORS => e` → multiple `except` clauses (handle `HTTPError` separately from `URLError`)
- `sleep` → `time.sleep()`
- `response.code.to_i` → `e.code` (already an int)
- `attempts > MAX_RETRIES` → guard condition before retry

**Important note**: Python's `urllib` splits HTTP errors into two exceptions:
- `urllib.error.HTTPError` — 4xx/5xx responses with status code and body
- `urllib.error.URLError` — connection/DNS/timeout errors without status

The Ruby code catches both at once; Python requires separate handlers.

---

### 4. Package Exports (`lib/boukensha.rb` → `src/boukensha/__init__.py`)

**Python** (modify existing file from 03_prompt_builder):
```python
# Boukensha API client — backends, tasks, registry, builder, and HTTP client
# Re-uses config, struct, registry, and prompt builder classes from prior steps

# Local struct, config, registry, and client classes
from .config import Config  # noqa: F401
from .tool import Tool  # noqa: F401
from .message import Message  # noqa: F401
from .context import Context  # noqa: F401
from .errors import UnknownToolError, UnsupportedModelError, ApiError  # noqa: F401
from .registry import Registry  # noqa: F401
from .prompt_builder import PromptBuilder  # noqa: F401
from .client import Client  # noqa: F401
from . import tasks  # noqa: F401
from . import backends  # noqa: F401

__all__ = [
    "Config",
    "Tool",
    "Message",
    "Context",
    "Registry",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "PromptBuilder",
    "Client",
    "tasks",
    "backends",
]
```

**Change**: Add `ApiError` to imports and `__all__`; add `Client` to imports and `__all__`.

---

### 5. Example (`examples/example.rb` → `examples/example.py`)

**Python**:
```python
import json
import os
from pathlib import Path

from boukensha import Config, Context, PromptBuilder, Client, Registry
from boukensha.tasks import Player
from boukensha.backends import Anthropic, Gemini, Ollama, OllamaCloud, OpenAI

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).resolve().parent.parent.parent / ".boukensha")
)

config = Config()
player_settings = config.tasks("player") or {}

system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

registry.tool(
    "read_file",
    description="Read the contents of a file from disk",
    parameters={"path": {"type": "string", "description": "The file path to read"}},
    block=lambda path: Path(path).read_text(),
)

registry.tool(
    "list_directory",
    description="List files in a directory",
    parameters={"path": {"type": "string", "description": "The directory path to list"}},
    block=lambda path: "\n".join(
        f for f in os.listdir(path) if not f.startswith(".")
    ),
)

ctx.add_message("user", "What files are in the current directory?")

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

print("=== BOUKENSHA Step 4: API Client ===")
print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Sending request to {builder.url()}...")
print()

response = client.call()
print("Raw response:")
print(json.dumps(response, indent=2, default=str))
```

**Key translation notes**:
- `ENV.fetch()` → `os.environ["..."]` (both raise on missing key)
- `File.read()` → `Path(...).read_text()`
- `Dir.entries().reject` → list comprehension with `os.listdir()`
- `puts` → `print()`
- Ruby blocks passed to `registry.tool()` → Python lambdas/functions

---

### 6. Update pyproject.toml

**Change**: Bump version from `0.3.0` to `0.4.0`:
```toml
[project]
name = "boukensha"
version = "0.4.0"
description = "A step-by-step guide to building AI agents with Claude"
# ... rest unchanged
```

---

### 7. Update README.md

Add a section for `Client`:

```markdown
## The Client

The `Client` class takes a `PromptBuilder` instance and makes the HTTP request to the API.

```python
from boukensha import PromptBuilder, Client

builder = PromptBuilder(ctx, backend)
client = Client(builder)

response = client.call(max_output_tokens=2048)
```

The `call()` method:
- POSTs the payload to the backend's API endpoint
- Handles retries with exponential backoff (0.5s, 1s, 2s, 4s)
- Retries on transient errors (connection resets, timeouts, DNS failures)
- Retries on retryable HTTP codes (408, 429, 500-503)
- Raises `ApiError` on non-2xx response after retries exhausted
- Returns the raw JSON response as a dict

### Retry Behavior

| Scenario | Behavior |
|----------|----------|
| Connection reset | Retry with backoff (up to 3 times) |
| HTTP 429 (rate limit) | Retry with backoff |
| HTTP 500 (server error) | Retry with backoff |
| HTTP 400 (bad request) | Fail immediately (not retryable) |
| HTTP 401 (auth failure) | Fail immediately (not retryable) |
| All retries exhausted | Raise `ApiError` with details |

### SSL/TLS

The client uses Python's default `ssl.create_default_context()` for HTTPS endpoints. This automatically:
- Loads system root certificates
- Verifies the server certificate
- Enables hostname verification

For local Ollama instances using `http://`, SSL is disabled.

```python
# HTTPS endpoint (Anthropic, OpenAI, Gemini)
backend = Anthropic(api_key=key, model="claude-opus-4-8")

# HTTP endpoint (local Ollama)
backend = Ollama(model="llama3.2")  # uses http://localhost:11434
```
```

---

## Dependency Chain

```
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
1. **ApiError**: Create the exception; verify it's catchable with message
2. **Client initialization**: Verify `Client(builder)` stores the builder
3. **Retry logic**: Verify `_retry_delay()` produces correct sequence (0.5, 1, 2, 4)
4. **HTTP request construction**: Verify headers, body, method are correct
5. **Response parsing**: Verify `json.loads()` converts response body to dict
6. **Transient error handling**: Mock a connection error; verify it retries then raises `ApiError`
7. **Retryable status handling**: Mock HTTP 429; verify it retries then succeeds on retry
8. **Non-retryable error**: Mock HTTP 400; verify it fails immediately without retry
9. **Example smoke test**: Run `python examples/example.py`; verify it makes an API call and prints JSON response

### Full integration test:
```bash
source venv/bin/activate
pip install -e week1_baseline/python/04_api_client
./week1_baseline/bin/python/04_api_client
```

### Expected output (shape, not exact values):
The output should be raw JSON from the selected API. For Anthropic:
```json
{
  "id": "msg_01XY",
  "type": "message",
  "role": "assistant",
  "content": [
    { "type": "text", "text": "I don't have a function available to list directory..." }
  ],
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 585, "output_tokens": 118 }
}
```

---

## Common Pitfalls

### 1. HTTP status code type confusion
**Problem**: Ruby's `response.code.to_i` vs Python's exception `.code` behave differently.
**Fix**: In Python, `HTTPError.code` is already an int; don't call `.to_i()`.

### 2. SSL context and non-HTTPS endpoints
**Problem**: Passing `ssl_context` to `urlopen()` for `http://` URLs causes errors.
**Fix**: Only pass `ssl_context` when `use_ssl == True`.

### 3. Missing `headers` dict in urllib.request.Request
**Problem**: Forgot to pass headers to the Request constructor.
**Fix**: Always pass `headers=dict` to `urllib.request.Request()`.

### 4. Retry loop exits without response
**Problem**: Loop breaks but `response` is still `None` on non-2xx code after retries.
**Fix**: Use a guard condition (`if status_code in RETRYABLE...`) to decide whether to continue or raise.

### 5. Confusing urllib.error.HTTPError with urllib.error.URLError
**Problem**: HTTPError (4xx/5xx) has a status code; URLError (connection errors) does not.
**Fix**: Handle both separately — HTTPError for status-based retries, URLError for transient errors.

### 6. JSON decode errors on non-JSON response
**Problem**: `json.loads(response_body)` raises if body is not valid JSON.
**Fix**: Catch `json.JSONDecodeError` if needed; but for API calls, assume body is JSON or wrap in `try/except`.

### 7. Forgetting to close response objects
**Problem**: Unclosed responses leak file handles.
**Fix**: Call `response.close()` after `response.read()`, or use a context manager.

---

## Verifying Success

```bash
source venv/bin/activate
python -c "
from boukensha import Client, ApiError
print('Imports work')
# Verify ApiError exists and is catchable
try:
    raise ApiError('test error')
except ApiError as e:
    print(f'ApiError works: {e}')
"
./week1_baseline/bin/python/04_api_client
```

---

## Additional Resources

- **Ruby source**: `week1_baseline/ruby/04_api_client/lib/boukensha/client.rb`
- **Python 03_prompt_builder reference**: `week1_baseline/python/03_prompt_builder/`
- **Python stdlib urllib docs**: https://docs.python.org/3/library/urllib.html
- **Python ssl module**: https://docs.python.org/3/library/ssl.html
- **Exponential backoff reference**: https://en.wikipedia.org/wiki/Exponential_backoff

---

## What NOT to Do

- Don't make API calls in example unless necessary for testing
- Don't hardcode API endpoints — read from builder
- Don't ignore SSL certificate verification
- Don't swallow exceptions — let ApiError propagate
- Don't retry on non-retryable errors (4xx except 408/429)
- Don't forget to close response objects
- Don't hardcode platform-specific certificate paths
- Don't redefine PromptBuilder or backend classes — copy from 03_prompt_builder

---

## Files to Create/Modify

1. Copy entire `week1_baseline/python/03_prompt_builder/` to `week1_baseline/python/04_api_client/`
2. Modify `src/boukensha/errors.py` — add `ApiError`
3. Create `src/boukensha/client.py` — Client class
4. Modify `src/boukensha/__init__.py` — export `Client` and `ApiError`
5. Create/update `examples/example.py` — smoke test with Client
6. Update `pyproject.toml` — version bump to 0.4.0
7. Update `README.md` — add Client usage documentation
8. `week1_baseline/bin/python/04_api_client` — executable launcher (should already exist, mirrors 03_prompt_builder)
