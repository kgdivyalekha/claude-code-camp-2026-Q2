from typing import Any, Callable, Dict, Optional

from .tool import Tool
from .errors import UnknownToolError


class Registry:
    """
    Tool Registry for BOUKENSHA.
    
    Manages tool registration and dispatch. The Registry wraps a Context and provides
    a fluent interface for registering tools and dispatching them by name.
    """

    def __init__(self, context: Any) -> None:
        """Initialize the Registry with a Context."""
        self.context = context

    def tool(
        self,
        name: str,
        *,
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
        block: Optional[Callable] = None
    ) -> Tool:
        """
        Register a tool with the context.
        
        Args:
            name: The tool name (used for dispatch)
            description: Human-readable description of what the tool does
            parameters: Dict of parameter names to parameter specs
            block: The callable that implements the tool
        
        Returns:
            The registered Tool instance
        
        Usage:
            registry.tool(
                "move",
                description="Move in a direction",
                parameters={"direction": {"type": "string"}},
                block=lambda direction: f"You move {direction}"
            )
        """
        if parameters is None:
            parameters = {}

        tool = Tool(name, description, parameters, block)
        self.context.register_tool(tool)
        return tool

    def dispatch(self, name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """
        Dispatch a tool by name with the given arguments.
        
        Transforms string-keyed arguments (from JSON APIs) to keyword arguments
        expected by the tool block.
        
        Args:
            name: The tool name to dispatch
            args: String-keyed dict of arguments (typically from JSON API)
        
        Returns:
            The result of calling the tool block
        
        Raises:
            UnknownToolError: If the tool name is not registered
        
        Example:
            result = registry.dispatch("move", {"direction": "north"})
        """
        if args is None:
            args = {}

        tool = self.context.tools.get(name)
        if not tool:
            raise UnknownToolError(f"No tool registered as '{name}'")

        # Transform string-keyed args to keyword arguments
        # This is a critical translation point: APIs return JSON (string keys),
        # but Python callables expect keyword arguments.
        kwargs = {str(k): v for k, v in args.items()}
        return tool.block(**kwargs)
