class RunDSL:
    """DSL object exposed as `self` inside Boukensha.run() blocks.

    It exposes only `tool`, keeping the DSL surface intentionally small.
    """

    def __init__(self, registry):
        self.registry = registry

    def tool(self, name, description, parameters=None, fn=None):
        """Register a tool in the registry.

        Args:
            name: Tool name
            description: Tool description
            parameters: Dict of parameter specs
            fn: Callable that implements the tool
        """
        if parameters is None:
            parameters = {}
        self.registry.tool(name, description=description, parameters=parameters, block=fn)

    def instance_eval(self, fn):
        """Execute a function with this object as self (via call with self parameter)."""
        if fn is not None:
            fn(self)
