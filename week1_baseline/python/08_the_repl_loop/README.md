# The API Client

The API Client takes the payload assembled by `PromptBuilder` and sends it to the API via HTTP POST. One HTTP POST, one response. No tool loop yet — just proving the round trip works.

The client handles retries, transient errors, SSL verification, and platform-specific certificate resolution using exponential backoff (0.5s, 1s, 2s, 4s...).

Supported providers:
- Anthropic Claude API
- OpenAI Chat Completions API
- Google Gemini API
- Ollama (local)
- Ollama Cloud (hosted models)

Configuration is task-based, carried forward from prior steps. The `player` task owns its provider, model, and prompt override settings.

## New Files (Step 04)

| File | Description |
|---|---|
| `src/boukensha/client.py` | Makes HTTP requests to LLM APIs with retry logic and error handling |

## Carried Forward (Steps 00-03)

| File | Description |
|---|---|
| `src/boukensha/prompt_builder.py` | Delegates serialization to the active backend |
| `src/boukensha/tasks/base.py` | Abstract task helper for provider/model and prompt resolution |
| `src/boukensha/tasks/player.py` | The concrete player task used by the main loop |
| `prompts/system.md` | Default system prompt used when a task does not override it |
| `src/boukensha/backends/base.py` | Shared backend contract for model validation and model metadata |
| `src/boukensha/backends/anthropic.py` | Serializes context into the Anthropic API format |
| `src/boukensha/backends/ollama.py` | Serializes context into the Ollama API format |
| `src/boukensha/backends/ollama_cloud.py` | Serializes context into the Ollama Cloud API format |
| `src/boukensha/backends/openai.py` | Serializes context into the OpenAI Chat Completions format |
| `src/boukensha/backends/gemini.py` | Serializes context into the Gemini `generateContent` format |

## How It Works

```
Context (Python objects)
        ↓
PromptBuilder
        ↓
Backend (Anthropic, OpenAI, Gemini, or Ollama)
        ↓
API Payload (plain dicts and lists)
        ↓
Client (HTTP POST with retries)
        ↓
API Response (raw JSON)
```

## The Client

The `Client` class takes a `PromptBuilder` instance and makes the HTTP request to the API.

```python
from boukensha import PromptBuilder, Client

builder = PromptBuilder(ctx, backend)
client = Client(builder)

response = client.call(max_output_tokens=2048)
```

### Client Behavior

| Scenario | Behavior |
|----------|----------|
| Connection reset | Retry with exponential backoff (up to 3 times) |
| HTTP 429 (rate limit) | Retry with backoff |
| HTTP 500 (server error) | Retry with backoff |
| HTTP 400 (bad request) | Fail immediately (not retryable) |
| HTTP 401 (auth failure) | Fail immediately (not retryable) |
| All retries exhausted | Raise `ApiError` with details |

### Retry Strategy

- **Initial delay**: 0.5 seconds
- **Exponential backoff**: Each retry doubles the delay (1s, 2s, 4s...)
- **Max retries**: 3 attempts total
- **Transient errors**: Connection resets, timeouts, SSL errors, DNS failures

### SSL/TLS

The client uses Python's default `ssl.create_default_context()` for HTTPS endpoints, which automatically:
- Loads system root certificates
- Verifies the server certificate
- Enables hostname verification

For local Ollama instances using `http://`, SSL is disabled automatically.

---

## PromptBuilder

| Method | Description |
|---|---|
| `to_messages()` | Delegates message serialization to the backend |
| `to_tools()` | Delegates tool serialization to the backend |
| `to_api_payload()` | Assembles the complete payload ready to POST |
| `headers()` | Returns the correct headers for the backend |
| `url()` | Returns the correct endpoint URL for the backend |

## Backends

Each API has its own conventions for how data is expected. Anthropic and Gemini are the most alike (system prompt as a top-level field), while OpenAI and Ollama share the same `function`-wrapped tool schema.

Backends also own their supported model table. A backend refuses to initialize
with an unknown model (raising `UnsupportedModelError`), so `settings.yaml` cannot silently select an unsupported
or misspelled model. Each model entry carries:

| Key | Meaning |
|---|---|
| `context_window` | The model's known token context window |
| `cost_per_million.input` | USD input token price per million tokens, when known |
| `cost_per_million.output` | USD output token price per million tokens, when known |
| `usage_unit` | `"tokens"`, `"local_compute"`, or `"ollama_cloud_usage"` |
| `usage_level` | Ollama Cloud usage tier, when applicable |

Backend instances expose `context_window`, `input_token_cost_per_million`,
`output_token_cost_per_million`, `usage_unit`, `usage_level`, and
`estimate_cost(input_tokens, output_tokens)`.
For local Ollama models, token API cost is `0.0`. For Ollama Cloud, public
pricing is plan/usage based rather than token based, so `estimate_cost` returns
`None`.

The prices in this step are static tutorial data, current as of June 16, 2026,
and should be reviewed whenever the selected model set changes.

### Anthropic

