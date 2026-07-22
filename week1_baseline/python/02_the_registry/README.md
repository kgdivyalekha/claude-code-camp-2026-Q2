# The Tool Registry

The Tool Registry is how BOUKENSHA manages what capabilities the agent can use.

It has two jobs:
  1. Storing tools
  2. Dispatching tools when asked

## How It Works

The agent NEVER calls a tool directly.
It emits a structured request (name and args) and the Registry looks up the tool and runs it.

```
Agent:     "Hey registry call move with direction='north'"
Registry:  "Looking up 'move' in the tool table"
Registry:  "Found it, now calling the block with the provided args"
Registry:  "Here's the result"
Agent:     "Thanks buddy"
Registry:  "That's why you pay me the big bucks"
```

## Boukensha::Registry

| Method | Description |
|---|---|
| `tool(name, description, parameters, block)` | Registers a new tool on the context |
| `dispatch(name, args)` | Looks up a tool by name and calls it with the provided args |

## Boukensha::UnknownToolError

Raised when `dispatch` is called with a name that has no registered tool.
A harness needs explicit error boundaries — an unrecognized tool name should never silently fail.

**Example:**
```
UnknownToolError: No tool registered as 'flee'
```

## Expected Output

```
=== BOUKENSHA Step 2: Tool Registry ===

Config:  <Boukensha.Config dir=~/.boukensha tasks=player>
Context: <Context task=player turns=0 tools=2>
Tools:
  <Tool name=move description="Move the player in a direction (north, south, east, west, up, down)" params=['direction']>
  <Tool name=shout description="Shout a message so everyone in the zone can hear it" params=['message']>

Dispatching 'shout' with message='dragon spotted'...
Result: DRAGON SPOTTED

Dispatching 'move' with direction='north'...
Result: You move north into a torch-lit corridor.

UnknownToolError caught: No tool registered as 'flee'
```

## Considerations

`dispatch` transforms string-keyed arguments (from JSON APIs) to keyword arguments before calling the block.
The API returns arguments as string-keyed JSON but Python callables expect keyword arguments.
This translation is a real gotcha in production harnesses; BOUKENSHA makes it visible for learning purposes.

## Run Example

```sh
./week1_baseline/bin/python/02_the_registry
```
