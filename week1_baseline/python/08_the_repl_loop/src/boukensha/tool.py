from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(repr=False)
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    block: Callable

    def __repr__(self) -> str:
        desc_preview = str(self.description)[:41]
        params = list(self.parameters.keys())
        return f"<Tool name={self.name} description={desc_preview} params={params}>"

    def __str__(self) -> str:
        return self.__repr__()
