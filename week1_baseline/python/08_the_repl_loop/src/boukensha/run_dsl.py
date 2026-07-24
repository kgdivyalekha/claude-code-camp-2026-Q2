from typing import Any, Callable, Dict, Optional

from .registry import Registry


class RunDSL:
    """The object passed into a ``boukensha.run(..., configure=...)`` callback.

    Exposes only ``tool``, keeping the DSL surface intentionally small.
    ``tool`` is used as a decorator, mirroring how Ruby's inline block reads:

        def register_tools(dsl):
            @dsl.tool(
                "read_file",
                description="Read a file from disk",
                parameters={"path": {"type": "string"}},
            )
            def read_file(path):
                return Path(path).read_text()
    """

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def tool(
        self,
        name: str,
        *,
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Callable[[Callable], Callable]:
        def decorator(func: Callable) -> Callable:
            self._registry.tool(
                name, description=description, parameters=parameters or {}, block=func
            )
            return func

        return decorator