Talks to `https://api.anthropic.com/v1/messages`.
Requires an `ANTHROPIC_API_KEY`. Supported models are listed in
`Anthropic.MODELS`.

### Ollama

Talks to `http://localhost:11434/api/chat`.
Requires `ollama serve` running locally. No API key needed. Supported models are
listed in `Ollama.MODELS`.

### OllamaCloud

Talks to `https://ollama.com/api/chat`. Requires an `OLLAMA_API_KEY`. Supported
models are listed in `OllamaCloud.MODELS`.

### OpenAI

Talks to `https://api.openai.com/v1/chat/completions`.
Requires an `OPENAI_API_KEY`. Supported models are listed in
`OpenAI.MODELS`.

### Gemini

Talks to `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`.
Requires a `GEMINI_API_KEY`. Supported models are listed in
`Gemini.MODELS`.

### System Prompt

Anthropic and Gemini send the system prompt as a top-level field, separate from the messages array. Ollama and OpenAI put it inside the messages array as a `role: system` message.

```json
// Anthropic
{ "system": "You are a MUD player assistant.", "messages": [ ... ] }

// Gemini
{ "systemInstruction": { "parts": [{ "text": "You are a MUD player assistant." }] }, "contents": [ ... ] }

// Ollama / OpenAI
{ "messages": [ { "role": "system", "content": "You are a MUD player assistant." }, ... ] }
```

### Tool Results

Anthropic wraps tool results in a user message. Ollama and OpenAI use their own `role: tool` message type (with slightly different identifier fields). Gemini wraps results in a `functionResponse` part on a `user` message.

```json
// Anthropic
{ "role": "user", "content": [{ "type": "tool_result", "tool_use_id": "toolu_01X", "content": "A damp stone corridor stretches north. Torches flicker on the walls." }] }

// Ollama
{ "role": "tool", "tool_name": "look", "content": "A damp stone corridor stretches north. Torches flicker on the walls." }

// OpenAI
{ "role": "tool", "tool_call_id": "toolu_01X", "content": "A damp stone corridor stretches north. Torches flicker on the walls." }

// Gemini
{ "role": "user", "parts": [{ "functionResponse": { "name": "toolu_01X", "response": { "content": "A damp stone corridor stretches north. Torches flicker on the walls." } } }] }
```

### Tool Definitions

Anthropic uses `input_schema`. Ollama and OpenAI wrap everything in a `function` envelope with `parameters`. Gemini wraps tools in a `functionDeclarations` array.

```json
// Anthropic
{ "name": "move", "description": "Move the player in a direction (north, south, east, west, up, down)", "input_schema": { "type": "object", "properties": { "direction": { "type": "string", "description": "The direction to move" } }, "required": ["direction"] } }

// Ollama / OpenAI
{ "type": "function", "function": { "name": "move", "description": "Move the player in a direction (north, south, east, west, up, down)", "parameters": { "type": "object", "properties": { "direction": { "type": "string", "description": "The direction to move" } }, "required": ["direction"] } } }

// Gemini
{ "functionDeclarations": [ { "name": "move", "description": "Move the player in a direction (north, south, east, west, up, down)", "parameters": { "type": "object", "properties": { "direction": { "type": "string", "description": "The direction to move" } }, "required": ["direction"] } } ] }
```

### Message Roles

Anthropic, Ollama, and OpenAI all use `assistant` for the model's turn. Gemini calls it `model`.

```json
// Anthropic / Ollama / OpenAI
{ "role": "assistant", "content": "Let me take a look around first." }

// Gemini
{ "role": "model", "parts": [{ "text": "Let me take a look around first." }] }
```

## Considerations

**The conversation is stateless.** The model has no memory between turns. Every API call includes the entire history from the beginning. BOUKENSHA is responsible for carrying that state.

**Tool results are user messages on Anthropic.** This feels counterintuitive the result came from BOUKENSHA, not the human but it reflects how the Anthropic API models the conversation. Ollama, OpenAI, and Gemini all handle this with dedicated message/part types instead.

**The agent only sees schemas.** The `description` field on each tool is the only thing the agent uses to decide which tool to call. The actual block never leaves BOUKENSHA.

**`PromptBuilder.to_messages()` has a known quirk carried over from Ruby.** It always calls the backend's `to_messages` with a single argument, which only matches Anthropic and Gemini's signature. OpenAI, Ollama, and Ollama Cloud backends require `to_messages(system, messages)`, so calling `builder.to_messages()` directly for those three providers raises a `TypeError`. Only `to_api_payload()` is used in practice — it always calls each backend's `to_messages` with the correct arguments internally.

## ApiError

The `ApiError` exception is raised when:
- A non-2xx response is received after all retries are exhausted
- A transient error occurs after all retries are exhausted
- An API key is missing or invalid

Example:
```python
from boukensha import Client, ApiError

try:
    response = client.call()
except ApiError as e:
    print(f"API failed: {e}")
```

## Run Example

```sh
./week1_baseline/bin/python/04_api_client
```

Expected output: Raw JSON response from your configured API provider.
