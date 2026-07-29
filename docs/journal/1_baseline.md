# Week 1 Baseline Technical Documentation

## Technical Goal
Build a custom agentic loop framework ("Boukensha") that can drive an agent to play tbaMUD on instructions, with support for multiple LLM backends and a specialized tool system via MCP (Model Context Protocol).

Key objectives:
- Create a LLM-agnostic agent framework supporting Anthropic, OpenAI, Gemini, Ollama, and other providers
- Implement MCP client to connect to external tool servers (eg. mud-manager)
- Build a registry-based tool dispatch system to store and dispatch whenever called for.
- Create a REPL interface for agent control like interactively
- Implement proper logging and session visualization eg, log_viz
- Port architecture from Ruby to Python for language-agnostic support and have potential to include other NLP libraries for building a capable agent in the upcoming week.

## Technical Uncertainty
- Whether the custom agentic loop will efficiently handle long-running MUD sessions with proper memory and state management
- How well multi-agent scenario can be played with optimized token usage
- If MCP server is integrated, will that be able to handle long telnet or netcat sessions without breaking intermittently
- How to properly manage multi-player concurrent sessions in a MUD environment

## Technical Hypotheses
- A specialized agentic loop will outperform SDK built earlier because we can optimize for MUD-specific state management and session longevity
- MCP as a standard protocol will allow us to separate tool implementation from the core agentic framework.
- Multi LLMs implementation so as to reduce the token usage instead of relying only on Claude.
- A proper logging/visualization layer is critical for debugging agent behavior and understanding failure modes in long-running sessions
- Scope for porting to another language that can help with adding more features to the agent. eg. observability

## Technical Observations
- Boukensha successfully implements a custom agentic loop with proper state management, message history, and context windows
- MCP client starts as soon as the tool is loaded.
- The tool registry prevents collisions across MCP servers reducing complexity.
- Log Viz effectively visualizes session transcripts with token/usage view 
- Python port done effectively so that all of the essence is captured.
- Multi-backend support works across Anthropic, OpenAI, Gemini, Ollama with environmaent variables and settings (.env & settings.yaml)


## Technical Conclusions
- Boukensha does proper session management, context windows, and backend abstraction
- MCP is the right standard for tool integration as it allows us to plugin mud-manager, filesystem, and other servers without much code changes
- Logging infrastructure is built in from the start so that visualization helps with greater understanding of the application.
- Language-agnostic architecture requires careful design upfront and it was implemented with assumptions and documentation made for Ruby code to port to python without much issues.
- Config-driven tool registration (settings.yaml) is best in here instead of hard-coding implementation.
- Session isolation and proper cost tracking per provider/model will be critical for high-volume production use

## Key Takeaway
A custom agentic loop with proper abstraction (MCP for tools, config for capabilities, backends for providers) is feasible and outperforms generic SDKs for specialized use-cases. 