module Boukensha
  # Static model → capability table.
  #
  # `context_window` is a known *model* fact — the physical input ceiling — not a
  # value the user sets. The agent looks it up from its configured model id; the
  # user never configures it in settings.yaml. Unknown models fall back to a
  # conservative default so an unrecognised id can't silently assume a huge window.
  module Models
    TABLE = {
      # Anthropic
      "claude-opus-4-8"           => { context_window: 1_000_000 },
      "claude-sonnet-4-6"         => { context_window: 1_000_000 },
      "claude-haiku-4-5"          => { context_window: 200_000 },
      "claude-haiku-4-5-20251001" => { context_window: 200_000 },
      # OpenAI
      "gpt-5.5"                   => { context_window: 1_000_000 },
      "gpt-5.4-mini"              => { context_window: 400_000 },
      "gpt-5.4-nano"              => { context_window: 400_000 },
      # Gemini
      "gemini-3.5-flash"          => { context_window: 1_048_576 },
      "gemini-3.1-flash-lite"     => { context_window: 1_048_576 },
      "gemini-2.5-pro"            => { context_window: 1_048_576 },
      "gemini-2.5-flash"          => { context_window: 1_048_576 },
      "gemini-2.5-flash-lite"     => { context_window: 1_048_576 },
      # Ollama
      "gemma4"                    => { context_window: 128_000 },
      "gemma4:e2b"                => { context_window: 128_000 },
      "gemma4:e4b"                => { context_window: 128_000 },
      "gemma4:12b"                => { context_window: 256_000 },
      "gemma4:26b"                => { context_window: 256_000 },
      "gemma4:31b"                => { context_window: 256_000 },
      "qwen3:30b"                 => { context_window: 256_000 },
      "qwen3:8b"                  => { context_window: 40_000 },
      "deepseek-r1:8b"            => { context_window: 128_000 },
      # Ollama Cloud
      "gemma4:31b-cloud"          => { context_window: 256_000 },
      "kimi-k2.5:cloud"           => { context_window: 256_000 },
      "minimax-m3:cloud"          => { context_window: 512_000 },
    }.freeze

    DEFAULT_CONTEXT_WINDOW = 32_000

    def self.context_window(model)
      TABLE.dig(model.to_s, :context_window) || DEFAULT_CONTEXT_WINDOW
    end
  end
end
